//
//  ContentView.swift
//  tuppence
//

import SwiftUI

struct ContentView: View {
    @StateObject private var viewModel = AppViewModel()
    @ObservedObject private var settings = AppSettings.shared
    @ObservedObject private var authManager = AuthenticationManager.shared

    @State private var currentPage: Page = .amount
    @State private var amountDisplay: AmountDisplay = .total
    @State private var selectedBudgetIndex = 0
    // Default to current month (last entry in months[]). Updated in .onAppear
    // so it stays correct as we roll into a new month mid-session.
    @State private var selectedMonthIndex: Int = max(0, Calendar.current.component(.month, from: Date()) - 1)
    @State private var isShowingAddExpense = false
    @State private var editingEntry: LedgerEntry?

    @Environment(\.colorScheme) var colorScheme
    @Environment(\.scenePhase) var scenePhase

    private var months: [Date] {
        Date.monthsInCurrentYear()
    }

    // Always a real Date (current month at the end of the array). Backend
    // accepts the explicit "YYYY-MM" string for any month.
    private var selectedMonth: Date? {
        months[safe: selectedMonthIndex] ?? months.last
    }

    private var selectedBudget: Budget? {
        viewModel.budgets[safe: selectedBudgetIndex]
    }

    var body: some View {
        if authManager.isAuthenticated {
            authenticatedContent
        } else {
            LoginView()
        }
    }

    private var authenticatedContent: some View {
        ZStack {
            // Background
            Theme.backgroundColor(for: colorScheme)
                .ignoresSafeArea()

            // Content — fills the screen behind the floating nav bar.
            // Scrollable pages apply their own fadingBottom modifier so the
            // last rows visibly fade out before reaching the nav bar.
            pageContent
                .frame(maxWidth: .infinity, maxHeight: .infinity)

            // Navigation Bar
            NavigationBar(
                currentPage: $currentPage,
                amountDisplay: $amountDisplay,
                selectedBudgetIndex: $selectedBudgetIndex,
                selectedMonthIndex: $selectedMonthIndex,
                budgets: viewModel.budgets,
                months: months
            )
            .onChange(of: currentPage) { _, newPage in
                Task {
                    switch newPage {
                    case .amount:
                        await viewModel.loadAmounts()
                    case .analysis:
                        if let budget = selectedBudget {
                            await viewModel.loadCategoryMap(for: selectedMonth, budgetEmoji: budget.emoji)
                        }
                    case .spendings:
                        await viewModel.loadLedger(for: selectedMonth)
                    case .settings:
                        // No data loading needed for settings page
                        break
                    }
                }
            }

            // Floating add button
            FloatingAddButton(isShowingSheet: $isShowingAddExpense)

            // Loading overlay
            if viewModel.isLoading {
                ProgressView()
                    .scaleEffect(1.5)
                    .frame(maxWidth: .infinity, maxHeight: .infinity)
                    .background(Color.black.opacity(0.2))
            }
        }
        .addExpenseSheet(
            isPresented: $isShowingAddExpense,
            budgets: viewModel.budgets,
            splitOptions: settings.splitBudgetOptions,
            editingEntry: editingEntry,
            onSave: { amount, emojis, description in
                if let entry = editingEntry, let emoji = emojis.first {
                    await viewModel.updateSpending(
                        entry: entry,
                        amount: amount,
                        budgetEmoji: emoji,
                        description: description
                    )
                } else {
                    await viewModel.addSpending(
                        amount: amount,
                        budgetEmojis: emojis,
                        description: description
                    )
                }
                // Refresh whatever the user is currently looking at so the
                // changed ledger state shows up immediately.
                await viewModel.loadLedger(for: selectedMonth)
                if currentPage == .analysis, let budget = selectedBudget {
                    await viewModel.loadCategoryMap(for: selectedMonth, budgetEmoji: budget.emoji)
                }
            }
        )
        .onChange(of: isShowingAddExpense) { _, isShowing in
            if !isShowing {
                editingEntry = nil
            }
        }
        .task {
            await viewModel.syncAndLoad()
        }
        .onChange(of: scenePhase) { _, newPhase in
            if newPhase == .active {
                Task {
                    await viewModel.syncAndLoad()
                }
            }
        }
        .alert("Error", isPresented: .constant(viewModel.errorMessage != nil)) {
            Button("OK") {
                viewModel.errorMessage = nil
            }
        } message: {
            if let error = viewModel.errorMessage {
                Text(error)
            }
        }
    }

    @ViewBuilder
    private var pageContent: some View {
        switch currentPage {
        case .amount:
            AmountView(
                budgets: viewModel.budgets,
                displayMode: amountDisplay
            )
        case .analysis:
            if let budget = selectedBudget {
                AnalysisView(categories: viewModel.categoryData)
                    .onChange(of: selectedBudgetIndex) { _, _ in
                        Task {
                            if let budget = selectedBudget {
                                await viewModel.loadCategoryMap(for: selectedMonth, budgetEmoji: budget.emoji)
                            }
                        }
                    }
                    .onChange(of: selectedMonthIndex) { _, _ in
                        Task {
                            if let budget = selectedBudget {
                                await viewModel.loadCategoryMap(for: selectedMonth, budgetEmoji: budget.emoji)
                            }
                        }
                    }
                    .task {
                        await viewModel.loadCategoryMap(for: selectedMonth, budgetEmoji: budget.emoji)
                    }
            } else {
                emptyState(message: "No budgets configured.\nPlease add budgets in Settings.")
            }
        case .spendings:
            SpendingsView(
                entries: viewModel.ledgerEntries,
                budgets: viewModel.budgets,
                onDelete: { uuid in
                    await viewModel.deleteSpending(uuid: uuid)
                },
                onEdit: { entry in
                    editingEntry = entry
                    isShowingAddExpense = true
                },
                onRefresh: {
                    // Run in parallel: chaining `await loadLedger; await loadAmounts`
                    // caused SwiftUI to re-render after loadLedger's state update,
                    // which cancelled the .refreshable Task before loadAmounts'
                    // URLSession call completed and left the spinner spinning.
                    async let ledger: () = viewModel.loadLedger(for: selectedMonth)
                    async let amounts: () = viewModel.loadAmounts()
                    _ = await (ledger, amounts)
                }
            )
            .onChange(of: selectedMonthIndex) { _, _ in
                Task {
                    await viewModel.loadLedger(for: selectedMonth)
                }
            }
            .task {
                await viewModel.loadLedger(for: selectedMonth)
            }
        case .settings:
            SettingsView()
        }
    }

    @ViewBuilder
    private func emptyState(message: String) -> some View {
        VStack {
            Spacer()
            Text(message)
                .themedText(size: 18)
                .multilineTextAlignment(.center)
                .padding()
            Spacer()
        }
    }
}

// MARK: - Array Extension

extension Array {
    subscript(safe index: Int) -> Element? {
        indices.contains(index) ? self[index] : nil
    }
}

#Preview {
    ContentView()
}
