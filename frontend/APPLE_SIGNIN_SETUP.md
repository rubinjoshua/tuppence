# Apple Sign In Setup Guide

## Error 1000 Fix

Error 1000 from Apple Sign In typically means the authorization request failed. This is usually due to missing configuration in Xcode.

## Required Steps

### 1. Add Sign in with Apple Capability in Xcode

1. Open the project in Xcode: `tuppence.xcodeproj`
2. Select the **tuppence** target (not the project)
3. Go to the **Signing & Capabilities** tab
4. Click the **+ Capability** button
5. Search for and add **"Sign in with Apple"**
6. Ensure the capability shows "Default" configuration

### 2. Add Entitlements File to Target

The entitlements file has been created at: `tuppence/tuppence.entitlements`

**In Xcode:**
1. Select the **tuppence** target
2. Go to **Build Settings**
3. Search for "Code Signing Entitlements"
4. Set the value to: `tuppence/tuppence.entitlements`

Alternatively, if the file isn't automatically added:
1. In the Project Navigator, drag `tuppence.entitlements` to ensure it's in the tuppence folder
2. Make sure it's added to the tuppence target (check the File Inspector)

### 3. Configure Bundle Identifier & Team

1. In **Signing & Capabilities** tab:
   - Ensure **Automatically manage signing** is checked
   - Select your **Team** (Personal Team or Organization)
   - Note the **Bundle Identifier** (e.g., `com.yourname.tuppence`)

### 4. Apple Developer Account Setup (if using real device)

**For Simulator:** Sign in with Apple works in simulator with any Apple ID.

**For Real Device:**
1. Go to [Apple Developer Portal](https://developer.apple.com/)
2. Sign in with your Apple ID
3. Go to **Certificates, Identifiers & Profiles**
4. Select **Identifiers**
5. Find or create an App ID matching your bundle identifier
6. Ensure **Sign in with Apple** capability is enabled
7. Save changes

### 5. Test Configuration

After completing the above steps:
1. Clean build folder (Cmd+Shift+K)
2. Rebuild the app
3. Test Apple Sign In on:
   - Simulator (quick test)
   - Real device (full test)

### 6. Common Issues

**Error 1000 persists:**
- Ensure you've restarted Xcode after adding the capability
- Clean derived data: `rm -rf ~/Library/Developer/Xcode/DerivedData`
- Check that entitlements file is properly linked in Build Settings

**"Missing com.apple.developer.applesignin entitlement":**
- The entitlements file isn't properly added to the target
- Check Build Settings → Code Signing Entitlements

**Works in simulator but not on device:**
- Need to configure App ID in Apple Developer Portal
- Ensure provisioning profile includes Sign in with Apple

## Verification

After setup, the app should:
1. Show the Apple Sign In button
2. When tapped, show the Apple authorization sheet
3. Complete sign in successfully
4. No error 1000

## Current Implementation

The app uses SwiftUI's `SignInWithAppleButton` which handles presentation automatically. The implementation:
- Requests email and full name scopes
- Extracts identity token and authorization code
- Sends to backend at `/auth/apple-signin`
- Stores session in keychain on success

## Backend Requirements

The backend must have an endpoint at `/auth/apple-signin` that accepts:
```json
{
  "identity_token": "string",
  "authorization_code": "string",
  "full_name": "string (optional)",
  "household_token": "string (optional)"
}
```

And returns:
```json
{
  "sessionToken": "string",
  "userId": "string",
  "householdId": "string",
  "email": "string",
  "householdName": "string (optional)"
}
```
