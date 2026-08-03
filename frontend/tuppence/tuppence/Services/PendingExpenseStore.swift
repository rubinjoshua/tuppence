//
//  PendingExpenseStore.swift
//  tuppence
//
//  Atomic, cross-process queue for expenses pending upload to the backend.
//  Backed by a JSON file in the App Group container so the Shortcut /
//  App Intent extension and the main app share the same queue. Uses
//  NSFileCoordinator to serialize concurrent reads/writes across
//  processes.
//

import Foundation

final class PendingExpenseStore {
    static let shared = PendingExpenseStore()

    static let didChangeNotification = Notification.Name("PendingExpenseStoreDidChange")

    private let url: URL = {
        let group = FileManager.default.containerURL(
            forSecurityApplicationGroupIdentifier: AppSettings.appGroupID
        )
        // Fallback to a tmp file if the App Group isn't available (e.g. a
        // misconfigured target). Better than crashing — the queue just
        // won't be cross-process.
        let base = group ?? FileManager.default.temporaryDirectory
        return base.appendingPathComponent("pending_expenses.json")
    }()

    private let encoder: JSONEncoder = {
        let e = JSONEncoder()
        e.dateEncodingStrategy = .iso8601
        return e
    }()

    private let decoder: JSONDecoder = {
        let d = JSONDecoder()
        d.dateDecodingStrategy = .iso8601
        return d
    }()

    private init() {}

    // MARK: - Public API

    func all() -> [PendingExpense] {
        var items: [PendingExpense] = []
        let coordinator = NSFileCoordinator(filePresenter: nil)
        var coordError: NSError?
        coordinator.coordinate(readingItemAt: url, options: [], error: &coordError) { coordURL in
            items = readUnlocked(from: coordURL)
        }
        return items
    }

    @discardableResult
    func append(_ expense: PendingExpense) -> [PendingExpense] {
        modify { items in
            items.append(expense)
        }
    }

    @discardableResult
    func remove(id: UUID) -> [PendingExpense] {
        modify { items in
            items.removeAll { $0.id == id }
        }
    }

    @discardableResult
    func replace(_ expense: PendingExpense) -> [PendingExpense] {
        modify { items in
            if let index = items.firstIndex(where: { $0.id == expense.id }) {
                items[index] = expense
            }
        }
    }

    @discardableResult
    func markAttempt(id: UUID) -> [PendingExpense] {
        modify { items in
            if let idx = items.firstIndex(where: { $0.id == id }) {
                items[idx].attemptCount += 1
                items[idx].lastAttemptAt = Date()
            }
        }
    }

    // MARK: - Internals

    @discardableResult
    private func modify(_ block: (inout [PendingExpense]) -> Void) -> [PendingExpense] {
        var finalItems: [PendingExpense] = []
        let coordinator = NSFileCoordinator(filePresenter: nil)
        var coordError: NSError?
        coordinator.coordinate(writingItemAt: url, options: .forReplacing, error: &coordError) { coordURL in
            var items = readUnlocked(from: coordURL)
            block(&items)
            writeUnlocked(items, to: coordURL)
            finalItems = items
        }
        NotificationCenter.default.post(name: Self.didChangeNotification, object: nil)
        return finalItems
    }

    private func readUnlocked(from url: URL) -> [PendingExpense] {
        guard let data = try? Data(contentsOf: url) else { return [] }
        return (try? decoder.decode([PendingExpense].self, from: data)) ?? []
    }

    private func writeUnlocked(_ items: [PendingExpense], to url: URL) {
        guard let data = try? encoder.encode(items) else { return }
        try? data.write(to: url, options: .atomic)
    }
}
