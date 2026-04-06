//
//  AddExpenseButton.swift
//  tuppence
//

import SwiftUI

struct AddExpenseButton: View {
    @Binding var isShowingSheet: Bool
    @Environment(\.colorScheme) var colorScheme

    var body: some View {
        Button(action: {
            isShowingSheet = true
        }) {
            Image(systemName: "plus")
                .font(.system(size: 20, weight: .semibold))
                .foregroundColor(Theme.textColor(for: colorScheme))
                .frame(width: 44, height: 44)
                .background(liquidGlassBackground)
                .clipShape(Circle())
                .shadow(
                    color: Theme.shadowColor(for: colorScheme).opacity(0.3),
                    radius: 4,
                    x: 2,
                    y: 2
                )
        }
    }

    @ViewBuilder
    private var liquidGlassBackground: some View {
        if #available(iOS 18.0, *) {
            // iOS 18+ liquid glass effect
            Circle()
                .fill(.ultraThinMaterial)
                .overlay(
                    Circle()
                        .fill(
                            LinearGradient(
                                gradient: Gradient(colors: [
                                    Color.white.opacity(0.3),
                                    Color.white.opacity(0.1)
                                ]),
                                startPoint: .topLeading,
                                endPoint: .bottomTrailing
                            )
                        )
                )
        } else {
            // iOS 17 fallback - glass-ish transparency
            Circle()
                .fill(.ultraThinMaterial)
                .overlay(
                    Circle()
                        .fill(Color.white.opacity(0.15))
                )
        }
    }
}

struct FloatingAddButton: View {
    @Binding var isShowingSheet: Bool

    var body: some View {
        VStack {
            HStack {
                Spacer()
                AddExpenseButton(isShowingSheet: $isShowingSheet)
                    .padding(.trailing, 20)
                    .padding(.top, 12)
            }
            Spacer()
        }
    }
}
