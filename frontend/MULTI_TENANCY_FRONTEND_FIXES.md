# Frontend Fixes Following Backend Multi-Tenancy Completion

The backend has been updated to enforce auth + household scoping on every data
endpoint. Most frontend code already does the right thing (it uses
`addAuthHeader` and the new `/budgets` CRUD endpoints), but there is some dead
code, stale documentation, and a couple of behaviors worth verifying before the
next TestFlight build.

The backend PR that prompted this doc:
`backend/MULTI_TENANCY_COMPLETION_BRIEF.md` (problem statement) and the matching
commit (fix). Read those first if you want context.

---

## Required changes

### 1. Remove the dead `syncBudgets` API call

`tuppence/Services/APIService.swift:121` defines:

```swift
func syncBudgets(_ budgets: [Budget]) async throws {
    let request = SyncBudgetsRequest(...)
    let _: SuccessResponse = try await post(endpoint: "/sync_budgets", body: request)
}
```

The `/sync_budgets` endpoint has been **deleted** from the backend. No caller in
the iOS project invokes `syncBudgets(_:)` anymore (the new flow is the
`/budgets` CRUD endpoints in `listBudgets`, `createBudget`, `updateBudget`,
`deleteBudget`). Please:

- Delete `func syncBudgets(_:)` from `APIService.swift`.
- Delete the `SyncBudgetsRequest` struct it depends on (and any nested
  `BudgetSync` type used only there).
- Grep for `sync_budgets` / `SyncBudgetsRequest` and remove any leftover refs.

If you find a hidden caller, that code path is broken in production (the
endpoint will 404) — convert it to the `/budgets` CRUD calls.

### 2. Update stale frontend documentation

These files still describe `/sync_budgets` as a live endpoint and need editing:

- `tuppence/tuppence/documents/API_REFERENCE.md` (lines ~177, ~339, ~437)
- `tuppence/tuppence/documents/README.md` (line ~101)
- `tuppence/tuppence/documents/IMPLEMENTATION_SUMMARY.md` (line ~68)
- `tuppence/tuppence/documents/FRONTEND_TO_BACKEND_NOTES.md` — question 2 about
  `GET /sync_budgets` is moot now; either delete the question or note it's
  resolved by the `/budgets` CRUD endpoints.

Replace references with the new contract:

```
GET    /budgets                  - list household's budgets
POST   /budgets                  - create budget (body: emoji, label, monthly_amount)
GET    /budgets/{id}             - get one budget
PUT    /budgets/{id}             - update budget
DELETE /budgets/{id}             - delete budget
```

All require `Authorization: Bearer <session_uuid>`. All are scoped to the
authenticated user's household — no `household_id` in URL or body.

### 3. Verify widget auth across the App Group

`Widget/TuppenceWidget.swift` calls `APIService.shared.getAmounts()`. The
backend now requires a bearer token on `/amounts`. `addAuthHeader` reads the
session token from `KeychainHelper`, so this works **if and only if** the
widget extension and the main app share the same keychain access group.

Please confirm:

- The main app target and the widget extension both list the same Keychain
  Sharing entitlement (App Group + matching `kSecAttrAccessGroup`), and
- `KeychainHelper.shared.get(.sessionToken)` actually returns the token from
  inside the widget process.

If the widget returns empty due to a missing token, that's the expected new
behavior when the user is signed out — but it should *not* happen for a
signed-in user. If it does, fix the keychain sharing rather than weakening the
backend.

### 4. Update the backend URL once Railway is redeployed

`tuppence/Models/AppSettings.swift` holds the hardcoded backend URL. The
current value (`https://tuppence-production-8de5.up.railway.app`) returns 404
from Railway — the service slug appears to be gone. After the new Railway
deploy:

- If the URL changes, update `AppSettings.swift` to the new domain.
- If the slug is restored as-is, no change needed.

---

## Behavior changes to be aware of (no code change required, but verify UX)

### A. Every core endpoint now returns 401 when not signed in

Previously the user could (accidentally) read/write the global ledger without a
token. Now `/amounts`, `/monthly_budgets`, `/ledger`, `/category_map`,
`/make_spending`, `/undo_spending/{uuid}`, `/sync_settings`,
`/check_automations`, `/export_year`, `/archive_year` all return **401** if the
bearer token is missing or expired.

`AppViewModel.loadAmounts` already gates on `AuthenticationManager.shared.isAuthenticated`,
which is good. Please verify:

- After session expiration (30 days idle), the app routes to the login screen
  rather than showing a generic error.
- The "Failed to load budgets" fallback paths don't silently mask 401s — log
  them or surface a re-login prompt.

### B. `/undo_spending/{uuid}` returns 404 for entries belonging to other households

Previously a known UUID would delete the entry regardless of who created it.
Now the backend enforces `(uuid, household_id)` matching, so attempting to
delete somebody else's entry returns 404. In practice this shouldn't happen
through your UI (the user only sees their own entries), but if you ever build a
"deep link to entry" feature, expect 404 in that edge case.

### C. Monthly budget automation now catches up if the user misses the 1st

The original `/check_automations` only ran when `today.day == 1`. Now it runs
once per calendar month, on whatever day the user first opens the app that
month. `AppViewModel.syncAndLoad` already calls `/check_automations` on every
launch and foreground, so no frontend change is needed — but the user will now
see their monthly top-up land on the 2nd, 3rd, etc. if that's when they next
opened the app. This is the spec'd behavior ("an automation at the first of
every month that adds each budget's amount to that budget"); just confirming
it's working as intended.

---

## Quick verification checklist

After pulling the backend changes and redeploying:

- [ ] Cold launch with a valid session → budgets load, ledger loads, widget
      populates within 15 min.
- [ ] Cold launch when signed out → login screen shows, no spinner forever.
- [ ] Sign in as user A, create a budget + spending. Sign out, sign in as user
      B → user B sees an empty app (no carry-over).
- [ ] Add a spending, swipe to delete → entry disappears. Add a spending, try
      to delete an entry from a different (fake) UUID → expect a graceful
      404 path, not a crash.
- [ ] Open the app on or after the 1st of a new month → monthly budget
      additions appear in the ledger.
- [ ] Widget on a device where the user is signed in → shows current amounts.
- [ ] Widget on a device where the user is signed out → shows "No budgets",
      not an error toast.

---

## Files NOT touched on the frontend side

None of the Swift behavior changed in this backend PR. The only iOS source
file we *recommend* editing is `APIService.swift` (item 1 above, removing dead
code). Everything else is documentation cleanup or test verification.

If any of the verifications above fail, ping back and we'll figure out whether
it's a frontend bug or a backend regression.
