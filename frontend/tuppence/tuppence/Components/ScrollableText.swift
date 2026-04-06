//
//  ScrollableText.swift
//  tuppence
//

import SwiftUI

struct ScrollableText: View {
    let options: [String]
    @Binding var selectedIndex: Int
    let fontSize: CGFloat

    @State private var dragOffset: CGFloat = 0
    @Environment(\.colorScheme) var colorScheme

    private var safeIndex: Int {
        guard !options.isEmpty else { return 0 }
        return min(max(selectedIndex, 0), options.count - 1)
    }

    var body: some View {
        if options.isEmpty {
            EmptyView()
        } else {
        ZStack {
            // The currently selected text (always visible)
            Text(options[safeIndex])
                .font(Theme.Fonts.heading(size: fontSize))
                .foregroundColor(Theme.headingColor(for: colorScheme))
                .shadow(
                    color: Theme.shadowColor(for: colorScheme).opacity(0.3),
                    radius: Theme.Layout.shadowRadius,
                    x: Theme.Layout.shadowX,
                    y: Theme.Layout.shadowY
                )
                .opacity(1.0 - min(abs(dragOffset) / 60, 1.0))
                .offset(y: dragOffset * 0.5)

            // Previous option (only visible during drag)
            if safeIndex > 0 && dragOffset > 0 {
                Text(options[safeIndex - 1])
                    .font(Theme.Fonts.heading(size: fontSize))
                    .foregroundColor(Theme.headingColor(for: colorScheme))
                    .shadow(
                        color: Theme.shadowColor(for: colorScheme).opacity(0.3),
                        radius: Theme.Layout.shadowRadius,
                        x: Theme.Layout.shadowX,
                        y: Theme.Layout.shadowY
                    )
                    .opacity(min(abs(dragOffset) / 60, 1.0))
                    .offset(y: -30 + dragOffset * 0.5)
            }

            // Next option (only visible during drag)
            if safeIndex < options.count - 1 && dragOffset < 0 {
                Text(options[safeIndex + 1])
                    .font(Theme.Fonts.heading(size: fontSize))
                    .foregroundColor(Theme.headingColor(for: colorScheme))
                    .shadow(
                        color: Theme.shadowColor(for: colorScheme).opacity(0.3),
                        radius: Theme.Layout.shadowRadius,
                        x: Theme.Layout.shadowX,
                        y: Theme.Layout.shadowY
                    )
                    .opacity(min(abs(dragOffset) / 60, 1.0))
                    .offset(y: 30 + dragOffset * 0.5)
            }
        }
        .contentShape(Rectangle())
        .gesture(
            DragGesture(minimumDistance: 10)
                .onChanged { value in
                    // Only allow vertical drag
                    dragOffset = value.translation.height
                }
                .onEnded { value in
                    let threshold: CGFloat = 30
                    withAnimation(.spring(response: 0.3, dampingFraction: 0.7)) {
                        if value.translation.height < -threshold && selectedIndex < options.count - 1 {
                            selectedIndex += 1
                        } else if value.translation.height > threshold && selectedIndex > 0 {
                            selectedIndex -= 1
                        }
                        dragOffset = 0
                    }
                }
        )
        .animation(.spring(response: 0.3, dampingFraction: 0.7), value: dragOffset)
        }
    }
}
