//
//  SpendingsView.swift
//  tuppence
//

import SwiftUI

struct SpendingsView: View {
    let entries: [LedgerEntry]
    let budgets: [Budget]
    let onDelete: (String) async -> Void
    let onEdit: (LedgerEntry) -> Void
    let onRefresh: () async -> Void

    @State private var expandedDates: Set<Date> = []
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
        ScrollView {
            LazyVStack(spacing: 0) {
                ForEach(groupedEntries, id: \.date) { group in
                    dayGroup(group: group)
                }
            }
            .padding(.bottom, 260)  // Headroom so last row can scroll above the fade region.
        }
        // Anchor the initial scroll position at the bottom (today) every time
        // the view is recreated. Using `defaultScrollAnchor` instead of a manual
        // `ScrollViewReader.scrollTo` in `.onAppear` avoids the race where the
        // LazyVStack hasn't laid out its child IDs yet and the scroll silently
        // no-ops.
        .defaultScrollAnchor(.bottom)
        .refreshable {
            await onRefresh()
        }
        .padding(.top, 64)  // Clear floating add button.
        .fadingBottom()
        .onDisappear {
            // Collapse everything when leaving the page so re-entry starts clean.
            expandedDates.removeAll()
        }
    }

    @ViewBuilder
    private func dayGroup(group: (date: Date, entries: [LedgerEntry])) -> some View {
        let isFirst = group.date == groupedEntries.first?.date
        let topPadding: CGFloat = isFirst ? 20 : 32

        // Date heading — tappable to expand/collapse that day's spending
        // summary. Appearance is unchanged so the affordance is
        // "hidden in plain sight".
        Text(formatDate(group.date))
            .font(Theme.Fonts.body(size: 17))
            .foregroundColor(Theme.shadowColor(for: colorScheme))
            .opacity(0.6)
            .frame(maxWidth: .infinity, alignment: .center)
            .padding(.top, topPadding)
            .padding(.bottom, 12)
            .contentShape(Rectangle())
            .onTapGesture {
                withAnimation(.easeInOut(duration: 0.2)) {
                    if expandedDates.contains(group.date) {
                        expandedDates.remove(group.date)
                    } else {
                        expandedDates.insert(group.date)
                    }
                }
            }

        if expandedDates.contains(group.date) {
            dailySummary(for: group.date)
                .transition(.opacity)
        }

        ForEach(group.entries.sorted(by: { $0.datetime < $1.datetime })) { entry in
            SpendingRow(
                entry: entry,
                onEdit: {
                    onEdit(entry)
                },
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

    // Spending is derived directly from the ledger. Income and monthly
    // budget additions are positive entries, so they don't count as spent.
    private func spendingTotals(on date: Date) -> [(emoji: String, amount: Int)] {
        let calendar = Calendar.current
        var totals: [String: Int] = budgets.reduce(into: [:]) { result, budget in
            result[budget.emoji] = 0
        }
        for entry in entries where entry.amount < 0 && calendar.isDate(entry.datetime, inSameDayAs: date) {
            totals[entry.budgetEmoji, default: 0] += abs(entry.amount)
        }
        return budgets.map { (emoji: $0.emoji, amount: totals[$0.emoji] ?? 0) }
    }

    @ViewBuilder
    private func dailySummary(for date: Date) -> some View {
        let currencySymbol = AppSettings.shared.currencySymbol
        VStack(alignment: .leading, spacing: 8) {
            Text("Spent on this day")
                .themedText(size: 12)
                .opacity(0.6)
                .padding(.horizontal, 16)

            VStack(spacing: 10) {
                ForEach(spendingTotals(on: date), id: \.emoji) { row in
                    HStack(spacing: 12) {
                        Text(row.emoji)
                            .font(.system(size: 18 * Theme.Layout.emojiScale))
                        Text("\(currencySymbol)\(row.amount)")
                            .themedText(size: 18)
                        Spacer()
                    }
                    .padding(.horizontal, 16)
                }
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
        // The fold-down has no taps, edits, or buttons — turning hit testing
        // off lets vertical drags reach the ScrollView so the user can swipe
        // over the summary to scroll the list (matching the rest of the page).
        .allowsHitTesting(false)
        // Slightly narrower than the main list of spendings.
        .padding(.horizontal, Theme.Layout.screenPadding + 20)
        .padding(.bottom, 8)
    }
}

struct SpendingRow: View {
    let entry: LedgerEntry
    let onEdit: () -> Void
    let onDelete: () -> Void

    @State private var offset: CGFloat = 0
    @State private var revealedAction: RevealedAction?
    @Environment(\.colorScheme) var colorScheme

    private enum RevealedAction: Equatable {
        case edit
        case delete
    }

    private let buttonWidth: CGFloat = 60
    private let revealThreshold: CGFloat = 30

    var body: some View {
        ZStack {
            if revealedAction == .edit || offset > 0 {
                HStack {
                    Image(systemName: "pencil")
                        .foregroundColor(.white)
                        .frame(width: buttonWidth)
                        .frame(maxHeight: .infinity)
                        .background(Color.accentColor)
                        .onTapGesture {
                            closeAction()
                            onEdit()
                        }
                    Spacer()
                }
            }

            if revealedAction == .delete || offset < 0 {
                HStack {
                    Spacer()
                    Image(systemName: "trash.fill")
                        .foregroundColor(.white)
                        .frame(width: buttonWidth)
                        .frame(maxHeight: .infinity)
                        .background(Theme.Colors.deleteRed)
                        .onTapGesture {
                            closeAction()
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

                Text(entry.descriptionText ?? "")
                    .themedText(size: 17)
                    .lineLimit(1)
                    .frame(maxWidth: .infinity, alignment: .leading)

                if entry.isPending {
                    // Small arrow-up-cloud while we wait for the upload.
                    Image(systemName: "arrow.up.to.line")
                        .font(.system(size: 12, weight: .semibold))
                        .foregroundColor(Theme.textColor(for: colorScheme).opacity(0.5))
                }

                Text(formattedAmount)
                    .themedText(size: 17)
                    .opacity(entry.isPending ? 0.7 : 1.0)
            }
            .padding(.vertical, 12)
            .background(Theme.backgroundColor(for: colorScheme))
            .offset(x: offset)
            // minimumDistance > the ScrollView's pan threshold so vertical
            // drags scroll the list; only deliberate horizontal swipes
            // activate this gesture.
            .gesture(
                DragGesture(minimumDistance: 20)
                    .onChanged { value in
                        guard abs(value.translation.width) > abs(value.translation.height) else { return }
                        offset = min(max(value.translation.width, -buttonWidth * 1.5), buttonWidth * 1.5)
                    }
                    .onEnded { value in
                        if value.translation.width > revealThreshold {
                            reveal(.edit)
                        } else if value.translation.width < -revealThreshold {
                            reveal(.delete)
                        } else {
                            closeAction()
                        }
                    }
            )
        }
        .contentShape(Rectangle())
        .onTapGesture {
            if revealedAction != nil {
                closeAction()
            }
        }
    }

    private func reveal(_ action: RevealedAction) {
        withAnimation(.spring()) {
            revealedAction = action
            offset = action == .edit ? buttonWidth : -buttonWidth
        }
    }

    private func closeAction() {
        withAnimation(.spring()) {
            offset = 0
            revealedAction = nil
        }
    }

    private var formattedAmount: String {
        let currencySymbol = AppSettings.shared.currencySymbol
        let sign = entry.amount >= 0 ? "+" : "-"
        let absAmount = abs(entry.amount)
        return "\(sign)\(currencySymbol)\(absAmount)"
    }
}
