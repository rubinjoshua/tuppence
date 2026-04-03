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

    // The longest possible heading is "Analysis of this month's [emoji] spendings"
    // We calculate a font size so that this fills the screen width
    private func headingFontSize(for screenWidth: CGFloat) -> CGFloat {
        let longestHeading = "Analysis of this month's \u{1F4B0} spendings"
        let padding: CGFloat = Theme.Layout.screenPadding * 2
        let availableWidth = screenWidth - padding

        // Use a temporary UIFont to measure the longest heading
        // Styrene-like = system light sans-serif
        var testSize: CGFloat = 30
        while testSize > 8 {
            let font = UIFont.systemFont(ofSize: testSize, weight: .light)
            let attributes: [NSAttributedString.Key: Any] = [.font: font]
            let size = (longestHeading as NSString).size(withAttributes: attributes)
            if size.width <= availableWidth {
                return testSize
            }
            testSize -= 0.5
        }
        return testSize
    }

    var body: some View {
        GeometryReader { geometry in
            let fontSize = headingFontSize(for: geometry.size.width)

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
                .frame(height: 60)
                .animation(.easeInOut(duration: 0.3), value: currentPage)
                .padding(.bottom, 20)
                .padding(.horizontal, Theme.Layout.screenPadding)
            }
        }
    }

    // MARK: - Amount: "[Amount] in [total]"
    @ViewBuilder
    private func amountHeading(fontSize: CGFloat) -> some View {
        HStack(spacing: 0) {
            Spacer()

            ScrollableText(
                options: Page.allCases.map { $0.rawValue },
                selectedIndex: Binding(
                    get: { Page.allCases.firstIndex(of: currentPage) ?? 0 },
                    set: { currentPage = Page.allCases[$0] }
                ),
                fontSize: fontSize
            )
            .fixedSize()

            Text(" in ")
                .font(Theme.Fonts.heading(size: fontSize))
                .foregroundColor(Theme.headingColor(for: colorScheme))
                .shadow(
                    color: Theme.shadowColor(for: colorScheme).opacity(0.3),
                    radius: Theme.Layout.shadowRadius,
                    x: Theme.Layout.shadowX,
                    y: Theme.Layout.shadowY
                )

            ScrollableText(
                options: AmountDisplay.allCases.map { $0.rawValue },
                selectedIndex: Binding(
                    get: { AmountDisplay.allCases.firstIndex(of: amountDisplay) ?? 0 },
                    set: { amountDisplay = AmountDisplay.allCases[$0] }
                ),
                fontSize: fontSize
            )
            .fixedSize()

            Spacer()
        }
    }

    // MARK: - Analysis: "[Analysis] of [this month]'s [emoji] spendings"
    @ViewBuilder
    private func analysisHeading(fontSize: CGFloat) -> some View {
        let monthNames = ["this month"] + months.dropLast().map { $0.monthName }

        HStack(spacing: 0) {
            Spacer()

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

            ScrollableText(
                options: monthNames,
                selectedIndex: $selectedMonthIndex,
                fontSize: fontSize
            )
            .fixedSize()

            Text("'s ")
                .font(Theme.Fonts.heading(size: fontSize))
                .foregroundColor(Theme.headingColor(for: colorScheme))
                .shadow(
                    color: Theme.shadowColor(for: colorScheme).opacity(0.3),
                    radius: Theme.Layout.shadowRadius,
                    x: Theme.Layout.shadowX,
                    y: Theme.Layout.shadowY
                )

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

            Spacer()
        }
    }

    // MARK: - Spendings: "[Spendings] made [this month]"
    @ViewBuilder
    private func spendingsHeading(fontSize: CGFloat) -> some View {
        let monthNames = ["this month"] + months.dropLast().map { $0.monthName }

        HStack(spacing: 0) {
            Spacer()

            ScrollableText(
                options: Page.allCases.map { $0.rawValue },
                selectedIndex: Binding(
                    get: { Page.allCases.firstIndex(of: currentPage) ?? 0 },
                    set: { currentPage = Page.allCases[$0] }
                ),
                fontSize: fontSize
            )
            .fixedSize()

            Text(" made ")
                .font(Theme.Fonts.heading(size: fontSize))
                .foregroundColor(Theme.headingColor(for: colorScheme))
                .shadow(
                    color: Theme.shadowColor(for: colorScheme).opacity(0.3),
                    radius: Theme.Layout.shadowRadius,
                    x: Theme.Layout.shadowX,
                    y: Theme.Layout.shadowY
                )

            ScrollableText(
                options: monthNames,
                selectedIndex: $selectedMonthIndex,
                fontSize: fontSize
            )
            .fixedSize()

            Spacer()
        }
    }
}
