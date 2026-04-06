# Multi-Tenant Database Architecture Design

## Overview
Design for adding authentication and multi-tenant household support to Tuppence while maintaining database isolation and security.

## Architecture Decision: PostgreSQL Schemas (Row-Level Security)

### Chosen Approach: **Shared Database with Row-Level Security (RLS)**

After evaluating options, we'll use a **single PostgreSQL database with Row-Level Security** for multi-tenancy:

**Rationale:**
1. **Railway Constraints**: Railway pricing makes multiple databases expensive; single DB with RLS is cost-effective
2. **Simplicity**: Single connection pool, simpler migrations, easier backups
3. **Security**: PostgreSQL RLS provides robust database-level isolation
4. **Scalability**: Can scale to thousands of households in single database
5. **Performance**: Modern PostgreSQL handles RLS efficiently with proper indexing

**Trade-offs:**
- ❌ No true physical isolation (all data in one DB)
- ❌ Slightly more complex queries (must filter by household_id)
- ✅ Simple deployment and migration management
- ✅ Cost-effective on Railway
- ✅ Easy to backup and restore
- ✅ Built-in PostgreSQL security features

## Database Schema Design

### New Tables

#### 1. `users` Table
Stores user accounts with authentication credentials.

```sql
CREATE TABLE users (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    email VARCHAR(255) UNIQUE NOT NULL,
    password_hash VARCHAR(255),  -- NULL for Apple Sign In users
    apple_id VARCHAR(255) UNIQUE,  -- NULL for email/password users
    full_name VARCHAR(255),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    last_login TIMESTAMP WITH TIME ZONE,
    is_active BOOLEAN DEFAULT TRUE,

    -- Constraints
    CONSTRAINT check_auth_method CHECK (
        (password_hash IS NOT NULL AND apple_id IS NULL) OR
        (password_hash IS NULL AND apple_id IS NOT NULL)
    )
);

CREATE INDEX idx_users_email ON users(email);
CREATE INDEX idx_users_apple_id ON users(apple_id) WHERE apple_id IS NOT NULL;
CREATE INDEX idx_users_created_at ON users(created_at);
```

#### 2. `households` Table
Represents shared budget households (1 or more users).

```sql
CREATE TABLE households (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(255) NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX idx_households_created_at ON households(created_at);
```

#### 3. `household_members` Table
Links users to households (many-to-many).

```sql
CREATE TABLE household_members (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    household_id UUID NOT NULL REFERENCES households(id) ON DELETE CASCADE,
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    role VARCHAR(50) NOT NULL DEFAULT 'member',  -- 'owner' or 'member'
    joined_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),

    UNIQUE(household_id, user_id)
);

CREATE INDEX idx_household_members_household ON household_members(household_id);
CREATE INDEX idx_household_members_user ON household_members(user_id);
```

#### 4. `sharing_tokens` Table
Stores one-time tokens for inviting users to households.

```sql
CREATE TABLE sharing_tokens (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    household_id UUID NOT NULL REFERENCES households(id) ON DELETE CASCADE,
    token VARCHAR(64) UNIQUE NOT NULL,  -- Cryptographically secure random token
    created_by UUID NOT NULL REFERENCES users(id),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    expires_at TIMESTAMP WITH TIME ZONE NOT NULL,
    used_at TIMESTAMP WITH TIME ZONE,
    used_by UUID REFERENCES users(id),
    is_active BOOLEAN DEFAULT TRUE,

    CONSTRAINT check_token_not_expired CHECK (expires_at > created_at)
);

CREATE INDEX idx_sharing_tokens_token ON sharing_tokens(token) WHERE is_active = TRUE;
CREATE INDEX idx_sharing_tokens_household ON sharing_tokens(household_id);
CREATE INDEX idx_sharing_tokens_expires ON sharing_tokens(expires_at) WHERE is_active = TRUE;
```

### Modified Existing Tables

All existing tables need a `household_id` column for multi-tenancy:

#### `ledger` (LedgerEntry)
```sql
ALTER TABLE ledger
    ADD COLUMN household_id UUID REFERENCES households(id) ON DELETE CASCADE,
    ADD CONSTRAINT ledger_household_not_null CHECK (household_id IS NOT NULL);

CREATE INDEX idx_ledger_household ON ledger(household_id);
CREATE INDEX idx_ledger_household_year ON ledger(household_id, year);
CREATE INDEX idx_ledger_household_budget_year ON ledger(household_id, budget_emoji, year);

-- Drop old user_id column (not needed with household model)
ALTER TABLE ledger DROP COLUMN user_id;
```

#### `budgets` (Budget)
```sql
ALTER TABLE budgets
    ADD COLUMN household_id UUID REFERENCES households(id) ON DELETE CASCADE,
    ADD CONSTRAINT budgets_household_not_null CHECK (household_id IS NOT NULL);

CREATE INDEX idx_budgets_household ON budgets(household_id);

-- Drop unique constraint on emoji (must be unique per household, not globally)
ALTER TABLE budgets DROP CONSTRAINT budgets_emoji_key;
CREATE UNIQUE INDEX idx_budgets_household_emoji ON budgets(household_id, emoji);

-- Drop old user_id column
ALTER TABLE budgets DROP COLUMN user_id;
```

#### `categories` Table
**Decision**: Keep categories **global** (not household-specific).

Rationale:
- Categories are predefined and read-only
- Same 150 categories used across all households
- Simplifies AI categorization
- Reduces data duplication

**No changes needed** to `categories` table.

#### `text_category_cache` Table
Check if this needs household isolation:

```sql
-- Need to review this table - likely needs household_id too
```

#### `settings` Table
```sql
ALTER TABLE settings
    ADD COLUMN household_id UUID REFERENCES households(id) ON DELETE CASCADE,
    ADD CONSTRAINT settings_household_not_null CHECK (household_id IS NOT NULL);

-- Change primary key from id to household_id (one settings row per household)
ALTER TABLE settings DROP CONSTRAINT settings_pkey;
ALTER TABLE settings ADD PRIMARY KEY (household_id);
ALTER TABLE settings DROP COLUMN id;
```

## Row-Level Security (RLS) Policies

Enable RLS on all household-scoped tables:

```sql
-- Enable RLS
ALTER TABLE ledger ENABLE ROW LEVEL SECURITY;
ALTER TABLE budgets ENABLE ROW LEVEL SECURITY;
ALTER TABLE settings ENABLE ROW LEVEL SECURITY;
ALTER TABLE households ENABLE ROW LEVEL SECURITY;
ALTER TABLE household_members ENABLE ROW LEVEL SECURITY;
ALTER TABLE sharing_tokens ENABLE ROW LEVEL SECURITY;

-- RLS Policy: Users can only access their household data
CREATE POLICY household_isolation_policy ON ledger
    USING (
        household_id IN (
            SELECT household_id
            FROM household_members
            WHERE user_id = current_setting('app.current_user_id')::UUID
        )
    );

CREATE POLICY household_isolation_policy ON budgets
    USING (
        household_id IN (
            SELECT household_id
            FROM household_members
            WHERE user_id = current_setting('app.current_user_id')::UUID
        )
    );

CREATE POLICY household_isolation_policy ON settings
    USING (
        household_id IN (
            SELECT household_id
            FROM household_members
            WHERE user_id = current_setting('app.current_user_id')::UUID
        )
    );

CREATE POLICY household_isolation_policy ON households
    USING (
        id IN (
            SELECT household_id
            FROM household_members
            WHERE user_id = current_setting('app.current_user_id')::UUID
        )
    );

CREATE POLICY household_members_policy ON household_members
    USING (
        user_id = current_setting('app.current_user_id')::UUID OR
        household_id IN (
            SELECT household_id
            FROM household_members
            WHERE user_id = current_setting('app.current_user_id')::UUID
        )
    );

CREATE POLICY sharing_tokens_policy ON sharing_tokens
    USING (
        household_id IN (
            SELECT household_id
            FROM household_members
            WHERE user_id = current_setting('app.current_user_id')::UUID
        )
    );
```

## Authentication Flow

### Registration Flow (Email/Password)
1. User submits email + password to `/auth/register`
2. Backend validates email uniqueness
3. Hash password with bcrypt (cost=12)
4. Create user record
5. Create default household for user
6. Add user as household owner
7. Return JWT token + household_id

### Login Flow (Email/Password)
1. User submits email + password to `/auth/login`
2. Backend validates credentials
3. Load user's household memberships
4. Generate JWT token with user_id + household_id (default household)
5. Update last_login timestamp
6. Return JWT + user info + household list

### Apple Sign In Flow
1. iOS app handles Apple Sign In
2. App sends Apple ID token to `/auth/apple-signin`
3. Backend verifies token with Apple
4. Check if user exists by apple_id
5. If new user: create user + household
6. If existing: load household memberships
7. Return JWT + household info

### Token Sharing Flow
1. User A generates sharing token: `POST /households/{id}/share-token`
2. Backend generates cryptographically secure token (32 bytes, hex-encoded)
3. Store token with 7-day expiration
4. User A shares token code with User B (via text, QR code, etc.)
5. User B submits token: `POST /households/join?token={token}`
6. Backend validates token (exists, not expired, not used)
7. Add User B to household as member
8. Mark token as used
9. Return success + household info

## JWT Token Structure

```json
{
  "sub": "user_uuid",
  "household_id": "current_household_uuid",
  "email": "user@example.com",
  "exp": 1234567890,
  "iat": 1234567890
}
```

Token expiration: **30 days** (refresh required after expiration)

## Middleware Architecture

### Database Isolation Middleware
Every request sets the user context for RLS:

```python
@app.middleware("http")
async def set_user_context(request: Request, call_next):
    # Extract user_id from JWT
    user_id = get_user_id_from_token(request)

    if user_id:
        # Set PostgreSQL session variable for RLS
        db = get_db()
        db.execute(f"SET app.current_user_id = '{user_id}'")

    response = await call_next(request)
    return response
```

### Authentication Middleware
Protect endpoints requiring authentication:

```python
async def get_current_user(
    request: Request,
    db: Session = Depends(get_db)
) -> User:
    token = extract_jwt_from_header(request)
    payload = verify_jwt(token)
    user = db.query(User).filter(User.id == payload["sub"]).first()
    if not user or not user.is_active:
        raise HTTPException(status_code=401)
    return user
```

## Migration Strategy

### Phase 1: Add Multi-Tenant Schema (Backwards Compatible)
1. Create new tables: users, households, household_members, sharing_tokens
2. Add household_id columns to existing tables (nullable)
3. **Do not enable RLS yet**

### Phase 2: Migrate Existing Data
1. Create default household: "Legacy Household"
2. Set household_id on all existing ledger/budget/settings rows
3. Make household_id NOT NULL with constraint

### Phase 3: Enable RLS and Deploy
1. Deploy updated API with authentication endpoints
2. Enable RLS policies
3. Update frontend to require authentication

### Rollback Plan
If issues arise:
- Disable RLS policies
- Revert to old API without household filtering
- household_id columns remain but are ignored

## Security Considerations

### Password Security
- Hash with **bcrypt** (work factor 12)
- Alternative: **Argon2id** (more secure but slightly slower)
- Never log or expose password hashes

### Token Security
- JWT secret: 256-bit random key (stored in environment variable)
- Sharing tokens: 32-byte cryptographically secure random (256 bits)
- Use `secrets.token_urlsafe(32)` for token generation

### SQL Injection Prevention
- Use SQLAlchemy ORM (parameterized queries)
- Never concatenate user input into SQL

### Database Isolation
- RLS policies enforce household boundaries
- Even if application bug exists, database prevents cross-household access
- Regular security audits of RLS policies

### HTTPS Only
- Enforce HTTPS in production (Railway provides this)
- Set secure cookie flags for JWT

## Performance Considerations

### Connection Pooling
Current setup uses SQLAlchemy connection pooling:
- Pool size: 5 connections (default)
- Max overflow: 10 connections
- Pool pre-ping: enabled (verify connections)

**No changes needed** - RLS works with connection pooling.

### Indexing Strategy
All household-scoped queries include household_id in indexes:
- `idx_ledger_household_year`
- `idx_ledger_household_budget_year`
- `idx_budgets_household_emoji`

### Query Performance
- RLS policies use indexed columns (household_members.user_id)
- PostgreSQL query planner optimizes RLS subqueries
- Expected overhead: <5ms per query

## API Endpoints

### Authentication
- `POST /auth/register` - Email/password registration
- `POST /auth/login` - Email/password login
- `POST /auth/apple-signin` - Apple Sign In
- `POST /auth/refresh` - Refresh JWT token
- `POST /auth/logout` - Invalidate token (optional)

### Household Management
- `GET /households` - List user's households
- `POST /households` - Create new household
- `GET /households/{id}` - Get household details
- `PATCH /households/{id}` - Update household name
- `DELETE /households/{id}` - Delete household (owner only)
- `POST /households/{id}/share-token` - Generate sharing token
- `POST /households/join` - Join household with token
- `DELETE /households/{id}/members/{user_id}` - Remove member (owner only)
- `POST /households/{id}/leave` - Leave household

### User Profile
- `GET /users/me` - Get current user info
- `PATCH /users/me` - Update user profile
- `DELETE /users/me` - Delete account

## Environment Variables

New environment variables needed:

```bash
# JWT Configuration
JWT_SECRET_KEY=<256-bit-random-key>
JWT_ALGORITHM=HS256
JWT_EXPIRATION_DAYS=30

# Apple Sign In (if implementing)
APPLE_CLIENT_ID=<apple-client-id>
APPLE_TEAM_ID=<apple-team-id>
APPLE_KEY_ID=<apple-key-id>
APPLE_PRIVATE_KEY=<apple-private-key>

# Security
BCRYPT_ROUNDS=12
```

## Testing Strategy

### Unit Tests
- Password hashing/verification
- JWT generation/validation
- Token generation/validation
- RLS policy enforcement

### Integration Tests
- Full auth flow (register → login → API access)
- Household sharing flow
- Cross-household isolation verification
- Token expiration handling

### Security Tests
- Attempt cross-household data access
- Test SQL injection vectors
- Verify password hash security
- Test token replay attacks

## Open Questions for Team

1. **Apple Sign In Priority**: Should we implement Apple Sign In in MVP or defer to v2?
2. **Email Verification**: Should we require email verification for email/password accounts?
3. **Password Reset**: Should we implement password reset flow in MVP?
4. **Multi-Household UI**: Should iOS app support switching between multiple households?
5. **Token Format**: Should sharing tokens be simple codes (e.g., "ABC-123") or UUIDs?

## Next Steps

1. Get team approval on architecture ✅
2. Create database migration scripts (Task #12)
3. Implement User/Household models (Task #4)
4. Implement authentication endpoints (Task #4)
5. Implement token sharing system (Task #5)
6. Create database isolation middleware (Task #6)
7. Security audit (Task #11)
