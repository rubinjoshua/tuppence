//
//  AppSettings.swift
//  tuppence
//

import Combine
import Foundation

class AppSettings: ObservableObject {
    static let shared = AppSettings()

    private let defaults = UserDefaults.standard
    private static let maxBudgetSlots = 10

    @Published var currencySymbol: String = "$"
    @Published var budgets: [Budget] = []
    @Published var emailAddresses: [String] = []

    let backendURL = "https://tuppence-production-8de5.up.railway.app"

    private init() {
        registerDefaults()
        loadFromSettings()
    }

    /// Register Settings.bundle defaults so they appear before the user opens Settings
    private func registerDefaults() {
        var defaults: [String: Any] = [
            "currency_symbol": "$",
            "email_addresses_text": ""
        ]
        for i in 1...Self.maxBudgetSlots {
            defaults["budget_\(i)_emoji"] = ""
            defaults["budget_\(i)_label"] = ""
            defaults["budget_\(i)_amount"] = ""
        }
        UserDefaults.standard.register(defaults: defaults)
    }

    /// Reload all settings from UserDefaults (called on app activation)
    func loadFromSettings() {
        currencySymbol = defaults.string(forKey: "currency_symbol") ?? "$"

        // Read budget slots from Settings.bundle keys
        var loadedBudgets: [Budget] = []
        for i in 1...Self.maxBudgetSlots {
            let emoji = defaults.string(forKey: "budget_\(i)_emoji")?.trimmingCharacters(in: .whitespaces) ?? ""
            let label = defaults.string(forKey: "budget_\(i)_label")?.trimmingCharacters(in: .whitespaces) ?? ""
            let amountStr = defaults.string(forKey: "budget_\(i)_amount")?.trimmingCharacters(in: .whitespaces) ?? ""

            // Only include slots where at least the emoji is filled in
            if !emoji.isEmpty {
                let monthlyAmount = Int(amountStr) ?? 0
                let budget = Budget(
                    emoji: emoji,
                    label: label.isEmpty ? emoji : label,
                    monthlyAmount: monthlyAmount,
                    totalAmount: nil
                )
                loadedBudgets.append(budget)
            }
        }
        budgets = loadedBudgets

        // Read email addresses (comma-separated text from Settings.bundle)
        let emailText = defaults.string(forKey: "email_addresses_text") ?? ""
        emailAddresses = emailText
            .split(separator: ",")
            .map { $0.trimmingCharacters(in: .whitespaces) }
            .filter { !$0.isEmpty }
    }

    // Currency code mapping for backend
    var currencyCode: String {
        switch currencySymbol {
        case "$": return "USD"
        case "€": return "EUR"
        case "₪": return "ILS"
        default: return "USD"
        }
    }
}
