//
//  NavigationBar.swift
//  tuppence
//

import SwiftUI

enum Page: String, CaseIterable {
    case amount = "Amount"
    case analysis = "Analysis"
    case spendings = "Spendings"
}

enum AmountDisplay: String, CaseIterable {
    case total = "total"
    case percentage = "percentage of budgets"
}

struct NavigationBar: View {
    @Binding var currentPage: Page
    @Binding var amountDisplay: AmountDisplay
    @Binding var selectedBudgetIndex: Int
    @Binding var selectedMonthIndex: Int

    let budgets: [Budget]
    let months: [Date]

    @Environment(\.colorScheme) var colorScheme

    // The longest line when split is "Analysis of this month's"
    // We calculate a font size so that this longest line spans almost the full screen width
    private func headingFontSize(for screenWidth: CGFloat) -> CGFloat {
        // Measure the first line which is the longest: "Analysis of this month's"
        let longestLine = "Analysis of this month's"
        let padding: CGFloat = Theme.Layout.screenPadding * 2
        // Target 95% of available width - almost the full screen, just a bit shy
        let targetWidth = (screenWidth - padding) * 0.95

        // Use a temporary UIFont to measure the longest line
        // Start from an even larger size for maximum prominence
        var testSize: CGFloat = 150
        while testSize > 12 {
            let font = UIFont.systemFont(ofSize: testSize, weight: .light)
            let attributes: [NSAttributedString.Key: Any] = [.font: font]
            let size = (longestLine as NSString).size(withAttributes: attributes)
            if size.width <= targetWidth {
                return testSize
            }
            testSize -= 0.5
        }
        return testSize
    }

    var body: some View {
        GeometryReader { geometry in
            let fontSize = headingFontSize(for: geometry.size.width)
            let _ = print("🔤 Calculated fontSize: \(fontSize) for width: \(geometry.size.width)")

            VStack {
                Spacer()

                Group {
                    switch currentPage {
                    case .amount:
                        amountHeading(fontSize: fontSize)
                    case .analysis:
                        analysisHeading(fontSize: fontSize)
                    case .spendings:
                        spendingsHeading(fontSize: fontSize)
                    }
                }
                .frame(maxWidth: .infinity)
                .frame(height: 140) // Increased to accommodate larger font and 2 lines
                .animation(.easeInOut(duration: 0.3), value: currentPage)
                .padding(.bottom, 20)
                .padding(.horizontal, Theme.Layout.screenPadding)
            }
        }
    }

    // MARK: - Amount: "[Amount] in [total]"
    @ViewBuilder
    private func amountHeading(fontSize: CGFloat) -> some View {
        VStack(spacing: 4) {
            // Line 1: "Amount in"
            HStack(spacing: 0) {
                ScrollableText(
                    options: Page.allCases.map { $0.rawValue },
                    selectedIndex: Binding(
                        get: { Page.allCases.firstIndex(of: currentPage) ?? 0 },
                        set: { currentPage = Page.allCases[$0] }
                    ),
                    fontSize: fontSize
                )
                .fixedSize()

                Text(" in")
                    .font(Theme.Fonts.heading(size: fontSize))
                    .foregroundColor(Theme.headingColor(for: colorScheme))
                    .shadow(
                        color: Theme.shadowColor(for: colorScheme).opacity(0.3),
                        radius: Theme.Layout.shadowRadius,
                        x: Theme.Layout.shadowX,
                        y: Theme.Layout.shadowY
                    )
                    .fixedSize()
            }
            .frame(maxWidth: .infinity)

            // Line 2: "total" or "percentage of budgets"
            HStack(spacing: 0) {
                ScrollableText(
                    options: AmountDisplay.allCases.map { $0.rawValue },
                    selectedIndex: Binding(
                        get: { AmountDisplay.allCases.firstIndex(of: amountDisplay) ?? 0 },
                        set: { amountDisplay = AmountDisplay.allCases[$0] }
                    ),
                    fontSize: fontSize
                )
                .fixedSize()
            }
            .frame(maxWidth: .infinity)
        }
        .frame(maxWidth: .infinity)
    }

    // MARK: - Analysis: "[Analysis] of [this month]'s [emoji] spendings"
    @ViewBuilder
    private func analysisHeading(fontSize: CGFloat) -> some View {
        let monthNames = ["this month"] + months.dropLast().map { $0.monthName }

        VStack(spacing: 4) {
            // Line 1: "Analysis of this month's"
            HStack(spacing: 0) {
                ScrollableText(
                    options: Page.allCases.map { $0.rawValue },
                    selectedIndex: Binding(
                        get: { Page.allCases.firstIndex(of: currentPage) ?? 0 },
                        set: { currentPage = Page.allCases[$0] }
                    ),
                    fontSize: fontSize
                )
                .fixedSize()

                Text(" of ")
                    .font(Theme.Fonts.heading(size: fontSize))
                    .foregroundColor(Theme.headingColor(for: colorScheme))
                    .shadow(
                        color: Theme.shadowColor(for: colorScheme).opacity(0.3),
                        radius: Theme.Layout.shadowRadius,
                        x: Theme.Layout.shadowX,
                        y: Theme.Layout.shadowY
                    )
                    .fixedSize()

                ScrollableText(
                    options: monthNames,
                    selectedIndex: $selectedMonthIndex,
                    fontSize: fontSize
                )
                .fixedSize()

                Text("'s")
                    .font(Theme.Fonts.heading(size: fontSize))
                    .foregroundColor(Theme.headingColor(for: colorScheme))
                    .shadow(
                        color: Theme.shadowColor(for: colorScheme).opacity(0.3),
                        radius: Theme.Layout.shadowRadius,
                        x: Theme.Layout.shadowX,
                        y: Theme.Layout.shadowY
                    )
                    .fixedSize()
            }
            .frame(maxWidth: .infinity)

            // Line 2: "[emoji] spendings"
            HStack(spacing: 0) {
                ScrollableText(
                    options: budgets.map { $0.emoji },
                    selectedIndex: $selectedBudgetIndex,
                    fontSize: fontSize
                )
                .fixedSize()

                Text(" spendings")
                    .font(Theme.Fonts.heading(size: fontSize))
                    .foregroundColor(Theme.headingColor(for: colorScheme))
                    .shadow(
                        color: Theme.shadowColor(for: colorScheme).opacity(0.3),
                        radius: Theme.Layout.shadowRadius,
                        x: Theme.Layout.shadowX,
                        y: Theme.Layout.shadowY
                    )
                    .fixedSize()
            }
            .frame(maxWidth: .infinity)
        }
        .frame(maxWidth: .infinity)
    }

    // MARK: - Spendings: "[Spendings] made [this month]"
    @ViewBuilder
    private func spendingsHeading(fontSize: CGFloat) -> some View {
        let monthNames = ["this month"] + months.dropLast().map { $0.monthName }

        VStack(spacing: 4) {
            // Line 1: "Spendings made"
            HStack(spacing: 0) {
                ScrollableText(
                    options: Page.allCases.map { $0.rawValue },
                    selectedIndex: Binding(
                        get: { Page.allCases.firstIndex(of: currentPage) ?? 0 },
                        set: { currentPage = Page.allCases[$0] }
                    ),
                    fontSize: fontSize
                )
                .fixedSize()

                Text(" made")
                    .font(Theme.Fonts.heading(size: fontSize))
                    .foregroundColor(Theme.headingColor(for: colorScheme))
                    .shadow(
                        color: Theme.shadowColor(for: colorScheme).opacity(0.3),
                        radius: Theme.Layout.shadowRadius,
                        x: Theme.Layout.shadowX,
                        y: Theme.Layout.shadowY
                    )
                    .fixedSize()
            }
            .frame(maxWidth: .infinity)

            // Line 2: "this month"
            HStack(spacing: 0) {
                ScrollableText(
                    options: monthNames,
                    selectedIndex: $selectedMonthIndex,
                    fontSize: fontSize
                )
                .fixedSize()
            }
            .frame(maxWidth: .infinity)
        }
        .frame(maxWidth: .infinity)
    }
}
