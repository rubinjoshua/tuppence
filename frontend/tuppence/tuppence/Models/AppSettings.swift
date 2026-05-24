//
//  AppSettings.swift
//  tuppence
//

import Combine
import Foundation

class AppSettings: ObservableObject {
    static let shared = AppSettings()

    private let defaults = UserDefaults.standard
    private var isLoading = false

    @Published var currencySymbol: String = "$" {
        didSet {
            guard !isLoading, currencySymbol != oldValue else { return }
            defaults.set(currencySymbol, forKey: "currency_symbol")
        }
    }

    let backendURL = "https://tuppence-production-8de5.up.railway.app"

    private init() {
        registerDefaults()
        loadFromSettings()
    }

    private func registerDefaults() {
        UserDefaults.standard.register(defaults: ["currency_symbol": "$"])
    }

    func loadFromSettings() {
        isLoading = true
        currencySymbol = defaults.string(forKey: "currency_symbol") ?? "$"
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
