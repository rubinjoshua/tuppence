//
//  AnalysisView.swift
//  tuppence
//

import SwiftUI
import Charts

// A splash/splat shape for the category color indicator
struct SplashShape: Shape {
    func path(in rect: CGRect) -> Path {
        var path = Path()
        let center = CGPoint(x: rect.midX, y: rect.midY)
        let radius = min(rect.width, rect.height) / 2

        // Create an irregular splat shape with varying radii
        let points = 12
        for i in 0..<points {
            let angle = (Double(i) / Double(points)) * 2 * .pi - .pi / 2
            // Alternate between larger and smaller radii for a splash effect
            let r: CGFloat
            if i % 3 == 0 {
                r = radius * 1.0
            } else if i % 3 == 1 {
                r = radius * 0.65
            } else {
                r = radius * 0.85
            }
            let point = CGPoint(
                x: center.x + r * cos(angle),
                y: center.y + r * sin(angle)
            )
            if i == 0 {
                path.move(to: point)
            } else {
                // Use quad curves for organic look
                let controlAngle = (Double(i) - 0.5) / Double(points) * 2 * .pi - .pi / 2
                let controlR = radius * 0.9
                let control = CGPoint(
                    x: center.x + controlR * cos(controlAngle),
                    y: center.y + controlR * sin(controlAngle)
                )
                path.addQuadCurve(to: point, control: control)
            }
        }
        path.closeSubpath()
        return path
    }
}

struct AnalysisView: View {
    let categories: [CategoryData]

    @State private var expandedCategories: Set<String> = []
    @Environment(\.colorScheme) var colorScheme

    var body: some View {
        GeometryReader { geometry in
            let topThirdY = geometry.size.height * Theme.Layout.topThird
            // Centre the pie chart on the top-third line, same as before. The
            // legend then sits below in a scroll region that fades into the
            // floating nav bar at the bottom and behind the pie at the top.
            let pieSize: CGFloat = 200
            let pieTop = max(16, topThirdY - pieSize / 2)

            if !categories.isEmpty {
                VStack(spacing: 0) {
                    Chart(categories) { category in
                        SectorMark(
                            angle: .value("Amount", abs(category.totalAmount)),
                            innerRadius: .ratio(0.5),
                            angularInset: 2
                        )
                        .foregroundStyle(category.color)
                    }
                    .frame(width: pieSize, height: pieSize)
                    .padding(.top, pieTop)
                    .padding(.bottom, 16)

                    ScrollView {
                        LazyVStack(alignment: .leading, spacing: 12) {
                            ForEach(categories) { category in
                                categoryRow(category: category)
                                if expandedCategories.contains(category.id) {
                                    categoryEntries(category)
                                        .transition(.opacity)
                                }
                            }
                            totalRow
                                .padding(.top, 4)
                        }
                        .padding(.horizontal, Theme.Layout.screenPadding)
                        .padding(.bottom, 220)  // Headroom so last row fades above the nav bar.
                    }
                    .fadingBottom(gradientHeight: 60, clearHeight: 130)
                }
                .frame(maxWidth: .infinity, maxHeight: .infinity, alignment: .top)
                .onDisappear {
                    expandedCategories.removeAll()
                }
            } else {
                Text("No spending data")
                    .themedText(size: 18)
                    .frame(maxWidth: .infinity)
                    .position(x: geometry.size.width / 2, y: topThirdY)
            }
        }
    }

    private var totalRow: some View {
        HStack(spacing: 12) {
            Text("Total")
                .themedText(size: 16)
                .frame(maxWidth: .infinity, alignment: .leading)
            Text("\(AppSettings.shared.currencySymbol)\(categories.reduce(0) { $0 + abs($1.totalAmount) })")
                .themedText(size: 16)
        }
        .padding(.leading, 32)
    }

    @ViewBuilder
    private func categoryRow(category: CategoryData) -> some View {
        Button(action: {
            withAnimation(.easeInOut(duration: 0.2)) {
                if expandedCategories.contains(category.id) {
                    expandedCategories.remove(category.id)
                } else {
                    expandedCategories.insert(category.id)
                }
            }
        }) {
            HStack(spacing: 12) {
                // Splash-type color indicator
                SplashShape()
                    .fill(category.color)
                    .frame(width: 20, height: 20)
                    .shadow(
                        color: Theme.shadowColor(for: colorScheme).opacity(0.3),
                        radius: Theme.Layout.shadowRadius,
                        x: Theme.Layout.shadowX,
                        y: Theme.Layout.shadowY
                    )

                Text(category.categoryName)
                    .themedText(size: 16)
                    .frame(maxWidth: .infinity, alignment: .leading)

                Text("\(AppSettings.shared.currencySymbol)\(abs(category.totalAmount))")
                    .themedText(size: 16)
            }
            .contentShape(Rectangle())
        }
        .buttonStyle(.plain)
    }

    @ViewBuilder
    private func categoryEntries(_ category: CategoryData) -> some View {
        let currencySymbol = AppSettings.shared.currencySymbol
        VStack(spacing: 8) {
            ForEach(category.entries) { entry in
                HStack(spacing: 10) {
                    Text(shortDate(entry.datetime))
                        .themedText(size: 13)
                        .opacity(0.6)
                        .frame(width: 44, alignment: .leading)
                    Text("\(currencySymbol)\(entry.amount)")
                        .themedText(size: 15)
                    Text(entry.description)
                        .themedText(size: 15)
                        .lineLimit(1)
                        .frame(maxWidth: .infinity, alignment: .leading)
                }
                .padding(.horizontal, 16)
            }
        }
        .padding(.vertical, 12)
        .background(
            RoundedRectangle(cornerRadius: 12)
                .fill(Color.white.opacity(0.06))
                .overlay(
                    RoundedRectangle(cornerRadius: 12)
                        .stroke(Color.white.opacity(0.10), lineWidth: 0.5)
                )
        )
        // No buttons or taps inside — let drags pass through to the ScrollView.
        .allowsHitTesting(false)
        .padding(.horizontal, 20)
        .padding(.bottom, 4)
    }

    private func shortDate(_ date: Date) -> String {
        let calendar = Calendar.current
        let m = calendar.component(.month, from: date)
        let d = calendar.component(.day, from: date)
        return "\(m)/\(d)"
    }
}
