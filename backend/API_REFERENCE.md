# Tuppence Backend API Reference

Quick reference for all API endpoints.

## Base URL

**Local:** http://localhost:8000
**Production:** https://your-app.up.railway.app

## API Documentation

Interactive docs available at: `{BASE_URL}/docs`

---

## Core Data Endpoints

### Get Amounts
Get total amount left per budget for current year.

```http
GET /amounts
```

**Response:**
```json
{
  "budgets": [
    {
      "emoji": "🛒",
      "label": "Groceries",
      "monthly_amount": 500,
      "total_amount": 1200
    }
  ]
}
```

---

### Get Monthly Budgets
Get monthly increment amounts per budget.

```http
GET /monthly_budgets
```

**Response:**
```json
{
  "budgets": [
    {
      "emoji": "🛒",
      "label": "Groceries",
      "monthly_amount": 500
    }
  ]
}
```

---

### Get Ledger
Get spending history for specified month.

```http
GET /ledger?month=2026-03
```

**Query Parameters:**
- `month` (optional): Format `YYYY-MM`, defaults to current month

**Response:**
```json
[
  {
    "uuid": "123e4567-e89b-12d3-a456-426614174000",
    "amount": -50,
    "currency": "USD",
    "budget_emoji": "🛒",
    "datetime": "2026-03-15T14:30:00Z",
    "description_text": "milk and eggs",
    "category": "Groceries"
  }
]
```

---

### Get Category Map
Get category breakdown for pie chart.

```http
GET /category_map?month=2026-03&budget_emoji=🛒
```

**Query Parameters:**
- `month` (optional): Format `YYYY-MM`, defaults to current month
- `budget_emoji` (required): Budget emoji to filter by

**Response:**
```json
{
  "categories": [
    {
      "category_name": "Groceries",
      "hex_color": "#D9CA94",
      "texts": ["milk and eggs", "bread", "cheese"],
      "total_amount": 125
    },
    {
      "category_name": "Coffee & Cafe",
      "hex_color": "#AC8546",
      "texts": ["starbucks latte"],
      "total_amount": 5
    }
  ]
}
```

---

## Spending Management

### Make Spending
Log new spending with AI categorization.

```http
POST /make_spending
Content-Type: application/json

{
  "amount": -50,
  "currency": "USD",
  "budget_emoji": "🛒",
  "description_text": "milk and eggs",
  "datetime": "2026-03-15T14:30:00Z"  // optional, defaults to now
}
```

**Response:**
```json
{
  "uuid": "123e4567-e89b-12d3-a456-426614174000",
  "category": "Groceries",
  "success": true
}
```

**Note:** Amount should be negative for spending, positive for income.

---

### Undo Spending
Remove ledger entry by UUID.

```http
DELETE /undo_spending/{uuid}
```

**Response:**
```json
{
  "success": true,
  "message": "Spending entry deleted successfully"
}
```

---

## Configuration Sync

### Sync Budgets
Sync budgets from iOS Settings (upserts).

```http
POST /sync_budgets
Content-Type: application/json

{
  "budgets": [
    {
      "emoji": "🛒",
      "label": "Groceries",
      "monthly_amount": 500
    },
    {
      "emoji": "✈️",
      "label": "Travel",
      "monthly_amount": 1000
    }
  ]
}
```

**Response:**
```json
{
  "success": true,
  "synced_count": 2
}
```

---

### Sync Settings
Sync currency and other settings.

```http
POST /sync_settings
Content-Type: application/json

{
  "currency_symbol": "$"
}
```

**Response:**
```json
{
  "success": true
}
```

---

## Automations

### Check Automations
Check and run monthly automation if needed.

```http
POST /check_automations
```

**Response:**
```json
{
  "monthly_update_ran": true,
  "monthly_update_date": "2026-04-01",
  "message": "Monthly update completed for 3 budgets"
}
```

**When to call:** On app launch/open

---

## Year-End Export

### Export Year
Export all ledger entries for a year as CSV.

```http
GET /export_year?year=2025
```

**Query Parameters:**
- `year` (required): Year to export (e.g., 2025)

**Response:** CSV file download

```csv
Date,Budget,Description,Category,Amount,Currency
"2025-01-15 14:30:00","🛒","milk and eggs","Groceries",-50,"USD"
"2025-01-20 10:00:00","✈️","flight to paris","Flights",-500,"USD"
```

---

### Archive Year
Mark year as archived.

```http
POST /archive_year?year=2025
```

**Query Parameters:**
- `year` (required): Year to archive

**Response:**
```json
{
  "success": true,
  "year": 2025
}
```

**When to call:** After successful CSV export

---

## Utility Endpoints

### Health Check
Simple health check.

```http
GET /health
```

**Response:**
```json
{
  "status": "ok",
  "service": "tuppence-backend"
}
```

---

### Root
API information.

```http
GET /
```

**Response:**
```json
{
  "service": "Tuppence Backend",
  "version": "1.0.0",
  "status": "running",
  "docs": "/docs"
}
```

---

## iOS App Integration Flow

### 1. App Launch
```swift
// Sync settings
POST /sync_settings {"currency_symbol": "$"}

// Sync budgets from iOS Settings
POST /sync_budgets {"budgets": [...]}

// Check for monthly automation
POST /check_automations

// Load initial data
GET /amounts
```

### 2. User Adds Spending
```swift
// Round amount to integer first!
let roundedAmount = Int(round(amount))

POST /make_spending {
  "amount": roundedAmount,
  "currency": "USD",
  "budget_emoji": "🛒",
  "description_text": "milk and eggs"
}

// Refresh amounts
GET /amounts
```

### 3. User Views Ledger
```swift
// Get current month ledger
GET /ledger?month=2026-03

// User can tap to undo
DELETE /undo_spending/{uuid}
```

### 4. User Views Analysis
```swift
// Get category breakdown
GET /category_map?month=2026-03&budget_emoji=🛒

// Display pie chart with colors
```

### 5. Year-End Export
```swift
// User taps "Export 2025 Budget" in Settings
GET /export_year?year=2025  // Download CSV

// After successful export
POST /archive_year?year=2025
```

---

## Important Notes

### Amount Formatting
- **Always** send amounts as integers (cents/smallest currency unit)
- Frontend must round before sending: `Int(round(dollars * 100))`
- Negative for spending, positive for income/budget additions

### Date Formats
- **ISO 8601:** `2026-03-30T14:30:00Z` (with timezone)
- **Month queries:** `YYYY-MM` format (e.g., "2026-03")
- **Year queries:** Integer (e.g., 2025)

### Emoji Handling
- Emojis are stored as strings (works fine in PostgreSQL)
- Ensure iOS sends emoji as-is, not encoded
- Use `String(10)` column to support multi-codepoint emojis

### Error Handling
All endpoints return:
- **200-299:** Success
- **400:** Bad request (invalid parameters)
- **404:** Not found (e.g., UUID doesn't exist)
- **500:** Server error

Error response format:
```json
{
  "detail": "Error message here"
}
```

### Currency
- Currently stores 3-character code (e.g., "USD")
- All amounts in same currency per transaction
- Symbol stored in settings ("$", "€", "₪")

---

## Testing with cURL

```bash
# Health check
curl http://localhost:8000/health

# Sync budgets
curl -X POST http://localhost:8000/sync_budgets \
  -H "Content-Type: application/json" \
  -d '{"budgets":[{"emoji":"🛒","label":"Groceries","monthly_amount":500}]}'

# Make spending
curl -X POST http://localhost:8000/make_spending \
  -H "Content-Type: application/json" \
  -d '{"amount":-50,"currency":"USD","budget_emoji":"🛒","description_text":"milk"}'

# Get amounts
curl http://localhost:8000/amounts

# Export year
curl http://localhost:8000/export_year?year=2026 --output ledger.csv
```

---

## Rate Limits

No rate limits currently implemented. Consider adding if needed:
- Per-user: 100 requests/minute
- Per-IP: 1000 requests/hour

---

## Support

- Interactive API docs: `{BASE_URL}/docs`
- OpenAPI spec: `{BASE_URL}/openapi.json`
- GitHub issues: Your repo issues page
