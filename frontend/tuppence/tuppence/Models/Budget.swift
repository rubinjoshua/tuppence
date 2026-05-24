//
//  Budget.swift
//  tuppence
//

import Foundation

struct Budget: Codable, Identifiable, Hashable {
    let id: Int?  // Backend ID (nil for local-only budgets)
    let emoji: String
    let label: String
    let monthlyAmount: Int
    var totalAmount: Int?

    enum CodingKeys: String, CodingKey {
        case id
        case emoji
        case label
        case monthlyAmount = "monthly_amount"
        case totalAmount = "total_amount"
    }

    // For creating new budgets (no ID yet)
    init(emoji: String, label: String, monthlyAmount: Int) {
        self.id = nil
        self.emoji = emoji
        self.label = label
        self.monthlyAmount = monthlyAmount
        self.totalAmount = nil
    }

    // For backend budgets (has ID)
    init(id: Int, emoji: String, label: String, monthlyAmount: Int, totalAmount: Int? = nil) {
        self.id = id
        self.emoji = emoji
        self.label = label
        self.monthlyAmount = monthlyAmount
        self.totalAmount = totalAmount
    }
}

struct BudgetsResponse: Codable {
    let budgets: [Budget]
}
