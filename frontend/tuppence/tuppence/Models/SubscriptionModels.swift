//
//  SubscriptionModels.swift
//  tuppence
//

import Foundation

enum SubscriptionTier: String, Codable {
    case free, premium, pro
}

enum SubscriptionStatus: String, Codable {
    case active, expired
    case inBillingRetry = "in_billing_retry"
    case inGracePeriod = "in_grace_period"
    case revoked, refunded, inactive
}

struct SubscriptionResponse: Codable {
    let householdId: String
    let tier: SubscriptionTier
    let status: SubscriptionStatus
    let productId: String?
    let environment: String?
    let currentPeriodStart: Date?
    let currentPeriodEnd: Date?
    let autoRenewStatus: Bool?
    let isActive: Bool
}

struct PricingTier: Codable {
    let tier: SubscriptionTier
    let displayName: String
    let monthlyProductId: String
    let yearlyProductId: String
    let features: [String]
}

struct PricingResponse: Codable {
    let tiers: [PricingTier]
    let currentTier: SubscriptionTier
}

struct VerifyTransactionRequest: Codable {
    let signedTransaction: String
}
