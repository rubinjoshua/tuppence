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
    static var title: LocalizedStringResource = "Log Expense"
    static var description = IntentDescription(
        "Log a spending. The Shortcut creator supplies an Amount and a list of common Descriptions (end the list with 'Something else' to allow free-text). At run time you pick one description and a budget; picking 'Something else' opens a text field."
    )

    @Parameter(title: "Amount")
    var amount: Int

    // Shortcut creator fills this in when building the Shortcut.
    // End the list with "Something else" to give the runtime user a text-input fallback.
    @Parameter(
        title: "Description options",
        description: "Choices shown to the user at run time. End with 'Something else' to allow free-text input."
    )
    var descriptionOptions: [String]

    // Picker shown to the runtime user; populated from descriptionOptions
    // via IntentParameterDependency on DescriptionChoiceQuery.
    @Parameter(title: "Description")
    var description: DescriptionChoice

    @Parameter(title: "Budget", optionsProvider: BudgetOptionsProvider())
    var budget: BudgetEntity

    // Only prompted if the user picks "Something else".
    @Parameter(
        title: "Custom description",
        requestValueDialog: "Enter description"
    )
    var customDescription: String?

    func perform() async throws -> some IntentResult {
        let (currencyCode, currencySymbol) = await MainActor.run {
            let settings = AppSettings.shared
            return (settings.currencyCode, settings.currencySymbol)
        }

        let finalDescription: String
        if description.text.localizedCaseInsensitiveCompare("Something else") == .orderedSame {
            finalDescription = try await $customDescription.requestValue()
        } else {
            finalDescription = description.text
        }

        do {
            _ = try await APIService.shared.makeSpending(
                amount: -abs(amount),
                currency: currencyCode,
                budgetEmoji: budget.emoji,
                description: finalDescription,
                datetime: Date()
            )

            return .result(dialog: "Added \(currencySymbol)\(amount) — \(finalDescription) — to \(budget.emoji) \(budget.label)")
        } catch {
            throw IntentError.message("Failed to add spending: \(error.localizedDescription)")
        }
    }
}

// MARK: - Description Choice (per-shortcut list)

@available(iOS 18.0, *)
struct DescriptionChoice: AppEntity {
    var id: String { text }
    let text: String

    var displayRepresentation: DisplayRepresentation {
        DisplayRepresentation(title: "\(text)")
    }

    static var typeDisplayRepresentation = TypeDisplayRepresentation(name: "Description")
    static var defaultQuery = DescriptionChoiceQuery()
}

@available(iOS 18.0, *)
struct DescriptionChoiceQuery: EntityQuery {
    // Reads descriptionOptions off the calling intent at runtime — that's how
    // the picker becomes populated from the creator-supplied list.
    @IntentParameterDependency<QuickAddSpendingIntent>(\.$descriptionOptions)
    var dependency

    func entities(for identifiers: [String]) async throws -> [DescriptionChoice] {
        identifiers.map { DescriptionChoice(text: $0) }
    }

    func suggestedEntities() async throws -> [DescriptionChoice] {
        (dependency?.descriptionOptions ?? []).map { DescriptionChoice(text: $0) }
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
