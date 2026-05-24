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
                        authManager.prepareAppleRequest(request)
                    } onCompletion: { result in
                        Task {
                            await authManager.handleAppleCompletion(result, householdToken: nil)
                            if authManager.isAuthenticated {
                                dismiss()
                            }
                        }
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
