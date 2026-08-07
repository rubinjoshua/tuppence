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

    // Split-budget options
    @State private var showAddSplitOption = false
    @State private var editingSplitOption: SplitOptionIdentifier?
    @State private var splitOptionError: String?

    // Categorization rules
    @State private var isSavingRules = false
    @State private var rulesError: String?
    @State private var rulesSaved = false

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

                // Split-Budget Options Section
                splitBudgetOptionsSection

                Divider()
                    .background(Theme.textColor(for: colorScheme).opacity(0.3))
                    .padding(.horizontal, -Theme.Layout.screenPadding)

                // Categorization Rules Section
                categorizationRulesSection

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

                Spacer(minLength: 260)  // Headroom so last section can scroll above the fade region.
            }
            .padding(.horizontal, Theme.Layout.screenPadding)
            .padding(.top, 40)
        }
        .fadingBottom()
        .onAppear {
            loadEmailFromSettings()
            Task {
                await loadBudgets()
                await loadCategorizationRulesIfNeeded()
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
        guard let backendId = budget.backendId else { return }

        do {
            let updatedBudget = try await APIService.shared.updateBudget(
                id: backendId,
                emoji: emoji,
                label: label,
                monthlyAmount: monthlyAmount
            )
            await MainActor.run {
                if let index = budgets.firstIndex(where: { $0.backendId == backendId }) {
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
        guard let backendId = budget.backendId else { return }

        do {
            try await APIService.shared.deleteBudget(id: backendId)
            await MainActor.run {
                budgets.removeAll { $0.backendId == backendId }
                NotificationCenter.default.post(name: .budgetsDidChange, object: nil)
            }
        } catch {
            await MainActor.run {
                budgetError = "Failed to delete budget: \(error.localizedDescription)"
            }
        }
    }

    private func moveBudget(from source: IndexSet, to destination: Int) {
        budgets.move(fromOffsets: source, toOffset: destination)
        persistBudgetOrder()
    }

    private func persistBudgetOrder() {
        let orderedIds = budgets.compactMap { $0.backendId }
        guard !orderedIds.isEmpty else { return }
        Task {
            do {
                try await APIService.shared.reorderBudgets(orderedIds: orderedIds)
                NotificationCenter.default.post(name: .budgetsDidChange, object: nil)
            } catch {
                await MainActor.run {
                    budgetError = "Failed to save order: \(error.localizedDescription)"
                }
                await loadBudgets()
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
                    ForEach(Array(budgets.enumerated()), id: \.element.id) { index, budget in
                        BudgetRow(
                            budget: budget,
                            canMoveUp: index > 0,
                            canMoveDown: index < budgets.count - 1,
                            onMoveUp: {
                                moveBudget(from: IndexSet(integer: index), to: index - 1)
                            },
                            onMoveDown: {
                                // SwiftUI offsets: moving down requires destination = index+2
                                moveBudget(from: IndexSet(integer: index), to: index + 2)
                            },
                            onEdit: {
                                editingBudget = budget
                            },
                            onDelete: {
                                Task {
                                    await deleteBudget(budget)
                                }
                            }
                        )
                    }
                }

                Text("Budgets are shared across all household members. Use the arrows to change their order across the app.")
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

    // MARK: - Split-Budget Options Section

    @ViewBuilder
    private var splitBudgetOptionsSection: some View {
        VStack(alignment: .leading, spacing: 16) {
            HStack {
                Text("Split-Budget Options")
                    .themedHeading(size: 20)
                Spacer()
                if authManager.isAuthenticated {
                    Button(action: {
                        editingSplitOption = nil
                        showAddSplitOption = true
                    }) {
                        Image(systemName: "plus.circle.fill")
                            .font(.system(size: 24))
                            .foregroundColor(Theme.headingColor(for: colorScheme))
                    }
                }
            }

            if !authManager.isAuthenticated {
                Text("Sign in to configure split options")
                    .themedText(size: 14)
                    .opacity(0.6)
            } else if settings.splitBudgetOptions.isEmpty {
                Text("No split options yet. Tap + to add one (e.g. 🛒🦊 to split between two budgets).")
                    .themedText(size: 14)
                    .opacity(0.6)
                    .fixedSize(horizontal: false, vertical: true)
            } else {
                VStack(spacing: 12) {
                    ForEach(Array(settings.splitBudgetOptions.enumerated()), id: \.offset) { index, option in
                        SplitOptionRow(
                            emojiString: option,
                            label: splitOptionLabel(option),
                            isStale: !splitOptionIsValid(option),
                            canMoveUp: index > 0,
                            canMoveDown: index < settings.splitBudgetOptions.count - 1,
                            onMoveUp: { moveSplitOption(from: index, to: index - 1) },
                            onMoveDown: { moveSplitOption(from: index, to: index + 1) },
                            onEdit: {
                                editingSplitOption = SplitOptionIdentifier(index: index, value: option)
                            },
                            onDelete: {
                                deleteSplitOption(at: index)
                            }
                        )
                    }
                }

                Text("Picking a split option in Add Expense divides the amount evenly across the listed budgets.")
                    .themedText(size: 12)
                    .opacity(0.6)
                    .padding(.top, 4)
            }

            if let error = splitOptionError {
                Text(error)
                    .themedText(size: 13)
                    .foregroundColor(Theme.Colors.deleteRed)
            }
        }
        .sheet(isPresented: $showAddSplitOption) {
            SplitOptionEditView(
                initial: nil,
                budgets: budgets,
                existing: settings.splitBudgetOptions,
                onSave: { saveSplitOption(newValue: $0, replacingIndex: nil) }
            )
        }
        .sheet(item: $editingSplitOption) { ident in
            SplitOptionEditView(
                initial: ident.value,
                budgets: budgets,
                existing: settings.splitBudgetOptions,
                onSave: { saveSplitOption(newValue: $0, replacingIndex: ident.index) }
            )
        }
    }

    private func splitOptionLabel(_ option: String) -> String {
        let parts = option.emojiTokens.map { token -> String in
            budgets.first(where: { $0.emoji == token })?.label ?? "??"
        }
        return parts.joined(separator: " / ")
    }

    private func splitOptionIsValid(_ option: String) -> Bool {
        let tokens = option.emojiTokens
        guard tokens.count >= 2 else { return false }
        return tokens.allSatisfy { token in budgets.contains(where: { $0.emoji == token }) }
    }

    private func saveSplitOption(newValue: String, replacingIndex: Int?) {
        var updated = settings.splitBudgetOptions
        if let idx = replacingIndex {
            updated[idx] = newValue
        } else {
            updated.append(newValue)
        }
        settings.splitBudgetOptions = updated
        persistSplitOptions()
    }

    private func deleteSplitOption(at index: Int) {
        guard settings.splitBudgetOptions.indices.contains(index) else { return }
        settings.splitBudgetOptions.remove(at: index)
        persistSplitOptions()
    }

    private func moveSplitOption(from source: Int, to destination: Int) {
        var updated = settings.splitBudgetOptions
        guard updated.indices.contains(source), destination >= 0, destination < updated.count else { return }
        let value = updated.remove(at: source)
        updated.insert(value, at: destination)
        settings.splitBudgetOptions = updated
        persistSplitOptions()
    }

    private func persistSplitOptions() {
        let snapshot = settings.splitBudgetOptions
        Task {
            do {
                try await APIService.shared.syncSettings(
                    currencySymbol: settings.currencySymbol,
                    splitBudgetOptions: snapshot
                )
                await MainActor.run { splitOptionError = nil }
            } catch {
                await MainActor.run {
                    splitOptionError = "Failed to save split options: \(error.localizedDescription)"
                }
            }
        }
    }

    // MARK: - Categorization Rules Section

    @ViewBuilder
    private var categorizationRulesSection: some View {
        VStack(alignment: .leading, spacing: 16) {
            Text("Categorization Rules")
                .themedHeading(size: 20)

            if !authManager.isAuthenticated {
                Text("Sign in to customize categorization rules")
                    .themedText(size: 14)
                    .opacity(0.6)
            } else {
                Text("These rules are added to the AI prompt that categorizes your spending. Edit them to tweak how descriptions get sorted into categories.")
                    .themedText(size: 13)
                    .opacity(0.7)
                    .fixedSize(horizontal: false, vertical: true)

                TextEditor(text: $settings.categorizationRules)
                    .themedText(size: 14)
                    .frame(minHeight: 160)
                    .scrollContentBackground(.hidden)
                    .padding(8)
                    .background(Theme.textColor(for: colorScheme).opacity(0.05))
                    .cornerRadius(8)
                    .autocorrectionDisabled()

                Button(action: {
                    Task { await saveCategorizationRules() }
                }) {
                    HStack {
                        if isSavingRules {
                            ProgressView().tint(Theme.textColor(for: colorScheme))
                        } else {
                            Image(systemName: rulesSaved ? "checkmark" : "square.and.arrow.up")
                            Text(rulesSaved ? "Saved" : "Save Rules")
                        }
                    }
                    .themedText(size: 16)
                    .frame(maxWidth: .infinity)
                    .padding(.vertical, 12)
                    .background(Theme.headingColor(for: colorScheme).opacity(0.2))
                    .cornerRadius(8)
                }
                .disabled(isSavingRules)

                Text("Rules are shared across all household members.")
                    .themedText(size: 12)
                    .opacity(0.6)

                if let error = rulesError {
                    Text(error)
                        .themedText(size: 13)
                        .foregroundColor(Theme.Colors.deleteRed)
                }
            }
        }
    }

    /// Populate the editor with the household's rules (the backend returns the
    /// default seed when none has been set) so a first-time user sees editable
    /// starting text rather than an empty box.
    private func loadCategorizationRulesIfNeeded() async {
        guard authManager.isAuthenticated,
              settings.categorizationRules.isEmpty else { return }
        do {
            let remote = try await APIService.shared.getSettings()
            await MainActor.run {
                if settings.categorizationRules.isEmpty {
                    settings.categorizationRules = remote.categorizationRules
                }
            }
        } catch {
            // Non-fatal: the editor stays empty and the user can still type.
        }
    }

    private func saveCategorizationRules() async {
        await MainActor.run {
            isSavingRules = true
            rulesError = nil
            rulesSaved = false
        }
        do {
            try await APIService.shared.syncSettings(
                currencySymbol: settings.currencySymbol,
                categorizationRules: settings.categorizationRules
            )
            await MainActor.run {
                isSavingRules = false
                rulesSaved = true
            }
            try? await Task.sleep(nanoseconds: 2_000_000_000)
            await MainActor.run { rulesSaved = false }
        } catch {
            await MainActor.run {
                isSavingRules = false
                rulesError = "Failed to save rules: \(error.localizedDescription)"
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
    let canMoveUp: Bool
    let canMoveDown: Bool
    let onMoveUp: () -> Void
    let onMoveDown: () -> Void
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

            VStack(spacing: 4) {
                Button(action: onMoveUp) {
                    Image(systemName: "chevron.up")
                        .font(.system(size: 12, weight: .semibold))
                        .foregroundColor(Theme.headingColor(for: colorScheme))
                        .frame(width: 32, height: 20)
                        .background(Theme.headingColor(for: colorScheme).opacity(canMoveUp ? 0.1 : 0.04))
                        .cornerRadius(6)
                }
                .disabled(!canMoveUp)
                .opacity(canMoveUp ? 1 : 0.4)

                Button(action: onMoveDown) {
                    Image(systemName: "chevron.down")
                        .font(.system(size: 12, weight: .semibold))
                        .foregroundColor(Theme.headingColor(for: colorScheme))
                        .frame(width: 32, height: 20)
                        .background(Theme.headingColor(for: colorScheme).opacity(canMoveDown ? 0.1 : 0.04))
                        .cornerRadius(6)
                }
                .disabled(!canMoveDown)
                .opacity(canMoveDown ? 1 : 0.4)
            }

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

// MARK: - Split-Budget Option Support

struct SplitOptionIdentifier: Identifiable {
    let index: Int
    let value: String
    var id: String { "\(index)-\(value)" }
}

extension String {
    /// Split this string into emoji grapheme clusters (`"🛒🦊🦩" → ["🛒", "🦊", "🦩"]`).
    /// Whitespace + ASCII separators are dropped so paste of "🛒 / 🦊" still works.
    var emojiTokens: [String] {
        self.compactMap { ch in
            // Drop whitespace + common separators users might paste between emojis.
            if ch.isWhitespace || ch == "/" || ch == "," || ch == "-" || ch == "+" {
                return nil
            }
            // Drop plain ASCII digits/letters; everything else (emoji,
            // including ZWJ-joined sequences like 👨‍👩‍👧) is kept as one token.
            if ch.isASCII { return nil }
            return String(ch)
        }
    }
}

struct SplitOptionRow: View {
    let emojiString: String
    let label: String
    let isStale: Bool
    let canMoveUp: Bool
    let canMoveDown: Bool
    let onMoveUp: () -> Void
    let onMoveDown: () -> Void
    let onEdit: () -> Void
    let onDelete: () -> Void

    @Environment(\.colorScheme) var colorScheme

    var body: some View {
        HStack(spacing: 12) {
            if isStale {
                Image(systemName: "exclamationmark.triangle.fill")
                    .foregroundColor(.yellow)
                    .font(.system(size: 18))
            }

            Text(emojiString)
                .font(.system(size: 28))
                .opacity(isStale ? 0.5 : 1.0)

            VStack(alignment: .leading, spacing: 2) {
                Text(label)
                    .themedText(size: 15)
                    .opacity(isStale ? 0.5 : 1.0)
                if isStale {
                    Text("Missing budget — won't appear in pickers")
                        .themedText(size: 11)
                        .opacity(0.6)
                }
            }

            Spacer()

            VStack(spacing: 4) {
                Button(action: onMoveUp) {
                    Image(systemName: "chevron.up")
                        .font(.system(size: 12, weight: .semibold))
                        .foregroundColor(Theme.headingColor(for: colorScheme))
                        .frame(width: 32, height: 20)
                        .background(Theme.headingColor(for: colorScheme).opacity(canMoveUp ? 0.1 : 0.04))
                        .cornerRadius(6)
                }
                .disabled(!canMoveUp)
                .opacity(canMoveUp ? 1 : 0.4)

                Button(action: onMoveDown) {
                    Image(systemName: "chevron.down")
                        .font(.system(size: 12, weight: .semibold))
                        .foregroundColor(Theme.headingColor(for: colorScheme))
                        .frame(width: 32, height: 20)
                        .background(Theme.headingColor(for: colorScheme).opacity(canMoveDown ? 0.1 : 0.04))
                        .cornerRadius(6)
                }
                .disabled(!canMoveDown)
                .opacity(canMoveDown ? 1 : 0.4)
            }

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

struct SplitOptionEditView: View {
    let initial: String?
    let budgets: [Budget]
    let existing: [String]
    let onSave: (String) -> Void

    @Environment(\.dismiss) var dismiss
    @Environment(\.colorScheme) var colorScheme

    @State private var text: String

    init(initial: String?, budgets: [Budget], existing: [String], onSave: @escaping (String) -> Void) {
        self.initial = initial
        self.budgets = budgets
        self.existing = existing
        self.onSave = onSave
        _text = State(initialValue: initial ?? "")
    }

    private var tokens: [String] { text.emojiTokens }

    private var duplicate: Bool {
        let normalized = tokens.joined()
        guard !normalized.isEmpty else { return false }
        // If editing, the unchanged value isn't a duplicate of itself.
        if let initial = initial, initial == normalized { return false }
        return existing.contains(normalized)
    }

    private var unknownEmojis: [String] {
        tokens.filter { token in !budgets.contains(where: { $0.emoji == token }) }
    }

    private var hasDuplicateEmoji: Bool {
        Set(tokens).count != tokens.count
    }

    private var validationError: String? {
        if tokens.isEmpty {
            return "Enter at least two budget emojis (e.g. 🛒🦊)."
        }
        if tokens.count < 2 {
            return "Add at least two emojis to split between."
        }
        if hasDuplicateEmoji {
            return "Each budget can only appear once."
        }
        if !unknownEmojis.isEmpty {
            return "Unknown budget(s): \(unknownEmojis.joined(separator: " "))."
        }
        if duplicate {
            return "This split option already exists."
        }
        return nil
    }

    private var isValid: Bool { validationError == nil }

    var body: some View {
        NavigationView {
            ZStack {
                Theme.backgroundColor(for: colorScheme).ignoresSafeArea()

                VStack(spacing: 16) {
                    Text("Enter the emojis of the budgets to split across (e.g. 🛒🦊 for groceries + Bob).")
                        .themedText(size: 13)
                        .opacity(0.7)
                        .fixedSize(horizontal: false, vertical: true)

                    TextField("🛒🦊", text: $text)
                        .textFieldStyle(ThemedTextFieldStyle())
                        .font(.system(size: 32))

                    if !budgets.isEmpty {
                        VStack(alignment: .leading, spacing: 6) {
                            Text("Available budgets:")
                                .themedText(size: 12)
                                .opacity(0.6)
                            HStack(spacing: 6) {
                                ForEach(budgets) { b in
                                    Text(b.emoji)
                                        .font(.system(size: 22))
                                        .onTapGesture {
                                            text += b.emoji
                                        }
                                }
                                Spacer()
                            }
                        }
                    }

                    if let error = validationError {
                        Text(error)
                            .themedText(size: 13)
                            .foregroundColor(Theme.Colors.deleteRed)
                            .fixedSize(horizontal: false, vertical: true)
                    }

                    Spacer()
                }
                .padding(.horizontal, Theme.Layout.screenPadding)
                .padding(.top, 20)
            }
            .navigationTitle(initial == nil ? "New Split Option" : "Edit Split Option")
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .cancellationAction) {
                    Button("Cancel") { dismiss() }
                }
                ToolbarItem(placement: .confirmationAction) {
                    Button("Save") {
                        onSave(tokens.joined())
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
