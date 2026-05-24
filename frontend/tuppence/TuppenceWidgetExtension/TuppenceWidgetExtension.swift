//
//  TuppenceWidgetExtension.swift
//  TuppenceWidgetExtension
//

import WidgetKit
import SwiftUI
import Security

// MARK: - Widget Model

struct WidgetBudget: Decodable, Identifiable {
    // /amounts returns BudgetWithTotal which has no id field. Without a
    // stable identity ForEach would dedupe rows and render the first
    // emoji five times. Emoji is the user-facing budget key.
    var id: String { emoji }

    let emoji: String
    let label: String
    let totalAmount: Int?

    enum CodingKeys: String, CodingKey {
        case emoji
        case label
        case totalAmount = "total_amount"
    }
}

private struct WidgetAmountsResponse: Decodable {
    let budgets: [WidgetBudget]
}

// MARK: - Shared Keychain (reads main app's session token)

private enum WidgetKeychain {
    private static let service = "com.tuppence.app"
    private static let sessionTokenKey = "session_token"
    private static let currencySymbolKey = "currency_symbol"

    static var sessionToken: String? {
        let query: [String: Any] = [
            kSecClass as String: kSecClassGenericPassword,
            kSecAttrService as String: service,
            kSecAttrAccount as String: sessionTokenKey,
            kSecReturnData as String: true,
            kSecMatchLimit as String: kSecMatchLimitOne
        ]
        var result: AnyObject?
        guard SecItemCopyMatching(query as CFDictionary, &result) == errSecSuccess,
              let data = result as? Data else { return nil }
        return String(data: data, encoding: .utf8)
    }
}

// MARK: - API Call

private func fetchBudgets() async -> [WidgetBudget] {
    guard let token = WidgetKeychain.sessionToken else { return [] }

    let backendURL = "https://tuppence-production-8de5.up.railway.app"
    guard let url = URL(string: "\(backendURL)/amounts") else { return [] }

    var request = URLRequest(url: url)
    request.setValue("Bearer \(token)", forHTTPHeaderField: "Authorization")

    do {
        let (data, response) = try await URLSession.shared.data(for: request)
        guard let http = response as? HTTPURLResponse, http.statusCode == 200 else {
            return []
        }
        return try JSONDecoder().decode(WidgetAmountsResponse.self, from: data).budgets
    } catch {
        return []
    }
}

// MARK: - Timeline

struct BudgetEntry: TimelineEntry {
    let date: Date
    let budgets: [WidgetBudget]
}

struct Provider: TimelineProvider {
    func placeholder(in context: Context) -> BudgetEntry {
        BudgetEntry(date: Date(), budgets: [])
    }

    func getSnapshot(in context: Context, completion: @escaping (BudgetEntry) -> Void) {
        Task {
            let budgets = await fetchBudgets()
            completion(BudgetEntry(date: Date(), budgets: budgets))
        }
    }

    func getTimeline(in context: Context, completion: @escaping (Timeline<BudgetEntry>) -> Void) {
        Task {
            let budgets = await fetchBudgets()
            let entry = BudgetEntry(date: Date(), budgets: budgets)
            let nextUpdate = Calendar.current.date(byAdding: .minute, value: 15, to: Date())!
            completion(Timeline(entries: [entry], policy: .after(nextUpdate)))
        }
    }
}

// MARK: - View

private let currencySymbol: String = {
    UserDefaults.standard.string(forKey: "currency_symbol") ?? "$"
}()

struct TuppenceWidgetExtensionEntryView: View {
    var entry: BudgetEntry

    var body: some View {
        if entry.budgets.isEmpty {
            Text("No budgets")
                .font(.system(size: 14))
                .frame(maxWidth: .infinity, maxHeight: .infinity)
        } else {
            VStack(alignment: .leading, spacing: 8) {
                ForEach(entry.budgets.prefix(6)) { budget in
                    HStack(spacing: 8) {
                        Text(budget.emoji)
                            .font(.system(size: 18))
                        Text("\(currencySymbol)\(budget.totalAmount ?? 0)")
                            .font(.system(size: 14))
                            .frame(maxWidth: .infinity, alignment: .leading)
                    }
                }
            }
        }
    }
}

// MARK: - Widget

struct TuppenceWidgetExtension: Widget {
    let kind: String = "TuppenceWidgetExtension"

    var body: some WidgetConfiguration {
        StaticConfiguration(kind: kind, provider: Provider()) { entry in
            TuppenceWidgetExtensionEntryView(entry: entry)
                .containerBackground(.fill.tertiary, for: .widget)
        }
        .configurationDisplayName("Tuppence")
        .description("Your remaining budgets at a glance.")
        .supportedFamilies([.systemSmall, .systemMedium])
    }
}

#Preview(as: .systemSmall) {
    TuppenceWidgetExtension()
} timeline: {
    BudgetEntry(date: .now, budgets: [])
}
