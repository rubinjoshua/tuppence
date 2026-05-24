//
//  SignupView.swift
//  tuppence
//

import SwiftUI
import AuthenticationServices

struct SignupView: View {
    @Environment(\.dismiss) var dismiss
    @Environment(\.colorScheme) var colorScheme
    @ObservedObject private var authManager = AuthenticationManager.shared

    @State private var email = ""
    @State private var password = ""
    @State private var confirmPassword = ""
    @State private var fullName = ""
    @State private var householdToken = ""
    @State private var showTokenField = false

    private var passwordsMatch: Bool {
        password == confirmPassword
    }

    private var isFormValid: Bool {
        !email.isEmpty &&
        password.count >= 8 &&
        passwordsMatch
    }

    var body: some View {
        ZStack {
            Theme.backgroundColor(for: colorScheme)
                .ignoresSafeArea()

            ScrollView {
                VStack(spacing: 24) {
                    Spacer(minLength: 40)

                    Text("Sign Up")
                        .themedHeading(size: 32)

                    VStack(spacing: 16) {
                        TextField("Email", text: $email)
                            .textFieldStyle(ThemedTextFieldStyle())
                            .keyboardType(.emailAddress)
                            .textInputAutocapitalization(.never)
                            .autocorrectionDisabled()

                        TextField("Full Name (optional)", text: $fullName)
                            .textFieldStyle(ThemedTextFieldStyle())
                            .textInputAutocapitalization(.words)

                        SecureField("Password (min 8 characters)", text: $password)
                            .textFieldStyle(ThemedTextFieldStyle())

                        SecureField("Confirm Password", text: $confirmPassword)
                            .textFieldStyle(ThemedTextFieldStyle())

                        if !password.isEmpty && password.count < 8 {
                            HStack {
                                Text("Password must be at least 8 characters")
                                    .themedText(size: 13)
                                    .foregroundColor(Theme.Colors.deleteRed)
                                Spacer()
                            }
                        }

                        if !confirmPassword.isEmpty && !passwordsMatch {
                            HStack {
                                Text("Passwords do not match")
                                    .themedText(size: 13)
                                    .foregroundColor(Theme.Colors.deleteRed)
                                Spacer()
                            }
                        }

                        Button(action: {
                            showTokenField.toggle()
                        }) {
                            HStack {
                                Text(showTokenField ? "Hide household token field" : "Join existing household with token")
                                    .themedText(size: 14)
                                    .foregroundColor(Theme.headingColor(for: colorScheme))
                                Spacer()
                                Image(systemName: showTokenField ? "chevron.up" : "chevron.down")
                                    .foregroundColor(Theme.headingColor(for: colorScheme))
                            }
                        }

                        if showTokenField {
                            TextField("Household Token (optional)", text: $householdToken)
                                .textFieldStyle(ThemedTextFieldStyle())
                                .font(.system(.body, design: .monospaced))
                                .textInputAutocapitalization(.never)
                                .autocorrectionDisabled()
                        }
                    }

                    if let error = authManager.errorMessage {
                        Text(error)
                            .themedText(size: 14)
                            .foregroundColor(Theme.Colors.deleteRed)
                            .multilineTextAlignment(.center)
                    }

                    Button(action: {
                        Task {
                            let name = fullName.isEmpty ? nil : fullName
                            let token = householdToken.isEmpty ? nil : householdToken
                            await authManager.signup(email: email, password: password, fullName: name, householdToken: token)
                            if authManager.isAuthenticated {
                                dismiss()
                            }
                        }
                    }) {
                        if authManager.isLoading {
                            ProgressView()
                                .tint(Theme.textColor(for: colorScheme))
                        } else {
                            Text("Sign Up")
                                .themedText(size: 18)
                        }
                    }
                    .frame(maxWidth: .infinity)
                    .frame(height: 50)
                    .background(Theme.headingColor(for: colorScheme).opacity(0.2))
                    .cornerRadius(12)
                    .disabled(authManager.isLoading || !isFormValid)

                    Text("or")
                        .themedText(size: 14)
                        .opacity(0.6)

                    SignInWithAppleButton(.signUp) { request in
                        request.requestedScopes = [.email, .fullName]
                    } onCompletion: { result in
                        handleAppleSignIn(result)
                    }
                    .signInWithAppleButtonStyle(colorScheme == .dark ? .white : .black)
                    .frame(height: 50)
                    .cornerRadius(12)

                    Button(action: {
                        dismiss()
                    }) {
                        Text("Already have an account? Sign In")
                            .themedText(size: 15)
                            .foregroundColor(Theme.headingColor(for: colorScheme))
                    }
                    .padding(.top, 16)

                    Spacer(minLength: 40)
                }
                .padding(.horizontal, Theme.Layout.screenPadding)
            }
        }
    }

    private func handleAppleSignIn(_ result: Result<ASAuthorization, Error>) {
        switch result {
        case .success(let authorization):
            print("[Apple Sign In] Authorization successful")
            guard let appleIDCredential = authorization.credential as? ASAuthorizationAppleIDCredential else {
                print("[Apple Sign In] Failed to get Apple ID credential")
                authManager.errorMessage = "Apple Sign In failed: Invalid credential type"
                return
            }

            guard let identityToken = appleIDCredential.identityToken else {
                print("[Apple Sign In] Missing identity token")
                authManager.errorMessage = "Apple Sign In failed: Missing identity token"
                return
            }

            guard let tokenString = String(data: identityToken, encoding: .utf8) else {
                print("[Apple Sign In] Failed to decode identity token")
                authManager.errorMessage = "Apple Sign In failed: Invalid token encoding"
                return
            }

            guard let authorizationCode = appleIDCredential.authorizationCode else {
                print("[Apple Sign In] Missing authorization code")
                authManager.errorMessage = "Apple Sign In failed: Missing authorization code"
                return
            }

            guard let codeString = String(data: authorizationCode, encoding: .utf8) else {
                print("[Apple Sign In] Failed to decode authorization code")
                authManager.errorMessage = "Apple Sign In failed: Invalid code encoding"
                return
            }

            let fullName = [
                appleIDCredential.fullName?.givenName,
                appleIDCredential.fullName?.familyName
            ]
            .compactMap { $0 }
            .joined(separator: " ")

            let token = householdToken.isEmpty ? nil : householdToken

            print("[Apple Sign In] Processing with user: \(appleIDCredential.user)")
            print("[Apple Sign In] Email: \(appleIDCredential.email ?? "not provided")")
            print("[Apple Sign In] Full name: \(fullName.isEmpty ? "not provided" : fullName)")
            print("[Apple Sign In] Household token: \(token != nil ? "provided" : "not provided")")

            Task {
                await authManager.appleSignIn(
                    identityToken: tokenString,
                    authorizationCode: codeString,
                    fullName: fullName.isEmpty ? nil : fullName,
                    householdToken: token
                )
                if authManager.isAuthenticated {
                    dismiss()
                }
            }

        case .failure(let error):
            let nsError = error as NSError
            print("[Apple Sign In] Error: \(error.localizedDescription)")
            print("[Apple Sign In] Error code: \(nsError.code)")
            print("[Apple Sign In] Error domain: \(nsError.domain)")

            if nsError.code == 1000 {
                authManager.errorMessage = "Apple Sign In setup required. Please check APPLE_SIGNIN_SETUP.md for configuration instructions."
            } else if nsError.code == 1001 {
                authManager.errorMessage = "Apple Sign In canceled"
            } else {
                authManager.errorMessage = "Apple Sign In error: \(error.localizedDescription)"
            }
        }
    }
}

#Preview {
    SignupView()
}
