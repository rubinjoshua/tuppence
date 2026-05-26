//
//  AddExpenseSheet.swift
//  tuppence
//

import SwiftUI

struct AddExpenseSheet: View {
    @Binding var isPresented: Bool
    let budgets: [Budget]
    let onAddExpense: (Int, String, String) async -> Void

    @State private var selectedEmoji: String = ""
    @State private var hasPickedBudget: Bool = false
    @State private var description: String = ""
    @State private var isPositive: Bool = false  // Default to - (expense)
    @State private var amountText: String = ""
    @State private var isShowingEmojiPicker = false
    @State private var isShowingSignPicker = false
    @FocusState private var focusedField: Field?

    @Environment(\.colorScheme) var colorScheme
    @ObservedObject private var settings = AppSettings.shared

    private enum Field {
        case description
        case amount
    }

    init(isPresented: Binding<Bool>, budgets: [Budget], onAddExpense: @escaping (Int, String, String) async -> Void) {
        self._isPresented = isPresented
        self.budgets = budgets
        self.onAddExpense = onAddExpense
    }

    var body: some View {
        ZStack {
            // Dimmed background with tap-to-dismiss
            Color.black.opacity(0.3)
                .ignoresSafeArea()
                .onTapGesture(perform: handleBackgroundTap)

            VStack(spacing: 0) {
                if hasPickedBudget {
                    expenseEntryRow
                        .padding(.horizontal, 16)
                        .padding(.vertical, 16)
                        .background(liquidGlassBackground)
                        .clipShape(RoundedRectangle(cornerRadius: 16))
                        .shadow(
                            color: Theme.shadowColor(for: colorScheme).opacity(0.3),
                            radius: 8,
                            x: 0,
                            y: 4
                        )
                        .padding(.horizontal, 40)
                } else {
                    inlineBudgetPicker
                        .padding(.horizontal, 20)
                }
            }
            .frame(maxHeight: .infinity, alignment: .center)

            // Re-select emoji from entry row
            if isShowingEmojiPicker {
                emojiPickerOverlay
            }

            // Sign picker
            if isShowingSignPicker {
                signPickerOverlay
            }
        }
        .onAppear {
            // Reset to defaults when appearing — user picks budget first.
            selectedEmoji = ""
            hasPickedBudget = false
            description = ""
            isPositive = false  // Default to - (expense)
            amountText = ""
        }
    }

    // MARK: - Inline Budget Picker (initial state)

    private var inlineBudgetPicker: some View {
        VStack(spacing: 0) {
            Text("Pick a budget")
                .themedText(size: 15)
                .opacity(0.7)
                .frame(maxWidth: .infinity, alignment: .leading)
                .padding(.horizontal, 16)
                .padding(.top, 16)
                .padding(.bottom, 8)

            VStack(spacing: 6) {
                ForEach(budgets) { budget in
                    Button(action: {
                        selectedEmoji = budget.emoji
                        hasPickedBudget = true
                        // Move focus to the description field so the user can type immediately.
                        DispatchQueue.main.asyncAfter(deadline: .now() + 0.05) {
                            focusedField = .description
                        }
                    }) {
                        HStack(spacing: 12) {
                            Text(budget.emoji)
                                .font(.system(size: 22 * Theme.Layout.emojiScale))
                            Text(budget.label)
                                .themedText(size: 17)
                            Spacer()
                        }
                        .padding(.horizontal, 16)
                        .padding(.vertical, 10)
                        .background(Color.white.opacity(0.001))  // Hit-test fill
                        .contentShape(Rectangle())
                    }
                }
            }
            .padding(.bottom, 12)
        }
        .background(liquidGlassBackground)
        .clipShape(RoundedRectangle(cornerRadius: 16))
        .shadow(
            color: Theme.shadowColor(for: colorScheme).opacity(0.3),
            radius: 8,
            x: 0,
            y: 4
        )
    }

    // MARK: - Main Expense Entry Row

    private var expenseEntryRow: some View {
        HStack(spacing: 8) {
            // Emoji
            Button(action: {
                focusedField = nil
                // Delay to avoid lag when dismissing keyboard
                DispatchQueue.main.asyncAfter(deadline: .now() + 0.1) {
                    isShowingEmojiPicker.toggle()
                    isShowingSignPicker = false
                }
            }) {
                Text(selectedEmoji)
                    .font(.system(size: 20 * Theme.Layout.emojiScale))
                    .shadow(
                        color: Theme.shadowColor(for: colorScheme).opacity(0.3),
                        radius: Theme.Layout.shadowRadius,
                        x: Theme.Layout.shadowX,
                        y: Theme.Layout.shadowY
                    )
            }

            // Description (2 lines, optimized for no lag)
            TextField("description", text: $description, axis: .vertical)
                .font(Theme.Fonts.body(size: 17))
                .foregroundColor(Theme.textColor(for: colorScheme))
                .focused($focusedField, equals: .description)
                .frame(maxWidth: .infinity, alignment: .leading)
                .lineLimit(2)
                .onSubmit {
                    focusedField = nil
                }

            // +/- toggle
            Button(action: {
                focusedField = nil
                // Delay to avoid lag when dismissing keyboard
                DispatchQueue.main.asyncAfter(deadline: .now() + 0.1) {
                    isShowingSignPicker.toggle()
                    isShowingEmojiPicker = false
                }
            }) {
                Text(isPositive ? "+" : "-")
                    .themedText(size: 17)
                    .frame(minWidth: 20)
            }

            // Currency symbol and amount (tighter spacing)
            HStack(spacing: 2) {
                Text(settings.currencySymbol)
                    .themedText(size: 17)

                TextField("0", text: $amountText)
                    .font(Theme.Fonts.body(size: 17))
                    .foregroundColor(Theme.textColor(for: colorScheme))
                    .keyboardType(.numberPad)
                    .multilineTextAlignment(.trailing)
                    .focused($focusedField, equals: .amount)
                    .frame(width: 60, alignment: .trailing)
                    .onChange(of: amountText) { _, newValue in
                        // Only allow digits
                        amountText = newValue.filter { $0.isNumber }
                    }
            }

            // Confirm button — glass, not red. The red caret was misleading
            // (looked like a "delete" affordance). Liquid Glass on iOS 26;
            // translucent material on iOS 18.
            Button(action: handleAddExpense) {
                Image(systemName: "plus")
                    .font(.system(size: 18, weight: .semibold))
                    .foregroundColor(Theme.textColor(for: colorScheme))
                    .frame(width: 32, height: 32)
                    .background(confirmButtonBackground)
                    .clipShape(Circle())
            }
        }
    }

    // MARK: - Pickers

    private var emojiPickerOverlay: some View {
        VStack(spacing: 0) {
            ScrollView {
                VStack(spacing: 8) {
                    ForEach(budgets) { budget in
                        Button(action: {
                            selectedEmoji = budget.emoji
                            isShowingEmojiPicker = false
                        }) {
                            HStack {
                                Text(budget.emoji)
                                    .font(.system(size: 20 * Theme.Layout.emojiScale))
                                Text(budget.label)
                                    .themedText(size: 17)
                                Spacer()
                            }
                            .padding(.horizontal, 16)
                            .padding(.vertical, 12)
                            .background(selectedEmoji == budget.emoji ? Color.white.opacity(0.2) : Color.clear)
                            .cornerRadius(8)
                        }
                    }
                }
                .padding(.vertical, 8)
            }
            .frame(maxHeight: 200)
            .padding(.horizontal, 20)
            .background(liquidGlassBackground)
            .clipShape(RoundedRectangle(cornerRadius: 16))
            .shadow(
                color: Theme.shadowColor(for: colorScheme).opacity(0.3),
                radius: 8,
                x: 0,
                y: 4
            )
            .padding(.horizontal, 20)
        }
        .frame(maxHeight: .infinity, alignment: .center)
        .padding(.top, 80)
    }

    private var signPickerOverlay: some View {
        VStack(spacing: 0) {
            VStack(spacing: 8) {
                Button(action: {
                    isPositive = true
                    isShowingSignPicker = false
                }) {
                    HStack {
                        Text("+")
                            .themedText(size: 20)
                        Text("Income")
                            .themedText(size: 17)
                        Spacer()
                    }
                    .padding(.horizontal, 16)
                    .padding(.vertical, 12)
                    .background(isPositive ? Color.white.opacity(0.2) : Color.clear)
                    .cornerRadius(8)
                }

                Button(action: {
                    isPositive = false
                    isShowingSignPicker = false
                }) {
                    HStack {
                        Text("-")
                            .themedText(size: 20)
                        Text("Expense")
                            .themedText(size: 17)
                        Spacer()
                    }
                    .padding(.horizontal, 16)
                    .padding(.vertical, 12)
                    .background(!isPositive ? Color.white.opacity(0.2) : Color.clear)
                    .cornerRadius(8)
                }
            }
            .padding(.vertical, 8)
            .padding(.horizontal, 20)
            .background(liquidGlassBackground)
            .clipShape(RoundedRectangle(cornerRadius: 16))
            .shadow(
                color: Theme.shadowColor(for: colorScheme).opacity(0.3),
                radius: 8,
                x: 0,
                y: 4
            )
            .padding(.horizontal, 20)
        }
        .frame(maxHeight: .infinity, alignment: .center)
        .padding(.top, 80)
    }

    // MARK: - Backgrounds

    @ViewBuilder
    private var liquidGlassBackground: some View {
        if #available(iOS 18.0, *) {
            // iOS 18+ liquid glass effect
            RoundedRectangle(cornerRadius: 16)
                .fill(.ultraThinMaterial)
                .overlay(
                    RoundedRectangle(cornerRadius: 16)
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
            RoundedRectangle(cornerRadius: 16)
                .fill(.ultraThinMaterial)
                .overlay(
                    RoundedRectangle(cornerRadius: 16)
                        .fill(Color.white.opacity(0.15))
                )
        }
    }

    @ViewBuilder
    private var confirmButtonBackground: some View {
        if #available(iOS 26.0, *) {
            // Native Liquid Glass on iOS 26.
            Circle()
                .fill(.clear)
                .glassEffect(.regular.interactive(), in: Circle())
        } else {
            // iOS 18: translucent material so the button reads as glass
            // rather than the red heading color.
            Circle()
                .fill(.ultraThinMaterial)
                .overlay(
                    Circle().stroke(Theme.textColor(for: colorScheme).opacity(0.2), lineWidth: 0.5)
                )
        }
    }

    // MARK: - Actions

    private func handleBackgroundTap() {
        // Dismiss keyboard first
        focusedField = nil

        // Then dismiss pickers/sheet after a brief delay
        DispatchQueue.main.asyncAfter(deadline: .now() + 0.15) {
            if self.isShowingEmojiPicker || self.isShowingSignPicker {
                self.isShowingEmojiPicker = false
                self.isShowingSignPicker = false
            } else {
                self.isPresented = false
            }
        }
    }

    private func handleAddExpense() {
        // Validate input
        guard let amount = Int(amountText), amount > 0 else {
            // Don't add if amount is 0 or invalid
            return
        }

        guard !description.isEmpty else {
            // Don't add if description is empty
            return
        }

        guard !selectedEmoji.isEmpty else {
            // Don't add if no emoji selected
            return
        }

        let finalAmount = isPositive ? amount : -amount

        Task {
            await onAddExpense(finalAmount, selectedEmoji, description)
            isPresented = false
        }
    }
}

// MARK: - Sheet Presentation

struct AddExpenseSheetModifier: ViewModifier {
    @Binding var isPresented: Bool
    let budgets: [Budget]
    let onAddExpense: (Int, String, String) async -> Void

    func body(content: Content) -> some View {
        ZStack {
            content

            if isPresented {
                AddExpenseSheet(
                    isPresented: $isPresented,
                    budgets: budgets,
                    onAddExpense: onAddExpense
                )
                .transition(.opacity)
                .zIndex(999)
            }
        }
        .animation(.easeInOut(duration: 0.2), value: isPresented)
    }
}

extension View {
    func addExpenseSheet(
        isPresented: Binding<Bool>,
        budgets: [Budget],
        onAddExpense: @escaping (Int, String, String) async -> Void
    ) -> some View {
        modifier(AddExpenseSheetModifier(
            isPresented: isPresented,
            budgets: budgets,
            onAddExpense: onAddExpense
        ))
    }
}
