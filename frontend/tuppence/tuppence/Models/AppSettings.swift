//
//  AppSettings.swift
//  tuppence
//

import Combine
import Foundation
import WidgetKit

class AppSettings: ObservableObject {
    static let shared = AppSettings()

    // App Group container so the Widget Extension reads the same value.
    // UserDefaults.standard is per-process-sandbox and isn't visible to
    // the widget; this group is on both targets' entitlements.
    static let appGroupID = "group.com.joshuarubin.tuppence"
    private let defaults = UserDefaults(suiteName: AppSettings.appGroupID) ?? .standard
    private var isLoading = false

    @Published var currencySymbol: String = "$" {
        didSet {
            guard !isLoading, currencySymbol != oldValue else { return }
            defaults.set(currencySymbol, forKey: "currency_symbol")
            // Nudge the widget to redraw immediately instead of waiting up
            // to 15 minutes for the next timeline refresh.
            WidgetCenter.shared.reloadAllTimelines()
        }
    }

    // List of multi-emoji strings (e.g. "🛒🦊"). Each becomes a row at the
    // bottom of the budget picker; choosing one divides the amount across
    // the constituent budgets. Persisted in the App Group so the Shortcuts
    // extension reads the same list as the main app.
    @Published var splitBudgetOptions: [String] = [] {
        didSet {
            guard !isLoading, splitBudgetOptions != oldValue else { return }
            if let data = try? JSONEncoder().encode(splitBudgetOptions) {
                defaults.set(data, forKey: "split_budget_options")
            }
        }
    }

    // Free-text rules appended to the AI categorization prompt on the backend.
    // Household-scoped and shared across members; the widget/Shortcuts
    // extensions never categorize locally so this lives only in the main app's
    // defaults for offline display in Settings.
    @Published var categorizationRules: String = "" {
        didSet {
            guard !isLoading, categorizationRules != oldValue else { return }
            defaults.set(categorizationRules, forKey: "categorization_rules")
        }
    }

    let backendURL = "https://tuppence-production-8de5.up.railway.app"

    private init() {
        migrateFromStandardDefaultsIfNeeded()
        registerDefaults()
        loadFromSettings()
    }

    private func registerDefaults() {
        defaults.register(defaults: ["currency_symbol": "$"])
    }

    private func migrateFromStandardDefaultsIfNeeded() {
        guard defaults.string(forKey: "currency_symbol") == nil,
              let legacy = UserDefaults.standard.string(forKey: "currency_symbol") else { return }
        defaults.set(legacy, forKey: "currency_symbol")
    }

    func loadFromSettings() {
        isLoading = true
        currencySymbol = defaults.string(forKey: "currency_symbol") ?? "$"
        if let data = defaults.data(forKey: "split_budget_options"),
           let options = try? JSONDecoder().decode([String].self, from: data) {
            splitBudgetOptions = options
        } else {
            splitBudgetOptions = []
        }
        categorizationRules = defaults.string(forKey: "categorization_rules") ?? ""
        isLoading = false
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
