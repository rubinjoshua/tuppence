//
//  APIService.swift
//  tuppence
//

import Foundation

enum APIError: LocalizedError {
    case invalidURL
    case requestFailed(Error)
    case invalidResponse
    case decodingFailed(Error)
    case httpError(Int, String)
    case notAuthenticated

    var errorDescription: String? {
        switch self {
        case .invalidURL:
            return "Invalid API URL"
        case .requestFailed(let error):
            return "Network request failed: \(error.localizedDescription)"
        case .invalidResponse:
            return "Server returned a non-HTTP response"
        case .decodingFailed(let error):
            return "Failed to decode response: \(error.localizedDescription)"
        case .httpError(let code, let body):
            let snippet = body.count > 200 ? String(body.prefix(200)) + "…" : body
            return "HTTP \(code): \(snippet)"
        case .notAuthenticated:
            return "Not signed in — open the Tuppence app and sign in before using this shortcut"
        }
    }
}

class APIService {
    static let shared = APIService()

    private var baseURL: String {
        AppSettings.shared.backendURL
    }

    private let decoder: JSONDecoder = {
        let decoder = JSONDecoder()
        decoder.dateDecodingStrategy = .iso8601
        return decoder
    }()

    private let encoder: JSONEncoder = {
        let encoder = JSONEncoder()
        encoder.dateEncodingStrategy = .iso8601
        return encoder
    }()

    private init() {}

    // MARK: - Auth Header Helper

    private func addAuthHeader(to request: inout URLRequest) {
        if let sessionToken = KeychainHelper.shared.get(KeychainHelper.Keys.sessionToken) {
            request.setValue("Bearer \(sessionToken)", forHTTPHeaderField: "Authorization")
        }
    }

    // MARK: - Core Data Endpoints

    func getAmounts() async throws -> BudgetsResponse {
        try await get(endpoint: "/amounts")
    }

    func getMonthlyBudgets() async throws -> BudgetsResponse {
        try await get(endpoint: "/monthly_budgets")
    }

    func getLedger(month: String? = nil) async throws -> [LedgerEntry] {
        var endpoint = "/ledger"
        if let month = month {
            endpoint += "?month=\(month)"
        }
        return try await get(endpoint: endpoint)
    }

    func getCategoryMap(month: String? = nil, budgetEmoji: String) async throws -> CategoryMapResponse {
        var endpoint = "/category_map?budget_emoji=\(budgetEmoji.addingPercentEncoding(withAllowedCharacters: .urlQueryAllowed) ?? budgetEmoji)"
        if let month = month {
            endpoint += "&month=\(month)"
        }
        return try await get(endpoint: endpoint)
    }

    // MARK: - Spending Management

    func makeSpending(amount: Int, currency: String, budgetEmoji: String, description: String, datetime: Date? = nil) async throws -> MakeSpendingResponse {
        let request = MakeSpendingRequest(
            amount: amount,
            currency: currency,
            budgetEmoji: budgetEmoji,
            descriptionText: description,
            datetime: datetime
        )
        print("Making spending request to: \(baseURL)/make_spending")
        print("Request body: amount=\(amount), currency=\(currency), budgetEmoji=\(budgetEmoji), description=\(description)")

        do {
            let response: MakeSpendingResponse = try await post(endpoint: "/make_spending", body: request)
            print("Response received: \(response)")
            return response
        } catch {
            print("Error making spending: \(error)")
            throw error
        }
    }

    func undoSpending(uuid: String) async throws {
        let _: SuccessResponse = try await delete(endpoint: "/undo_spending/\(uuid)")
    }

    // MARK: - Budget Management (CRUD)

    func listBudgets() async throws -> [Budget] {
        let response: ListBudgetsResponse = try await get(endpoint: "/budgets")
        return response.budgets
    }

    func createBudget(emoji: String, label: String, monthlyAmount: Int) async throws -> Budget {
        let request = CreateBudgetRequest(emoji: emoji, label: label, monthlyAmount: monthlyAmount)
        return try await post(endpoint: "/budgets", body: request)
    }

    func updateBudget(id: Int, emoji: String?, label: String?, monthlyAmount: Int?) async throws -> Budget {
        let request = UpdateBudgetRequest(emoji: emoji, label: label, monthlyAmount: monthlyAmount)
        return try await put(endpoint: "/budgets/\(id)", body: request)
    }

    func deleteBudget(id: Int) async throws {
        let _: DeleteBudgetResponse = try await delete(endpoint: "/budgets/\(id)")
    }

    // MARK: - Configuration

    func syncSettings(currencySymbol: String) async throws {
        let request = ["currency_symbol": currencySymbol]
        let _: SuccessResponse = try await post(endpoint: "/sync_settings", body: request)
    }

    // MARK: - Automations

    func checkAutomations() async throws {
        let _: AutomationResponse = try await post(endpoint: "/check_automations", body: EmptyBody())
    }

    // MARK: - Subscription (groundwork — not exercised from UI in TestFlight builds)

    func getSubscriptionStatus() async throws -> SubscriptionResponse {
        try await get(endpoint: "/subscriptions/status")
    }

    func getPricing() async throws -> PricingResponse {
        try await get(endpoint: "/subscriptions/pricing")
    }

    func verifyTransaction(jws: String) async throws -> SubscriptionResponse {
        let body = VerifyTransactionRequest(signedTransaction: jws)
        return try await post(endpoint: "/subscriptions/verify", body: body)
    }

    // MARK: - Household Sharing

    func generateHouseholdToken(expiresInDays: Int = 7) async throws -> String {
        guard let householdId = KeychainHelper.shared.get(KeychainHelper.Keys.householdId) else {
            throw APIError.httpError(401, "Not signed in")
        }
        let body = GenerateSharingTokenRequest(expiresInDays: expiresInDays)
        let response: SharingTokenResponse = try await post(
            endpoint: "/households/\(householdId)/share-token",
            body: body
        )
        return response.token
    }

    func joinHousehold(token: String) async throws -> JoinedHousehold {
        let body = JoinHouseholdRequestBody(token: token)
        let response: JoinHouseholdAPIResponse = try await post(endpoint: "/households/join", body: body)
        return response.household
    }

    // MARK: - Year-End

    func exportYear(_ year: Int) async throws -> Data {
        guard let url = URL(string: "\(baseURL)/export_year?year=\(year)") else {
            throw APIError.invalidURL
        }

        var request = URLRequest(url: url)
        addAuthHeader(to: &request)

        let (data, response) = try await URLSession.shared.data(for: request)

        guard let httpResponse = response as? HTTPURLResponse else {
            throw APIError.invalidResponse
        }

        guard (200...299).contains(httpResponse.statusCode) else {
            throw APIError.httpError(httpResponse.statusCode, "Export failed")
        }

        return data
    }

    func archiveYear(_ year: Int) async throws {
        let _: SuccessResponse = try await post(endpoint: "/archive_year?year=\(year)", body: EmptyBody())
    }

    // MARK: - Generic HTTP Methods

    private func get<T: Decodable>(endpoint: String) async throws -> T {
        guard let url = URL(string: "\(baseURL)\(endpoint)") else {
            throw APIError.invalidURL
        }

        var request = URLRequest(url: url)
        addAuthHeader(to: &request)

        do {
            let (data, response) = try await URLSession.shared.data(for: request)

            guard let httpResponse = response as? HTTPURLResponse else {
                throw APIError.invalidResponse
            }

            guard (200...299).contains(httpResponse.statusCode) else {
                let errorMessage = String(data: data, encoding: .utf8) ?? "Unknown error"
                throw APIError.httpError(httpResponse.statusCode, errorMessage)
            }

            do {
                return try decoder.decode(T.self, from: data)
            } catch {
                throw APIError.decodingFailed(error)
            }
        } catch let error as APIError {
            throw error
        } catch {
            throw APIError.requestFailed(error)
        }
    }

    private func post<T: Encodable, U: Decodable>(endpoint: String, body: T) async throws -> U {
        guard let url = URL(string: "\(baseURL)\(endpoint)") else {
            throw APIError.invalidURL
        }

        var request = URLRequest(url: url)
        request.httpMethod = "POST"
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")
        addAuthHeader(to: &request)

        do {
            request.httpBody = try encoder.encode(body)
        } catch {
            throw APIError.decodingFailed(error)
        }

        do {
            let (data, response) = try await URLSession.shared.data(for: request)

            guard let httpResponse = response as? HTTPURLResponse else {
                throw APIError.invalidResponse
            }

            guard (200...299).contains(httpResponse.statusCode) else {
                let errorMessage = String(data: data, encoding: .utf8) ?? "Unknown error"
                throw APIError.httpError(httpResponse.statusCode, errorMessage)
            }

            do {
                return try decoder.decode(U.self, from: data)
            } catch {
                throw APIError.decodingFailed(error)
            }
        } catch let error as APIError {
            throw error
        } catch {
            throw APIError.requestFailed(error)
        }
    }

    private func put<T: Encodable, U: Decodable>(endpoint: String, body: T) async throws -> U {
        guard let url = URL(string: "\(baseURL)\(endpoint)") else {
            throw APIError.invalidURL
        }

        var request = URLRequest(url: url)
        request.httpMethod = "PUT"
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")
        addAuthHeader(to: &request)

        do {
            request.httpBody = try encoder.encode(body)
        } catch {
            throw APIError.decodingFailed(error)
        }

        do {
            let (data, response) = try await URLSession.shared.data(for: request)

            guard let httpResponse = response as? HTTPURLResponse else {
                throw APIError.invalidResponse
            }

            guard (200...299).contains(httpResponse.statusCode) else {
                let errorMessage = String(data: data, encoding: .utf8) ?? "Unknown error"
                throw APIError.httpError(httpResponse.statusCode, errorMessage)
            }

            do {
                return try decoder.decode(U.self, from: data)
            } catch {
                throw APIError.decodingFailed(error)
            }
        } catch let error as APIError {
            throw error
        } catch {
            throw APIError.requestFailed(error)
        }
    }

    private func delete<T: Decodable>(endpoint: String) async throws -> T {
        guard let url = URL(string: "\(baseURL)\(endpoint)") else {
            throw APIError.invalidURL
        }

        var request = URLRequest(url: url)
        request.httpMethod = "DELETE"
        addAuthHeader(to: &request)

        do {
            let (data, response) = try await URLSession.shared.data(for: request)

            guard let httpResponse = response as? HTTPURLResponse else {
                throw APIError.invalidResponse
            }

            guard (200...299).contains(httpResponse.statusCode) else {
                let errorMessage = String(data: data, encoding: .utf8) ?? "Unknown error"
                throw APIError.httpError(httpResponse.statusCode, errorMessage)
            }

            do {
                return try decoder.decode(T.self, from: data)
            } catch {
                throw APIError.decodingFailed(error)
            }
        } catch let error as APIError {
            throw error
        } catch {
            throw APIError.requestFailed(error)
        }
    }
}

// MARK: - Helper Types

private struct SuccessResponse: Codable {
    let success: Bool
}

private struct AutomationResponse: Codable {
    let monthlyUpdateRan: Bool?
    let monthlyUpdateDate: String?
    let message: String?

    enum CodingKeys: String, CodingKey {
        case monthlyUpdateRan = "monthly_update_ran"
        case monthlyUpdateDate = "monthly_update_date"
        case message
    }
}

private struct EmptyBody: Codable {}

// MARK: - Budget Types

private struct CreateBudgetRequest: Codable {
    let emoji: String
    let label: String
    let monthlyAmount: Int

    enum CodingKeys: String, CodingKey {
        case emoji
        case label
        case monthlyAmount = "monthly_amount"
    }
}

private struct UpdateBudgetRequest: Codable {
    let emoji: String?
    let label: String?
    let monthlyAmount: Int?

    enum CodingKeys: String, CodingKey {
        case emoji
        case label
        case monthlyAmount = "monthly_amount"
    }
}

private struct ListBudgetsResponse: Codable {
    let budgets: [Budget]
}

private struct DeleteBudgetResponse: Codable {
    let success: Bool
    let message: String
}

// MARK: - Household Types

private struct GenerateSharingTokenRequest: Codable {
    let expiresInDays: Int
    enum CodingKeys: String, CodingKey {
        case expiresInDays = "expires_in_days"
    }
}

private struct SharingTokenResponse: Codable {
    let token: String
}

private struct JoinHouseholdRequestBody: Codable {
    let token: String
}

private struct JoinHouseholdAPIResponse: Codable {
    let household: JoinedHousehold
}

struct JoinedHousehold: Codable {
    let id: String
    let name: String
}

