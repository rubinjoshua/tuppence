# Frontend to Backend Integration Notes

This document contains questions and suggestions from the frontend team regarding backend integration.

## Questions for Backend Team

### 1. Currency Handling

**Question:** The iOS app stores currency symbols ($, €, ₪) but the backend expects 3-letter codes (USD, EUR, ILS).

**Current Solution:** The frontend maps symbols to codes before sending to backend:
- $ → USD
- € → EUR
- ₪ → ILS

**Question:** Should the backend also accept currency symbols directly, or is the current mapping sufficient?

---

### 2. Budgets in Settings vs Backend — RESOLVED

Resolved by the `/budgets` CRUD endpoints (`GET`, `POST`, `PUT`, `DELETE
/budgets/{id}`), which are household-scoped on the backend. The backend is now
the single source of truth: the in-app Settings UI edits budgets directly via
these endpoints, so there's no local/remote sync conflict. iOS UserDefaults
no longer stores budgets.

---

### 3. Year-End Export Email Integration

**Question:** The backend has `/export_year` which returns CSV data, but doesn't send emails. The app description mentions emailing the CSV.

**Current Frontend Implementation:**
- User taps "Export 2025 Budget" in iOS Settings
- Frontend calls `/export_year?year=2025`
- Frontend receives CSV data
- Frontend uses iOS Share Sheet to let user share/email the CSV

**Question:** Should the backend handle emailing directly using the email addresses from settings, or is the current frontend approach (manual share via iOS) acceptable?

---

### 4. Budget Deletion

**Question:** The current API has no endpoint to delete a budget. What should happen when a user removes a budget from iOS Settings?

**Suggestion:** Add `DELETE /budgets/{emoji}` endpoint, or clarify that budgets should never be deleted (only amounts reset).

---

### 5. Monthly Automation Timing

**Question:** The `/check_automations` endpoint runs monthly budget additions on the first of each month. The frontend calls this on app launch.

**Concern:** What if the user doesn't open the app on the 1st? The automation won't run until they do.

**Suggestion:** Consider adding a backend cron job or scheduled task to run automations automatically, independent of frontend calls. Frontend can still call `/check_automations` to trigger it manually if needed.

---

### 6. Error Messages

**Question:** When API calls fail, the backend returns:
```json
{
  "detail": "Error message here"
}
```

**Suggestion:** For better UX, could the backend return more structured errors with error codes? For example:
```json
{
  "error_code": "BUDGET_NOT_FOUND",
  "detail": "Budget with emoji 🛒 not found",
  "status": 404
}
```

This would allow the frontend to show user-friendly messages for specific errors.

---

### 7. Widget Data Freshness

**Question:** The iOS widget fetches budget amounts via `GET /amounts` every 15 minutes. Is this polling frequency acceptable for the backend, or should we reduce it?

**Alternative:** Could the backend support push notifications when amounts change significantly (e.g., when a spending is logged)?

---

### 8. Offline Support

**Question:** The frontend currently has no offline support - all operations require backend connectivity.

**Discussion:** Should we add local caching with sync when online? This would require:
- Local CoreData/SwiftData storage
- Conflict resolution when syncing
- Queue for pending operations

Is this complexity worth it for a budgeting app?

---

### 9. Large Ledgers Performance

**Question:** The `GET /ledger` endpoint returns all entries for a month. What happens when a month has hundreds of entries?

**Suggestion:** Consider adding pagination:
```
GET /ledger?month=2026-03&page=1&limit=50
```

Or add a `limit` parameter for mobile views that only need recent entries.

---

### 10. Category Colors Consistency

**Question:** The backend provides hex colors for categories from the 150 predefined Wes Anderson colors.

**Confirmation:** These colors are static and never change per category, correct? The frontend can cache the category-to-color mapping?

---

## Suggested Enhancements (Optional)

### 1. Batch Operations

For better performance when syncing, consider adding:
- `POST /batch_spending` - Add multiple spending entries at once
- `DELETE /batch_undo_spending` - Delete multiple entries

This would be useful for offline sync scenarios.

---

### 2. Budget Statistics Endpoint

Consider adding an endpoint that returns useful stats:
```
GET /stats?year=2026
```

Response:
```json
{
  "total_spent": -15000,
  "total_budgeted": 20000,
  "budgets": [
    {
      "emoji": "🛒",
      "total_spent": -5000,
      "total_budgeted": 6000,
      "percentage_used": 83,
      "top_categories": [
        {"category": "Groceries", "amount": -3000},
        {"category": "Coffee & Cafe", "amount": -2000}
      ]
    }
  ],
  "monthly_breakdown": [...]
}
```

This would be useful for future analytics features.

---

### 3. Search/Filter Ledger

Consider adding search functionality:
```
GET /ledger/search?query=coffee&month=2026-03
```

This would help users find specific transactions.

---

## Known Limitations in Current Frontend

1. **No Budget Management UI:** Users cannot add/edit budgets within the app - they must use iOS Settings. This was intentional per spec, but could be improved in future versions.

2. **No In-App Spending Entry:** Users can only add spending via Shortcuts. This keeps the main app clean for viewing only.

3. **No Multi-Currency Support:** While the backend stores currency per transaction, the frontend assumes all transactions use the same currency set in Settings.

4. **Year-End Export is Manual:** User must tap a button in Settings to export. No automatic email on Jan 1st.

5. **No Data Backup/Restore:** If user deletes app, all local settings are lost (though backend data remains).

---

## Integration Testing Checklist

- [ ] Test budget sync when Settings has budgets but backend doesn't
- [ ] Test budget sync when backend has budgets but Settings doesn't
- [ ] Test monthly automation on app launch
- [ ] Test category colors display correctly from backend
- [ ] Test swipe-to-delete spending entry
- [ ] Test year-end export and archive
- [ ] Test widget updates after spending entry
- [ ] Test Shortcuts integration for adding spending
- [ ] Test app behavior when backend is unreachable
- [ ] Test with empty budgets list
- [ ] Test with 10+ budgets
- [ ] Test with months that have 100+ ledger entries
- [ ] Test currency symbol changes
- [ ] Test dark mode color scheme
- [ ] Test navigation scrolling between pages

---

## Backend URL Configuration

**Important:** The frontend currently has a hardcoded backend URL:

```swift
let backendURL = "http://localhost:8000"  // TODO: Update to production URL
```

**Location:** `frontend/tuppence/tuppence/Models/AppSettings.swift:30`

**Action Required:** Update this to the production Railway URL once deployed:
```swift
let backendURL = "https://your-app.up.railway.app"
```

---

## Contact

For any clarifications or discussions about these integration points, please open an issue or contact the frontend team.

**Frontend Implementation:** Complete ✅
**Backend URL:** Pending deployment
**Integration Testing:** Pending backend deployment
