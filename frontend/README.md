# Tuppence iOS App

Beautiful personal budgeting app for iOS with emoji-based budgets, AI-powered categorization, and elegant design.

## Features

- 🔐 **Multi-User Authentication** - Secure login with email/password or Apple Sign In
- 👨‍👩‍👧‍👦 **Household Sharing** - Share budgets with family via secure tokens
- 📊 **Budget Tracking** - Track multiple budgets with custom emojis
- 🎯 **Monthly Budgets** - Automatic monthly budget additions
- 📈 **Analytics** - Pie chart breakdown of spending by category
- 📝 **Spending History** - View and manage all transactions
- 🎨 **Wes Anderson Design** - Pastel color scheme with beautiful UI
- 🌓 **Dark Mode** - Automatic dark mode support
- 🔄 **Widget** - Home screen widget showing budget amounts
- ⚡ **Shortcuts** - Add spending via Siri Shortcuts
- 🌍 **Multi-Currency** - Support for $, €, ₪

## Requirements

- iOS 18.0+
- Xcode 16.0+
- Swift 6.0+

## Architecture

### Project Structure

```
tuppence/
├── Models/              # Data models
│   ├── AuthModels.swift
│   ├── Budget.swift
│   ├── LedgerEntry.swift
│   ├── CategoryData.swift
│   └── AppSettings.swift
├── Services/            # API and business logic
│   ├── AuthService.swift
│   └── APIService.swift
├── ViewModels/          # State management
│   └── AppViewModel.swift
├── Views/               # SwiftUI views
│   ├── AmountView.swift
│   ├── AnalysisView.swift
│   └── SpendingsView.swift
├── Components/          # Reusable components
│   ├── ScrollableText.swift
│   └── NavigationBar.swift
├── Theme/               # Design system
│   └── Theme.swift
├── Utils/               # Helper utilities
│   └── DateFormatter+Extensions.swift
├── Intents/             # App Intents for Shortcuts
│   └── AddSpendingIntent.swift
├── Widget/              # WidgetKit widget
│   └── TuppenceWidget.swift
└── Settings.bundle/     # iOS Settings integration
```

### Design Patterns

- **MVVM Architecture** - Clear separation of concerns
- **ObservableObject** - Reactive state management
- **async/await** - Modern concurrency
- **SwiftUI** - Declarative UI

## Setup

### 1. Clone and Open Project

```bash
cd frontend/tuppence
open tuppence.xcodeproj
```

### 2. Configure Backend URL

Update the backend URL in `Models/AppSettings.swift:30`:

```swift
let backendURL = "https://your-backend-url.railway.app"
```

### 3. Add App Icons

The project includes three icon files:
- `icon_light.png` - For light mode
- `icon_dark.png` - For dark mode
- `icon_clear.png` - Transparent version

Add these to `Assets.xcassets/AppIcon`:
1. Open `Assets.xcassets` in Xcode
2. Select AppIcon
3. Drag icon files to appropriate slots

### 4. Build and Run

1. Select target device/simulator
2. Press Cmd+R to build and run

## Authentication

### First-Time Setup

When you first launch the app, you'll see the login/signup screen.

#### Option 1: Create New Account

1. Tap "Sign Up"
2. Enter email and password (8+ characters, uppercase, lowercase, digit required)
3. Optionally enter your full name
4. Tap "Create Account"
5. A new household is automatically created for you

#### Option 2: Join Existing Household

1. Get a household sharing token from an existing user (see Household Sharing below)
2. Tap "Sign Up"
3. Enter email and password
4. Enter your full name (optional)
5. Paste the household token in the "Household Token" field
6. Tap "Create Account"
7. You'll join the existing household and see all shared budgets

#### Option 3: Apple Sign In

1. Tap "Sign in with Apple"
2. Authenticate with Face ID/Touch ID
3. Optionally enter household token to join existing household
4. A new household is created if no token provided

### Household Sharing

To share your household with family members:

1. Open Settings page in the app
2. Tap "Generate Sharing Token"
3. Share the token securely with your family member (text, email, etc.)
4. Token expires in 7 days and can only be used once
5. After they sign up, they'll have access to all household budgets

**Note:** Only the household owner can generate sharing tokens.

### Session Management

- **Auto-Login:** Your session persists for 30 days
- **Stay Logged In:** App automatically extends your session with each use
- **Sign Out:** Tap "Sign Out" in Settings to log out immediately
- **Disconnect:** Remove yourself from a household (keeps your account)

### Security

- **Keychain Storage:** Session tokens stored securely in iOS Keychain
- **Secure Transport:** All authentication uses HTTPS with Bearer tokens
- **Password Security:** Passwords never stored locally (Argon2id hashed on server)
- **Immediate Revocation:** Sign out immediately invalidates your session

## Usage

### Navigation

The app uses a unique bottom navigation system:
- Words in the navigation bar are scrollable
- Swipe up/down on words to change options
- Page switches happen smoothly with animations

### Three Main Pages

1. **Amount** - View total or percentage remaining per budget
2. **Analysis** - Pie chart breakdown by category
3. **Spendings** - List of all transactions with swipe-to-delete

### Adding Spending

Spending can only be added via Shortcuts:
1. Open Shortcuts app
2. Create new shortcut with "Quick Add Spending" action
3. Configure budget, amount, and description
4. Run shortcut or add to home screen

### iOS Settings

Configure the app in Settings app:
- **Currency** - Choose $, €, or ₪
- **Email** - Set email for year-end reports
- **Budgets** - Managed within the app (reference only)

### Widget

Add the Tuppence widget to your home screen:
1. Long press on home screen
2. Tap "+" to add widget
3. Search for "Tuppence"
4. Choose widget size (Small or Medium)

## API Integration

The app integrates with the Tuppence FastAPI backend. All API calls are made through `APIService.swift`.

### Key Integration Points

1. **App Launch** - Syncs settings, budgets, and checks automations
2. **Foreground** - Re-syncs when app comes to foreground
3. **Page Switches** - Refreshes relevant data
4. **User Actions** - Real-time updates after spending/deleting

### Error Handling

All API errors are caught and displayed to the user via alerts. The app includes:
- Loading states during API calls
- User-friendly error messages
- Automatic retry on foreground

## Customization

### Colors

Edit colors in `Theme/Theme.swift`:
```swift
struct Colors {
    static let lightBackground = Color(hex: "#D9CA94")
    static let lightText = Color(hex: "#334E63")
    // ...
}
```

### Fonts

The app uses:
- **Heading** - SF Pro Light (substitute for Styrene)
- **Body** - New York Regular (iOS system serif, substitute for Tiempos)

To use custom fonts:
1. Add font files to project
2. Update `Info.plist` with font names
3. Update `Theme.Fonts` to use custom fonts

## Testing

### Manual Testing Checklist

**Authentication:**
- [ ] Sign up creates new account and household
- [ ] Login with valid credentials works
- [ ] Invalid credentials show error message
- [ ] Session persists after app restart
- [ ] Sign out clears session
- [ ] Join household via token works
- [ ] Apple Sign In works (if configured)

**Core Features:**
- [ ] Budget amounts display correctly
- [ ] Currency symbol changes reflect immediately
- [ ] Swipe-to-delete works on spending entries
- [ ] Navigation scrolling is smooth
- [ ] Dark mode switches colors correctly
- [ ] Widget updates after changes
- [ ] Shortcuts can add spending
- [ ] Pie chart displays correct colors
- [ ] Month selection works in analysis/spendings
- [ ] App syncs on launch and foreground

### Backend Integration Testing

Requires running backend locally or deployed to Railway.

See `documents/FRONTEND_TO_BACKEND_NOTES.md` for integration testing checklist.

## Troubleshooting

### "Invalid email or password"

**Cause:** Incorrect login credentials

**Fix:**
1. Verify email is correct
2. Check password (case-sensitive)
3. Ensure account exists (try signup if new user)

### "Session expired. Please log in again"

**Cause:** Session token expired after 30 days of inactivity

**Fix:**
1. Tap "Sign Out" if shown
2. Log in again with email/password
3. Session will be renewed for 30 days

### "Invalid or inactive sharing token"

**Cause:** Household token is expired, already used, or invalid

**Fix:**
1. Request a new token from household owner
2. Tokens expire after 7 days
3. Tokens can only be used once
4. Verify token was copied correctly

### "Failed to load amounts"

**Cause:** Backend is not reachable or URL is incorrect

**Fix:**
1. Check backend URL in `AppSettings.swift`
2. Verify backend is running
3. Check network connectivity
4. Ensure you're logged in (valid session token)

### "No budgets configured"

**Cause:** No budgets set in iOS Settings or app

**Fix:**
1. Open iOS Settings app
2. Scroll to Tuppence
3. Note: Budget management is within the app (coming soon)

### Widget not updating

**Cause:** Widget timeline needs refresh

**Fix:**
1. Remove and re-add widget
2. Or wait 15 minutes for automatic update

## Known Limitations

1. **No In-App Budget Management** - Budgets are managed in iOS Settings (per original spec)
2. **No Offline Mode** - Requires backend connectivity for all operations (including authentication)
3. **Single Currency** - All transactions use the currency set in Settings
4. **Manual Year Export** - User must trigger year-end export via Settings
5. **Single Household per User** - Users can only belong to one household at a time

## Future Enhancements

- [ ] In-app budget management UI
- [ ] Offline support with sync
- [ ] Search/filter transactions
- [ ] Budget statistics and trends
- [ ] Automatic year-end export
- [ ] Multi-currency support per transaction
- [ ] Multiple household membership per user
- [ ] iCloud sync for settings
- [ ] Push notifications for budget limits

## Contributing

This is a personal project. For questions or suggestions, please open an issue.

## License

Private project for personal use.

## Support

- **Backend API Docs**: https://your-backend-url.railway.app/docs
- **iOS App Issues**: Open an issue in this repository
- **Integration Notes**: See `documents/FRONTEND_TO_BACKEND_NOTES.md`
