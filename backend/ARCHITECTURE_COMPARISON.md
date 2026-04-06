# Authentication Architecture Comparison

**Date:** 2026-04-06
**Status:** DECISION REQUIRED
**Documents:**
- Security Architecture: `/backend/AUTH_SECURITY_ARCHITECTURE.md` (security-reviewer, Task #3)
- Multi-Tenant Design: `/backend/MULTI_TENANT_DESIGN.md` (backend-dev, Task #2)

## Executive Summary

Two authentication architectures have been proposed with **significant conflicts** that must be resolved before implementation begins.

**Critical Decision Points:**
1. **JWT vs Session-Based Auth** (blocking issue - JWT cannot be revoked)
2. **Argon2id vs bcrypt** (security best practice vs familiar tool)
3. **RLS vs Middleware** (defense in depth vs simplicity)

## Side-by-Side Comparison

| Aspect | Security Arch (Task #3) | Multi-Tenant Design (Task #2) | Recommendation |
|--------|-------------------------|-------------------------------|----------------|
| **Authentication Method** | Session-based with HTTP-only cookies | JWT tokens (30-day expiration) | **Sessions** - JWT revocation is unsolved |
| **Password Hashing** | Argon2id (memory=65536, time=3) | bcrypt (work factor 12) | **Argon2id** - Industry standard 2025 |
| **Database Isolation** | Middleware filtering by household_id | PostgreSQL Row-Level Security (RLS) | **Debate** - Both valid, different trade-offs |
| **Sharing Tokens** | `secrets.token_urlsafe(24)` = 32 chars | "32 bytes hex" = 64 chars | **Either** - Both secure |
| **Token Expiration** | 7 days, one-time use | 7 days, one-time use | **Aligned** ✅ |
| **Session/Token Expiration** | 30 days sliding window | 30 days fixed | **Sliding** - Better UX |
| **Rate Limiting** | Defined (slowapi, per-endpoint limits) | Not mentioned | **Required** - Must add |
| **Audit Logging** | Defined (security events) | Not mentioned | **Required** - Must add |

## 1. JWT vs Session-Based Authentication

### Security Architecture (Sessions)

**Approach:**
- HTTP-only cookies with server-side sessions
- Session stored in PostgreSQL `sessions` table
- Session contains: user_id, household_id, expiration, metadata

**Advantages:**
✅ **Immediate revocation** - Delete session from DB, user loses access instantly
✅ **Simpler security model** - No token signing/verification
✅ **Smaller payload** - Just session ID in cookie
✅ **XSS protection** - HTTP-only flag prevents JavaScript access
✅ **Household switching** - Update session.household_id, no new token needed

**Disadvantages:**
❌ Server-side state (requires DB storage)
❌ Not suitable for microservices (not applicable here)

**Revocation Flow:**
```python
# User B removed from household
db.query(Session).filter(
    Session.user_id == user_b_id,
    Session.household_id == household_id
).delete()
# User B's next API call → 401 error (session not found)
```

---

### Multi-Tenant Design (JWT)

**Approach:**
- JWT tokens with 30-day expiration
- Token contains: user_id, household_id, email
- Signed with HS256 algorithm

**Advantages:**
✅ Stateless (no server-side storage)
✅ Good for microservices (not applicable here)
✅ Self-contained (all info in token)

**Disadvantages:**
❌ **CANNOT BE REVOKED** before expiration
❌ Household removal requires waiting up to 30 days
❌ Larger payload (entire JWT in every request)
❌ Requires token refresh mechanism
❌ Vulnerable to token theft (if not HTTP-only)

**Revocation Problem:**
```
User B removed from household at day 1
→ JWT still valid for 29 days
→ User B can still access household data
→ NO WAY to invalidate the JWT
```

**Possible Workarounds:**
1. **Token Blacklist** - Store revoked tokens in DB (defeats stateless purpose)
2. **Short Expiration** - 5-minute tokens + refresh tokens (complex, still has revocation window)
3. **Check Membership on Every Request** - Query household_members table (defeats stateless purpose, same as sessions)

**Conclusion:** JWT's revocation problem is a **production security vulnerability** for this use case.

---

## 2. Argon2id vs bcrypt

### Security Architecture (Argon2id)

**Approach:**
```python
from argon2 import PasswordHasher

ph = PasswordHasher(
    time_cost=3,
    memory_cost=65536,  # 64 MB
    parallelism=4,
    hash_len=32,
    salt_len=16
)
```

**Why Argon2id:**
- Winner of Password Hashing Competition (2015)
- **Memory-hard algorithm** - Resistant to GPU/ASIC attacks
- Recommended by OWASP 2025, NIST, and security researchers
- Modern standard (bcrypt is from 1999)

**Performance:** ~100-300ms per hash (same as bcrypt)

---

### Multi-Tenant Design (bcrypt)

**Approach:**
```python
import bcrypt

hashed = bcrypt.hashpw(password.encode(), bcrypt.gensalt(rounds=12))
```

**Why bcrypt:**
- Well-tested and proven (25+ years)
- Widely used and understood
- Built into many frameworks

**Issues:**
- Vulnerable to GPU acceleration (can crack 10x faster with modern GPUs)
- Not memory-hard (ASIC/FPGA attacks possible)
- Outdated standard (better alternatives exist)

**Performance:** ~100-300ms per hash (same as Argon2id)

---

**Conclusion:** Argon2id is the **modern best practice** with no downside. Use it.

---

## 3. RLS vs Middleware Filtering

### Multi-Tenant Design (PostgreSQL RLS)

**Approach:**
```sql
-- Enable RLS on all tables
ALTER TABLE ledger ENABLE ROW LEVEL SECURITY;

-- Policy: Users can only see their household data
CREATE POLICY household_isolation_policy ON ledger
    USING (
        household_id IN (
            SELECT household_id FROM household_members
            WHERE user_id = current_setting('app.current_user_id')::UUID
        )
    );
```

**Middleware sets user context:**
```python
@app.middleware("http")
async def set_user_context(request, call_next):
    user_id = get_user_id_from_token(request)
    db.execute(f"SET app.current_user_id = '{user_id}'")
    return await call_next(request)
```

**Advantages:**
✅ **Defense in depth** - Database enforces security even if app has bugs
✅ **Cannot bypass** - SQL injection can't circumvent RLS
✅ **Centralized policies** - Security rules in one place
✅ **Automatic enforcement** - Developers can't forget to filter

**Disadvantages:**
❌ **High complexity** - Requires understanding PostgreSQL RLS
❌ **Debugging difficulty** - "Why is this query empty?" hard to diagnose
❌ **Performance overhead** - Subquery on every row access
❌ **Testing complexity** - Requires real database (can't mock)
❌ **Failure mode** - If middleware fails to set user_id, ALL queries fail (app crash)
❌ **Silent failures** - Setting user context can fail without error

---

### Security Architecture (Middleware Filtering)

**Approach:**
```python
@app.middleware("http")
async def enforce_household_isolation(request, call_next):
    session = get_session_from_cookie(request)
    if session:
        request.state.household_id = session.household_id
        request.state.user_id = session.user_id
    return await call_next(request)
```

**Every query filters explicitly:**
```python
# CORRECT
entries = db.query(LedgerEntry).filter(
    LedgerEntry.household_id == request.state.household_id,
    LedgerEntry.year == year
).all()

# WRONG - Security violation (linter can catch this)
entries = db.query(LedgerEntry).filter(
    LedgerEntry.year == year
).all()
```

**Advantages:**
✅ **Simple and explicit** - Clear what's happening
✅ **Easy to debug** - Errors are in application code
✅ **Fast** - No subquery overhead
✅ **Testable** - Can mock request.state.household_id
✅ **Graceful failure** - Forgotten filter = security bug but app works (easier to catch in testing)

**Disadvantages:**
❌ **Relies on developers** - Must remember to filter (mitigated by code review, linting, security checklist)
❌ **Application-level only** - Not database-enforced
❌ **No protection against SQL injection bypass** (but we use ORM, not raw SQL)

---

**Conclusion:** This is a **legitimate trade-off**. Both approaches are valid.

**Recommendation:**
- **If team is experienced with PostgreSQL:** RLS provides defense in depth
- **If team prefers simplicity:** Middleware is easier to implement and debug
- **Hybrid approach:** Use BOTH (middleware for clarity, RLS for defense in depth)

---

## 4. Missing Security Features

Both architectures should include (currently only in Security Architecture):

1. **Rate Limiting**
   - Login: 5 attempts/minute
   - Signup: 3 attempts/hour
   - Invite send: 5/day
   - Token redemption: 10/hour

2. **Audit Logging**
   - Failed login attempts
   - Household membership changes
   - Invite token creation/redemption
   - Security events

3. **HTTPS Enforcement**
   - Redirect HTTP to HTTPS
   - Secure cookie flags
   - HSTS headers

4. **Input Validation**
   - Pydantic schemas for all endpoints
   - Email format validation
   - Password strength requirements

---

## 5. Recommendations

### Critical (Must Decide Before Implementation)

**Decision 1: JWT vs Sessions**

| Option | Pros | Cons | Recommendation |
|--------|------|------|----------------|
| **Sessions** | Immediate revocation, simpler | Server-side state | ✅ **RECOMMENDED** |
| JWT + Blacklist | Familiar to devs | Defeats stateless purpose | ❌ Don't use |
| JWT + Short Expiry | Stateless | Complex refresh flow, still has revocation window | ❌ Don't use |

**Verdict:** Use **session-based auth**. JWT's inability to revoke is a production security flaw for this use case.

---

**Decision 2: Argon2id vs bcrypt**

| Option | Pros | Cons | Recommendation |
|--------|------|------|----------------|
| **Argon2id** | Modern standard, GPU-resistant | Less familiar | ✅ **RECOMMENDED** |
| bcrypt | Well-known, proven | Vulnerable to GPU attacks | ⚠️ Adequate but not ideal |

**Verdict:** Use **Argon2id**. Same performance, better security, modern best practice.

---

**Decision 3: RLS vs Middleware**

| Option | Pros | Cons | Recommendation |
|--------|------|------|----------------|
| **RLS** | Defense in depth, automatic | Complex, hard to debug | ✅ If team is experienced |
| **Middleware** | Simple, explicit, debuggable | Requires discipline | ✅ If team prefers simplicity |
| **Both (Hybrid)** | Best security, clear code | More work | ✅ **RECOMMENDED** |

**Verdict:** Use **both RLS and middleware** (belt and suspenders approach):
- Middleware sets `request.state.household_id` and filters queries (clear, explicit)
- RLS provides database-level enforcement (defense in depth)
- Best of both worlds

---

### Implementation Plan (If Using Recommendations)

**Phase 1: Core Auth**
1. ✅ Create `users`, `households`, `household_members` tables (keep from both designs)
2. ✅ Create `sessions` table (Security Architecture)
3. ✅ Implement Argon2id password hashing (Security Architecture)
4. ✅ Implement session management with HTTP-only cookies (Security Architecture)
5. ✅ Build `/auth/signup`, `/auth/login`, `/auth/logout` endpoints

**Phase 2: Database Isolation**
1. ✅ Add `household_id` to existing tables (both designs agree)
2. ✅ Create middleware to set `request.state.household_id` (Security Architecture)
3. ✅ Update all queries to filter by `household_id` (Security Architecture)
4. ✅ Enable PostgreSQL RLS policies (Multi-Tenant Design)
5. ✅ Test both middleware and RLS enforcement

**Phase 3: Household Sharing**
1. ✅ Create `household_invites` table (renaming from `sharing_tokens`)
2. ✅ Implement token generation with `secrets.token_urlsafe(24)`
3. ✅ Build email sending service
4. ✅ Create `/households/send_invite`, `/households/join`, `/households/leave` endpoints

**Phase 4: Security Hardening**
1. ✅ Add rate limiting (slowapi)
2. ✅ Add audit logging
3. ✅ Security testing and penetration test
4. ✅ Code review with security checklist

---

## 6. Open Questions for Team Decision

1. **JWT vs Sessions:** Can we agree on sessions for immediate revocation capability?
2. **Argon2id vs bcrypt:** Any reason NOT to use the modern standard?
3. **RLS vs Middleware:** Do we want defense in depth (RLS) or simplicity (middleware only)? Or both?
4. **Email service:** Which provider? (SendGrid, AWS SES, Mailgun)
5. **Email verification:** Required for MVP or defer to Phase 2?

---

## 7. Next Steps

**BLOCKER: Cannot proceed with Task #4 (backend auth) or Task #12 (migrations) until we decide:**

1. **Session-based auth** vs JWT
2. **Argon2id** vs bcrypt
3. **RLS, middleware, or both**

**Recommendation:**
- Team-lead to schedule quick discussion
- Security-reviewer and backend-dev to align on approach
- Update one of the architecture documents as the **canonical design**
- Proceed with implementation

---

## 8. Summary Table

| Question | Security Arch | Multi-Tenant Design | Recommended Decision |
|----------|---------------|---------------------|----------------------|
| Auth Method | Sessions | JWT | **Sessions** |
| Password Hash | Argon2id | bcrypt | **Argon2id** |
| Isolation | Middleware | RLS | **Both (Hybrid)** |
| Sharing Tokens | `token_urlsafe(24)` | "32 bytes hex" | **`token_urlsafe(24)`** |
| Rate Limiting | Defined | Missing | **Add to design** |
| Audit Logging | Defined | Missing | **Add to design** |
| Token Expiry | 7 days | 7 days | **Aligned** ✅ |
| Session Expiry | 30 days sliding | 30 days fixed | **Sliding** |

---

**Document prepared by:** security-reviewer
**Status:** Pending team decision
**Blocking:** Tasks #4, #5, #6, #12
