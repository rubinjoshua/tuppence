//
//  Budget.swift
//  tuppence
//

import Foundation

struct Budget: Codable, Identifiable, Hashable {
    // SwiftUI Identifiable — must be unique per-instance even when the
    // backend's /amounts endpoint omits the numeric id (BudgetWithTotal
    // has no id field). Emoji is the user-facing budget key.
    var id: String { emoji }

    let backendId: Int?
    let emoji: String
    let label: String
    let monthlyAmount: Int
    var totalAmount: Int?

    enum CodingKeys: String, CodingKey {
        case backendId = "id"
        case emoji
        case label
        case monthlyAmount = "monthly_amount"
        case totalAmount = "total_amount"
    }

    init(emoji: String, label: String, monthlyAmount: Int) {
        self.backendId = nil
        self.emoji = emoji
        self.label = label
        self.monthlyAmount = monthlyAmount
        self.totalAmount = nil
    }

    init(id: Int, emoji: String, label: String, monthlyAmount: Int, totalAmount: Int? = nil) {
        self.backendId = id
        self.emoji = emoji
        self.label = label
        self.monthlyAmount = monthlyAmount
        self.totalAmount = totalAmount
    }
}

struct BudgetsResponse: Codable {
    let budgets: [Budget]
}
