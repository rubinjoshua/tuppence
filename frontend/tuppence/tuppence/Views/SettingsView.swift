//
//  SettingsView.swift
//  tuppence
//

import SwiftUI

struct SettingsView: View {
    @ObservedObject private var settings = AppSettings.shared
    @ObservedObject private var authManager = AuthenticationManager.shared
    @Environment(\.colorScheme) var colorScheme

    @State private var showLogin = false
    @State private var showSignup = false
    @State private var showSignOutConfirmation = false
    @State private var householdToken: String?
    @State private var householdTokenCopied = false
    @State private var householdTokenError: String?
    @State private var isGeneratingToken = false
    @State private var showJoinHousehold = false
    @State private var joinTokenInput = ""
    @State private var joinError: String?
    @State private var isJoining = false
    @State private var reportEmail = ""
    @State private var selectedYear = Calendar.current.component(.year, from: Date())
    @State private var isExporting = false
    @State private var exportError: String?
    @State private var showShareSheet = false
    @State private var exportedFileURL: URL?

    // Budget management
    @State private var budgets: [Budget] = []
    @State private var isLoadingBudgets = false
    @State private var budgetError: String?
    @State private var showAddBudget = false
    @State private var editingBudget: Budget?

    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 24) {
                // Authentication Section
                authenticationSection

                Divider()
                    .background(Theme.textColor(for: colorScheme).opacity(0.3))
                    .padding(.horizontal, -Theme.Layout.screenPadding)

                // Currency Section
                currencySection

                Divider()
                    .background(Theme.textColor(for: colorScheme).opacity(0.3))
                    .padding(.horizontal, -Theme.Layout.screenPadding)

                // Budget Management Section
                budgetManagementSection

                Divider()
                    .background(Theme.textColor(for: colorScheme).opacity(0.3))
                    .padding(.horizontal, -Theme.Layout.screenPadding)

                // Export Section
                exportSection

                Divider()
                    .background(Theme.textColor(for: colorScheme).opacity(0.3))
                    .padding(.horizontal, -Theme.Layout.screenPadding)

                // About Section
                aboutSection

                Spacer(minLength: 100)
            }
            .padding(.horizontal, Theme.Layout.screenPadding)
            .padding(.top, 40)
        }
        .onAppear {
            loadEmailFromSettings()
            Task {
                await loadBudgets()
            }
        }
    }

    private func loadEmailFromSettings() {
        // Load email from iOS Settings.bundle (UserDefaults)
        if let email = UserDefaults.standard.string(forKey: "email_addresses") {
            reportEmail = email
        }
    }

    // MARK: - Budget CRUD Functions

    private func loadBudgets() async {
        guard authManager.isAuthenticated else { return }

        await MainActor.run {
            isLoadingBudgets = true
            budgetError = nil
        }

        do {
            let fetchedBudgets = try await APIService.shared.listBudgets()
            await MainActor.run {
                budgets = fetchedBudgets
                isLoadingBudgets = false
            }
        } catch {
            await MainActor.run {
                budgetError = "Failed to load budgets: \(error.localizedDescription)"
                isLoadingBudgets = false
            }
        }
    }

    private func createBudget(emoji: String, label: String, monthlyAmount: Int) async {
        do {
            let newBudget = try await APIService.shared.createBudget(
                emoji: emoji,
                label: label,
                monthlyAmount: monthlyAmount
            )
            await MainActor.run {
                budgets.append(newBudget)
                showAddBudget = false
                NotificationCenter.default.post(name: .budgetsDidChange, object: nil)
            }
        } catch {
            await MainActor.run {
                budgetError = "Failed to create budget: \(error.localizedDescription)"
            }
        }
    }

    private func updateBudget(_ budget: Budget, emoji: String, label: String, monthlyAmount: Int) async {
        guard let id = budget.id else { return }

        do {
            let updatedBudget = try await APIService.shared.updateBudget(
                id: id,
                emoji: emoji,
                label: label,
                monthlyAmount: monthlyAmount
            )
            await MainActor.run {
                if let index = budgets.firstIndex(where: { $0.id == id }) {
                    budgets[index] = updatedBudget
                }
                editingBudget = nil
                NotificationCenter.default.post(name: .budgetsDidChange, object: nil)
            }
        } catch {
            await MainActor.run {
                budgetError = "Failed to update budget: \(error.localizedDescription)"
            }
        }
    }

    private func deleteBudget(_ budget: Budget) async {
        guard let id = budget.id else { return }

        do {
            try await APIService.shared.deleteBudget(id: id)
            await MainActor.run {
                budgets.removeAll { $0.id == id }
                NotificationCenter.default.post(name: .budgetsDidChange, object: nil)
            }
        } catch {
            await MainActor.run {
                budgetError = "Failed to delete budget: \(error.localizedDescription)"
            }
        }
    }

    // MARK: - Authentication Section

    @ViewBuilder
    private var authenticationSection: some View {
        VStack(alignment: .leading, spacing: 16) {
            Text("Account")
                .themedHeading(size: 20)

            if authManager.isAuthenticated, let user = authManager.currentUser {
                // Authenticated state - shows user info and sign out
                VStack(alignment: .leading, spacing: 12) {
                    HStack {
                        Text("Email:")
                            .themedText(size: 15)
                        Spacer()
                        Text(user.email)
                            .themedText(size: 15)
                            .lineLimit(1)
                            .truncationMode(.middle)
                    }

                    HStack {
                        Text("Household:")
                            .themedText(size: 15)
                        Spacer()
                        Text(user.householdName)
                            .themedText(size: 15)
                    }

                    householdSharingSection

                    Button(action: {
                        showJoinHousehold = true
                    }) {
                        Text("Join Another Household")
                            .themedText(size: 16)
                            .frame(maxWidth: .infinity)
                            .padding(.vertical, 12)
                            .background(Theme.headingColor(for: colorScheme).opacity(0.15))
                            .cornerRadius(8)
                    }

                    Button(action: {
                        showSignOutConfirmation = true
                    }) {
                        Text("Sign Out")
                            .themedText(size: 16)
                            .frame(maxWidth: .infinity)
                            .padding(.vertical, 12)
                            .background(Theme.Colors.deleteRed.opacity(0.2))
                            .cornerRadius(8)
                    }
                }
            } else {
                // Unauthenticated state - shows login/signup buttons
                Text("Sign in to sync your budgets across devices and share with household members.")
                    .themedText(size: 14)
                    .fixedSize(horizontal: false, vertical: true)

                HStack(spacing: 12) {
                    Button(action: {
                        showLogin = true
                    }) {
                        Text("Sign In")
                            .themedText(size: 16)
                            .frame(maxWidth: .infinity)
                            .padding(.vertical, 12)
                            .background(Theme.headingColor(for: colorScheme).opacity(0.2))
                            .cornerRadius(8)
                    }

                    Button(action: {
                        showSignup = true
                    }) {
                        Text("Sign Up")
                            .themedText(size: 16)
                            .frame(maxWidth: .infinity)
                            .padding(.vertical, 12)
                            .background(Theme.headingColor(for: colorScheme).opacity(0.2))
                            .cornerRadius(8)
                    }
                }
            }
        }
        .sheet(isPresented: $showLogin) {
            LoginView()
        }
        .sheet(isPresented: $showSignup) {
            SignupView()
        }
        .sheet(isPresented: $showJoinHousehold) {
            joinHouseholdSheet
        }
        .alert("Sign Out", isPresented: $showSignOutConfirmation) {
            Button("Cancel", role: .cancel) { }
            Button("Sign Out", role: .destructive) {
                authManager.logout()
            }
        } message: {
            Text("Are you sure you want to sign out?")
        }
    }

    @ViewBuilder
    private var householdSharingSection: some View {
        VStack(alignment: .leading, spacing: 8) {
            Text("Share Household")
                .themedText(size: 15)

            if let token = householdToken {
                HStack {
                    Text(token)
                        .font(.system(.body, design: .monospaced))
                        .themedText(size: 14)
                        .lineLimit(1)
                        .truncationMode(.middle)
                        .padding(.horizontal, 12)
                        .padding(.vertical, 8)
                        .background(Theme.textColor(for: colorScheme).opacity(0.1))
                        .cornerRadius(8)

                    Button(action: {
                        UIPasteboard.general.string = token
                        householdTokenCopied = true
                        DispatchQueue.main.asyncAfter(deadline: .now() + 2) {
                            householdTokenCopied = false
                        }
                    }) {
                        Image(systemName: householdTokenCopied ? "checkmark" : "doc.on.doc")
                            .foregroundColor(Theme.headingColor(for: colorScheme))
                            .frame(width: 40, height: 40)
                            .background(Theme.headingColor(for: colorScheme).opacity(0.1))
                            .cornerRadius(8)
                    }
                }

                Text("Token expires in 7 days. One-time use.")
                    .themedText(size: 12)
                    .opacity(0.7)
            } else {
                Button(action: {
                    Task { await generateHouseholdToken() }
                }) {
                    HStack {
                        if isGeneratingToken {
                            ProgressView().tint(Theme.textColor(for: colorScheme))
                        } else {
                            Image(systemName: "person.badge.plus")
                            Text("Generate Sharing Token")
                        }
                    }
                    .themedText(size: 15)
                    .frame(maxWidth: .infinity)
                    .padding(.vertical, 12)
                    .background(Theme.headingColor(for: colorScheme).opacity(0.15))
                    .cornerRadius(8)
                }
                .disabled(isGeneratingToken)

                Text("Generate a token to invite family members to share this household's budgets.")
                    .themedText(size: 12)
                    .opacity(0.7)
                    .fixedSize(horizontal: false, vertical: true)
            }

            if let error = householdTokenError {
                Text(error)
                    .themedText(size: 12)
                    .foregroundColor(Theme.Colors.deleteRed)
            }
        }
    }

    @ViewBuilder
    private var joinHouseholdSheet: some View {
        NavigationView {
            ZStack {
                Theme.backgroundColor(for: colorScheme).ignoresSafeArea()
                VStack(spacing: 20) {
                    Text("Paste a sharing token from someone in the household you want to join. You will lose access to your current household's data.")
                        .themedText(size: 14)
                        .fixedSize(horizontal: false, vertical: true)

                    TextField("Sharing token", text: $joinTokenInput)
                        .textFieldStyle(ThemedTextFieldStyle())
                        .autocorrectionDisabled()
                        .textInputAutocapitalization(.never)

                    if let error = joinError {
                        Text(error)
                            .themedText(size: 13)
                            .foregroundColor(Theme.Colors.deleteRed)
                    }

                    Button(action: {
                        Task { await joinHousehold() }
                    }) {
                        HStack {
                            if isJoining {
                                ProgressView().tint(Theme.textColor(for: colorScheme))
                            } else {
                                Text("Join Household")
                            }
                        }
                        .themedText(size: 16)
                        .frame(maxWidth: .infinity)
                        .padding(.vertical, 12)
                        .background(Theme.headingColor(for: colorScheme).opacity(0.2))
                        .cornerRadius(8)
                    }
                    .disabled(joinTokenInput.isEmpty || isJoining)

                    Spacer()
                }
                .padding(.horizontal, Theme.Layout.screenPadding)
                .padding(.top, 20)
            }
            .navigationTitle("Join Household")
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .cancellationAction) {
                    Button("Cancel") {
                        showJoinHousehold = false
                        joinTokenInput = ""
                        joinError = nil
                    }
                }
            }
        }
    }

    private func generateHouseholdToken() async {
        await MainActor.run {
            isGeneratingToken = true
            householdTokenError = nil
        }
        do {
            let token = try await APIService.shared.generateHouseholdToken()
            await MainActor.run {
                householdToken = token
                isGeneratingToken = false
            }
        } catch {
            await MainActor.run {
                householdTokenError = error.localizedDescription
                isGeneratingToken = false
            }
        }
    }

    private func joinHousehold() async {
        await MainActor.run {
            isJoining = true
            joinError = nil
        }
        do {
            let joined = try await APIService.shared.joinHousehold(token: joinTokenInput)
            await authManager.updateHousehold(id: joined.id, name: joined.name)
            await MainActor.run {
                showJoinHousehold = false
                joinTokenInput = ""
                isJoining = false
            }
            NotificationCenter.default.post(name: .budgetsDidChange, object: nil)
        } catch {
            await MainActor.run {
                joinError = error.localizedDescription
                isJoining = false
            }
        }
    }

    // MARK: - Currency Section

    @ViewBuilder
    private var currencySection: some View {
        VStack(alignment: .leading, spacing: 16) {
            Text("Currency")
                .themedHeading(size: 20)

            HStack {
                Text("Currency Symbol")
                    .themedText(size: 15)
                Spacer()
                Picker("Currency Symbol", selection: $settings.currencySymbol) {
                    Text("$ (Dollar)").tag("$")
                    Text("€ (Euro)").tag("€")
                    Text("₪ (Shekel)").tag("₪")
                }
                .pickerStyle(.menu)
                .themedText(size: 15)
            }
        }
    }

    // MARK: - Budget Management Section

    @ViewBuilder
    private var budgetManagementSection: some View {
        VStack(alignment: .leading, spacing: 16) {
            HStack {
                Text("Budgets")
                    .themedHeading(size: 20)
                Spacer()
                if authManager.isAuthenticated {
                    Button(action: {
                        showAddBudget = true
                    }) {
                        Image(systemName: "plus.circle.fill")
                            .font(.system(size: 24))
                            .foregroundColor(Theme.headingColor(for: colorScheme))
                    }
                }
            }

            if !authManager.isAuthenticated {
                Text("Sign in to manage budgets")
                    .themedText(size: 14)
                    .opacity(0.6)
            } else if isLoadingBudgets {
                HStack {
                    Spacer()
                    ProgressView()
                    Spacer()
                }
                .padding(.vertical, 20)
            } else if let error = budgetError {
                Text(error)
                    .themedText(size: 14)
                    .foregroundColor(Theme.Colors.deleteRed)
            } else if budgets.isEmpty {
                Text("No budgets yet. Tap + to add your first budget.")
                    .themedText(size: 14)
                    .opacity(0.6)
            } else {
                VStack(spacing: 12) {
                    ForEach(budgets) { budget in
                        BudgetRow(budget: budget) {
                            editingBudget = budget
                        } onDelete: {
                            Task {
                                await deleteBudget(budget)
                            }
                        }
                    }
                }

                Text("Budgets are shared across all household members")
                    .themedText(size: 12)
                    .opacity(0.6)
                    .padding(.top, 4)
            }
        }
        .sheet(isPresented: $showAddBudget) {
            BudgetEditView(budget: nil) { emoji, label, monthlyAmount in
                Task {
                    await createBudget(emoji: emoji, label: label, monthlyAmount: monthlyAmount)
                }
            }
        }
        .sheet(item: $editingBudget) { budget in
            BudgetEditView(budget: budget) { emoji, label, monthlyAmount in
                Task {
                    await updateBudget(budget, emoji: emoji, label: label, monthlyAmount: monthlyAmount)
                }
            }
        }
    }

    // MARK: - Export Section

    @ViewBuilder
    private var exportSection: some View {
        VStack(alignment: .leading, spacing: 16) {
            Text("Year-End Export")
                .themedHeading(size: 20)

            Text("Export your budget data as a CSV file for records or tax purposes.")
                .themedText(size: 13)
                .opacity(0.7)
                .fixedSize(horizontal: false, vertical: true)

            // Email for reports
            VStack(alignment: .leading, spacing: 8) {
                Text("Email for Reports")
                    .themedText(size: 15)

                TextField("email@example.com", text: $reportEmail)
                    .textFieldStyle(ThemedTextFieldStyle())
                    .keyboardType(.emailAddress)
                    .textInputAutocapitalization(.never)
                    .autocorrectionDisabled()
                    .onChange(of: reportEmail) { oldValue, newValue in
                        // Save to UserDefaults (for backwards compatibility with Settings.bundle)
                        UserDefaults.standard.set(newValue, forKey: "email_addresses")
                        // TODO: Save email to backend when we have the API
                    }

                Text("Optional: Email address to send reports to.")
                    .themedText(size: 12)
                    .opacity(0.6)
            }

            // Year selector
            HStack {
                Text("Export Year")
                    .themedText(size: 15)
                Spacer()
                Picker("Year", selection: $selectedYear) {
                    ForEach((2020...Calendar.current.component(.year, from: Date())), id: \.self) { year in
                        Text(String(year)).tag(year)
                    }
                }
                .pickerStyle(.menu)
                .themedText(size: 15)
            }

            // Export button
            Button(action: {
                Task {
                    await exportYear()
                }
            }) {
                HStack {
                    if isExporting {
                        ProgressView()
                            .tint(Theme.textColor(for: colorScheme))
                    } else {
                        Image(systemName: "square.and.arrow.down")
                        Text("Export \(selectedYear)")
                    }
                }
                .themedText(size: 16)
                .frame(maxWidth: .infinity)
                .padding(.vertical, 12)
                .background(Theme.headingColor(for: colorScheme).opacity(0.2))
                .cornerRadius(8)
            }
            .disabled(isExporting || !authManager.isAuthenticated)

            if let error = exportError {
                Text(error)
                    .themedText(size: 13)
                    .foregroundColor(Theme.Colors.deleteRed)
            }

            if !authManager.isAuthenticated {
                Text("Sign in to export data")
                    .themedText(size: 13)
                    .opacity(0.6)
            }
        }
        .sheet(isPresented: $showShareSheet) {
            if let url = exportedFileURL {
                ShareSheet(items: [url])
            }
        }
    }

    // MARK: - About Section

    @ViewBuilder
    private var aboutSection: some View {
        VStack(alignment: .leading, spacing: 16) {
            Text("About")
                .themedHeading(size: 20)

            HStack {
                Text("Version")
                    .themedText(size: 15)
                Spacer()
                Text("1.0.0")
                    .themedText(size: 15)
            }

            Text("Tuppence is a simple budgeting app with a Wes Anderson aesthetic.")
                .themedText(size: 13)
                .fixedSize(horizontal: false, vertical: true)
                .opacity(0.7)
        }
    }

    // MARK: - Export Function

    private func exportYear() async {
        await MainActor.run {
            isExporting = true
            exportError = nil
        }

        do {
            let csvData = try await APIService.shared.exportYear(selectedYear)

            // Save to temporary file
            let tempDir = FileManager.default.temporaryDirectory
            let fileName = "tuppence_export_\(selectedYear).csv"
            let fileURL = tempDir.appendingPathComponent(fileName)

            try csvData.write(to: fileURL)

            await MainActor.run {
                exportedFileURL = fileURL
                showShareSheet = true
                isExporting = false
            }
        } catch {
            await MainActor.run {
                exportError = "Export failed: \(error.localizedDescription)"
                isExporting = false
            }
        }
    }
}

// MARK: - Budget Row

struct BudgetRow: View {
    let budget: Budget
    let onEdit: () -> Void
    let onDelete: () -> Void

    @Environment(\.colorScheme) var colorScheme

    var body: some View {
        HStack(spacing: 12) {
            Text(budget.emoji)
                .font(.system(size: 32))

            VStack(alignment: .leading, spacing: 4) {
                Text(budget.label)
                    .themedText(size: 16)
                Text("$\(budget.monthlyAmount)/month")
                    .themedText(size: 13)
                    .opacity(0.6)
            }

            Spacer()

            Button(action: onEdit) {
                Image(systemName: "pencil")
                    .foregroundColor(Theme.headingColor(for: colorScheme))
                    .frame(width: 40, height: 40)
                    .background(Theme.headingColor(for: colorScheme).opacity(0.1))
                    .cornerRadius(8)
            }

            Button(action: onDelete) {
                Image(systemName: "trash")
                    .foregroundColor(Theme.Colors.deleteRed)
                    .frame(width: 40, height: 40)
                    .background(Theme.Colors.deleteRed.opacity(0.1))
                    .cornerRadius(8)
            }
        }
        .padding(.vertical, 8)
    }
}

// MARK: - Budget Edit View

struct BudgetEditView: View {
    let budget: Budget?
    let onSave: (String, String, Int) -> Void

    @Environment(\.dismiss) var dismiss
    @Environment(\.colorScheme) var colorScheme

    @State private var emoji: String
    @State private var label: String
    @State private var monthlyAmountText: String

    init(budget: Budget?, onSave: @escaping (String, String, Int) -> Void) {
        self.budget = budget
        self.onSave = onSave
        _emoji = State(initialValue: budget?.emoji ?? "")
        _label = State(initialValue: budget?.label ?? "")
        _monthlyAmountText = State(initialValue: budget != nil ? String(budget!.monthlyAmount) : "")
    }

    private var isValid: Bool {
        !emoji.isEmpty && !label.isEmpty && monthlyAmount > 0
    }

    private var monthlyAmount: Int {
        Int(monthlyAmountText) ?? 0
    }

    var body: some View {
        NavigationView {
            ZStack {
                Theme.backgroundColor(for: colorScheme)
                    .ignoresSafeArea()

                VStack(spacing: 20) {
                    TextField("Emoji", text: $emoji)
                        .textFieldStyle(ThemedTextFieldStyle())
                        .font(.system(size: 32))

                    TextField("Label", text: $label)
                        .textFieldStyle(ThemedTextFieldStyle())

                    TextField("Monthly Amount", text: $monthlyAmountText)
                        .textFieldStyle(ThemedTextFieldStyle())
                        .keyboardType(.numberPad)

                    Spacer()
                }
                .padding(.horizontal, Theme.Layout.screenPadding)
                .padding(.top, 20)
            }
            .navigationTitle(budget == nil ? "New Budget" : "Edit Budget")
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .cancellationAction) {
                    Button("Cancel") {
                        dismiss()
                    }
                }
                ToolbarItem(placement: .confirmationAction) {
                    Button("Save") {
                        onSave(emoji, label, monthlyAmount)
                        dismiss()
                    }
                    .disabled(!isValid)
                }
            }
        }
    }
}

// MARK: - Share Sheet

struct ShareSheet: UIViewControllerRepresentable {
    let items: [Any]

    func makeUIViewController(context: Context) -> UIActivityViewController {
        let controller = UIActivityViewController(activityItems: items, applicationActivities: nil)
        return controller
    }

    func updateUIViewController(_ uiViewController: UIActivityViewController, context: Context) {}
}

#Preview {
    SettingsView()
        .themedBackground()
}
