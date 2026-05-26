//
//  AuthenticationManager.swift
//  tuppence
//

import Foundation
import Combine
import AuthenticationServices
import CryptoKit

@MainActor
class AuthenticationManager: ObservableObject {
    static let shared = AuthenticationManager()

    @Published var isAuthenticated = false
    @Published var currentUser: UserInfo?
    @Published var isLoading = false
    @Published var errorMessage: String?

    private let keychain = KeychainHelper.shared
    private let backendURL = AppSettings.shared.backendURL
    private var pendingAppleNonce: String?

    private init() {
        // Re-save existing keychain items under the new AfterFirstUnlock
        // accessibility class so App Intents triggered from background
        // contexts can read the session token reliably.
        keychain.upgradeAccessibilityIfNeeded(for: KeychainHelper.Keys.sessionToken)
        keychain.upgradeAccessibilityIfNeeded(for: KeychainHelper.Keys.userId)
        keychain.upgradeAccessibilityIfNeeded(for: KeychainHelper.Keys.userEmail)
        keychain.upgradeAccessibilityIfNeeded(for: KeychainHelper.Keys.householdId)
        keychain.upgradeAccessibilityIfNeeded(for: KeychainHelper.Keys.householdName)
        checkAuthState()
    }

    // MARK: - Apple Sign In Helpers

    func prepareAppleRequest(_ request: ASAuthorizationAppleIDRequest) {
        let raw = Self.randomNonceString()
        pendingAppleNonce = raw
        request.requestedScopes = [.email, .fullName]
        request.nonce = Self.sha256(raw)
    }

    func handleAppleCompletion(_ result: Result<ASAuthorization, Error>, householdToken: String?) async {
        let nonce = pendingAppleNonce
        pendingAppleNonce = nil

        switch result {
        case .success(let authorization):
            guard let credential = authorization.credential as? ASAuthorizationAppleIDCredential,
                  let identityTokenData = credential.identityToken,
                  let identityToken = String(data: identityTokenData, encoding: .utf8),
                  let authCodeData = credential.authorizationCode,
                  let authCode = String(data: authCodeData, encoding: .utf8) else {
                errorMessage = "Apple Sign In failed: missing credential data"
                return
            }

            let fullName = [credential.fullName?.givenName, credential.fullName?.familyName]
                .compactMap { $0 }
                .joined(separator: " ")

            await appleSignIn(
                identityToken: identityToken,
                authorizationCode: authCode,
                fullName: fullName.isEmpty ? nil : fullName,
                householdToken: householdToken,
                nonce: nonce
            )

        case .failure(let error):
            if let asError = error as? ASAuthorizationError {
                switch asError.code {
                case .canceled:
                    errorMessage = nil
                case .failed:
                    errorMessage = "Apple Sign In failed. Verify the capability is enabled in Xcode and the App ID."
                case .invalidResponse:
                    errorMessage = "Apple returned an invalid response."
                case .notHandled:
                    errorMessage = "Apple Sign In could not be handled. Please try again."
                case .notInteractive:
                    errorMessage = "Apple Sign In requires user interaction."
                case .unknown:
                    errorMessage = "Apple Sign In failed: \(error.localizedDescription)"
                @unknown default:
                    errorMessage = "Apple Sign In failed: \(error.localizedDescription)"
                }
            } else {
                errorMessage = "Apple Sign In failed: \(error.localizedDescription)"
            }
        }
    }

    private static func randomNonceString(length: Int = 32) -> String {
        precondition(length > 0)
        let charset: [Character] = Array("0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz-._")
        var result = ""
        var remaining = length
        while remaining > 0 {
            var randoms = [UInt8](repeating: 0, count: 16)
            let status = SecRandomCopyBytes(kSecRandomDefault, randoms.count, &randoms)
            precondition(status == errSecSuccess)
            for byte in randoms where remaining > 0 {
                if byte < charset.count {
                    result.append(charset[Int(byte) % charset.count])
                    remaining -= 1
                }
            }
        }
        return result
    }

    private static func sha256(_ input: String) -> String {
        let data = Data(input.utf8)
        let hash = SHA256.hash(data: data)
        return hash.compactMap { String(format: "%02x", $0) }.joined()
    }

    // MARK: - Auth State

    func checkAuthState() {
        if let sessionToken = keychain.get(KeychainHelper.Keys.sessionToken),
           let userId = keychain.get(KeychainHelper.Keys.userId),
           let email = keychain.get(KeychainHelper.Keys.userEmail),
           let householdId = keychain.get(KeychainHelper.Keys.householdId),
           let householdName = keychain.get(KeychainHelper.Keys.householdName),
           !sessionToken.isEmpty {
            currentUser = UserInfo(
                userId: userId,
                email: email,
                householdId: householdId,
                householdName: householdName
            )
            isAuthenticated = true
        } else {
            isAuthenticated = false
            currentUser = nil
        }
    }

    // MARK: - Login

    func login(email: String, password: String) async {
        await MainActor.run { isLoading = true }

        let result = await performLogin(email: email, password: password)

        await MainActor.run {
            isLoading = false
            switch result {
            case .success(let response):
                saveAuthData(response)
                checkAuthState()
                errorMessage = nil
            case .failure(let error):
                errorMessage = error.localizedDescription
            }
        }
    }

    // MARK: - Signup

    func signup(email: String, password: String, fullName: String?, householdToken: String?) async {
        await MainActor.run { isLoading = true }

        let result = await performSignup(email: email, password: password, fullName: fullName, householdToken: householdToken)

        await MainActor.run {
            isLoading = false
            switch result {
            case .success(let response):
                saveAuthData(response)
                checkAuthState()
                errorMessage = nil
            case .failure(let error):
                errorMessage = error.localizedDescription
            }
        }
    }

    // MARK: - Apple Sign In

    func appleSignIn(identityToken: String, authorizationCode: String, fullName: String?, householdToken: String?, nonce: String?) async {
        isLoading = true

        let result = await performAppleSignIn(
            identityToken: identityToken,
            authorizationCode: authorizationCode,
            fullName: fullName,
            householdToken: householdToken,
            nonce: nonce
        )

        isLoading = false
        switch result {
        case .success(let response):
            saveAuthData(response)
            checkAuthState()
            errorMessage = nil
        case .failure(let error):
            errorMessage = error.localizedDescription
        }
    }

    // MARK: - Household Updates

    @MainActor
    func updateHousehold(id: String, name: String) {
        _ = keychain.save(id, for: KeychainHelper.Keys.householdId)
        _ = keychain.save(name, for: KeychainHelper.Keys.householdName)
        if let existing = currentUser {
            currentUser = UserInfo(
                userId: existing.userId,
                email: existing.email,
                householdId: id,
                householdName: name
            )
        }
    }

    // MARK: - Logout

    func logout() {
        keychain.deleteAll()
        isAuthenticated = false
        currentUser = nil
        errorMessage = nil
    }

    // MARK: - Private Helpers

    private func saveAuthData(_ response: AuthResponse) {
        _ = keychain.save(response.sessionToken, for: KeychainHelper.Keys.sessionToken)
        _ = keychain.save(response.userId, for: KeychainHelper.Keys.userId)
        _ = keychain.save(response.email, for: KeychainHelper.Keys.userEmail)
        _ = keychain.save(response.householdId, for: KeychainHelper.Keys.householdId)
        _ = keychain.save(response.householdName ?? "My Household", for: KeychainHelper.Keys.householdName)
    }

    // MARK: - Mock API (Debug Only)

    #if DEBUG
    private func mockLogin(email: String, password: String) async -> Result<AuthResponse, AuthError> {
        try? await Task.sleep(nanoseconds: 500_000_000)

        if email.isEmpty || password.isEmpty {
            return .failure(.invalidCredentials)
        }

        if password.count < 8 {
            return .failure(.unknown("Password must be at least 8 characters"))
        }

        let response = AuthResponse(
            sessionToken: UUID().uuidString,  // UUID session token
            userId: UUID().uuidString,
            householdId: UUID().uuidString,
            email: email,
            householdName: "\(email.split(separator: "@").first ?? "User")'s Household"
        )

        return .success(response)
    }

    private func mockSignup(email: String, password: String, householdToken: String?) async -> Result<AuthResponse, AuthError> {
        try? await Task.sleep(nanoseconds: 500_000_000)

        if email.isEmpty || password.isEmpty {
            return .failure(.invalidCredentials)
        }

        if password.count < 8 {
            return .failure(.unknown("Password must be at least 8 characters"))
        }

        let householdName = householdToken != nil ? "Shared Household" : "\(email.split(separator: "@").first ?? "User")'s Household"

        let response = AuthResponse(
            sessionToken: UUID().uuidString,  // UUID session token
            userId: UUID().uuidString,
            householdId: householdToken ?? UUID().uuidString,
            email: email,
            householdName: householdName
        )

        return .success(response)
    }

    private func mockAppleSignIn(identityToken: String, fullName: String?) async -> Result<AuthResponse, AuthError> {
        try? await Task.sleep(nanoseconds: 500_000_000)

        let name = fullName ?? "Apple User"
        let response = AuthResponse(
            sessionToken: UUID().uuidString,  // UUID session token
            userId: UUID().uuidString,
            householdId: UUID().uuidString,
            email: "apple_user_\(UUID().uuidString.prefix(8))@privaterelay.appleid.com",
            householdName: "\(name)'s Household"
        )

        return .success(response)
    }
    #endif

    // MARK: - Real API (Production)

    private func performLogin(email: String, password: String) async -> Result<AuthResponse, AuthError> {
        let url = URL(string: "\(backendURL)/auth/login")!
        var request = URLRequest(url: url)
        request.httpMethod = "POST"
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")

        let loginRequest = LoginRequest(email: email, password: password)
        request.httpBody = try? JSONEncoder().encode(loginRequest)

        do {
            let (data, response) = try await URLSession.shared.data(for: request)

            guard let httpResponse = response as? HTTPURLResponse else {
                return .failure(.invalidResponse)
            }

            if httpResponse.statusCode == 200 {
                let authResponse = try JSONDecoder().decode(AuthResponse.self, from: data)
                return .success(authResponse)
            } else if httpResponse.statusCode == 401 {
                return .failure(.invalidCredentials)
            } else {
                let errorResponse = try? JSONDecoder().decode(ErrorResponse.self, from: data)
                return .failure(.unknown(errorResponse?.detail ?? "Unknown error"))
            }
        } catch {
            return .failure(.networkError)
        }
    }

    private func performSignup(email: String, password: String, fullName: String?, householdToken: String?) async -> Result<AuthResponse, AuthError> {
        let url = URL(string: "\(backendURL)/auth/register")!
        var request = URLRequest(url: url)
        request.httpMethod = "POST"
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")

        let signupRequest = SignupRequest(email: email, password: password, fullName: fullName, householdToken: householdToken)
        request.httpBody = try? JSONEncoder().encode(signupRequest)

        do {
            let (data, response) = try await URLSession.shared.data(for: request)

            guard let httpResponse = response as? HTTPURLResponse else {
                return .failure(.invalidResponse)
            }

            if httpResponse.statusCode == 200 || httpResponse.statusCode == 201 {
                let authResponse = try JSONDecoder().decode(AuthResponse.self, from: data)
                return .success(authResponse)
            } else {
                let errorResponse = try? JSONDecoder().decode(ErrorResponse.self, from: data)
                return .failure(.unknown(errorResponse?.detail ?? "Registration failed"))
            }
        } catch {
            return .failure(.networkError)
        }
    }

    private func performAppleSignIn(identityToken: String, authorizationCode: String, fullName: String?, householdToken: String?, nonce: String?) async -> Result<AuthResponse, AuthError> {
        let url = URL(string: "\(backendURL)/auth/apple-signin")!
        var request = URLRequest(url: url)
        request.httpMethod = "POST"
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")

        let appleRequest = AppleSignInRequest(
            identityToken: identityToken,
            authorizationCode: authorizationCode,
            fullName: fullName,
            householdToken: householdToken,
            nonce: nonce
        )
        request.httpBody = try? JSONEncoder().encode(appleRequest)

        do {
            let (data, response) = try await URLSession.shared.data(for: request)

            guard let httpResponse = response as? HTTPURLResponse else {
                return .failure(.invalidResponse)
            }

            if httpResponse.statusCode == 200 || httpResponse.statusCode == 201 {
                let authResponse = try JSONDecoder().decode(AuthResponse.self, from: data)
                return .success(authResponse)
            } else {
                let errorResponse = try? JSONDecoder().decode(ErrorResponse.self, from: data)
                return .failure(.unknown(errorResponse?.detail ?? "Apple Sign In failed"))
            }
        } catch {
            return .failure(.networkError)
        }
    }
}
