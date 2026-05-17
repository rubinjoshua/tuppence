# Apple Subscriptions Setup — App Store Connect & Railway

End-to-end checklist for getting StoreKit 2 subscriptions working with the
Tuppence backend. The code is already in place; everything below is one-time
config in App Store Connect plus seven env vars in Railway.

When you're done, the backend can:
- Verify signed transactions iOS posts after a successful purchase
- Receive Apple's Server Notifications V2 for renewals, refunds, etc.
- Poll the App Store Server API to refresh subscription state

---

## 1. Register the app in App Store Connect (if not done)

1. Go to https://appstoreconnect.apple.com → **My Apps** → **+** → **New App**.
2. Bundle ID must exactly match `APPLE_BUNDLE_ID` in `backend/app/config.py`
   — currently `com.joshuarubin.tuppence`. If you pick a different one,
   update both the iOS Xcode project's bundle identifier *and* set the env
   var in Railway.
3. Once created, note the numeric **Apple ID** (top of the app's page,
   labeled "Apple ID: 1234567890"). This is `APPLE_APP_APPLE_ID`.

---

## 2. Create the subscription products

Each tier has a monthly and a yearly product. Four products total. The
backend expects these *exact* product IDs by default (override via env if
you want different ones):

| Tier    | Period   | Product ID                                        |
|---------|----------|---------------------------------------------------|
| Premium | Monthly  | `com.joshuarubin.tuppence.premium.monthly`        |
| Premium | Yearly   | `com.joshuarubin.tuppence.premium.yearly`         |
| Pro     | Monthly  | `com.joshuarubin.tuppence.pro.monthly`            |
| Pro     | Yearly   | `com.joshuarubin.tuppence.pro.yearly`             |

Steps:

1. In your app → **Monetization** → **Subscriptions** → **+** to create a
   subscription group called `Tuppence Subscriptions`. A group lets users
   upgrade/downgrade between tiers within it.
2. Inside the group, add the four products. For each:
   - Reference Name: `Tuppence Premium Monthly` (etc.) — internal only
   - Product ID: as in the table above
   - Subscription Duration: 1 Month or 1 Year
   - Set the price tier (e.g. `$4.99`, `$49.00`)
   - Add a localization (Display Name, Description) for English at minimum
   - Review screenshot (1024×1024 PNG) is required before live, but you can
     skip it during sandbox testing

3. Submit each product for review **with your next app submission**. They
   stay in "Ready to Submit" until then; sandbox testing works regardless.

---

## 3. Generate the In-App Purchase API key

This is what lets the backend call the App Store Server API (used by
`refresh_subscription_status` and by the library's verifier).

1. **Users and Access** → **Integrations** → **In-App Purchase**.
2. Click **+** → name it `tuppence-backend` → **Generate**.
3. **Download the `.p8` file immediately** (you can't re-download it later).
4. On the same page, copy:
   - **Issuer ID** (UUID at the top of the page) → `APPLE_ISSUER_ID`
   - **Key ID** (10 characters, next to your key name) → `APPLE_KEY_ID`
5. Open the `.p8` file in a text editor; the whole multi-line PEM
   (`-----BEGIN PRIVATE KEY-----` through `-----END PRIVATE KEY-----`) goes
   into `APPLE_PRIVATE_KEY`.

---

## 4. Configure Server Notifications V2

Apple POSTs subscription events to this endpoint. Without it, refunds and
auto-renewal changes won't sync until the next time iOS asks the backend.

1. In your app → **App Information** → scroll to **App Store Server
   Notifications**.
2. Set **Production Server URL**:
   `https://<your-railway-domain>/subscriptions/apple-notification`
3. Set **Sandbox Server URL** to the same path on whichever environment
   you use for sandbox testing.
4. **Version**: Version 2 Notifications.
5. Save.
6. Click **Send Test Notification** to verify the endpoint is reachable.
   Look in `apple_notifications` table for a `TEST` row.

---

## 5. Set Railway env vars

In the Railway service → **Variables** tab, paste these. The `_test_default`
placeholders in `config.py` keep the app bootable; setting real values flips
the subscription endpoints from 503 to functional.

```
APPLE_BUNDLE_ID=com.joshuarubin.tuppence
APPLE_APP_APPLE_ID=1234567890       # numeric Apple ID from step 1
APPLE_ISSUER_ID=00000000-0000-0000-0000-000000000000   # UUID from step 3
APPLE_KEY_ID=ABCDEFGHIJ              # 10-char key ID from step 3
APPLE_PRIVATE_KEY=-----BEGIN PRIVATE KEY-----
MIGTAgEAMBMGByqGSM49AgEGCCqGSM49AwEHBHkwdwIB...
-----END PRIVATE KEY-----
APPLE_ENVIRONMENT=Sandbox            # flip to "Production" when you launch
```

Railway's variable editor accepts multi-line values — paste the whole PEM
including the `BEGIN`/`END` lines and the newlines.

Saving env vars triggers a redeploy automatically.

---

## 6. Sandbox testing

1. **App Store Connect → Users and Access → Sandbox Testers**: create a
   tester with an email Apple hasn't seen before (a `+tag` on your real
   address works, e.g. `josh+sandbox@example.com`).
2. On the test device, **Settings → App Store → Sandbox Account** → sign in
   with the tester. (Don't sign out of your real iCloud — sandbox is a
   separate slot.)
3. Build & run the iOS app from Xcode → tap your subscribe UI → Apple's
   purchase sheet should show the product with "[Sandbox]" labels.
4. Complete the purchase. The iOS app calls `/subscriptions/verify`. Hit
   `GET /subscriptions/status` to confirm `tier=premium`, `status=active`.
5. Watch the backend logs for the `SUBSCRIBED` notification arriving from
   Apple a few seconds later. A row in `apple_notifications` with
   `processed=true` confirms the webhook works.
6. Sandbox renewals happen on accelerated schedules (a "1 month" sub
   renews every 5 min, up to 6 times). Use this to test `DID_RENEW` and
   `EXPIRED` flows.

---

## 7. Going live

1. Submit the four subscription products with your app build for review.
2. Apple reviews subscription metadata as part of the app review.
3. Once approved and the app goes live:
   - In Railway, change `APPLE_ENVIRONMENT` from `Sandbox` to `Production`.
   - Verify the production Server Notifications URL still points at the live
     Railway domain.
4. Make a test purchase with a real Apple ID + real card on a non-developer
   account to confirm the production path works.

---

## What lives where

- **Code**: `app/services/apple_service.py` (verify + handle notifications),
  `app/api/subscriptions.py` (HTTP), `app/models/subscription.py` (schema).
- **Migration**: `alembic/versions/010_replace_stripe_with_apple.py`. Runs
  automatically on Railway deploy (`alembic upgrade head` is in
  `nixpacks.toml`'s start command).
- **Tests**: `tests/test_subscriptions.py` — 16 tests, all use mocks for the
  Apple library so they run offline.
- **Apple root certificates**: `app/certs/apple/*.cer` — committed to the
  repo. These verify the chain on signed transactions and notifications;
  they don't rotate often, but if Apple publishes a new root CA, drop the
  new `.cer` into this directory and redeploy.

---

## Endpoints

| Method | Path                                    | Auth          | What it does |
|--------|-----------------------------------------|---------------|---|
| GET    | `/subscriptions/status`                 | Bearer        | Current household subscription state |
| GET    | `/subscriptions/pricing`                | Bearer        | Tiers + Apple product IDs for `Product.products(for:)` |
| POST   | `/subscriptions/verify`                 | Bearer, owner | iOS posts JWS after purchase; backend verifies + upserts |
| POST   | `/subscriptions/apple-notification`     | Apple JWS     | Apple posts Server Notifications V2 here |

`/verify` returns 503 with a clear message while env vars are missing —
the endpoint exists so the iOS dev can start wiring, but won't succeed
until you've completed step 5.
