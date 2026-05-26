//
//  AppViewModel.swift
//  tuppence
//

import Combine
import Foundation
import SwiftUI
import WidgetKit

extension Notification.Name {
    static let budgetsDidChange = Notification.Name("budgetsDidChange")
}

/// Recognize the cooperative-cancellation errors that bubble up when SwiftUI
/// cancels its host Task (e.g. .refreshable's task gets replaced while the
/// closure is still awaiting). URLSession translates Swift Concurrency
/// cancellation to URLError(.cancelled); APIService wraps that as
/// .requestFailed; the raw Swift error is CancellationError.
private func isCancellation(_ error: Error) -> Bool {
    if error is CancellationError { return true }
    if let urlError = error as? URLError, urlError.code == .cancelled { return true }
    if case APIError.requestFailed(let inner) = error {
        if let urlError = inner as? URLError, urlError.code == .cancelled { return true }
    }
    return false
}

@MainActor
class AppViewModel: ObservableObject {
    @Published var budgets: [Budget] = []
    @Published var ledgerEntries: [LedgerEntry] = []
    @Published var categoryData: [CategoryData] = []

    @Published var isLoading = false
    @Published var errorMessage: String?

    private let apiService = APIService.shared
    private let settings = AppSettings.shared

    // App Group container so the cache is shared with the widget.
    private static let cachedBudgetsKey = "cached_budgets"
    private var sharedDefaults: UserDefaults {
        UserDefaults(suiteName: AppSettings.appGroupID) ?? .standard
    }

    init() {
        // Seed budgets from the on-disk cache so the Amount page doesn't
        // flash zeros while /amounts is in flight.
        budgets = loadCachedBudgets()

        // Observe app lifecycle for syncing
        NotificationCenter.default.addObserver(
            self,
            selector: #selector(handleAppLaunch),
            name: UIApplication.didFinishLaunchingNotification,
            object: nil
        )

        NotificationCenter.default.addObserver(
            self,
            selector: #selector(handleAppForeground),
            name: UIApplication.willEnterForegroundNotification,
            object: nil
        )

        // Observe budget changes from SettingsView
        NotificationCenter.default.addObserver(
            self,
            selector: #selector(handleBudgetsChanged),
            name: .budgetsDidChange,
            object: nil
        )
    }

    @objc private func handleBudgetsChanged() {
        Task {
            await loadBudgets()
            await loadAmounts()
        }
    }

    @objc private func handleAppLaunch() {
        Task {
            await syncAndLoad()
        }
    }

    @objc private func handleAppForeground() {
        Task {
            await syncAndLoad()
        }
    }

    func syncAndLoad() async {
        await syncSettings()
        await loadBudgets()
        await checkAutomations()
        await loadAmounts()
    }

    // MARK: - Sync Functions

    private func syncSettings() async {
        do {
            try await apiService.syncSettings(currencySymbol: settings.currencySymbol)
        } catch {
            print("Failed to sync settings: \(error)")
        }
    }

    private func loadBudgets() async {
        do {
            let fetchedBudgets = try await apiService.listBudgets()
            // /budgets has no totalAmount field. Carry forward the totals
            // we already have (from cache or a previous /amounts call) so
            // the Amount page doesn't flash zeros between /budgets and the
            // /amounts call that follows in syncAndLoad().
            let existingTotals: [String: Int] = budgets.reduce(into: [:]) { acc, b in
                if let total = b.totalAmount { acc[b.emoji] = total }
            }
            budgets = fetchedBudgets.map { fetched in
                var merged = fetched
                if merged.totalAmount == nil, let prior = existingTotals[fetched.emoji] {
                    merged.totalAmount = prior
                }
                return merged
            }
        } catch {
            print("Failed to load budgets: \(error)")
            // Keep what we already have — the cache + previous /amounts data
            // is still more useful than wiping to empty.
        }
    }

    private func checkAutomations() async {
        do {
            try await apiService.checkAutomations()
        } catch {
            print("Failed to check automations: \(error)")
        }
    }

    // MARK: - Load Data

    func loadAmounts() async {
        guard AuthenticationManager.shared.isAuthenticated else {
            errorMessage = "Please sign in to view your budget data"
            budgets = []
            cacheBudgets([])
            return
        }

        isLoading = true
        errorMessage = nil

        do {
            let response = try await apiService.getAmounts()
            budgets = response.budgets
            cacheBudgets(response.budgets)
        } catch {
            // URLError.cancelled bubbles up when SwiftUI cancels the host
            // Task (e.g. .refreshable mid-state-update). Treating it as an
            // error spams a misleading alert; the next legitimate load will
            // overwrite the data anyway.
            if !isCancellation(error) {
                errorMessage = "Failed to load amounts: \(error.localizedDescription)"
            }
            // Keep the previously cached budgets in the UI on failure so the
            // user doesn't see zeros.
        }

        isLoading = false
    }

    // MARK: - Cache

    private func loadCachedBudgets() -> [Budget] {
        guard let data = sharedDefaults.data(forKey: Self.cachedBudgetsKey),
              let cached = try? JSONDecoder().decode([Budget].self, from: data) else {
            return []
        }
        return cached
    }

    private func cacheBudgets(_ budgets: [Budget]) {
        if let data = try? JSONEncoder().encode(budgets) {
            sharedDefaults.set(data, forKey: Self.cachedBudgetsKey)
        }
    }

    func loadLedger(for month: Date?) async {
        guard AuthenticationManager.shared.isAuthenticated else {
            errorMessage = "Please sign in to view your spending history"
            ledgerEntries = []
            return
        }

        isLoading = true
        errorMessage = nil

        do {
            let monthString = month?.monthYearString
            ledgerEntries = try await apiService.getLedger(month: monthString)
        } catch {
            if !isCancellation(error) {
                errorMessage = "Failed to load ledger: \(error.localizedDescription)"
            }
        }

        isLoading = false
    }

    func loadCategoryMap(for month: Date?, budgetEmoji: String) async {
        guard AuthenticationManager.shared.isAuthenticated else {
            errorMessage = "Please sign in to view your budget analysis"
            categoryData = []
            return
        }

        isLoading = true
        errorMessage = nil

        do {
            let monthString = month?.monthYearString
            let response = try await apiService.getCategoryMap(month: monthString, budgetEmoji: budgetEmoji)
            categoryData = response.categories
        } catch {
            errorMessage = "Failed to load category map: \(error.localizedDescription)"
        }

        isLoading = false
    }

    // MARK: - Actions

    func addSpending(amount: Int, budgetEmoji: String, description: String) async {
        do {
            let currency = settings.currencyCode
            print("Adding spending: amount=\(amount), currency=\(currency), emoji=\(budgetEmoji), description=\(description)")

            let response = try await apiService.makeSpending(
                amount: amount,
                currency: currency,
                budgetEmoji: budgetEmoji,
                description: description,
                datetime: nil  // Temporarily nil - backend not ready to accept datetime yet
            )

            print("Spending added successfully: \(response.uuid)")

            // Refresh data after adding
            await loadLedger(for: nil)
            await loadAmounts()
            WidgetCenter.shared.reloadAllTimelines()
        } catch let error as APIError {
            errorMessage = "Failed to add spending: \(error.localizedDescription)"
            print("API Error: \(errorMessage ?? "unknown")")
        } catch {
            errorMessage = "Failed to add spending: \(error.localizedDescription)"
            print("Unknown error: \(error)")
        }
    }

    func deleteSpending(uuid: String) async {
        do {
            try await apiService.undoSpending(uuid: uuid)
            // Refresh ledger after deletion
            await loadLedger(for: nil)
            await loadAmounts()
            WidgetCenter.shared.reloadAllTimelines()
        } catch {
            errorMessage = "Failed to delete spending: \(error.localizedDescription)"
        }
    }

    func exportYear(_ year: Int) async -> Data? {
        do {
            let csvData = try await apiService.exportYear(year)
            try await apiService.archiveYear(year)
            // Archiving removes ledger entries for that year — refresh
            // amounts and tell the widget to redraw.
            await loadAmounts()
            WidgetCenter.shared.reloadAllTimelines()
            return csvData
        } catch {
            errorMessage = "Failed to export year: \(error.localizedDescription)"
            return nil
        }
    }
}
