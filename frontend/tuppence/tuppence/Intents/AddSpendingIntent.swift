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

    // Lock-screen execution: don't force unlock for expense logging.
    static var authenticationPolicy: IntentAuthenticationPolicy = .alwaysAllowed
    static var openAppWhenRun: Bool = false
    static var isDiscoverable: Bool = true

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

        let dialogText = await logSpending(
            amount: finalAmount,
            currency: currencyCode,
            currencySymbol: currencySymbol,
            target: budget,
            description: description,
            transactionLabel: transactionType.rawValue
        )
        return .result(dialog: IntentDialog(stringLiteral: dialogText))
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

    // Lock-screen execution: don't force unlock for expense logging.
    static var authenticationPolicy: IntentAuthenticationPolicy = .alwaysAllowed
    static var openAppWhenRun: Bool = false
    static var isDiscoverable: Bool = true

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

        let dialogText = await logSpending(
            amount: -abs(amount),
            currency: currencyCode,
            currencySymbol: currencySymbol,
            target: resolvedBudget,
            description: finalDescription,
            transactionLabel: nil
        )
        return .result(dialog: IntentDialog(stringLiteral: dialogText))
    }
}

// MARK: - Shared Intent Helper

/// Enqueue the expense locally, then try to upload it. On network failure
/// the entry stays in the queue and the main app will retry on next launch
/// or when the device comes back online. The returned dialog text reflects
/// which path was taken so the user knows whether it was uploaded or queued.
///
/// When `target` is a split option (its `splitEmojis` non-nil and non-empty),
/// the amount is divided evenly across the listed budgets and one ledger
/// entry is created per budget.
@available(iOS 18.0, *)
private func logSpending(
    amount: Int,
    currency: String,
    currencySymbol: String,
    target: BudgetEntity,
    description: String,
    transactionLabel: String?
) async -> String {
    let emojis: [String]
    if let split = target.splitEmojis, !split.isEmpty {
        emojis = split
    } else {
        emojis = [target.emoji]
    }
    let perAmount = Int((Double(amount) / Double(emojis.count)).rounded())
    let now = Date()

    var pendingIds: [(id: UUID, emoji: String)] = []
    for emoji in emojis {
        let pending = PendingExpense(
            amount: perAmount,
            currency: currency,
            budgetEmoji: emoji,
            descriptionText: description,
            datetime: now
        )
        PendingExpenseStore.shared.append(pending)
        pendingIds.append((id: pending.id, emoji: emoji))
    }

    var uploadedCount = 0
    for entry in pendingIds {
        do {
            _ = try await APIService.shared.makeSpending(
                amount: perAmount,
                currency: currency,
                budgetEmoji: entry.emoji,
                description: description,
                datetime: now
            )
            PendingExpenseStore.shared.remove(id: entry.id)
            uploadedCount += 1
        } catch {
            // Best-effort — entry stays in the queue and the main app
            // will retry on launch / when the device is online.
        }
    }

    await MainActor.run {
        WidgetCenter.shared.reloadAllTimelines()
    }

    let amountText = "\(currencySymbol)\(abs(amount))"
    let typePrefix = transactionLabel.map { "\($0) of " } ?? ""
    let allUploaded = uploadedCount == pendingIds.count
    let targetText = target.label.isEmpty ? target.emoji : "\(target.emoji) \(target.label)"

    if allUploaded {
        return "Added \(typePrefix)\(amountText) — \(description) — to \(targetText)"
    } else {
        return "Queued \(typePrefix)\(amountText) — \(description) — to \(targetText) (will upload when online)"
    }
}

// MARK: - Budget Entity

@available(iOS 18.0, *)
struct BudgetEntity: AppEntity {
    static var typeDisplayRepresentation = TypeDisplayRepresentation(name: "Budget")

    var id: String { emoji }
    let emoji: String
    let label: String
    /// When non-nil, this entity represents a "split" option — the amount is
    /// divided evenly across these emojis at log time. Plain budgets leave
    /// this nil.
    let splitEmojis: [String]?

    init(emoji: String, label: String, splitEmojis: [String]? = nil) {
        self.emoji = emoji
        self.label = label
        self.splitEmojis = splitEmojis
    }

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
        let splitMap = Self.validSplitEntities(budgets: budgets)
        return identifiers.map { id in
            if let b = budgets.first(where: { $0.emoji == id }) {
                return BudgetEntity(emoji: b.emoji, label: b.label)
            }
            if let split = splitMap[id] {
                return split
            }
            return BudgetEntity(emoji: id, label: id)
        }
    }

    func suggestedEntities() async throws -> [BudgetEntity] {
        let budgets = try await APIService.shared.listBudgets()
        let splitMap = Self.validSplitEntities(budgets: budgets)
        let splitEntities = splitMap.values.sorted { $0.emoji < $1.emoji }
        return budgets.map { BudgetEntity(emoji: $0.emoji, label: $0.label) } + splitEntities
    }

    /// Build `BudgetEntity` rows for every split option whose emojis all
    /// map to a current budget. Keyed by the concatenated emoji string so
    /// `entities(for:)` can resolve a picked split by its id.
    private static func validSplitEntities(budgets: [Budget]) -> [String: BudgetEntity] {
        let options = AppSettings.shared.splitBudgetOptions
        let emojiToLabel: [String: String] = Dictionary(
            uniqueKeysWithValues: budgets.map { ($0.emoji, $0.label) }
        )

        var result: [String: BudgetEntity] = [:]
        for option in options {
            let tokens = Self.emojiTokens(in: option)
            guard tokens.count >= 2, tokens.allSatisfy({ emojiToLabel[$0] != nil }) else { continue }
            let label = tokens.map { emojiToLabel[$0] ?? $0 }.joined(separator: " / ")
            result[option] = BudgetEntity(emoji: option, label: label, splitEmojis: tokens)
        }
        return result
    }

    private static func emojiTokens(in s: String) -> [String] {
        s.compactMap { ch in
            if ch.isWhitespace || ch == "/" || ch == "," || ch == "-" || ch == "+" { return nil }
            if ch.isASCII { return nil }
            return String(ch)
        }
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
