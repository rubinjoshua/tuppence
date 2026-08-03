//
//  PendingExpense.swift
//  tuppence
//
//  A spending that has been logged locally but not yet pushed to the
//  backend. Lives in the App Group container so both the main app and
//  the App Intent extension process can read/write the same queue.
//

import Foundation

struct PendingExpense: Codable, Identifiable, Hashable {
    let id: UUID
    let amount: Int
    let currency: String
    let budgetEmoji: String
    let descriptionText: String
    let datetime: Date
    var attemptCount: Int
    var lastAttemptAt: Date?

    init(
        id: UUID = UUID(),
        amount: Int,
        currency: String,
        budgetEmoji: String,
        descriptionText: String,
        datetime: Date,
        attemptCount: Int = 0,
        lastAttemptAt: Date? = nil
    ) {
        self.id = id
        self.amount = amount
        self.currency = currency
        self.budgetEmoji = budgetEmoji
        self.descriptionText = descriptionText
        self.datetime = datetime
        self.attemptCount = attemptCount
        self.lastAttemptAt = lastAttemptAt
    }
}
