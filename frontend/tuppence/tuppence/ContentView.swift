//
//  ContentView.swift
//  tuppence
//

import SwiftUI

struct ContentView: View {
    @StateObject private var viewModel = AppViewModel()
    @ObservedObject private var settings = AppSettings.shared

    @State private var currentPage: Page = .amount
    @State private var amountDisplay: AmountDisplay = .total
    @State private var selectedBudgetIndex = 0
    @State private var selectedMonthIndex = 0
    @State private var isShowingAddExpense = false

    @Environment(\.colorScheme) var colorScheme
    @Environment(\.scenePhase) var scenePhase

    private var months: [Date] {
        Date.monthsInCurrentYear()
    }

    private var selectedMonth: Date? {
        selectedMonthIndex == 0 ? nil : months[safe: selectedMonthIndex]
    }

    private var selectedBudget: Budget? {
        settings.budgets[safe: selectedBudgetIndex]
    }

    var body: some View {
        ZStack {
            // Background
            Theme.backgroundColor(for: colorScheme)
                .ignoresSafeArea()

            // Content
            VStack {
                switch currentPage {
                case .amount:
                    AmountView(
                        budgets: viewModel.budgets.isEmpty ? settings.budgets : viewModel.budgets,
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
                        onDelete: { uuid in
                            await viewModel.deleteSpending(uuid: uuid)
                        },
                        onRefresh: {
                            await viewModel.loadLedger(for: selectedMonth)
                            await viewModel.loadAmounts()
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
                }

                Spacer()
            }

            // Navigation Bar
            NavigationBar(
                currentPage: $currentPage,
                amountDisplay: $amountDisplay,
                selectedBudgetIndex: $selectedBudgetIndex,
                selectedMonthIndex: $selectedMonthIndex,
                budgets: settings.budgets,
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
            budgets: settings.budgets,
            onAddExpense: { amount, emoji, description in
                await viewModel.addSpending(amount: amount, budgetEmoji: emoji, description: description)
            }
        )
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
