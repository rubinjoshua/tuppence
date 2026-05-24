//
//  SubscriptionView.swift
//  tuppence
//

import SwiftUI
import StoreKit

struct SubscriptionView: View {
    @ObservedObject private var subscriptionManager = SubscriptionManager.shared
    @ObservedObject private var storeKit = StoreKitManager.shared
    @Environment(\.colorScheme) var colorScheme
    @Environment(\.dismiss) var dismiss

    @State private var isPurchasing = false
    @State private var purchaseError: String?

    var body: some View {
        ZStack {
            Theme.backgroundColor(for: colorScheme)
                .ignoresSafeArea()

            ScrollView {
                VStack(spacing: 24) {
                    header

                    if subscriptionManager.isLoading || storeKit.products.isEmpty {
                        ProgressView().padding(.vertical, 40)
                    } else if let pricing = subscriptionManager.pricingInfo {
                        VStack(spacing: 16) {
                            ForEach(pricing.tiers.filter { $0.tier != .free }, id: \.tier) { tier in
                                pricingCard(tier: tier, currentTier: pricing.currentTier)
                            }
                        }
                        .padding(.horizontal, 20)
                    }

                    actionButtons

                    Text("Subscriptions auto-renew. Cancel anytime in Settings → Apple ID → Subscriptions.")
                        .font(Theme.Fonts.body(size: 12))
                        .foregroundColor(Theme.textColor(for: colorScheme).opacity(0.5))
                        .multilineTextAlignment(.center)
                        .padding(.horizontal, 20)
                        .padding(.bottom, 20)
                }
            }

            if isPurchasing {
                ProgressView()
                    .scaleEffect(1.5)
                    .frame(maxWidth: .infinity, maxHeight: .infinity)
                    .background(Color.black.opacity(0.2))
            }
        }
        .task {
            await subscriptionManager.loadPricing()
            await loadStoreKitProducts()
        }
        .alert("Error", isPresented: .constant(purchaseError != nil)) {
            Button("OK") { purchaseError = nil }
        } message: {
            Text(purchaseError ?? "")
        }
    }

    @ViewBuilder
    private var header: some View {
        VStack(spacing: 12) {
            Text("Unlock Tuppence Premium")
                .font(Theme.Fonts.heading(size: 28))
                .foregroundColor(Theme.textColor(for: colorScheme))

            Text("Track your spending and budgets with ease")
                .font(Theme.Fonts.body(size: 16))
                .foregroundColor(Theme.textColor(for: colorScheme).opacity(0.7))
                .multilineTextAlignment(.center)
        }
        .padding(.top, 40)
    }

    @ViewBuilder
    private var actionButtons: some View {
        VStack(spacing: 12) {
            Button {
                Task { await restore() }
            } label: {
                Text("Restore Purchases")
                    .font(Theme.Fonts.body(size: 15))
                    .foregroundColor(Theme.headingColor(for: colorScheme))
            }

            if subscriptionManager.isActive {
                Button {
                    Task { await manageSubscription() }
                } label: {
                    Text("Manage Subscription")
                        .font(Theme.Fonts.body(size: 15))
                        .foregroundColor(Theme.headingColor(for: colorScheme))
                }
            }
        }
        .padding(.top, 8)
    }

    @ViewBuilder
    private func pricingCard(tier: PricingTier, currentTier: SubscriptionTier) -> some View {
        let monthly = storeKit.products.first { $0.id == tier.monthlyProductId }
        let yearly = storeKit.products.first { $0.id == tier.yearlyProductId }
        let isCurrentTier = tier.tier == currentTier

        VStack(spacing: 16) {
            HStack {
                Text(tier.displayName)
                    .font(Theme.Fonts.heading(size: 20))
                    .foregroundColor(Theme.textColor(for: colorScheme))

                Spacer()

                if isCurrentTier {
                    Text("Current")
                        .font(Theme.Fonts.body(size: 12))
                        .foregroundColor(.green)
                        .padding(.horizontal, 12)
                        .padding(.vertical, 6)
                        .background(Color.green.opacity(0.2))
                        .cornerRadius(8)
                }
            }

            VStack(alignment: .leading, spacing: 8) {
                ForEach(tier.features, id: \.self) { feature in
                    HStack(spacing: 8) {
                        Image(systemName: "checkmark.circle.fill")
                            .foregroundColor(.green)
                            .font(.system(size: 16))
                        Text(feature)
                            .font(Theme.Fonts.body(size: 14))
                            .foregroundColor(Theme.textColor(for: colorScheme))
                    }
                }
            }

            if !isCurrentTier {
                if let monthly {
                    purchaseButton(product: monthly, label: "Monthly")
                }
                if let yearly {
                    purchaseButton(product: yearly, label: "Yearly")
                }
            }
        }
        .padding(20)
        .background(
            RoundedRectangle(cornerRadius: 16)
                .fill(colorScheme == .dark ? Color.white.opacity(0.1) : Color.black.opacity(0.05))
        )
        .overlay(
            RoundedRectangle(cornerRadius: 16)
                .stroke(isCurrentTier ? Color.green.opacity(0.5) : Color.blue.opacity(0.3),
                        lineWidth: isCurrentTier ? 2 : 1)
        )
    }

    @ViewBuilder
    private func purchaseButton(product: Product, label: String) -> some View {
        Button {
            Task { await purchase(product) }
        } label: {
            HStack {
                Text(label)
                    .font(Theme.Fonts.body(size: 16))
                Spacer()
                Text(product.displayPrice)
                    .font(Theme.Fonts.body(size: 16))
            }
            .foregroundColor(.white)
            .padding(.vertical, 14)
            .padding(.horizontal, 16)
            .frame(maxWidth: .infinity)
            .background(Color.blue)
            .cornerRadius(12)
        }
        .disabled(isPurchasing)
    }

    private func loadStoreKitProducts() async {
        guard let pricing = subscriptionManager.pricingInfo else { return }
        let ids = pricing.tiers
            .flatMap { [$0.monthlyProductId, $0.yearlyProductId] }
            .filter { !$0.isEmpty }
        do {
            try await storeKit.loadProducts(ids: ids)
        } catch {
            purchaseError = "Failed to load products: \(error.localizedDescription)"
        }
    }

    private func purchase(_ product: Product) async {
        isPurchasing = true
        defer { isPurchasing = false }
        do {
            _ = try await storeKit.purchase(product)
            dismiss()
        } catch StoreKitError.userCancelled {
            // No-op; user dismissed the sheet.
        } catch StoreKitError.pending {
            purchaseError = "Purchase pending approval. We'll unlock your subscription once it's approved."
        } catch {
            purchaseError = "Purchase failed: \(error.localizedDescription)"
        }
    }

    private func restore() async {
        isPurchasing = true
        defer { isPurchasing = false }
        do {
            try await storeKit.restorePurchases()
        } catch {
            purchaseError = "Restore failed: \(error.localizedDescription)"
        }
    }

    private func manageSubscription() async {
        guard let scene = UIApplication.shared.connectedScenes
            .first(where: { $0.activationState == .foregroundActive }) as? UIWindowScene
        else { return }
        do {
            try await AppStore.showManageSubscriptions(in: scene)
        } catch {
            purchaseError = "Could not open subscription management: \(error.localizedDescription)"
        }
    }
}

#Preview {
    SubscriptionView()
}
