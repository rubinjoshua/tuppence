# Row-Level Security (RLS) Migration Guide

## Overview

With the implementation of Row-Level Security (RLS), all database queries are automatically filtered by household membership. This document explains what has changed and what needs to be updated.

## How RLS Works

1. **Middleware** (`DatabaseIsolationMiddleware`) extracts `user_id` from JWT token
2. **Middleware** stores `user_id` in `request.state.user_id`
3. **Database dependency** (`get_db_with_rls`) sets PostgreSQL session variable:
   ```sql
   SET LOCAL app.current_user_id = 'user_id';
   ```
4. **RLS policies** (created in migration 005) automatically filter queries:
   ```sql
   -- Example: Ledger policy
   CREATE POLICY household_isolation_policy ON ledger
   USING (
       household_id IN (
           SELECT household_id
           FROM household_members
           WHERE user_id = current_setting('app.current_user_id', TRUE)::UUID
       )
   );
   ```
5. All queries to `ledger`, `budgets`, `settings`, etc. are automatically scoped to user's households

## What's Protected by RLS

These tables have RLS enabled:
- ✅ `ledger` - Transaction entries
- ✅ `budgets` - Budget definitions
- ✅ `settings` - Household settings
- ✅ `text_category_cache` - AI categorization cache
- ✅ `households` - Household records
- ✅ `household_members` - User-household relationships
- ✅ `sharing_tokens` - Invitation tokens

These tables are NOT protected (global):
- ❌ `categories` - Shared category list (read-only)
- ❌ `users` - User accounts (accessed via auth endpoints only)
- ❌ `refresh_tokens` - JWT refresh tokens (filtered by user_id directly)

## Changes Required for Existing Endpoints

### Option 1: Use RLS (Recommended)

Replace `Depends(get_db)` with `Depends(get_db_with_rls)` and add auth:

**Before:**
```python
@router.get("/amounts")
def get_amounts(db: Session = Depends(get_db)):
    # Queries return ALL data (insecure!)
    budgets = db.query(Budget).all()
    return budgets
```

**After:**
```python
from fastapi import Request
from app.dependencies.auth import get_current_user

@router.get("/amounts")
def get_amounts(
    request: Request,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db_with_rls)
):
    # Queries automatically filtered by household (secure!)
    budgets = db.query(Budget).all()
    return budgets
```

### Option 2: Manual Filtering (Not Recommended)

If you can't use RLS for some reason, manually filter by household:

```python
from app.dependencies.auth import get_current_user_and_household

@router.get("/amounts")
def get_amounts(
    user_household = Depends(get_current_user_and_household),
    db: Session = Depends(get_db)
):
    user, household = user_household
    # Manually filter by household_id
    budgets = db.query(Budget).filter(Budget.household_id == household.id).all()
    return budgets
```

## Endpoints That Need Updating

### Core Data Endpoints (app/api/routes.py)

1. **GET /amounts** - ✅ Needs auth + RLS
   - Returns budgets for current year
   - Must be scoped to user's household

2. **GET /monthly_budgets** - ✅ Needs auth + RLS
   - Returns monthly budget amounts
   - Must be scoped to user's household

3. **GET /ledger** - ✅ Needs auth + RLS
   - Returns ledger entries for month
   - Must be scoped to user's household

4. **GET /category_map** - ✅ Needs auth + RLS
   - Returns category breakdown
   - Must be scoped to user's household

5. **POST /make_spending** - ✅ Needs auth + RLS + household_id
   - Creates ledger entry
   - Must set `household_id` when creating entry

6. **DELETE /undo_spending/{uuid}** - ✅ Needs auth + RLS
   - Deletes ledger entry
   - RLS prevents deleting other household's entries

7. **POST /sync_budgets** - ✅ Needs auth + RLS + household_id
   - Syncs budgets from iOS
   - Must set `household_id` on budget records

8. **POST /sync_settings** - ✅ Needs auth + RLS + household_id
   - Syncs settings from iOS
   - Must use `household_id` as primary key

9. **POST /check_automations** - ✅ Needs auth + RLS
   - Runs monthly automation
   - Must be scoped to user's household

10. **GET /export_year** - ✅ Needs auth + RLS
    - Exports ledger for year
    - Must be scoped to user's household

11. **POST /archive_year** - ✅ Needs auth + RLS
    - Archives year
    - Must be scoped to user's household

### Auth Endpoints (app/api/auth.py)

These are already secure (don't need RLS):
- ✅ POST /auth/register
- ✅ POST /auth/login
- ✅ POST /auth/refresh
- ✅ POST /auth/logout

### Household Endpoints (app/api/household.py)

These are already secure (use `get_current_user`):
- ✅ GET /households
- ✅ POST /households
- ✅ GET /households/{id}
- ✅ PATCH /households/{id}
- ✅ POST /households/{id}/share-token
- ✅ POST /households/join
- ✅ POST /households/{id}/leave
- ✅ DELETE /households/{id}

## Example: Updating make_spending Endpoint

**Before (Single-tenant):**
```python
@router.post("/make_spending", response_model=MakeSpendingResponse)
async def make_spending(
    request: MakeSpendingRequest,
    db: Session = Depends(get_db)
):
    entry = LedgerEntry(
        amount=request.amount,
        currency=request.currency,
        budget_emoji=request.budget_emoji,
        datetime=dt,
        description_text=request.description_text,
        category=category,
        year=year
        # No household_id!
    )
    db.add(entry)
    db.commit()
    return MakeSpendingResponse(uuid=entry.uuid, category=category, success=True)
```

**After (Multi-tenant):**
```python
from fastapi import Request
from app.dependencies.auth import get_current_user_and_household

@router.post("/make_spending", response_model=MakeSpendingResponse)
async def make_spending(
    req: Request,
    request: MakeSpendingRequest,
    user_household = Depends(get_current_user_and_household),
    db: Session = Depends(get_db_with_rls)
):
    user, household = user_household

    entry = LedgerEntry(
        amount=request.amount,
        currency=request.currency,
        budget_emoji=request.budget_emoji,
        datetime=dt,
        description_text=request.description_text,
        category=category,
        year=year,
        household_id=household.id  # Set household_id!
    )
    db.add(entry)
    db.commit()
    return MakeSpendingResponse(uuid=entry.uuid, category=category, success=True)
```

## Testing RLS

### Manual Testing in psql

```sql
-- Set user context
SET app.current_user_id = 'user-uuid-here';

-- Query should only return data for user's households
SELECT * FROM ledger;
SELECT * FROM budgets;
SELECT * FROM settings;

-- Try to access another household's data (should return empty)
SELECT * FROM ledger WHERE household_id = 'other-household-uuid';
```

### Integration Testing

1. Create two users: User A and User B
2. User A creates spending entry
3. User B logs in
4. User B queries /ledger
5. Should NOT see User A's entry
6. User B joins User A's household
7. User B queries /ledger again
8. Should NOW see User A's entry

## Security Notes

1. **RLS is enforced at database level** - Even if app has bugs, database prevents cross-household access
2. **Session variable is scoped to connection** - Each request gets isolated variable
3. **Use SET LOCAL, not SET** - LOCAL ensures variable doesn't persist across pooled connections
4. **Always use get_current_user** - Ensures request is authenticated
5. **Always set household_id on INSERT** - RLS doesn't auto-set, only filters on SELECT/UPDATE/DELETE

## Performance Impact

- **Minimal overhead**: RLS policies use indexed columns (household_id, user_id)
- **Query planner optimization**: PostgreSQL optimizes RLS subqueries
- **Expected overhead**: <5ms per query
- **No changes to connection pooling**: Works with SQLAlchemy pooling

## Rollback Plan

If issues arise:

1. Disable RLS on tables:
   ```sql
   ALTER TABLE ledger DISABLE ROW LEVEL SECURITY;
   ALTER TABLE budgets DISABLE ROW LEVEL SECURITY;
   -- etc.
   ```

2. Revert to manual household_id filtering in application code

3. Run migration downgrade:
   ```bash
   alembic downgrade 004
   ```

## Next Steps

1. **Update all endpoints** in `/app/api/routes.py` to use auth + RLS
2. **Run integration tests** to verify isolation
3. **Security audit** to confirm no data leakage
4. **Performance testing** to measure RLS overhead
