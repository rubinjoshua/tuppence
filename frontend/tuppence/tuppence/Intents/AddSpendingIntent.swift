//
//  AddSpendingIntent.swift
//  tuppence
//

import AppIntents
import Foundation
import WidgetKit

@available(iOS 18.0, *)
struct AddSpendingIntent: AppIntent {
    static var title: LocalizedStringResource = "Add Spending"
    static var description = IntentDescription("Log a spending or income entry to your budget")

    @Parameter(title: "Budget")
    var budget: BudgetEntity

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

        let finalAmount: Int
        switch transactionType {
        case .spending:
            finalAmount = -abs(amount)
        case .income:
            finalAmount = abs(amount)
        }

        do {
            _ = try await APIService.shared.makeSpending(
                amount: finalAmount,
                currency: currencyCode,
                budgetEmoji: budget.emoji,
                description: description,
                datetime: Date()
            )

            await MainActor.run {
                WidgetCenter.shared.reloadAllTimelines()
            }

            let dialogText = "Added \(transactionType.rawValue) of \(currencySymbol)\(amount) to \(budget.emoji) \(budget.label)"
            return .result(dialog: IntentDialog(stringLiteral: dialogText))
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
        "Log a spending. Supply an Amount and a comma-separated list of common Descriptions. The user picks one at run time; 'Something else' is appended automatically as a free-text fallback."
    )

    @Parameter(title: "Amount")
    var amount: Int

    // Plain String (comma-separated) instead of [String] — the iOS
    // Shortcuts editor's per-item field for [String] eats keystrokes.
    @Parameter(
        title: "Description options (comma-separated)",
        description: "e.g. Lunch, Coffee, Groceries. 'Something else' is appended automatically as a free-text option."
    )
    var descriptionOptions: String

    // Optional so iOS does NOT auto-prompt before perform() runs. We prompt
    // manually inside perform() after the description disambiguation, so
    // the runtime order is description-then-budget per user request.
    @Parameter(title: "Budget")
    var budget: BudgetEntity?

    @Parameter(title: "Description")
    var pickedDescription: String?

    @Parameter(title: "Custom description", requestValueDialog: "Enter description")
    var customDescription: String?

    func perform() async throws -> some IntentResult {
        let (currencyCode, currencySymbol) = await MainActor.run {
            let settings = AppSettings.shared
            return (settings.currencyCode, settings.currencySymbol)
        }

        let parsedOptions = descriptionOptions
            .split(separator: ",")
            .map { $0.trimmingCharacters(in: .whitespaces) }
            .filter { !$0.isEmpty }
        let runtimeOptions = parsedOptions + ["Something else"]

        let picked = try await $pickedDescription.requestDisambiguation(
            among: runtimeOptions,
            dialog: "Pick a description"
        )

        let finalDescription: String
        if picked.localizedCaseInsensitiveCompare("Something else") == .orderedSame {
            finalDescription = try await $customDescription.requestValue("Enter description")
        } else {
            finalDescription = picked
        }

        let resolvedBudget: BudgetEntity
        if let configured = budget {
            resolvedBudget = configured
        } else {
            let allBudgets = try await BudgetQuery().suggestedEntities()
            guard !allBudgets.isEmpty else {
                throw IntentError.message("No budgets available")
            }
            resolvedBudget = try await $budget.requestDisambiguation(
                among: allBudgets,
                dialog: "Pick a budget"
            )
        }

        do {
            _ = try await APIService.shared.makeSpending(
                amount: -abs(amount),
                currency: currencyCode,
                budgetEmoji: resolvedBudget.emoji,
                description: finalDescription,
                datetime: Date()
            )

            await MainActor.run {
                WidgetCenter.shared.reloadAllTimelines()
            }

            let dialogText = "Added \(currencySymbol)\(amount) — \(finalDescription) — to \(resolvedBudget.emoji) \(resolvedBudget.label)"
            return .result(dialog: IntentDialog(stringLiteral: dialogText))
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
    // Be lenient: if the API call fails or the picked emoji is missing,
    // synthesize an entity from the identifier so iOS can still resolve
    // the user's pick. Returning [] here causes iOS 18 to loop the picker.
    func entities(for identifiers: [String]) async throws -> [BudgetEntity] {
        let budgets = (try? await APIService.shared.listBudgets()) ?? []
        return identifiers.map { id in
            if let b = budgets.first(where: { $0.emoji == id }) {
                return BudgetEntity(emoji: b.emoji, label: b.label)
            }
            return BudgetEntity(emoji: id, label: id)
        }
    }

    func suggestedEntities() async throws -> [BudgetEntity] {
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
