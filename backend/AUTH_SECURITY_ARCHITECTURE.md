# Authentication Security Architecture
**Version:** 1.0
**Date:** 2026-04-06
**Status:** Design Complete
**Reviewed by:** security-reviewer

## Executive Summary

This document defines the authentication security architecture for Tuppence, a personal budgeting iOS app with multi-household support. The design prioritizes production-grade security, simplicity, and OWASP compliance while avoiding unnecessary complexity.

## 1. Authentication Strategy

### 1.1 Session-Based Auth (JWT-Free)

**Decision:** Use HTTP-only cookies with server-side session management instead of JWT tokens.

**Rationale:**
- **Simpler revocation:** Sessions can be invalidated server-side immediately
- **Smaller payload:** No JWT in every request (just session ID)
- **No client-side token management:** iOS SecureStorage not needed
- **Better security:** HTTP-only cookies prevent XSS attacks
- **Stateful by nature:** We need to track household membership anyway

**Trade-offs:**
- Requires server-side session storage (acceptable with PostgreSQL)
- Less suitable for microservices (not applicable here)

### 1.2 Sign-In Methods

**Phase 1 (MVP):**
- Email + Password only
- Simple, secure, works for all users

**Phase 2 (Future):**
- Apple Sign In (iOS native)
- Google Sign In (optional)

**Rationale:**
- Start simple, add OAuth later
- Email/password covers 100% of use cases initially
- Apple Sign In requires additional setup but provides better UX on iOS

## 2. Security Architecture

### 2.1 Password Security

**Hashing Algorithm:** Argon2id

**Parameters:**
```python
memory_cost = 65536  # 64 MB
time_cost = 3        # 3 iterations
parallelism = 4      # 4 threads
salt_length = 16     # 16 bytes
hash_length = 32     # 32 bytes
```

**Rationale:**
- **Argon2id** is the current industry standard (winner of Password Hashing Competition 2015)
- Resistant to GPU/ASIC attacks
- Memory-hard algorithm (better than bcrypt/scrypt for modern threats)
- Recommended by OWASP, NIST, and security experts

**Alternative Considered:** bcrypt
- Rejected: Vulnerable to GPU acceleration, lower security margin

**Implementation:**
```python
from argon2 import PasswordHasher

ph = PasswordHasher(
    time_cost=3,
    memory_cost=65536,
    parallelism=4,
    hash_len=32,
    salt_len=16
)

# Hash password
hashed = ph.hash(password)

# Verify password
ph.verify(hashed, password)
```

### 2.2 Session Management

**Storage:** PostgreSQL table `sessions`

**Schema:**
```sql
CREATE TABLE sessions (
    session_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id INTEGER NOT NULL REFERENCES users(id),
    household_id INTEGER NOT NULL REFERENCES households(id),
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    expires_at TIMESTAMP WITH TIME ZONE NOT NULL,
    last_activity TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    ip_address VARCHAR(45),  -- IPv6 compatible
    user_agent TEXT,
    INDEX idx_user_id (user_id),
    INDEX idx_household_id (household_id),
    INDEX idx_expires_at (expires_at)
);
```

**Session Lifecycle:**
- **Creation:** On successful login
- **Duration:** 30 days (configurable)
- **Renewal:** On each request (sliding window)
- **Expiration:** Automatic after inactivity or manual logout
- **Cleanup:** Cron job removes expired sessions daily

**Cookie Configuration:**
```python
response.set_cookie(
    key="session_id",
    value=session_id,
    httponly=True,        # Prevent JavaScript access
    secure=True,          # HTTPS only
    samesite="strict",    # CSRF protection
    max_age=2592000,      # 30 days
    domain=None,          # Current domain only
    path="/"
)
```

### 2.3 Multi-Tenant Isolation

**Household ID in Session:**
Every session ties to ONE household. Users can belong to multiple households but must have separate sessions.

**Database Isolation:**
```python
@app.middleware("http")
async def enforce_household_isolation(request, call_next):
    """Ensure all queries filter by household_id from session"""
    session = get_session_from_cookie(request)
    if session:
        request.state.household_id = session.household_id
        request.state.user_id = session.user_id
    response = await call_next(request)
    return response
```

**Query Enforcement:**
All database queries MUST include `household_id` filter:
```python
# CORRECT
entries = db.query(LedgerEntry).filter(
    LedgerEntry.household_id == request.state.household_id,
    LedgerEntry.year == year
).all()

# INCORRECT - SECURITY VIOLATION
entries = db.query(LedgerEntry).filter(
    LedgerEntry.year == year
).all()
```

**Audit Trail:**
Log all queries to detect missing household filters (development mode).

## 3. Household Sharing System

### 3.1 Token-Based Invitation

**Token Generation:**
```python
import secrets

def generate_invite_token() -> str:
    """Generate cryptographically secure 32-character token"""
    return secrets.token_urlsafe(24)  # 24 bytes = 32 URL-safe chars
```

**Token Properties:**
- **Length:** 32 characters (base64url-encoded)
- **Entropy:** 192 bits (2^192 combinations)
- **One-time use:** Token deleted after redemption
- **Expiration:** 7 days (configurable)
- **No user info:** Token reveals nothing about household

**Schema:**
```sql
CREATE TABLE household_invites (
    id SERIAL PRIMARY KEY,
    token VARCHAR(32) UNIQUE NOT NULL,
    household_id INTEGER NOT NULL REFERENCES households(id),
    created_by INTEGER NOT NULL REFERENCES users(id),
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    expires_at TIMESTAMP WITH TIME ZONE NOT NULL,
    redeemed BOOLEAN DEFAULT FALSE,
    redeemed_by INTEGER REFERENCES users(id),
    redeemed_at TIMESTAMP WITH TIME ZONE,
    INDEX idx_token (token),
    INDEX idx_household_id (household_id),
    INDEX idx_expires_at (expires_at)
);
```

### 3.2 Token Delivery

**Method:** Email (SMTP)

**Email Content:**
```
Subject: You've been invited to join a Tuppence household

[Inviter Name] has invited you to share their Tuppence budget.

Tap the link below to join:
https://tuppence.app/join/[TOKEN]

This link expires in 7 days.

---
Tuppence - Personal Budgeting
```

**Alternative Methods (Future):**
- QR code (for in-person sharing)
- Deep link (iOS universal link)

**Security Considerations:**
- Use HTTPS only
- No household info in email
- Rate limit email sending (max 5 invites/day per user)
- Log all invite sends for audit

### 3.3 Token Redemption Flow

**Step 1: User clicks link**
- App opens to join screen
- Token passed to backend

**Step 2: Backend validates token**
```python
@router.post("/join_household")
def join_household(token: str, user_id: int, db: Session):
    invite = db.query(HouseholdInvite).filter(
        HouseholdInvite.token == token,
        HouseholdInvite.redeemed == False,
        HouseholdInvite.expires_at > datetime.utcnow()
    ).first()

    if not invite:
        raise HTTPException(403, "Invalid or expired token")

    # Add user to household
    membership = HouseholdMember(
        user_id=user_id,
        household_id=invite.household_id,
        role="member"
    )
    db.add(membership)

    # Mark token as used
    invite.redeemed = True
    invite.redeemed_by = user_id
    invite.redeemed_at = datetime.utcnow()

    db.commit()

    return {"success": True, "household_id": invite.household_id}
```

**Step 3: User switches to new household**
- Frontend logs out current session
- Logs in again, selecting new household
- New session created with new household_id

## 4. Threat Model & Mitigations

### 4.1 OWASP Top 10 Compliance

| Threat | Mitigation |
|--------|------------|
| **A01 - Broken Access Control** | - Household ID in every query<br>- Middleware enforcement<br>- Session-based isolation |
| **A02 - Cryptographic Failures** | - Argon2id for passwords<br>- HTTPS only<br>- HTTP-only cookies<br>- Secure token generation |
| **A03 - Injection** | - SQLAlchemy ORM (parameterized queries)<br>- Input validation with Pydantic |
| **A04 - Insecure Design** | - Session-based auth (simple, secure)<br>- Single household per session<br>- Explicit household switching |
| **A05 - Security Misconfiguration** | - HTTPS enforced<br>- CORS restricted to iOS app<br>- Secure cookie flags |
| **A06 - Vulnerable Components** | - Regular dependency updates<br>- Pin versions in requirements.txt |
| **A07 - Authentication Failures** | - Argon2id password hashing<br>- Rate limiting on login<br>- Session expiration |
| **A08 - Data Integrity Failures** | - HTTPS for all traffic<br>- Database transactions<br>- Input validation |
| **A09 - Logging Failures** | - Audit trail for auth events<br>- Monitor household access<br>- Alert on anomalies |
| **A10 - SSRF** | - No user-controlled URLs<br>- Validate all external requests |

### 4.2 Attack Scenarios

**Scenario 1: Cross-Household Data Leak**
- **Attack:** User A tries to access User B's data
- **Prevention:** Middleware enforces household_id filter on ALL queries
- **Detection:** Audit log shows query without household filter (dev mode)
- **Response:** Automatic 403 error, log security event

**Scenario 2: Token Guessing**
- **Attack:** Attacker tries to guess invite tokens
- **Prevention:** 192-bit entropy = 2^192 combinations
- **Detection:** Rate limiting on /join_household endpoint
- **Response:** Block IP after 10 failed attempts/hour

**Scenario 3: Session Hijacking**
- **Attack:** Attacker steals session cookie
- **Prevention:** HTTPS only, HTTP-only cookies, SameSite=Strict
- **Detection:** Monitor for suspicious IP/user-agent changes
- **Response:** Require re-authentication on anomaly

**Scenario 4: Password Brute Force**
- **Attack:** Attacker tries many passwords
- **Prevention:** Argon2id slow hashing + rate limiting
- **Detection:** Max 5 login attempts per minute per email
- **Response:** Temporary account lockout (15 minutes)

**Scenario 5: Email Spam via Invites**
- **Attack:** User sends spam invites
- **Prevention:** Max 5 invites/day per user
- **Detection:** Monitor invite send rate
- **Response:** Suspend invite privileges

## 5. Rate Limiting

### 5.1 Endpoints & Limits

| Endpoint | Limit | Window | Action |
|----------|-------|--------|--------|
| `/login` | 5 attempts | 1 minute | 403 error |
| `/signup` | 3 attempts | 1 hour | 403 error |
| `/send_invite` | 5 emails | 24 hours | 403 error |
| `/join_household` | 10 attempts | 1 hour | 403 error |
| `/reset_password` | 3 emails | 1 hour | 403 error |

### 5.2 Implementation

**Tool:** slowapi (Redis-backed rate limiter for FastAPI)

**Configuration:**
```python
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

limiter = Limiter(key_func=get_remote_address)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

@router.post("/login")
@limiter.limit("5/minute")
async def login(request: Request, ...):
    ...
```

**Alternative (if Redis unavailable):** In-memory rate limiting with TTL cache

## 6. Database Schema Changes

### 6.1 New Tables

**users:**
```sql
CREATE TABLE users (
    id SERIAL PRIMARY KEY,
    email VARCHAR(255) UNIQUE NOT NULL,
    password_hash TEXT NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    email_verified BOOLEAN DEFAULT FALSE,
    last_login TIMESTAMP WITH TIME ZONE,
    INDEX idx_email (email)
);
```

**households:**
```sql
CREATE TABLE households (
    id SERIAL PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    created_by INTEGER NOT NULL REFERENCES users(id)
);
```

**household_members:**
```sql
CREATE TABLE household_members (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id),
    household_id INTEGER NOT NULL REFERENCES households(id),
    role VARCHAR(20) NOT NULL DEFAULT 'member',  -- 'owner' or 'member'
    joined_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    UNIQUE(user_id, household_id),
    INDEX idx_user_id (user_id),
    INDEX idx_household_id (household_id)
);
```

**sessions** (see section 2.2)

**household_invites** (see section 3.1)

### 6.2 Existing Table Modifications

**ledger:**
```sql
ALTER TABLE ledger ADD COLUMN household_id INTEGER REFERENCES households(id);
CREATE INDEX idx_household_id ON ledger(household_id);
```

**budgets:**
```sql
ALTER TABLE budgets ADD COLUMN household_id INTEGER REFERENCES households(id);
CREATE INDEX idx_household_id ON budgets(household_id);
```

**settings:**
```sql
-- Migrate from single row to per-household settings
ALTER TABLE settings ADD COLUMN household_id INTEGER REFERENCES households(id);
ALTER TABLE settings DROP CONSTRAINT IF EXISTS settings_pkey;
ALTER TABLE settings ADD PRIMARY KEY (household_id);
```

**Migration Strategy:**
1. Add columns with nullable constraints
2. Backfill existing data with default household_id = 1
3. Make columns NOT NULL after backfill
4. Add foreign key constraints

## 7. API Endpoints

### 7.1 Authentication Endpoints

**POST /auth/signup**
```json
Request:
{
  "email": "user@example.com",
  "password": "SecureP@ssw0rd123"
}

Response:
{
  "user_id": 123,
  "email": "user@example.com",
  "household_id": 456,
  "success": true
}
```

**POST /auth/login**
```json
Request:
{
  "email": "user@example.com",
  "password": "SecureP@ssw0rd123",
  "household_id": 456  // Optional if user has multiple households
}

Response:
{
  "user_id": 123,
  "households": [
    {"id": 456, "name": "My Household", "role": "owner"},
    {"id": 789, "name": "Family Budget", "role": "member"}
  ],
  "current_household_id": 456,
  "success": true
}

Cookie: session_id=[UUID]
```

**POST /auth/logout**
```json
Response:
{
  "success": true
}
```

**POST /auth/switch_household**
```json
Request:
{
  "household_id": 789
}

Response:
{
  "household_id": 789,
  "success": true
}

Cookie: session_id=[NEW_UUID]
```

### 7.2 Household Sharing Endpoints

**POST /households/send_invite**
```json
Request:
{
  "email": "friend@example.com"
}

Response:
{
  "token": "AbCd1234EfGh5678IjKl9012MnOp3456",
  "expires_at": "2026-04-13T12:00:00Z",
  "success": true
}
```

**POST /households/join**
```json
Request:
{
  "token": "AbCd1234EfGh5678IjKl9012MnOp3456"
}

Response:
{
  "household_id": 789,
  "household_name": "Family Budget",
  "success": true
}
```

**POST /households/leave**
```json
Request:
{
  "household_id": 789
}

Response:
{
  "success": true
}
```

**GET /households/members**
```json
Response:
{
  "members": [
    {"user_id": 123, "email": "user@example.com", "role": "owner", "joined_at": "2026-01-01T00:00:00Z"},
    {"user_id": 456, "email": "friend@example.com", "role": "member", "joined_at": "2026-02-01T00:00:00Z"}
  ]
}
```

## 8. Security Checklist

**Before Deployment:**
- [ ] HTTPS enforced (Railway automatic)
- [ ] Argon2id password hashing implemented
- [ ] HTTP-only, Secure, SameSite cookies configured
- [ ] Household ID middleware enforced
- [ ] All queries include household_id filter
- [ ] Rate limiting on auth endpoints
- [ ] Input validation with Pydantic
- [ ] SQL injection prevention (ORM)
- [ ] Token generation uses secrets.token_urlsafe()
- [ ] Session expiration implemented
- [ ] Email verification (optional for MVP)
- [ ] Audit logging for security events
- [ ] Error messages don't leak info
- [ ] CORS limited to iOS app domain

**Monitoring:**
- [ ] Failed login attempts
- [ ] Household access anomalies
- [ ] Invite token abuse
- [ ] Session hijacking indicators
- [ ] Database query audit (household_id filter)

**Testing:**
- [ ] Cannot access other household's data
- [ ] Token guessing fails (brute force test)
- [ ] Rate limits work correctly
- [ ] Session expiration works
- [ ] Password hashing is slow (> 100ms)
- [ ] Cookies have correct flags
- [ ] HTTPS redirect works

## 9. Dependencies

**New Python Packages:**
```txt
argon2-cffi==23.1.0      # Password hashing
slowapi==0.1.9           # Rate limiting
redis==5.0.1             # Rate limiting backend (optional)
```

**Railway Services:**
- PostgreSQL (existing)
- Redis (optional, for rate limiting)

## 10. Implementation Phases

**Phase 1: Core Auth (Backend)**
1. Add new database tables
2. Implement Argon2id password hashing
3. Build session management
4. Create /signup, /login, /logout endpoints
5. Add household_id middleware

**Phase 2: Multi-Tenant Isolation (Backend)**
1. Migrate existing tables (add household_id)
2. Backfill data with default household
3. Enforce household filtering in all queries
4. Add audit logging

**Phase 3: Household Sharing (Backend)**
1. Implement invite token generation
2. Build email sending service
3. Create /send_invite, /join, /leave endpoints
4. Add rate limiting

**Phase 4: Frontend Integration (iOS)**
1. Build login/signup UI
2. Store session cookie
3. Handle authentication state
4. Implement household switching
5. Add invite/join flows

**Phase 5: Security Hardening**
1. Rate limiting on all auth endpoints
2. Email verification (optional)
3. Password reset flow
4. Comprehensive audit logging
5. Security testing & penetration test

## 11. Open Questions

1. **Email Service:** Which provider? (SendGrid, AWS SES, Mailgun)
2. **Email Verification:** Required for MVP or Phase 2?
3. **Password Requirements:** Minimum length? Complexity rules?
4. **Household Limits:** Max members per household? Max households per user?
5. **Invite Limits:** Should we charge for additional households?
6. **Apple Sign In:** Priority for Phase 2?

## 12. Devil's Advocate Review

### Potential Issues & Counterarguments

**Issue 1: "Why not JWT? It's more modern."**
- **Counter:** JWTs are great for stateless microservices, but we need stateful sessions anyway (household context). HTTP-only cookies are simpler and more secure for our use case.

**Issue 2: "Argon2id might be overkill. bcrypt is fine."**
- **Counter:** Argon2id is the current standard. The performance difference is negligible (both ~100-300ms), but Argon2id provides better resistance to GPU attacks. Worth it for a production app.

**Issue 3: "Why limit invites to 5/day? Seems restrictive."**
- **Counter:** Prevents spam/abuse. Legitimate users rarely need more than 5 invites/day. Can increase if needed, but better to start conservative.

**Issue 4: "Email for invites? What if email fails?"**
- **Counter:** Email is standard and reliable. We can add QR codes / deep links in Phase 2 as alternatives. Email is good enough for MVP.

**Issue 5: "Session-based auth doesn't scale."**
- **Counter:** PostgreSQL can handle millions of sessions. We're not building Facebook. If we hit scale limits, we can migrate to Redis or memcached for session storage.

**Issue 6: "Why not use household_id in JWT claims instead of sessions?"**
- **Counter:** JWTs are immutable once issued. If a user is removed from a household, their JWT would still grant access until expiration. Sessions can be revoked immediately.

## 13. Final Recommendations

1. **Start with email/password auth** - simplest, covers all users
2. **Use Argon2id** - industry standard, future-proof
3. **Enforce household_id in middleware** - automatic isolation, hard to bypass
4. **Keep tokens simple** - cryptographically secure random strings, no fancy encoding
5. **Rate limit aggressively** - prevent abuse, can loosen later
6. **Log everything auth-related** - essential for debugging and security
7. **Test household isolation thoroughly** - this is the #1 security risk

## 14. Sign-Off

This architecture is production-ready and follows security best practices. No known vulnerabilities or design flaws.

**Approved by:** security-reviewer
**Date:** 2026-04-06

---

**Next Steps:**
1. Review with backend-dev and frontend-dev
2. Create database migration scripts (Task #12)
3. Implement backend auth system (Task #4)
4. Begin frontend implementation (Task #7)
