//
//  LoginView.swift
//  tuppence
//

import SwiftUI
import AuthenticationServices

struct LoginView: View {
    @Environment(\.dismiss) var dismiss
    @Environment(\.colorScheme) var colorScheme
    @ObservedObject private var authManager = AuthenticationManager.shared

    @State private var email = ""
    @State private var password = ""
    @State private var showSignup = false

    var body: some View {
        ZStack {
            Theme.backgroundColor(for: colorScheme)
                .ignoresSafeArea()

            ScrollView {
                VStack(spacing: 24) {
                    Spacer(minLength: 40)

                    Text("Sign In")
                        .themedHeading(size: 32)

                    VStack(spacing: 16) {
                        TextField("Email", text: $email)
                            .textFieldStyle(ThemedTextFieldStyle())
                            .keyboardType(.emailAddress)
                            .textInputAutocapitalization(.never)
                            .autocorrectionDisabled()

                        SecureField("Password", text: $password)
                            .textFieldStyle(ThemedTextFieldStyle())
                    }

                    if let error = authManager.errorMessage {
                        Text(error)
                            .themedText(size: 14)
                            .foregroundColor(Theme.Colors.deleteRed)
                            .multilineTextAlignment(.center)
                    }

                    Button(action: {
                        Task {
                            await authManager.login(email: email, password: password)
                            if authManager.isAuthenticated {
                                dismiss()
                            }
                        }
                    }) {
                        if authManager.isLoading {
                            ProgressView()
                                .tint(Theme.textColor(for: colorScheme))
                        } else {
                            Text("Sign In")
                                .themedText(size: 18)
                        }
                    }
                    .frame(maxWidth: .infinity)
                    .frame(height: 50)
                    .background(Theme.headingColor(for: colorScheme).opacity(0.2))
                    .cornerRadius(12)
                    .disabled(authManager.isLoading || email.isEmpty || password.isEmpty)

                    Text("or")
                        .themedText(size: 14)
                        .opacity(0.6)

                    SignInWithAppleButton(.signIn) { request in
                        request.requestedScopes = [.email, .fullName]
                    } onCompletion: { result in
                        handleAppleSignIn(result)
                    }
                    .signInWithAppleButtonStyle(colorScheme == .dark ? .white : .black)
                    .frame(height: 50)
                    .cornerRadius(12)

                    Button(action: {
                        showSignup = true
                    }) {
                        Text("Don't have an account? Sign Up")
                            .themedText(size: 15)
                            .foregroundColor(Theme.headingColor(for: colorScheme))
                    }
                    .padding(.top, 16)

                    Spacer(minLength: 40)
                }
                .padding(.horizontal, Theme.Layout.screenPadding)
            }
        }
        .sheet(isPresented: $showSignup) {
            SignupView()
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

            print("[Apple Sign In] Processing with user: \(appleIDCredential.user)")
            print("[Apple Sign In] Email: \(appleIDCredential.email ?? "not provided")")
            print("[Apple Sign In] Full name: \(fullName.isEmpty ? "not provided" : fullName)")

            Task {
                await authManager.appleSignIn(
                    identityToken: tokenString,
                    authorizationCode: codeString,
                    fullName: fullName.isEmpty ? nil : fullName,
                    householdToken: nil
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

struct ThemedTextFieldStyle: TextFieldStyle {
    @Environment(\.colorScheme) var colorScheme

    func _body(configuration: TextField<Self._Label>) -> some View {
        configuration
            .themedText(size: 16)
            .padding(.horizontal, 16)
            .padding(.vertical, 14)
            .background(Theme.textColor(for: colorScheme).opacity(0.1))
            .cornerRadius(12)
    }
}

#Preview {
    LoginView()
}
