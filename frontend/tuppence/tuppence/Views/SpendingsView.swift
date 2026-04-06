//
//  SpendingsView.swift
//  tuppence
//

import SwiftUI

struct SpendingsView: View {
    let entries: [LedgerEntry]
    let onDelete: (String) async -> Void
    let onRefresh: () async -> Void

    @State private var isRefreshing = false
    @Environment(\.colorScheme) var colorScheme

    // Group entries by date
    private var groupedEntries: [(date: Date, entries: [LedgerEntry])] {
        let calendar = Calendar.current
        let grouped = Dictionary(grouping: entries) { entry in
            calendar.startOfDay(for: entry.datetime)
        }
        return grouped.map { (date: $0.key, entries: $0.value) }
            .sorted { $0.date < $1.date }  // Oldest first
    }

    var body: some View {
        VStack(spacing: 0) {
            ScrollView {
                LazyVStack(spacing: 0) {
                    ForEach(groupedEntries, id: \.date) { group in
                        // Date heading
                        Text(formatDate(group.date))
                            .font(Theme.Fonts.body(size: 17))
                            .foregroundColor(Theme.shadowColor(for: colorScheme))
                            .opacity(0.6)
                            .frame(maxWidth: .infinity, alignment: .center)
                            .padding(.top, group.date == groupedEntries.first?.date ? 20 : 32)
                            .padding(.bottom, 12)

                        // Entries for this date (sorted oldest to newest)
                        ForEach(group.entries.sorted(by: { $0.datetime < $1.datetime })) { entry in
                            SpendingRow(
                                entry: entry,
                                onDelete: {
                                    Task {
                                        await onDelete(entry.uuid)
                                    }
                                }
                            )
                            .padding(.horizontal, Theme.Layout.screenPadding)
                            .padding(.vertical, 8)
                        }
                    }
                }
            }
            .refreshable {
                await onRefresh()
            }

            Spacer()
        }
        .padding(.top, 64)  // Increased to clear floating button (44pt button + 12pt top padding + 8pt margin)
    }

    // Format date as "6/3/2026" or "today"
    private func formatDate(_ date: Date) -> String {
        let calendar = Calendar.current
        if calendar.isDateInToday(date) {
            return "today"
        }

        let day = calendar.component(.day, from: date)
        let month = calendar.component(.month, from: date)
        let year = calendar.component(.year, from: date)

        return "\(day)/\(month)/\(year)"
    }
}

struct SpendingRow: View {
    let entry: LedgerEntry
    let onDelete: () -> Void

    @State private var offset: CGFloat = 0
    @State private var showingDeleteButton = false
    @GestureState private var isDragging = false
    @Environment(\.colorScheme) var colorScheme

    private let deleteThreshold: CGFloat = -80
    private let deleteButtonWidth: CGFloat = 60

    var body: some View {
        ZStack(alignment: .trailing) {
            // Delete button background
            if showingDeleteButton || offset < 0 {
                HStack {
                    Spacer()
                    Image(systemName: "trash.fill")
                        .foregroundColor(.white)
                        .frame(width: deleteButtonWidth)
                        .frame(maxHeight: .infinity)
                        .background(Theme.Colors.deleteRed)
                        .onTapGesture {
                            withAnimation {
                                offset = 0
                                showingDeleteButton = false
                            }
                            onDelete()
                        }
                }
            }

            // Content row
            HStack(spacing: 12) {
                Text(entry.budgetEmoji)
                    .font(.system(size: 20 * Theme.Layout.emojiScale))
                    .shadow(
                        color: Theme.shadowColor(for: colorScheme).opacity(0.3),
                        radius: Theme.Layout.shadowRadius,
                        x: Theme.Layout.shadowX,
                        y: Theme.Layout.shadowY
                    )

                Text(entry.descriptionText)
                    .themedText(size: 17)
                    .lineLimit(1)
                    .frame(maxWidth: .infinity, alignment: .leading)

                Text(formattedAmount)
                    .themedText(size: 17)
            }
            .padding(.vertical, 12)
            .background(Theme.backgroundColor(for: colorScheme))
            .offset(x: offset)
            .gesture(
                DragGesture()
                    .updating($isDragging) { _, state, _ in
                        state = true
                    }
                    .onChanged { value in
                        // Only allow left swipe
                        if value.translation.width < 0 {
                            offset = value.translation.width
                        }
                    }
                    .onEnded { value in
                        if value.translation.width < deleteThreshold {
                            // Full swipe - delete
                            withAnimation {
                                offset = -500
                            }
                            DispatchQueue.main.asyncAfter(deadline: .now() + 0.3) {
                                onDelete()
                            }
                        } else if value.translation.width < deleteThreshold / 2 {
                            // Partial swipe - show delete button
                            withAnimation(.spring()) {
                                offset = -deleteButtonWidth
                                showingDeleteButton = true
                            }
                        } else {
                            // Snap back
                            withAnimation(.spring()) {
                                offset = 0
                                showingDeleteButton = false
                            }
                        }
                    }
            )
        }
        .contentShape(Rectangle())
        .onTapGesture {
            // Tap anywhere to close delete button
            if showingDeleteButton {
                withAnimation(.spring()) {
                    offset = 0
                    showingDeleteButton = false
                }
            }
        }
    }

    private var formattedAmount: String {
        let currencySymbol = AppSettings.shared.currencySymbol
        let sign = entry.amount >= 0 ? "+" : "-"
        let absAmount = abs(entry.amount)
        return "\(sign)\(currencySymbol)\(absAmount)"
    }
}
