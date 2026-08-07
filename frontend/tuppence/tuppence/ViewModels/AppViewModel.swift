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

/// Network-class errors that mean "retry later, don't surface to user".
/// Anything that's a URLError or APIError.requestFailed/invalidResponse
/// gets queued; explicit HTTP errors (4xx/5xx) don't.
private func isNetworkError(_ error: Error) -> Bool {
    if error is URLError { return true }
    if case APIError.requestFailed = error { return true }
    if case APIError.invalidResponse = error { return true }
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

    // Raw server data. Public `budgets` / `ledgerEntries` are these merged
    // with the pending offline queue so the UI is optimistic without
    // duplicating server entries.
    private var serverBudgets: [Budget] = []
    private var serverLedgerEntries: [LedgerEntry] = []
    private var loadedMonth: Date?

    // App Group container so the cache is shared with the widget.
    private static let cachedBudgetsKey = "cached_budgets"
    private var sharedDefaults: UserDefaults {
        UserDefaults(suiteName: AppSettings.appGroupID) ?? .standard
    }

    init() {
        // Seed budgets from the on-disk cache so the Amount page doesn't
        // flash zeros while /amounts is in flight.
        serverBudgets = loadCachedBudgets()
        rebuildDisplayed()

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

        // Drain the pending queue when the device comes back online.
        NotificationCenter.default.addObserver(
            self,
            selector: #selector(handleNetworkOnline),
            name: NetworkMonitor.didGoOnlineNotification,
            object: nil
        )

        // Same-process notifications when the queue file is mutated.
        // (Cross-process changes from the Intent extension are picked up
        // on the next foreground refresh.)
        NotificationCenter.default.addObserver(
            self,
            selector: #selector(handleStoreChanged),
            name: PendingExpenseStore.didChangeNotification,
            object: nil
        )

        // Force NWPathMonitor to start observing as early as possible.
        _ = NetworkMonitor.shared
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

    @objc private func handleNetworkOnline() {
        Task {
            await drainPendingQueue()
            await loadAmounts()
        }
    }

    @objc private func handleStoreChanged() {
        Task { @MainActor in
            rebuildDisplayed()
        }
    }

    func syncAndLoad() async {
        // Flush any expenses queued while offline / from the Intent before
        // we re-fetch from the server, so the refreshed data already
        // reflects the new state.
        await drainPendingQueue()
        await syncSettings()
        await loadBudgets()
        // Monthly budget automation runs on the backend (hourly scheduler);
        // the client doesn't need to nudge it.
        await loadAmounts()
    }

    // MARK: - Sync Functions

    private func syncSettings() async {
        // Pull authoritative state from the backend first so a household
        // member's changes on another device are picked up. Then push our
        // currency back (it's still device-driven via Settings.bundle).
        do {
            let remote = try await apiService.getSettings()
            await MainActor.run {
                if remote.splitBudgetOptions != settings.splitBudgetOptions {
                    settings.splitBudgetOptions = remote.splitBudgetOptions
                }
                if remote.categorizationRules != settings.categorizationRules {
                    settings.categorizationRules = remote.categorizationRules
                }
            }
        } catch {
            print("Failed to fetch settings: \(error)")
        }

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
            let existingTotals: [String: Int] = serverBudgets.reduce(into: [:]) { acc, b in
                if let total = b.totalAmount { acc[b.emoji] = total }
            }
            serverBudgets = fetchedBudgets.map { fetched in
                var merged = fetched
                if merged.totalAmount == nil, let prior = existingTotals[fetched.emoji] {
                    merged.totalAmount = prior
                }
                return merged
            }
            rebuildDisplayed()
        } catch {
            print("Failed to load budgets: \(error)")
            // Keep what we already have — the cache + previous /amounts data
            // is still more useful than wiping to empty.
        }
    }

    // MARK: - Load Data

    func loadAmounts() async {
        guard AuthenticationManager.shared.isAuthenticated else {
            errorMessage = "Please sign in to view your budget data"
            serverBudgets = []
            cacheBudgets([])
            rebuildDisplayed()
            return
        }

        isLoading = true
        errorMessage = nil

        do {
            let response = try await apiService.getAmounts()
            serverBudgets = response.budgets
            cacheBudgets(response.budgets)
            rebuildDisplayed()
        } catch {
            // URLError.cancelled bubbles up when SwiftUI cancels the host
            // Task (e.g. .refreshable mid-state-update). Treating it as an
            // error spams a misleading alert; the next legitimate load will
            // overwrite the data anyway.
            if !isCancellation(error) && !isNetworkError(error) {
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
            serverLedgerEntries = []
            rebuildDisplayed()
            return
        }

        isLoading = true
        errorMessage = nil

        do {
            let monthString = month?.monthYearString
            loadedMonth = month
            serverLedgerEntries = try await apiService.getLedger(month: monthString)
            rebuildDisplayed()
        } catch {
            if !isCancellation(error) && !isNetworkError(error) {
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
            if !isCancellation(error) && !isNetworkError(error) {
                errorMessage = "Failed to load category map: \(error.localizedDescription)"
            }
        }

        isLoading = false
    }

    // MARK: - Actions

    func addSpending(amount: Int, budgetEmojis: [String], description: String) async {
        guard !budgetEmojis.isEmpty else { return }
        let currency = settings.currencyCode

        // For a split option, divide the amount across all listed budgets
        // and round to the nearest integer (sign preserved). One ledger
        // entry per emoji, all sharing description + timestamp.
        let perAmount = Int((Double(amount) / Double(budgetEmojis.count)).rounded())
        let now = Date()

        for emoji in budgetEmojis {
            let pending = PendingExpense(
                amount: perAmount,
                currency: currency,
                budgetEmoji: emoji,
                descriptionText: description,
                datetime: now
            )
            PendingExpenseStore.shared.append(pending)
        }
        rebuildDisplayed()
        WidgetCenter.shared.reloadAllTimelines()

        // Try to flush right away.
        await drainPendingQueue()

        // Pull fresh totals from the server (no-op when offline).
        await loadAmounts()
    }

    func deleteSpending(uuid: String) async {
        // Allow deleting a pending (not-yet-uploaded) entry by removing
        // it from the local queue. UUIDs of pending entries are the
        // PendingExpense.id; server UUIDs come from the backend.
        if let pendingUUID = UUID(uuidString: uuid),
           PendingExpenseStore.shared.all().contains(where: { $0.id == pendingUUID }) {
            PendingExpenseStore.shared.remove(id: pendingUUID)
            rebuildDisplayed()
            WidgetCenter.shared.reloadAllTimelines()
            return
        }

        do {
            try await apiService.undoSpending(uuid: uuid)
            await loadLedger(for: loadedMonth)
            await loadAmounts()
            WidgetCenter.shared.reloadAllTimelines()
        } catch {
            errorMessage = "Failed to delete spending: \(error.localizedDescription)"
        }
    }

    func updateSpending(
        entry: LedgerEntry,
        amount: Int,
        budgetEmoji: String,
        description: String
    ) async {
        if let pendingUUID = UUID(uuidString: entry.uuid),
           let pending = PendingExpenseStore.shared.all().first(where: { $0.id == pendingUUID }) {
            PendingExpenseStore.shared.replace(PendingExpense(
                id: pending.id,
                amount: amount,
                currency: pending.currency,
                budgetEmoji: budgetEmoji,
                descriptionText: description,
                datetime: pending.datetime,
                attemptCount: pending.attemptCount,
                lastAttemptAt: pending.lastAttemptAt
            ))
            rebuildDisplayed()
            WidgetCenter.shared.reloadAllTimelines()
            await drainPendingQueue()
            await loadAmounts()
            return
        }

        do {
            _ = try await apiService.updateSpending(
                uuid: entry.uuid,
                amount: amount,
                budgetEmoji: budgetEmoji,
                description: description
            )
            await loadLedger(for: loadedMonth)
            await loadAmounts()
            WidgetCenter.shared.reloadAllTimelines()
        } catch {
            errorMessage = "Failed to update spending: \(error.localizedDescription)"
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

    // MARK: - Pending queue

    private var isDraining = false

    /// Attempt to upload every pending expense. On a network failure we
    /// stop early — the next reachability / foreground event will retry.
    /// Other errors (e.g. 4xx) are logged but the entry stays queued so
    /// the user can manually remove it if it's genuinely bad.
    func drainPendingQueue() async {
        guard !isDraining else { return }
        guard AuthenticationManager.shared.isAuthenticated else { return }

        isDraining = true
        defer { isDraining = false }

        let items = PendingExpenseStore.shared.all()
        guard !items.isEmpty else { return }

        for item in items {
            PendingExpenseStore.shared.markAttempt(id: item.id)
            do {
                _ = try await apiService.makeSpending(
                    amount: item.amount,
                    currency: item.currency,
                    budgetEmoji: item.budgetEmoji,
                    description: item.descriptionText,
                    datetime: item.datetime
                )
                PendingExpenseStore.shared.remove(id: item.id)
            } catch {
                if isNetworkError(error) {
                    // Offline / connection dropped — stop trying, wait for
                    // reachability to come back.
                    break
                }
                // Server-side error: keep the entry, log it, move on.
                print("drainPendingQueue: non-network error for \(item.id): \(error)")
            }
        }
        rebuildDisplayed()
    }

    // MARK: - Display merging

    private func rebuildDisplayed() {
        let pending = PendingExpenseStore.shared.all()

        // Adjust each budget's year-to-date total by pending amounts so
        // the Amount page is optimistic. /amounts is year-scoped, so any
        // pending in the current year contributes.
        let currentYear = Calendar.current.component(.year, from: Date())
        var pendingAdjustments: [String: Int] = [:]
        for p in pending where Calendar.current.component(.year, from: p.datetime) == currentYear {
            pendingAdjustments[p.budgetEmoji, default: 0] += p.amount
        }
        budgets = serverBudgets.map { b in
            guard let adj = pendingAdjustments[b.emoji] else { return b }
            var copy = b
            copy.totalAmount = (b.totalAmount ?? 0) + adj
            return copy
        }

        // Inject pending entries into the ledger as display-only rows,
        // but only those that belong to the currently-loaded month so
        // looking at past months doesn't surface today's pending entry.
        let calendar = Calendar.current
        let monthForFilter = loadedMonth ?? Date()
        let pendingInMonth = pending.filter { p in
            calendar.isDate(p.datetime, equalTo: monthForFilter, toGranularity: .month) &&
            calendar.isDate(p.datetime, equalTo: monthForFilter, toGranularity: .year)
        }
        let pendingEntries = pendingInMonth.map { LedgerEntry(pending: $0) }
        ledgerEntries = serverLedgerEntries + pendingEntries
    }
}
