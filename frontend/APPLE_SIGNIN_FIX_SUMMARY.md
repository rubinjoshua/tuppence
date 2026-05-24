# Apple Sign In Fix Summary

## Problem
Apple Sign In button doesn't work - Error 1000: "The operation couldn't be completed (comp.apple.AuthenticationServices.AuthorizationError erro 1000.)"

## Root Causes

### 1. Missing Xcode Configuration
- No "Sign in with Apple" capability enabled in Xcode
- No entitlements file configured

### 2. Missing Backend Endpoint
- Backend doesn't have `/auth/apple-signin` endpoint
- Frontend calls it but gets 404/network error

## What Was Fixed (Frontend)

### Files Created
1. **tuppence/tuppence.entitlements** - Apple Sign In entitlements
2. **APPLE_SIGNIN_SETUP.md** - Complete setup instructions
3. **Utils/AppleSignInHelper.swift** - Alternative implementation helper (if needed)

### Files Modified
1. **Views/LoginView.swift**
   - Added detailed error logging
   - Better error messages with setup instructions
   - Handles error 1000 specifically

2. **Views/SignupView.swift**
   - Same improvements as LoginView
   - Includes household token support

### Debug Logging Added
All Apple Sign In attempts now log:
- Authorization success/failure
- Credential extraction steps
- Error codes and domains
- User information (email, name)
- Clear indication of what step failed

## What Still Needs to Be Done

### 1. Xcode Configuration (User Action Required)
Follow instructions in `APPLE_SIGNIN_SETUP.md`:
1. Open project in Xcode
2. Add "Sign in with Apple" capability
3. Link entitlements file in Build Settings
4. Configure team and bundle ID

**Time estimate:** 5 minutes

### 2. Backend Implementation (Backend Developer)
Create endpoint: `POST /auth/apple-signin`

**Request body:**
```json
{
  "identity_token": "string",      // JWT from Apple
  "authorization_code": "string",   // One-time code from Apple
  "full_name": "string",           // Optional: first + last name
  "household_token": "string"      // Optional: join existing household
}
```

**Response:**
```json
{
  "sessionToken": "uuid-string",
  "userId": "uuid-string",
  "householdId": "uuid-string",
  "email": "string",
  "householdName": "string"
}
```

**Backend requirements:**
- Verify identity_token with Apple's public keys
- Extract user's Apple ID (sub claim from JWT)
- Check if user exists by Apple ID
  - If exists: login (create session)
  - If new: register (create user, household, session)
- Support household_token for joining existing households
- Return same format as `/auth/login` and `/auth/register`

**Dependencies needed:**
```python
pip install PyJWT cryptography
```

**Time estimate:** 1-2 hours

## Testing After Fix

1. **Xcode configuration:**
   - Build should succeed without errors
   - Check Build Settings shows entitlements file path
   - Check Signing & Capabilities shows "Sign in with Apple"

2. **Backend endpoint:**
   - Can hit `/auth/apple-signin` (not 404)
   - Returns proper error if token invalid
   - Creates user and session if token valid

3. **End-to-end flow:**
   - Tap Apple Sign In button
   - Apple authorization sheet appears
   - Complete authorization with Face ID/Touch ID
   - App logs in successfully
   - No error 1000

## Current Status
- ✅ Frontend code updated with logging and error handling
- ✅ Entitlements file created
- ✅ Setup documentation complete
- ⏳ Xcode configuration (user action needed)
- ⏳ Backend endpoint (backend dev needed)

## Files Changed
```
frontend/tuppence/tuppence/tuppence.entitlements (new)
frontend/tuppence/tuppence/Utils/AppleSignInHelper.swift (new)
frontend/APPLE_SIGNIN_SETUP.md (new)
frontend/APPLE_SIGNIN_FIX_SUMMARY.md (new)
frontend/tuppence/tuppence/Views/LoginView.swift (modified)
frontend/tuppence/tuppence/Views/SignupView.swift (modified)
```
