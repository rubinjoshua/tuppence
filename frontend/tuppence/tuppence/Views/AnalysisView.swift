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

    @Environment(\.colorScheme) var colorScheme

    var body: some View {
        GeometryReader { geometry in
            let topThirdY = geometry.size.height * Theme.Layout.topThird

            if !categories.isEmpty {
                // Measure the total content and center it on the top-third line
                VStack(spacing: 16) {
                    // Pie Chart
                    Chart(categories) { category in
                        SectorMark(
                            angle: .value("Amount", abs(category.totalAmount)),
                            innerRadius: .ratio(0.5),
                            angularInset: 2
                        )
                        .foregroundStyle(category.color)
                    }
                    .frame(width: 200, height: 200)

                    // Category Legend
                    VStack(alignment: .leading, spacing: 12) {
                        ForEach(categories) { category in
                            categoryRow(category: category)
                        }
                    }
                }
                .frame(maxWidth: .infinity)
                .padding(.horizontal, Theme.Layout.screenPadding)
                .position(x: geometry.size.width / 2, y: topThirdY)
            } else {
                Text("No spending data")
                    .themedText(size: 18)
                    .frame(maxWidth: .infinity)
                    .position(x: geometry.size.width / 2, y: topThirdY)
            }
        }
    }

    @ViewBuilder
    private func categoryRow(category: CategoryData) -> some View {
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
    }
}
