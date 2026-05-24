//
//  DateFormatter+Extensions.swift
//  tuppence
//

import Foundation

extension DateFormatter {
    static let monthYear: DateFormatter = {
        let formatter = DateFormatter()
        formatter.dateFormat = "yyyy-MM"
        return formatter
    }()

    static let monthName: DateFormatter = {
        let formatter = DateFormatter()
        formatter.dateFormat = "MMMM"
        return formatter
    }()

    static let ledgerDisplay: DateFormatter = {
        let formatter = DateFormatter()
        formatter.dateStyle = .medium
        formatter.timeStyle = .short
        return formatter
    }()
}

extension Date {
    var monthYearString: String {
        DateFormatter.monthYear.string(from: self)
    }

    var monthName: String {
        DateFormatter.monthName.string(from: self)
    }

    static func monthsInCurrentYear() -> [Date] {
        let calendar = Calendar.current
        let currentYear = calendar.component(.year, from: Date())
        let currentMonth = calendar.component(.month, from: Date())

        return (1...currentMonth).compactMap { month in
            var components = DateComponents()
            components.year = currentYear
            components.month = month
            components.day = 1
            return calendar.date(from: components)
        }
    }
}
