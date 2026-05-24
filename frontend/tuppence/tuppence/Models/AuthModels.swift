//
//  AuthModels.swift
//  tuppence
//

import Foundation

struct AuthResponse: Codable {
    let sessionToken: String  // UUID string, NOT JWT
    let userId: String
    let householdId: String
    let email: String
    let householdName: String?

    // No CodingKeys needed - backend sends camelCase
}

struct LoginRequest: Codable {
    let email: String
    let password: String
}

struct SignupRequest: Codable {
    let email: String
    let password: String
    let fullName: String?
    let householdToken: String?

    enum CodingKeys: String, CodingKey {
        case email
        case password
        case fullName = "full_name"
        case householdToken = "household_token"
    }
}

struct AppleSignInRequest: Codable {
    let identityToken: String
    let authorizationCode: String
    let fullName: String?
    let householdToken: String?
    let nonce: String?

    enum CodingKeys: String, CodingKey {
        case identityToken = "identity_token"
        case authorizationCode = "authorization_code"
        case fullName = "full_name"
        case householdToken = "household_token"
        case nonce
    }
}

struct UserInfo: Codable {
    let userId: String
    let email: String
    let householdId: String
    let householdName: String

    // No CodingKeys needed - using camelCase to match backend
}

struct ErrorResponse: Codable {
    let detail: String
}

enum AuthError: Error, LocalizedError {
    case invalidCredentials
    case networkError
    case invalidResponse
    case tokenExpired
    case unknown(String)

    var errorDescription: String? {
        switch self {
        case .invalidCredentials:
            return "Invalid email or password"
        case .networkError:
            return "Network connection failed"
        case .invalidResponse:
            return "Invalid response from server"
        case .tokenExpired:
            return "Session expired. Please log in again"
        case .unknown(let message):
            return message
        }
    }
}
