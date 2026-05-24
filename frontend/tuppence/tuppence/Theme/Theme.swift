//
//  Theme.swift
//  tuppence
//

import SwiftUI

struct Theme {
    // MARK: - Colors

    struct Colors {
        // Light Mode
        static let lightBackground = Color(hex: "#D9CA94")  // Pale Lemon Yellow
        static let lightText = Color(hex: "#334E63")        // Dark Medici Blue
        static let lightHeading = Color(hex: "#CD1D05")     // Red Orange
        static let lightShadow = Color(hex: "#AC8546")      // Isabella Color

        // Dark Mode
        static let darkBackground = Color(hex: "#AC8546")   // Isabella Color
        static let darkText = Color(hex: "#D9CA94")         // Pale Lemon Yellow
        static let darkHeading = Color(hex: "#D9CA94")      // Pale Lemon Yellow (all texts switch in dark mode)
        static let darkShadow = Color(hex: "#334E63")       // Dark Medici Blue

        // Delete Color
        static let deleteRed = Color(hex: "#CD1D05")        // Red Orange
    }

    // MARK: - Fonts

    struct Fonts {
        // Heading font: Styrene (light, sans-serif)
        // Using SF Pro as fallback since custom fonts need to be embedded
        static func heading(size: CGFloat) -> Font {
            .system(size: size, weight: .light, design: .default)
        }

        // Small text font: Tiempos (serif)
        // Using New York (iOS system serif) as native alternative
        static func body(size: CGFloat) -> Font {
            .system(size: size, weight: .regular, design: .serif)
        }
    }

    // MARK: - Dynamic Colors

    static func backgroundColor(for colorScheme: ColorScheme) -> Color {
        colorScheme == .dark ? Colors.darkBackground : Colors.lightBackground
    }

    static func textColor(for colorScheme: ColorScheme) -> Color {
        colorScheme == .dark ? Colors.darkText : Colors.lightText
    }

    static func headingColor(for colorScheme: ColorScheme) -> Color {
        colorScheme == .dark ? Colors.darkHeading : Colors.lightHeading
    }

    static func shadowColor(for colorScheme: ColorScheme) -> Color {
        colorScheme == .dark ? Colors.darkShadow : Colors.lightShadow
    }

    // MARK: - Layout Constants

    struct Layout {
        static let topThird: CGFloat = 1.0 / 3.0
        static let screenPadding: CGFloat = 20
        static let emojiScale: CGFloat = 1.3
        static let shadowRadius: CGFloat = 3
        static let shadowX: CGFloat = 2
        static let shadowY: CGFloat = 2
    }
}

// MARK: - View Modifiers

struct ThemedBackground: ViewModifier {
    @Environment(\.colorScheme) var colorScheme

    func body(content: Content) -> some View {
        content
            .background(Theme.backgroundColor(for: colorScheme))
    }
}

struct ThemedText: ViewModifier {
    @Environment(\.colorScheme) var colorScheme
    let size: CGFloat

    func body(content: Content) -> some View {
        content
            .font(Theme.Fonts.body(size: size))
            .foregroundColor(Theme.textColor(for: colorScheme))
            .shadow(
                color: Theme.shadowColor(for: colorScheme).opacity(0.3),
                radius: Theme.Layout.shadowRadius,
                x: Theme.Layout.shadowX,
                y: Theme.Layout.shadowY
            )
    }
}

struct ThemedHeading: ViewModifier {
    @Environment(\.colorScheme) var colorScheme
    let size: CGFloat

    func body(content: Content) -> some View {
        content
            .font(Theme.Fonts.heading(size: size))
            .foregroundColor(Theme.headingColor(for: colorScheme))
            .shadow(
                color: Theme.shadowColor(for: colorScheme).opacity(0.3),
                radius: Theme.Layout.shadowRadius,
                x: Theme.Layout.shadowX,
                y: Theme.Layout.shadowY
            )
    }
}

extension View {
    func themedBackground() -> some View {
        modifier(ThemedBackground())
    }

    func themedText(size: CGFloat = 17) -> some View {
        modifier(ThemedText(size: size))
    }

    func themedHeading(size: CGFloat = 24) -> some View {
        modifier(ThemedHeading(size: size))
    }
}
