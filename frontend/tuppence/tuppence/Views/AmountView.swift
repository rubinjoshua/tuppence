//
//  AmountView.swift
//  tuppence
//

import SwiftUI

struct AmountView: View {
    let budgets: [Budget]
    let displayMode: AmountDisplay

    @Environment(\.colorScheme) var colorScheme

    var body: some View {
        GeometryReader { geometry in
            let contentHeight = CGFloat(budgets.count) * 56 // approximate row height + spacing
            let topThirdY = geometry.size.height * Theme.Layout.topThird
            let topOffset = max(16, topThirdY - contentHeight / 2)

            VStack(spacing: 16) {
                ForEach(budgets) { budget in
                    budgetRow(budget: budget)
                }
            }
            .frame(maxWidth: .infinity)
            .padding(.horizontal, Theme.Layout.screenPadding)
            .offset(y: topOffset)
        }
    }

    @ViewBuilder
    private func budgetRow(budget: Budget) -> some View {
        HStack(spacing: 12) {
            Text(budget.emoji)
                .font(.system(size: 28 * Theme.Layout.emojiScale))
                .shadow(
                    color: Theme.shadowColor(for: colorScheme).opacity(0.3),
                    radius: Theme.Layout.shadowRadius,
                    x: Theme.Layout.shadowX,
                    y: Theme.Layout.shadowY
                )

            Text(formattedAmount(for: budget))
                .font(Theme.Fonts.body(size: 28))
                .foregroundColor(Theme.textColor(for: colorScheme))
                .shadow(
                    color: Theme.shadowColor(for: colorScheme).opacity(0.3),
                    radius: Theme.Layout.shadowRadius,
                    x: Theme.Layout.shadowX,
                    y: Theme.Layout.shadowY
                )
        }
    }

    private func formattedAmount(for budget: Budget) -> String {
        let currencySymbol = AppSettings.shared.currencySymbol
        let totalAmount = budget.totalAmount ?? 0

        switch displayMode {
        case .total:
            return "\(currencySymbol)\(totalAmount)"
        case .percentage:
            if budget.monthlyAmount > 0 {
                let percentage = Int((Double(totalAmount) / Double(budget.monthlyAmount)) * 100)
                return "\(percentage)%"
            }
            return "0%"
        }
    }
}
