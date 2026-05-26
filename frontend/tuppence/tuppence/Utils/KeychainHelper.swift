//
//  KeychainHelper.swift
//  tuppence
//

import Foundation
import Security

class KeychainHelper {
    static let shared = KeychainHelper()

    private let service = "com.tuppence.app"

    private init() {}

    func save(_ value: String, for key: String) -> Bool {
        guard let data = value.data(using: .utf8) else { return false }

        // kSecAttrAccessibleAfterFirstUnlock so an AppIntent triggered by an
        // automation (NFC tap, home screen widget) can read the session token
        // even when the main app is suspended/extension-hosted. The default
        // policy (WhenUnlocked) intermittently fails in extension contexts,
        // producing 403 "Not authenticated" responses from the backend.
        let query: [String: Any] = [
            kSecClass as String: kSecClassGenericPassword,
            kSecAttrService as String: service,
            kSecAttrAccount as String: key,
            kSecValueData as String: data,
            kSecAttrAccessible as String: kSecAttrAccessibleAfterFirstUnlock,
        ]

        SecItemDelete(query as CFDictionary)

        let status = SecItemAdd(query as CFDictionary, nil)
        return status == errSecSuccess
    }

    /// One-time migration: re-save the stored value under the new accessibility
    /// class. Items written before the switch to AfterFirstUnlock retain their
    /// original policy until re-written.
    func upgradeAccessibilityIfNeeded(for key: String) {
        guard let existing = get(key) else { return }
        _ = save(existing, for: key)
    }

    func get(_ key: String) -> String? {
        let query: [String: Any] = [
            kSecClass as String: kSecClassGenericPassword,
            kSecAttrService as String: service,
            kSecAttrAccount as String: key,
            kSecReturnData as String: true,
            kSecMatchLimit as String: kSecMatchLimitOne
        ]

        var result: AnyObject?
        let status = SecItemCopyMatching(query as CFDictionary, &result)

        guard status == errSecSuccess,
              let data = result as? Data,
              let value = String(data: data, encoding: .utf8) else {
            return nil
        }

        return value
    }

    func delete(_ key: String) -> Bool {
        let query: [String: Any] = [
            kSecClass as String: kSecClassGenericPassword,
            kSecAttrService as String: service,
            kSecAttrAccount as String: key
        ]

        let status = SecItemDelete(query as CFDictionary)
        return status == errSecSuccess || status == errSecItemNotFound
    }

    func deleteAll() -> Bool {
        let query: [String: Any] = [
            kSecClass as String: kSecClassGenericPassword,
            kSecAttrService as String: service
        ]

        let status = SecItemDelete(query as CFDictionary)
        return status == errSecSuccess || status == errSecItemNotFound
    }
}

extension KeychainHelper {
    enum Keys {
        static let sessionToken = "session_token"  // UUID session token
        static let userId = "user_id"
        static let userEmail = "user_email"
        static let householdId = "household_id"
        static let householdName = "household_name"
    }
}
