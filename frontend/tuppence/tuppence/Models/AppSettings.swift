//
//  AppSettings.swift
//  tuppence
//

import Combine
import Foundation

class AppSettings: ObservableObject {
    static let shared = AppSettings()

    private let defaults = UserDefaults.standard

    @Published var currencySymbol: String = "$"

    let backendURL = "https://tuppence-production-8de5.up.railway.app"

    private init() {
        registerDefaults()
        loadFromSettings()
    }

    /// Register Settings.bundle defaults so they appear before the user opens Settings
    private func registerDefaults() {
        let defaults: [String: Any] = [
            "currency_symbol": "$"
        ]
        UserDefaults.standard.register(defaults: defaults)
    }

    /// Reload all settings from UserDefaults (called on app activation)
    func loadFromSettings() {
        currencySymbol = defaults.string(forKey: "currency_symbol") ?? "$"
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
