//
//  StoreKitManager.swift
//  tuppence
//

import Foundation
import StoreKit
import Combine

@MainActor
final class StoreKitManager: ObservableObject {
    static let shared = StoreKitManager()

    @Published private(set) var products: [Product] = []

    private var transactionListener: Task<Void, Never>?

    private init() {
        transactionListener = listenForTransactions()
    }

    deinit { transactionListener?.cancel() }

    /// Load Apple's metadata (prices, localized titles) for the given product IDs.
    /// IDs come from `GET /subscriptions/pricing`.
    func loadProducts(ids: [String]) async throws {
        products = try await Product.products(for: ids)
    }

    /// Trigger Apple's native purchase sheet, then verify the result with the backend.
    func purchase(_ product: Product) async throws -> SubscriptionResponse {
        let result = try await product.purchase()

        switch result {
        case .success(let verification):
            let transaction = try verification.payloadValue
            let response = try await APIService.shared.verifyTransaction(jws: verification.jwsRepresentation)
            await transaction.finish()
            SubscriptionManager.shared.subscriptionStatus = response
            return response
        case .userCancelled:
            throw StoreKitError.userCancelled
        case .pending:
            throw StoreKitError.pending
        @unknown default:
            throw StoreKitError.unknown
        }
    }

    /// Restore: walk current entitlements and re-verify each with the backend.
    /// Called from a "Restore Purchases" button (required by App Review).
    func restorePurchases() async throws {
        for await result in Transaction.currentEntitlements {
            if case .verified(let transaction) = result {
                let response = try await APIService.shared.verifyTransaction(jws: result.jwsRepresentation)
                await transaction.finish()
                SubscriptionManager.shared.subscriptionStatus = response
            }
        }
    }

    /// Background listener for renewals, refunds, and cross-device updates
    /// that arrive while the app is running. Started on app launch.
    private func listenForTransactions() -> Task<Void, Never> {
        Task.detached {
            for await result in Transaction.updates {
                guard case .verified(let transaction) = result else { continue }
                if let response = try? await APIService.shared.verifyTransaction(jws: result.jwsRepresentation) {
                    await MainActor.run {
                        SubscriptionManager.shared.subscriptionStatus = response
                    }
                }
                await transaction.finish()
            }
        }
    }
}

enum StoreKitError: Error { case userCancelled, pending, unknown }
