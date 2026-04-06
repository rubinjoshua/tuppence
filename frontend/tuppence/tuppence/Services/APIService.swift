//
//  APIService.swift
//  tuppence
//

import Foundation

enum APIError: Error {
    case invalidURL
    case requestFailed(Error)
    case invalidResponse
    case decodingFailed(Error)
    case httpError(Int, String)
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
        try await delete(endpoint: "/undo_spending/\(uuid)")
    }

    // MARK: - Configuration

    func syncBudgets(_ budgets: [Budget]) async throws {
        let request = SyncBudgetsRequest(
            budgets: budgets.map { budget in
                SyncBudgetsRequest.BudgetSync(
                    emoji: budget.emoji,
                    label: budget.label,
                    monthlyAmount: budget.monthlyAmount
                )
            }
        )
        let _: SuccessResponse = try await post(endpoint: "/sync_budgets", body: request)
    }

    func syncSettings(currencySymbol: String) async throws {
        let request = ["currency_symbol": currencySymbol]
        let _: SuccessResponse = try await post(endpoint: "/sync_settings", body: request)
    }

    // MARK: - Automations

    func checkAutomations() async throws {
        let _: AutomationResponse = try await post(endpoint: "/check_automations", body: EmptyBody())
    }

    // MARK: - Year-End

    func exportYear(_ year: Int) async throws -> Data {
        guard let url = URL(string: "\(baseURL)/export_year?year=\(year)") else {
            throw APIError.invalidURL
        }

        let (data, response) = try await URLSession.shared.data(from: url)

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

        do {
            let (data, response) = try await URLSession.shared.data(from: url)

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

    private func delete(endpoint: String) async throws {
        guard let url = URL(string: "\(baseURL)\(endpoint)") else {
            throw APIError.invalidURL
        }

        var request = URLRequest(url: url)
        request.httpMethod = "DELETE"

        do {
            let (data, response) = try await URLSession.shared.data(for: request)

            guard let httpResponse = response as? HTTPURLResponse else {
                throw APIError.invalidResponse
            }

            guard (200...299).contains(httpResponse.statusCode) else {
                let errorMessage = String(data: data, encoding: .utf8) ?? "Unknown error"
                throw APIError.httpError(httpResponse.statusCode, errorMessage)
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
