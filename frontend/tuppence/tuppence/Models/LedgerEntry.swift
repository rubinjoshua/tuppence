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
    let descriptionText: String
    let category: String

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
