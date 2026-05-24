//
//  SubscriptionManager.swift
//  tuppence
//

import Foundation
import Combine

@MainActor
class SubscriptionManager: ObservableObject {
    static let shared = SubscriptionManager()

    @Published var subscriptionStatus: SubscriptionResponse?
    @Published var pricingInfo: PricingResponse?
    @Published var isLoading = false
    @Published var errorMessage: String?

    private let apiService = APIService.shared

    private init() {}

    func checkSubscriptionStatus() async {
        guard AuthenticationManager.shared.isAuthenticated else {
            subscriptionStatus = nil
            return
        }

        isLoading = true
        do {
            subscriptionStatus = try await apiService.getSubscriptionStatus()
            errorMessage = nil
        } catch {
            subscriptionStatus = nil
            errorMessage = "Failed to load subscription status: \(error.localizedDescription)"
        }
        isLoading = false
    }

    func loadPricing() async {
        guard AuthenticationManager.shared.isAuthenticated else {
            pricingInfo = nil
            return
        }

        isLoading = true
        do {
            pricingInfo = try await apiService.getPricing()
            errorMessage = nil
        } catch {
            pricingInfo = nil
            errorMessage = "Failed to load pricing: \(error.localizedDescription)"
        }
        isLoading = false
    }

    var isActive: Bool {
        subscriptionStatus?.isActive ?? false
    }

    var isPremiumOrHigher: Bool {
        guard let tier = subscriptionStatus?.tier else { return false }
        return tier == .premium || tier == .pro
    }
}
