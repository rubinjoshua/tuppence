//
//  AddExpenseSheet.swift
//  tuppence
//

import SwiftUI

struct AddExpenseSheet: View {
    @Binding var isPresented: Bool
    let budgets: [Budget]
    let onAddExpense: (Int, String, String) async -> Void

    @State private var step: Step = .amount
    @State private var amountText: String = ""
    @State private var isPositive: Bool = false
    @State private var description: String = ""
    @State private var showConfirmation: Bool = false
    @State private var isLogging: Bool = false
    @FocusState private var focusedField: Field?

    @Environment(\.colorScheme) var colorScheme
    @ObservedObject private var settings = AppSettings.shared

    private enum Step {
        case amount
        case description
        case budget
    }

    private enum Field {
        case amount
        case description
    }

    var body: some View {
        ZStack {
            Color.black.opacity(0.3)
                .ignoresSafeArea()
                .contentShape(Rectangle())
                .onTapGesture(perform: cancel)

            VStack {
                Spacer()
                stepCard
                    .padding(.horizontal, 30)
                Spacer()
            }
            .allowsHitTesting(!showConfirmation)

            if showConfirmation {
                addedConfirmation
                    .transition(.opacity)
            }
        }
        .onAppear(perform: resetState)
    }

    @ViewBuilder
    private var stepCard: some View {
        switch step {
        case .amount:      amountStep
        case .description: descriptionStep
        case .budget:      budgetStep
        }
    }

    // MARK: - Step 1: Amount

    private var amountStep: some View {
        VStack(spacing: 16) {
            Text("Amount")
                .themedText(size: 15)
                .opacity(0.7)
                .frame(maxWidth: .infinity, alignment: .leading)

            HStack(spacing: 12) {
                signToggle

                HStack(spacing: 4) {
                    Text(settings.currencySymbol)
                        .themedText(size: 28)
                    TextField("0", text: $amountText)
                        .font(Theme.Fonts.body(size: 28))
                        .foregroundColor(Theme.textColor(for: colorScheme))
                        .keyboardType(.numberPad)
                        .focused($focusedField, equals: .amount)
                        .multilineTextAlignment(.leading)
                        .onChange(of: amountText) { _, v in
                            amountText = v.filter { $0.isNumber }
                        }
                        .toolbar {
                            ToolbarItemGroup(placement: .keyboard) {
                                Spacer()
                                Button("Next") { advanceFromAmount() }
                                    .disabled(!isAmountValid)
                            }
                        }
                }
                .frame(maxWidth: .infinity, alignment: .leading)
            }
        }
        .padding(20)
        .background(card)
        .onAppear {
            DispatchQueue.main.asyncAfter(deadline: .now() + 0.1) {
                focusedField = .amount
            }
        }
    }

    private var signToggle: some View {
        HStack(spacing: 0) {
            signPill("−", isOn: !isPositive) { isPositive = false }
            signPill("+", isOn: isPositive) { isPositive = true }
        }
        .background(
            RoundedRectangle(cornerRadius: 10).fill(Color.white.opacity(0.08))
        )
        .overlay(
            RoundedRectangle(cornerRadius: 10).stroke(Color.white.opacity(0.15), lineWidth: 0.5)
        )
    }

    private func signPill(_ symbol: String, isOn: Bool, action: @escaping () -> Void) -> some View {
        Button(action: action) {
            Text(symbol)
                .themedText(size: 20)
                .frame(width: 36, height: 36)
                .background(isOn ? Color.white.opacity(0.25) : Color.clear)
                .cornerRadius(8)
        }
        .buttonStyle(.plain)
    }

    // MARK: - Step 2: Description

    private var descriptionStep: some View {
        VStack(spacing: 12) {
            HStack {
                backChevron { goBack(to: .amount) }
                Text("Description")
                    .themedText(size: 15)
                    .opacity(0.7)
                Spacer()
            }

            TextField("description", text: $description)
                .font(Theme.Fonts.body(size: 22))
                .foregroundColor(Theme.textColor(for: colorScheme))
                .focused($focusedField, equals: .description)
                .submitLabel(.next)
                .onSubmit(advanceFromDescription)
        }
        .padding(20)
        .background(card)
        .onAppear {
            DispatchQueue.main.asyncAfter(deadline: .now() + 0.1) {
                focusedField = .description
            }
        }
    }

    // MARK: - Step 3: Budget

    private var budgetStep: some View {
        VStack(spacing: 0) {
            HStack {
                backChevron { goBack(to: .description) }
                Text("Budget")
                    .themedText(size: 15)
                    .opacity(0.7)
                Spacer()
            }
            .padding(.horizontal, 16)
            .padding(.top, 16)
            .padding(.bottom, 8)

            VStack(spacing: 6) {
                ForEach(budgets) { budget in
                    Button(action: { pickBudget(budget) }) {
                        HStack(spacing: 12) {
                            Text(budget.emoji)
                                .font(.system(size: 22 * Theme.Layout.emojiScale))
                            Text(budget.label)
                                .themedText(size: 17)
                            Spacer()
                        }
                        .padding(.horizontal, 16)
                        .padding(.vertical, 10)
                        .background(Color.white.opacity(0.001))
                        .contentShape(Rectangle())
                    }
                    .disabled(isLogging)
                }
            }
            .padding(.bottom, 12)
        }
        .background(card)
        .onAppear {
            focusedField = nil
        }
    }

    // MARK: - Back chevron

    private func backChevron(action: @escaping () -> Void) -> some View {
        Button(action: action) {
            Image(systemName: "chevron.left")
                .font(.system(size: 16, weight: .semibold))
                .foregroundColor(Theme.textColor(for: colorScheme))
                .frame(width: 28, height: 28)
                .contentShape(Rectangle())
        }
    }

    // MARK: - Confirmation overlay

    private var addedConfirmation: some View {
        VStack(spacing: 10) {
            Image(systemName: "checkmark.circle.fill")
                .font(.system(size: 56, weight: .semibold))
                .foregroundColor(Theme.textColor(for: colorScheme))
            Text("Added")
                .themedText(size: 17)
        }
        .padding(.horizontal, 40)
        .padding(.vertical, 32)
        .background(card)
    }

    // MARK: - Card background

    @ViewBuilder
    private var card: some View {
        if #available(iOS 18.0, *) {
            RoundedRectangle(cornerRadius: 16)
                .fill(.ultraThinMaterial)
                .overlay(
                    RoundedRectangle(cornerRadius: 16)
                        .fill(LinearGradient(
                            colors: [Color.white.opacity(0.3), Color.white.opacity(0.1)],
                            startPoint: .topLeading,
                            endPoint: .bottomTrailing
                        ))
                )
                .shadow(color: Theme.shadowColor(for: colorScheme).opacity(0.3), radius: 8, x: 0, y: 4)
        } else {
            RoundedRectangle(cornerRadius: 16)
                .fill(.ultraThinMaterial)
                .overlay(RoundedRectangle(cornerRadius: 16).fill(Color.white.opacity(0.15)))
                .shadow(color: Theme.shadowColor(for: colorScheme).opacity(0.3), radius: 8, x: 0, y: 4)
        }
    }

    // MARK: - State + transitions

    private var isAmountValid: Bool {
        if let n = Int(amountText), n > 0 { return true }
        return false
    }

    private func resetState() {
        step = .amount
        amountText = ""
        isPositive = false
        description = ""
        showConfirmation = false
        isLogging = false
    }

    private func cancel() {
        focusedField = nil
        DispatchQueue.main.asyncAfter(deadline: .now() + 0.1) {
            isPresented = false
        }
    }

    private func goBack(to target: Step) {
        focusedField = nil
        DispatchQueue.main.asyncAfter(deadline: .now() + 0.05) {
            step = target
        }
    }

    private func advanceFromAmount() {
        guard isAmountValid else { return }
        focusedField = nil
        DispatchQueue.main.asyncAfter(deadline: .now() + 0.05) {
            step = .description
        }
    }

    private func advanceFromDescription() {
        guard !description.trimmingCharacters(in: .whitespaces).isEmpty else { return }
        focusedField = nil
        DispatchQueue.main.asyncAfter(deadline: .now() + 0.05) {
            step = .budget
        }
    }

    private func pickBudget(_ budget: Budget) {
        guard let amount = Int(amountText), amount > 0,
              !description.trimmingCharacters(in: .whitespaces).isEmpty,
              !isLogging else { return }

        isLogging = true
        let finalAmount = isPositive ? amount : -amount

        Task {
            await onAddExpense(finalAmount, budget.emoji, description)
            await MainActor.run {
                withAnimation(.easeInOut(duration: 0.2)) {
                    showConfirmation = true
                }
            }
            try? await Task.sleep(nanoseconds: 700_000_000)
            await MainActor.run {
                isPresented = false
            }
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
