//
//  LedgerEntry.swift
//  tuppence
//

import Foundation

struct LedgerEntry: Codable, Identifiable {
    let uuid: String
    let amount: Int
    let currency: String
    let budgetEmoji: String
    let datetime: Date
    // Backend columns are nullable; iOS 18's JSONDecoder fails the entire
    // array if any row's description_text/category is null and these are
    // declared non-optional.
    let descriptionText: String?
    let category: String?
    // Local-only: true when this entry is a pending offline upload that
    // hasn't been confirmed by the server yet. Not encoded to JSON.
    var isPending: Bool

    var id: String { uuid }

    enum CodingKeys: String, CodingKey {
        case uuid
        case amount
        case currency
        case budgetEmoji = "budget_emoji"
        case datetime
        case descriptionText = "description_text"
        case category
    }

    init(
        uuid: String,
        amount: Int,
        currency: String,
        budgetEmoji: String,
        datetime: Date,
        descriptionText: String?,
        category: String?,
        isPending: Bool = false
    ) {
        self.uuid = uuid
        self.amount = amount
        self.currency = currency
        self.budgetEmoji = budgetEmoji
        self.datetime = datetime
        self.descriptionText = descriptionText
        self.category = category
        self.isPending = isPending
    }

    init(from decoder: Decoder) throws {
        let container = try decoder.container(keyedBy: CodingKeys.self)
        uuid = try container.decode(String.self, forKey: .uuid)
        amount = try container.decode(Int.self, forKey: .amount)
        currency = try container.decode(String.self, forKey: .currency)
        budgetEmoji = try container.decode(String.self, forKey: .budgetEmoji)
        datetime = try container.decode(Date.self, forKey: .datetime)
        descriptionText = try container.decodeIfPresent(String.self, forKey: .descriptionText)
        category = try container.decodeIfPresent(String.self, forKey: .category)
        isPending = false
    }

    func encode(to encoder: Encoder) throws {
        var container = encoder.container(keyedBy: CodingKeys.self)
        try container.encode(uuid, forKey: .uuid)
        try container.encode(amount, forKey: .amount)
        try container.encode(currency, forKey: .currency)
        try container.encode(budgetEmoji, forKey: .budgetEmoji)
        try container.encode(datetime, forKey: .datetime)
        try container.encodeIfPresent(descriptionText, forKey: .descriptionText)
        try container.encodeIfPresent(category, forKey: .category)
    }

    /// Build a display-only ledger entry from a pending offline expense.
    init(pending: PendingExpense) {
        self.uuid = pending.id.uuidString
        self.amount = pending.amount
        self.currency = pending.currency
        self.budgetEmoji = pending.budgetEmoji
        self.datetime = pending.datetime
        self.descriptionText = pending.descriptionText
        self.category = nil
        self.isPending = true
    }
}

struct MakeSpendingRequest: Codable {
    let amount: Int
    let currency: String
    let budgetEmoji: String
    let descriptionText: String
    let datetime: Date?

    enum CodingKeys: String, CodingKey {
        case amount
        case currency
        case budgetEmoji = "budget_emoji"
        case descriptionText = "description_text"
        case datetime
    }

    // Custom encoding to omit datetime when nil
    func encode(to encoder: Encoder) throws {
        var container = encoder.container(keyedBy: CodingKeys.self)
        try container.encode(amount, forKey: .amount)
        try container.encode(currency, forKey: .currency)
        try container.encode(budgetEmoji, forKey: .budgetEmoji)
        try container.encode(descriptionText, forKey: .descriptionText)
        // Only encode datetime if it's not nil
        if let datetime = datetime {
            try container.encode(datetime, forKey: .datetime)
        }
    }
}

struct MakeSpendingResponse: Codable {
    let uuid: String
    let category: String
    let success: Bool
}

struct UpdateSpendingRequest: Codable {
    let amount: Int
    let budgetEmoji: String
    let descriptionText: String

    enum CodingKeys: String, CodingKey {
        case amount
        case budgetEmoji = "budget_emoji"
        case descriptionText = "description_text"
    }
}
