//
//  TuppenceWidget.swift
//  tuppence
//

import WidgetKit
import SwiftUI

struct TuppenceWidgetProvider: TimelineProvider {
    func placeholder(in context: Context) -> BudgetEntry {
        BudgetEntry(date: Date(), budgets: [])
    }

    func getSnapshot(in context: Context, completion: @escaping (BudgetEntry) -> Void) {
        Task {
            let budgets = await fetchBudgets()
            let entry = BudgetEntry(date: Date(), budgets: budgets)
            completion(entry)
        }
    }

    func getTimeline(in context: Context, completion: @escaping (Timeline<BudgetEntry>) -> Void) {
        Task {
            let budgets = await fetchBudgets()
            let entry = BudgetEntry(date: Date(), budgets: budgets)

            // Update every 15 minutes
            let nextUpdate = Calendar.current.date(byAdding: .minute, value: 15, to: Date())!
            let timeline = Timeline(entries: [entry], policy: .after(nextUpdate))

            completion(timeline)
        }
    }

    private func fetchBudgets() async -> [Budget] {
        do {
            let response = try await APIService.shared.getAmounts()
            return response.budgets
        } catch {
            print("Widget failed to fetch budgets: \(error)")
            return [] // Return empty array if fetch fails
        }
    }
}

struct BudgetEntry: TimelineEntry {
    let date: Date
    let budgets: [Budget]
}

struct TuppenceWidgetEntryView: View {
    var entry: BudgetEntry
    @Environment(\.colorScheme) var colorScheme

    var body: some View {
        VStack(alignment: .leading, spacing: 8) {
            if entry.budgets.isEmpty {
                Text("No budgets")
                    .themedText(size: 14)
                    .frame(maxWidth: .infinity, maxHeight: .infinity)
            } else {
                ForEach(entry.budgets.prefix(6)) { budget in
                    HStack(spacing: 8) {
                        Text(budget.emoji)
                            .font(.system(size: 18))

                        Text("\(AppSettings.shared.currencySymbol)\(budget.totalAmount ?? 0)")
                            .themedText(size: 14)
                            .frame(maxWidth: .infinity, alignment: .leading)
                    }
                }
            }
        }
        .padding()
        .themedBackground()
    }
}

struct TuppenceWidget: Widget {
    let kind: String = "TuppenceWidget"

    var body: some WidgetConfiguration {
        StaticConfiguration(kind: kind, provider: TuppenceWidgetProvider()) { entry in
            TuppenceWidgetEntryView(entry: entry)
        }
        .configurationDisplayName("Tuppence Budgets")
        .description("View your current budget amounts at a glance")
        .supportedFamilies([.systemSmall, .systemMedium])
    }
}

#Preview(as: .systemSmall) {
    TuppenceWidget()
} timeline: {
    var budget1 = Budget(emoji: "🛒", label: "Groceries", monthlyAmount: 500)
    budget1.totalAmount = 1200

    var budget2 = Budget(emoji: "✈️", label: "Travel", monthlyAmount: 1000)
    budget2.totalAmount = 500

    return BudgetEntry(date: .now, budgets: [budget1, budget2])
}
