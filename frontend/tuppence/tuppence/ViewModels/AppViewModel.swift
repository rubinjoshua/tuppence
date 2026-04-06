//
//  AppViewModel.swift
//  tuppence
//

import Combine
import Foundation
import SwiftUI

@MainActor
class AppViewModel: ObservableObject {
    @Published var budgets: [Budget] = []
    @Published var ledgerEntries: [LedgerEntry] = []
    @Published var categoryData: [CategoryData] = []

    @Published var isLoading = false
    @Published var errorMessage: String?

    private let apiService = APIService.shared
    private let settings = AppSettings.shared

    init() {
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
        await syncBudgets()
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

    private func syncBudgets() async {
        guard !settings.budgets.isEmpty else { return }

        do {
            try await apiService.syncBudgets(settings.budgets)
        } catch {
            print("Failed to sync budgets: \(error)")
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
        isLoading = true
        errorMessage = nil

        do {
            let response = try await apiService.getAmounts()
            budgets = response.budgets
        } catch {
            errorMessage = "Failed to load amounts: \(error.localizedDescription)"
        }

        isLoading = false
    }

    func loadLedger(for month: Date?) async {
        isLoading = true
        errorMessage = nil

        do {
            let monthString = month?.monthYearString
            ledgerEntries = try await apiService.getLedger(month: monthString)
        } catch {
            errorMessage = "Failed to load ledger: \(error.localizedDescription)"
        }

        isLoading = false
    }

    func loadCategoryMap(for month: Date?, budgetEmoji: String) async {
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
        } catch let error as APIError {
            switch error {
            case .invalidURL:
                errorMessage = "Failed to add spending: Invalid URL"
            case .requestFailed(let underlyingError):
                errorMessage = "Failed to add spending: Request failed - \(underlyingError.localizedDescription)"
            case .invalidResponse:
                errorMessage = "Failed to add spending: Invalid response from server"
            case .decodingFailed(let underlyingError):
                errorMessage = "Failed to add spending: Could not decode response - \(underlyingError.localizedDescription)"
            case .httpError(let code, let message):
                errorMessage = "Failed to add spending: HTTP \(code) - \(message)"
            }
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
        } catch {
            errorMessage = "Failed to delete spending: \(error.localizedDescription)"
        }
    }

    func exportYear(_ year: Int) async -> Data? {
        do {
            let csvData = try await apiService.exportYear(year)
            try await apiService.archiveYear(year)
            return csvData
        } catch {
            errorMessage = "Failed to export year: \(error.localizedDescription)"
            return nil
        }
    }
}
