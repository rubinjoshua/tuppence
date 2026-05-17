# Frontend Fixes — Migrating Subscriptions from Stripe to Apple StoreKit 2

The backend's subscription system has been completely rewritten around Apple
StoreKit 2 / the App Store Server API. **All Stripe code in iOS is dead and
must come out**, and the purchase flow needs to be re-implemented using
native StoreKit. There is no longer a checkout URL, no longer a customer
portal — purchases happen entirely inside the iOS app via Apple's UI, and
the backend's only job is to verify what the iOS app reports back.

Read `backend/APPLE_SETUP.md` for the App Store Connect side (product IDs,
sandbox testers, etc.) before wiring this up.

---

## What changed on the backend (so you know what to integrate against)

| Old (Stripe)                                    | New (Apple)                                                         |
|-------------------------------------------------|---------------------------------------------------------------------|
| `POST /subscriptions/checkout` → returns URL    | **Deleted.** Frontend calls StoreKit directly; no backend URL.      |
| `POST /subscriptions/portal` → returns URL      | **Deleted.** Use iOS `AppStore.showManageSubscriptions(in:)` instead. |
| `POST /subscriptions/webhook` (Stripe events)   | **Deleted.** Replaced by `/subscriptions/apple-notification` which Apple — not the frontend — calls. |
| `GET /subscriptions/pricing` returns prices     | Returns **product IDs** only. Display prices come from StoreKit via `Product.products(for:)`. |
| `GET /subscriptions/status` (Stripe shape)      | Same path, new fields. `cancelAtPeriodEnd` removed; `productId`, `environment`, `autoRenewStatus`, `isActive` added. |
| n/a                                             | **New: `POST /subscriptions/verify`** — frontend posts `Transaction.jwsRepresentation` after a purchase. Backend verifies + updates DB. |

Full updated `SubscriptionResponse` shape (camelCase, no `CodingKeys` needed):

```json
{
  "householdId": "uuid-string",
  "tier": "free | premium | pro",
  "status": "active | expired | in_billing_retry | in_grace_period | revoked | refunded | inactive",
  "productId": "com.joshuarubin.tuppence.premium.monthly" | null,
  "environment": "Sandbox" | "Production" | null,
  "currentPeriodStart": "ISO8601" | null,
  "currentPeriodEnd": "ISO8601" | null,
  "autoRenewStatus": true | false | null,
  "isActive": true | false
}
```

---

## Required changes in iOS

### 1. Delete all Stripe-shaped code

Files to delete:

- `tuppence/Models/SubscriptionModels.swift` — `PricingInfo`, `CheckoutSessionRequest`, `CheckoutSessionResponse`, `CustomerPortalRequest`, `CustomerPortalResponse` are all obsolete. Replace with the new shapes below.
- The Stripe-shaped methods in `tuppence/Services/APIService.swift`:
  - `createCheckoutSession(...)`
  - `createCustomerPortal(...)`
  - (Leave `getSubscriptionStatus` and `getPricing` but update their response types.)

In `SubscriptionManager.swift`, delete `createCheckoutSession`, `createCustomerPortal`, and any UI flow that opens a web view to Stripe.

### 2. Replace `SubscriptionModels.swift`

```swift
import Foundation

enum SubscriptionTier: String, Codable {
    case free, premium, pro
}

enum SubscriptionStatus: String, Codable {
    case active, expired
    case inBillingRetry = "in_billing_retry"
    case inGracePeriod = "in_grace_period"
    case revoked, refunded, inactive
}

struct SubscriptionResponse: Codable {
    let householdId: String
    let tier: SubscriptionTier
    let status: SubscriptionStatus
    let productId: String?
    let environment: String?
    let currentPeriodStart: Date?
    let currentPeriodEnd: Date?
    let autoRenewStatus: Bool?
    let isActive: Bool
}

struct PricingTier: Codable {
    let tier: SubscriptionTier
    let displayName: String
    let monthlyProductId: String
    let yearlyProductId: String
    let features: [String]
}

struct PricingResponse: Codable {
    let tiers: [PricingTier]
    let currentTier: SubscriptionTier
}

struct VerifyTransactionRequest: Codable {
    let signedTransaction: String
}
```

### 3. Add a StoreKit 2 manager

New file `tuppence/Managers/StoreKitManager.swift`:

```swift
import Foundation
import StoreKit

@MainActor
final class StoreKitManager: ObservableObject {
    static let shared = StoreKitManager()

    @Published private(set) var products: [Product] = []

    private var transactionListener: Task<Void, Never>?

    private init() {
        transactionListener = listenForTransactions()
    }

    deinit { transactionListener?.cancel() }

    /// Load Apple's metadata (prices, localized titles) for the given product IDs.
    /// IDs come from `GET /subscriptions/pricing`.
    func loadProducts(ids: [String]) async throws {
        products = try await Product.products(for: ids)
    }

    /// Trigger Apple's native purchase sheet, then verify the result with the backend.
    func purchase(_ product: Product) async throws -> SubscriptionResponse {
        let result = try await product.purchase()

        switch result {
        case .success(let verification):
            let transaction = try verification.payloadValue  // throws on .unverified
            let jws = verification.jwsRepresentation
            let response = try await APIService.shared.verifyTransaction(jws: jws)
            await transaction.finish()
            return response
        case .userCancelled:
            throw StoreKitError.userCancelled
        case .pending:
            throw StoreKitError.pending
        @unknown default:
            throw StoreKitError.unknown
        }
    }

    /// Restore: walk current entitlements and re-verify each with the backend.
    /// Called from a "Restore Purchases" button (required by App Review).
    func restorePurchases() async throws {
        for await result in Transaction.currentEntitlements {
            if case .verified(let transaction) = result {
                _ = try await APIService.shared.verifyTransaction(jws: result.jwsRepresentation)
                await transaction.finish()
            }
        }
    }

    /// Background listener for renewals, refunds, and cross-device updates
    /// that arrive while the app is running. Must be started on app launch.
    private func listenForTransactions() -> Task<Void, Never> {
        Task.detached { [weak self] in
            for await result in Transaction.updates {
                guard case .verified(let transaction) = result else { continue }
                _ = try? await APIService.shared.verifyTransaction(jws: result.jwsRepresentation)
                await transaction.finish()
                _ = self  // silence warning
            }
        }
    }
}

enum StoreKitError: Error { case userCancelled, pending, unknown }
```

Start the listener at app launch (e.g. in `tuppenceApp.swift`):

```swift
.task { _ = StoreKitManager.shared }
```

### 4. Add the verify call to `APIService.swift`

```swift
func verifyTransaction(jws: String) async throws -> SubscriptionResponse {
    let body = VerifyTransactionRequest(signedTransaction: jws)
    return try await post(endpoint: "/subscriptions/verify", body: body)
}
```

### 5. Rewrite `SubscriptionView.swift` purchase flow

Instead of opening a Safari view for Stripe checkout:

```swift
// 1. Fetch pricing metadata from backend (gives you the product IDs)
let pricing = try await APIService.shared.getPricing()

// 2. Hand IDs to StoreKit, get back Apple's localized Product objects with prices
let ids = pricing.tiers.flatMap { [$0.monthlyProductId, $0.yearlyProductId] }
    .filter { !$0.isEmpty }
try await StoreKitManager.shared.loadProducts(ids: ids)

// 3. When the user taps "Subscribe":
let response = try await StoreKitManager.shared.purchase(selectedProduct)
// response.tier is now "premium" — UI updates from this
```

For managing an existing subscription (cancel, change plan), use the
native sheet instead of a portal URL:

```swift
import StoreKit

if let scene = UIApplication.shared.connectedScenes.first as? UIWindowScene {
    try await AppStore.showManageSubscriptions(in: scene)
}
```

### 6. Configure StoreKit in Xcode for local testing

1. Project → `tuppence` target → **Signing & Capabilities** → **+ Capability** → **In-App Purchase**.
2. Create a StoreKit configuration file: File → New → File → **StoreKit Configuration File** (name it `Tuppence.storekit`).
3. Add the four subscription products in it with exactly the product IDs
   from `backend/APPLE_SETUP.md`. Set the test prices to whatever you want
   for local previews — they only affect Xcode runs.
4. Edit Scheme → Run → Options → **StoreKit Configuration** → pick
   `Tuppence.storekit`. Now purchases work entirely on-device against the
   config file (no Apple roundtrip) until you flip to a real sandbox tester.

---

## App Group / Keychain for the widget (unchanged note)

The widget calls `/amounts` which requires the same Bearer token as the
main app. The fix from `MULTI_TENANCY_FRONTEND_FIXES.md` (shared Keychain
access group, App Group entitlement on both targets) still applies — the
subscription change doesn't affect the widget.

---

## Verification checklist

- [ ] All Stripe references gone from iOS (`grep -ri stripe frontend/tuppence/`).
- [ ] `SubscriptionView` no longer opens an external Safari view.
- [ ] Tapping "Subscribe Premium" shows Apple's native purchase sheet.
- [ ] After a sandbox purchase, `/subscriptions/status` returns `tier=premium`.
- [ ] Restore Purchases button on the subscription screen calls `restorePurchases()` and re-verifies all current entitlements.
- [ ] `Transaction.updates` listener is started at app launch (test by triggering a sandbox renewal — backend should receive a `DID_RENEW` notification and the next `/status` call should show the bumped `currentPeriodEnd`).
- [ ] "Manage Subscription" opens the native sheet (`showManageSubscriptions`), not a web view.

---

## What stays unchanged

- Auth (session tokens, multi-tenancy, household scoping) — already working.
- All non-subscription endpoints — same as before.
- The widget's data path — unaffected by this change.
