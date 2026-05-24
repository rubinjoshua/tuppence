//
//  CategoryData.swift
//  tuppence
//

import Foundation
import SwiftUI

struct CategoryData: Codable, Identifiable {
    let categoryName: String
    let hexColor: String
    let texts: [String]
    let totalAmount: Int

    var id: String { categoryName }

    var color: Color {
        Color(hex: hexColor)
    }

    enum CodingKeys: String, CodingKey {
        case categoryName = "category_name"
        case hexColor = "hex_color"
        case texts
        case totalAmount = "total_amount"
    }
}

struct CategoryMapResponse: Codable {
    let categories: [CategoryData]
}

extension Color {
    init(hex: String) {
        let hex = hex.trimmingCharacters(in: CharacterSet.alphanumerics.inverted)
        var int: UInt64 = 0
        Scanner(string: hex).scanHexInt64(&int)
        let a, r, g, b: UInt64
        switch hex.count {
        case 3:
            (a, r, g, b) = (255, (int >> 8) * 17, (int >> 4 & 0xF) * 17, (int & 0xF) * 17)
        case 6:
            (a, r, g, b) = (255, int >> 16, int >> 8 & 0xFF, int & 0xFF)
        case 8:
            (a, r, g, b) = (int >> 24, int >> 16 & 0xFF, int >> 8 & 0xFF, int & 0xFF)
        default:
            (a, r, g, b) = (255, 0, 0, 0)
        }

        self.init(
            .sRGB,
            red: Double(r) / 255,
            green: Double(g) / 255,
            blue:  Double(b) / 255,
            opacity: Double(a) / 255
        )
    }
}
