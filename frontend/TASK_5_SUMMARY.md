# Task #5 Summary: Update iOS Settings.bundle to Only Have Default Settings

## Status: ✅ Complete

## Overview
Simplified iOS Settings.bundle by removing all user-configurable settings that have been moved to in-app SettingsView. iOS Settings now only shows read-only information.

## What Was Removed

### 1. Currency Settings
- **Before:** Currency symbol picker (Dollar, Euro, Shekel)
- **Now:** Removed (available in-app SettingsView)

### 2. Budget Management
- **Before:** "Manage Budgets" child pane with Budgets.plist
- **Now:** Removed (available in-app SettingsView)
- **Deleted:** `Settings.bundle/Budgets.plist`

### 3. Year-End Export
- **Before:** "Email for Reports" text field
- **Now:** Removed (available in-app SettingsView)

## What Remains

### Settings.bundle/Root.plist
- **Group:** "Tuppence" with helpful footer message
- **Version:** Read-only version number (1.0.0)
- **Footer:** "All settings have been moved to the in-app Settings page for easier access and household sharing."

## Migration Strategy

All removed settings are now available in the in-app SettingsView:

| Old Location (iOS Settings) | New Location (In-App) |
|----------------------------|----------------------|
| Currency Symbol picker | Settings → Currency Section |
| Manage Budgets | Settings → Budget Management Section |
| Email for Reports | Settings → Year-End Export Section |

## Benefits of Migration

1. **Household Sharing:** All settings now sync across household members via backend
2. **Better UX:** Settings are easier to find within the app
3. **Consistency:** All configuration in one place
4. **Real-time Updates:** Changes reflect immediately without app restart
5. **Authentication:** Settings require login, ensuring data privacy

## Files Modified

1. **Settings.bundle/Root.plist**
   - Removed: Currency section
   - Removed: Budgets section
   - Removed: Year-End Export section
   - Kept: Version info only
   - Added: Helpful footer message

2. **Settings.bundle/Budgets.plist**
   - Deleted entirely

## User Impact

### Before Migration
- Users go to iOS Settings app → Tuppence
- See currency, budgets, email fields
- Settings stored locally in UserDefaults
- No sharing between household members

### After Migration
- iOS Settings → Tuppence shows only app version
- Footer directs users to in-app settings
- All configuration in app's Settings tab
- Settings shared across household via backend

## Testing

- [ ] iOS Settings shows minimal settings
- [ ] Version number displays correctly
- [ ] Footer message is visible
- [ ] No crashes when opening iOS Settings
- [ ] In-app settings work correctly
- [ ] Currency persists from UserDefaults (backward compatible)
- [ ] Email persists from UserDefaults (backward compatible)

## Backward Compatibility

Even though settings were removed from iOS Settings.bundle:
- `currency_symbol` still read from/written to UserDefaults
- `email_addresses` still read from/written to UserDefaults
- Existing users' settings preserved

This maintains compatibility while encouraging migration to in-app settings.

## Next Steps

1. Consider adding in-app onboarding for existing users
2. Consider migrating existing Settings.bundle data to backend
3. Optional: Add "Open App Settings" link in iOS Settings
4. Optional: Remove Settings.bundle entirely if not needed

## Files Changed

- `/Users/joshuarubin/Code/personal_projects/tuppence/frontend/tuppence/tuppence/Settings.bundle/Root.plist` - Simplified to version only
- `/Users/joshuarubin/Code/personal_projects/tuppence/frontend/tuppence/tuppence/Settings.bundle/Budgets.plist` - Deleted

## Dependencies Complete

- Task #3 (Budget management in-app) - ✅
- Task #4 (Email settings in-app) - ✅

## Unblocked Tasks

- Task #6 (Update all views to use household budgets) - Can now proceed
