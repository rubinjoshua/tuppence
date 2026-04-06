# Tuppence - Quick Start Guide

Get up and running with Tuppence in 5 minutes.

## 🎯 Overview

Tuppence is a multi-user budgeting app with:
- **Authentication:** Session-based auth with household sharing
- **Backend:** FastAPI + PostgreSQL with multi-tenant isolation
- **Frontend:** SwiftUI iOS app with login/signup
- **Integration:** REST API with secure session tokens

## 📋 Prerequisites

### Backend
- Python 3.9+
- PostgreSQL
- OpenAI API key

### Frontend
- macOS with Xcode 16+
- iOS 18.0+ device/simulator

## 🚀 Quick Start

### Step 1: Deploy Backend to Railway

```bash
cd backend

# Follow backend/RAILWAY_DEPLOY.md for detailed steps
# Summary:
# 1. Sign up at railway.app
# 2. Connect GitHub repo
# 3. Add PostgreSQL database
# 4. Set OPENAI_API_KEY environment variable
# 5. Deploy
# 6. Note the production URL (e.g., https://tuppence.up.railway.app)
```

### Step 2: Configure iOS App

```bash
cd frontend/tuppence
```

1. **Update Backend URL:**
   - Open `tuppence/Models/AppSettings.swift`
   - Line 30: Change `http://localhost:8000` to your Railway URL

   ```swift
   let backendURL = "https://your-app-name.up.railway.app"
   ```

2. **Add App Icons:**
   - Open `tuppence.xcodeproj` in Xcode
   - Navigate to `Assets.xcassets` → `AppIcon`
   - Drag the icon files (`icon_light.png`, `icon_dark.png`, `icon_clear.png`) to appropriate slots

### Step 3: Create Account and Login

**First Launch:**

When you first launch the app, you'll see the login screen.

#### Option A: Create New Account

1. Tap "Sign Up"
2. Enter:
   - **Email:** Your email address
   - **Password:** 8+ characters (must include uppercase, lowercase, digit)
   - **Full Name:** Optional
3. Tap "Create Account"
4. You're logged in! A new household is created automatically.

#### Option B: Join Existing Household

If someone shared a household token with you:

1. Tap "Sign Up"
2. Enter email, password, and full name
3. **Paste the household token** in the "Household Token" field
4. Tap "Create Account"
5. You'll join their household and see their budgets!

#### Option C: Apple Sign In

1. Tap "Sign in with Apple"
2. Authenticate with Face ID/Touch ID
3. Optionally paste household token to join existing household
4. Done!

**Returning Users:**

Just enter your email and password on the login screen. Your session stays active for 30 days.

### Step 4: Share Household (Optional)

To share your budgets with family:

1. Open app Settings page
2. Tap "Generate Sharing Token"
3. Share the token with your family member (text, email, etc.)
4. They use it during signup (Step 3, Option B)
5. Token expires in 7 days and can only be used once

**Note:** Only household owners can generate sharing tokens.

### Step 5: Configure Settings

1. Open iOS **Settings** app (not the app's settings page)
2. Scroll down to "Tuppence"
3. Configure:
   - **Currency Symbol:** Choose $, €, or ₪
   - **Email:** Enter email for year-end reports

### Step 6: Add Budgets

**Note:** Currently budgets are synced from the app. Future versions will have in-app budget management.

For now, you can:
1. Create budgets programmatically by modifying `AppSettings.swift`, OR
2. Add budgets via the backend API directly, OR
3. Wait for the in-app budget management feature

**Temporary Workaround:**

In `AppSettings.swift`, modify the `init()` to add default budgets:

```swift
if self.budgets.isEmpty {
    self.budgets = [
        Budget(emoji: "🛒", label: "Groceries", monthlyAmount: 500),
        Budget(emoji: "✈️", label: "Travel", monthlyAmount: 1000),
        Budget(emoji: "🎬", label: "Entertainment", monthlyAmount: 200)
    ]
}
```

### Step 7: Add Spending via Shortcuts

1. Open **Shortcuts** app on iOS
2. Tap "+" to create new shortcut
3. Search for "Quick Add Spending"
4. Configure:
   - Select budget emoji
   - Enter amount
   - Enter description
5. Save shortcut
6. Run it to add your first spending!

### Step 8: Explore the App

**Amount Page:**
- View total amounts per budget
- Scroll "total" to see percentage view
- Scroll "Amount" to switch to Analysis or Spendings

**Analysis Page:**
- View pie chart of spending categories
- See category breakdown with colors
- Scroll month to see past months
- Scroll emoji to switch budgets

**Spendings Page:**
- View all transactions
- Swipe left on any entry to delete
- Pull down to refresh
- Scroll month to see past months

### Step 9: Add Widget (Optional)

1. Long press on home screen
2. Tap "+" in top left
3. Search "Tuppence"
4. Select widget size
5. Add to home screen

## 🧪 Testing

### Backend Health Check

```bash
curl https://your-backend-url.railway.app/health
```

Expected response:
```json
{
  "status": "ok",
  "service": "tuppence-backend"
}
```

### iOS App Testing

1. **Launch App:**
   - Should sync settings and budgets
   - Should show budget amounts (if budgets configured)

2. **Add Spending via Shortcut:**
   - Run your shortcut
   - Return to app
   - Pull down to refresh on Spendings page
   - Should see new entry

3. **View Analysis:**
   - Switch to Analysis page
   - Should see pie chart with categories
   - Colors should match backend category colors

4. **Delete Spending:**
   - Go to Spendings page
   - Swipe left on an entry
   - Tap delete or swipe fully
   - Entry should disappear

5. **Widget:**
   - Widget should show budget amounts
   - Updates every 15 minutes

## 📱 Common Workflows

### Adding Daily Spending

1. Use Siri: "Hey Siri, run [shortcut name]"
2. Or: Tap shortcut on home screen
3. Or: Use Shortcuts widget

### Viewing Monthly Report

1. Open app
2. Go to Analysis page
3. Scroll month to select month
4. Scroll emoji to see different budgets
5. View pie chart and categories

### Exporting Year Data

1. Open iOS Settings
2. Go to Tuppence
3. (Feature coming soon: Export button)
4. For now: Use backend directly:
   ```bash
   curl https://your-backend-url.railway.app/export_year?year=2026 --output budget.csv
   ```

### Changing Currency

1. Open iOS Settings
2. Go to Tuppence
3. Tap "Currency Symbol"
4. Select $, €, or ₪
5. Return to app - amounts update automatically

## 🔧 Troubleshooting

### "Invalid email or password"

**Causes:**
- Incorrect credentials
- Account doesn't exist

**Fixes:**
1. Verify email is correct (case-sensitive)
2. Check password (8+ chars, uppercase, lowercase, digit)
3. Try signup if new user

### "Session expired. Please log in again"

**Causes:**
- Session inactive for 30+ days
- Logged out from another device

**Fixes:**
1. Log in again with email/password
2. Session will be renewed for 30 days

### "Invalid or inactive sharing token"

**Causes:**
- Token expired (7 days)
- Token already used
- Invalid token format

**Fixes:**
1. Request new token from household owner
2. Verify token copied correctly (no spaces)
3. Use token within 7 days of generation

### App Shows "Failed to load amounts"

**Causes:**
- Backend not running
- Incorrect backend URL
- Network connectivity issue
- Not logged in

**Fixes:**
1. Ensure you're logged in (check login screen doesn't show)
2. Check backend URL in `AppSettings.swift`
3. Verify backend is running: `curl https://your-url.railway.app/health`
4. Check iPhone/simulator network

### "No budgets configured"

**Causes:**
- Budgets not set in Settings
- Backend has no budgets synced

**Fixes:**
1. Add budgets using the temporary workaround above
2. Or wait for in-app budget management

### Widget Shows Old Data

**Causes:**
- Widget timeline hasn't refreshed
- Backend unreachable when widget updated

**Fixes:**
1. Remove and re-add widget
2. Wait 15 minutes for automatic update
3. Check backend connectivity

### Shortcuts Don't Work

**Causes:**
- iOS 18+ required for App Intents
- Backend unreachable
- Budget doesn't exist

**Fixes:**
1. Verify iOS version is 18.0+
2. Check backend connectivity
3. Ensure budget emoji exists in Settings

## 📚 Documentation

- **Frontend:** `frontend/README.md`
- **Backend:** `backend/README.md`
- **API Reference:** `backend/API_REFERENCE.md`
- **Integration Notes:** `frontend/tuppence/tuppence/documents/FRONTEND_TO_BACKEND_NOTES.md`
- **Implementation Summary:** `frontend/IMPLEMENTATION_SUMMARY.md`

## 🎉 You're Ready!

Your Tuppence app is now set up and running. Enjoy tracking your budgets!

## 💡 Tips

1. **Set up Shortcuts wisely:**
   - Create one shortcut per budget for quick access
   - Add shortcuts to home screen for one-tap logging

2. **Use the widget:**
   - Glance at budget status without opening app
   - Updates automatically throughout the day

3. **Review monthly:**
   - Check Analysis page at month-end
   - See where your spending went
   - Adjust next month's budgets if needed

4. **Year-end:**
   - Export CSV before end of year
   - Review annual spending patterns
   - Archive for taxes/records

## 🆘 Need Help?

- Check documentation in `/frontend/` and `/backend/`
- Review `FRONTEND_TO_BACKEND_NOTES.md` for integration details
- Open an issue on GitHub

Happy budgeting! 💰
