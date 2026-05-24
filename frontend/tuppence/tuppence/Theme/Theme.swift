//
//  Theme.swift
//  tuppence
//

import SwiftUI

struct Theme {
    // MARK: - Colors

    struct Colors {
        // Light Mode (unchanged — Wes Anderson palette)
        static let lightBackground = Color(hex: "#D9CA94")  // Pale Lemon Yellow
        static let lightText = Color(hex: "#334E63")        // Dark Medici Blue
        static let lightHeading = Color(hex: "#CD1D05")     // Red Orange
        static let lightShadow = Color(hex: "#AC8546")      // Isabella Color
        static let lightDeleteRed = Color(hex: "#CD1D05")   // Red Orange

        // Dark Mode — pure-black OLED background with shifted palette.
        // See frontend/DARK_MODE_PALETTE.md for rationale.
        static let darkBackground = Color.black                  // #000000 — true OLED black
        static let darkText = Color(hex: "#E8DCB0")              // Pale lemon, lifted for AA contrast
        static let darkHeading = Color(hex: "#FF7A5E")           // Red-orange lifted + desaturated for retina comfort
        static let darkShadow = Color.white.opacity(0.08)        // Subtle white-glow elevation (drop shadows are invisible on pure black)
        static let darkDeleteRed = Color(hex: "#FF6B5C")         // Delete red lifted for higher contrast on black

        // Legacy accessor — prefer deleteRedColor(for:) below.
        static let deleteRed = Color(hex: "#CD1D05")
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

    static func deleteRedColor(for colorScheme: ColorScheme) -> Color {
        colorScheme == .dark ? Colors.darkDeleteRed : Colors.lightDeleteRed
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
        let shadowOpacity: Double = colorScheme == .dark ? 1.0 : 0.3
        return content
            .font(Theme.Fonts.body(size: size))
            .foregroundColor(Theme.textColor(for: colorScheme))
            .shadow(
                color: Theme.shadowColor(for: colorScheme).opacity(shadowOpacity),
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
        let shadowOpacity: Double = colorScheme == .dark ? 1.0 : 0.3
        return content
            .font(Theme.Fonts.heading(size: size))
            .foregroundColor(Theme.headingColor(for: colorScheme))
            .shadow(
                color: Theme.shadowColor(for: colorScheme).opacity(shadowOpacity),
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
