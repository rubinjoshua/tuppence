//
//  AddSpendingIntent.swift
//  tuppence
//

import AppIntents
import Foundation

@available(iOS 18.0, *)
struct AddSpendingIntent: AppIntent {
    static var title: LocalizedStringResource = "Add Spending"
    static var description = IntentDescription("Log a spending or income entry to your budget")

    @Parameter(title: "Budget")
    var budgetEmoji: String

    @Parameter(title: "Amount")
    var amount: Int

    @Parameter(title: "Description")
    var description: String

    @Parameter(title: "Type", default: .spending)
    var transactionType: TransactionType

    func perform() async throws -> some IntentResult {
        let (currencyCode, currencySymbol) = await MainActor.run {
            let settings = AppSettings.shared
            return (settings.currencyCode, settings.currencySymbol)
        }

        // Validate budget exists
        let budgets = try await APIService.shared.listBudgets()
        guard budgets.contains(where: { $0.emoji == budgetEmoji }) else {
            throw IntentError.message("Budget '\(budgetEmoji)' not found")
        }

        // Determine amount sign
        let finalAmount: Int
        switch transactionType {
        case .spending:
            finalAmount = -abs(amount)
        case .income:
            finalAmount = abs(amount)
        }

        // Call API
        do {
            _ = try await APIService.shared.makeSpending(
                amount: finalAmount,
                currency: currencyCode,
                budgetEmoji: budgetEmoji,
                description: description,
                datetime: Date()
            )

            return .result(dialog: "Added \(transactionType.rawValue) of \(currencySymbol)\(amount) to \(budgetEmoji)")
        } catch {
            throw IntentError.message("Failed to add spending: \(error.localizedDescription)")
        }
    }

    enum TransactionType: String, AppEnum {
        case spending = "Spending"
        case income = "Income"

        static var typeDisplayRepresentation = TypeDisplayRepresentation(name: "Transaction Type")
        static var caseDisplayRepresentations: [TransactionType: DisplayRepresentation] = [
            .spending: "Spending (subtract)",
            .income: "Income (add)"
        ]
    }
}

@available(iOS 18.0, *)
struct QuickAddSpendingIntent: AppIntent {
    static var title: LocalizedStringResource = "Quick Add Spending"
    static var description = IntentDescription("Quickly log spending with pre-selected budget")

    @Parameter(title: "Budget", optionsProvider: BudgetOptionsProvider())
    var budget: BudgetEntity

    @Parameter(title: "Amount")
    var amount: Int

    @Parameter(title: "Description")
    var description: String

    func perform() async throws -> some IntentResult {
        let (currencyCode, currencySymbol) = await MainActor.run {
            let settings = AppSettings.shared
            return (settings.currencyCode, settings.currencySymbol)
        }

        do {
            _ = try await APIService.shared.makeSpending(
                amount: -abs(amount),
                currency: currencyCode,
                budgetEmoji: budget.emoji,
                description: description,
                datetime: Date()
            )

            return .result(dialog: "Added spending of \(currencySymbol)\(amount) to \(budget.emoji) \(budget.label)")
        } catch {
            throw IntentError.message("Failed to add spending: \(error.localizedDescription)")
        }
    }
}

// MARK: - Budget Entity

@available(iOS 18.0, *)
struct BudgetEntity: AppEntity {
    static var typeDisplayRepresentation = TypeDisplayRepresentation(name: "Budget")

    var id: String { emoji }
    let emoji: String
    let label: String

    var displayRepresentation: DisplayRepresentation {
        DisplayRepresentation(title: "\(emoji) \(label)")
    }

    static var defaultQuery = BudgetQuery()
}

@available(iOS 18.0, *)
struct BudgetQuery: EntityQuery {
    func entities(for identifiers: [String]) async throws -> [BudgetEntity] {
        let budgets = try await APIService.shared.listBudgets()
        return budgets
            .filter { identifiers.contains($0.emoji) }
            .map { BudgetEntity(emoji: $0.emoji, label: $0.label) }
    }

    func suggestedEntities() async throws -> [BudgetEntity] {
        let budgets = try await APIService.shared.listBudgets()
        return budgets.map { BudgetEntity(emoji: $0.emoji, label: $0.label) }
    }
}

@available(iOS 18.0, *)
struct BudgetOptionsProvider: DynamicOptionsProvider {
    func results() async throws -> [BudgetEntity] {
        let budgets = try await APIService.shared.listBudgets()
        return budgets.map { BudgetEntity(emoji: $0.emoji, label: $0.label) }
    }
}

// MARK: - Intent Error

enum IntentError: LocalizedError {
    case message(String)

    var errorDescription: String? {
        switch self {
        case .message(let text):
            return text
        }
    }
}

// MARK: - App Shortcuts Provider

@available(iOS 18.0, *)
struct TuppenceShortcuts: AppShortcutsProvider {
    static var appShortcuts: [AppShortcut] {
        AppShortcut(
            intent: QuickAddSpendingIntent(),
            phrases: [
                "Add spending in \(.applicationName)",
                "Log expense in \(.applicationName)",
                "Record spending in \(.applicationName)"
            ],
            shortTitle: "Add Spending",
            systemImageName: "dollarsign.circle"
        )
    }
}
