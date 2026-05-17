# Backend Multi-Tenancy Completion Brief

## Context

The frontend now requires user sign-in (email/password or Apple) and expects every user's data to be scoped to their household. The backend migration to multi-tenancy was started but only half-finished: budgets are fully scoped, but ledger/amounts/spending/settings are still global.

There may also be a production outage — `https://tuppence-production-8de5.up.railway.app/health` returns `404 Application not found` from Railway (the app slug appears to be missing/deleted, not just down).

---

## Current State

### What's done (good)

- DB schema: migrations `002_add_multi_tenant_tables` → `005_enforce_household_constraints` add `household_id` (UUID, FK to `households`, CASCADE, NOT NULL) to `ledger`, `budgets`, `settings`, `text_category_cache`. Old `user_id` columns dropped from `ledger`/`budgets`. Composite indexes `idx_ledger_household_year` and `idx_ledger_household_budget_year` added. Unique constraint on `budgets` is now `(household_id, emoji)`.
- `app/models/budget.py` — fully updated: `household_id` NOT NULL, FK, CASCADE, unique `(household_id, emoji)`.
- `app/api/budgets.py` — all 4 endpoints (GET/POST/PATCH/DELETE) gated on `get_current_user_and_household` from `app/dependencies/auth.py`, filtered by `household.id`.
- Session-based auth via `app/dependencies/auth.py`:
  - `get_current_user(credentials, db) -> User`
  - `get_current_user_and_household(credentials, db) -> Tuple[User, Household]` ← **use this everywhere**

### What's broken (must fix)

#### 1. `app/models/ledger.py` is out of sync with the DB

File: `backend/app/models/ledger.py:51`. The model still declares `user_id = Column(Integer, nullable=True, index=True)` and has **no `household_id` column**. Migration 005 dropped `user_id` from the table and made `household_id` NOT NULL. This means in production:
- INSERTs via `LedgerEntry(...)` will fail (NOT NULL violation on `household_id`).
- The SQLAlchemy model references a column (`user_id`) that no longer exists — any SELECT mapping to this column will also fail.

This is likely why the Railway deployment is down/404.

#### 2. `app/models/settings.py` is also out of sync

File: `backend/app/models/settings.py`. Still uses single-row design (`id` PK with `CHECK (id = 1)`) and a `user_id` column. Migration 005 changed `settings.household_id` to be the primary key and dropped `id`. Model must be rewritten.

#### 3. `app/models/text_category_cache.py` doesn't have `household_id`

File: `backend/app/models/text_category_cache.py`. Migration 003 added `household_id` (nullable FK, CASCADE) and migration 005 made it NOT NULL. Model has no such column.

#### 4. All "core" data endpoints in `app/api/routes.py` are unauthenticated and unscoped

File: `backend/app/api/routes.py`. Every one of these has only `db: Session = Depends(get_db)` — no auth, no household filter:
- `GET /amounts` (line 60)
- `GET /monthly_budgets` (line 71)
- `GET /ledger` (line 82)
- `GET /category_map` (line 108)
- `POST /make_spending` (line 143)
- `DELETE /undo_spending/{uuid}` (line 192)
- `POST /sync_budgets` (line 221)
- `POST /sync_settings` (line 245)
- `POST /check_automations` (line 281)
- `GET /export_year` (line 306)
- `POST /archive_year` (line 331)

Result: anyone can hit these (even without a session token) and read/write the entire database. With auth added but routes shared, every signed-in user would see every other user's spending.

#### 5. Service layer has zero household filtering

- `app/services/ledger_service.py`: `get_amounts_for_current_year`, `get_ledger_for_month`, `get_category_map`, `delete_ledger_entry`, `export_year_as_csv` — none take or filter by `household_id`. `grep household_id` in this file returns zero hits.
- `app/services/budget_service.py`: `sync_budgets` upserts by `emoji` alone (line 27: `Budget.query.filter_by(emoji=...)`), no household. Will collide across households since the table now has `UNIQUE(household_id, emoji)`. `get_all_budgets` returns every household's budgets.
- `app/services/automation_service.py`: `check_and_run_monthly_automation` reads `Settings.id=1` (legacy single-row), iterates over all budgets globally (line 45), and inserts ledger entries without `household_id`. `archive_year` same pattern.
- `app/services/categorization_service.py`: caches in `text_category_cache` without `household_id`. **Recommendation:** keep this cache **global** — it's a text→category mapping (e.g., "starbucks latte" → "Coffee & Cafe") that doesn't leak user data, and global caching maximizes hit rate / minimizes OpenAI cost. If you keep it global, **revert migration 005's NOT NULL on `text_category_cache.household_id`** (or drop the column entirely in a new migration).

---

## Action Plan

Work through these in order. Each step is independently testable.

### Step 1 — Fix the SQLAlchemy models (unblocks all writes)

**`app/models/ledger.py`:** Drop `user_id`. Add:

```python
from sqlalchemy import ForeignKey
from sqlalchemy.dialects.postgresql import UUID as PG_UUID

household_id = Column(
    PG_UUID(as_uuid=True),
    ForeignKey('households.id', ondelete='CASCADE'),
    nullable=False,
    index=True,
)
```

Remove the old `idx_budget_year` and `idx_year_datetime` Index entries if migration 005 already created `idx_ledger_household_year` / `idx_ledger_household_budget_year` — keep the model in sync with what migrations actually built.

**`app/models/settings.py`:** Rewrite as per-household single-row table:

```python
class Settings(Base):
    __tablename__ = "settings"

    household_id = Column(
        PG_UUID(as_uuid=True),
        ForeignKey('households.id', ondelete='CASCADE'),
        primary_key=True,
    )
    currency_symbol = Column(String(3), nullable=False, default="$")
    last_monthly_update_date = Column(Date, nullable=True)
    last_yearly_archive_date = Column(Date, nullable=True)
```

Drop the `CheckConstraint('id = 1')`, drop `id`, drop `user_id`.

**`app/models/text_category_cache.py`:** Decision point. Recommend keeping global; if so, write a new migration `009_revert_text_category_cache_household.py` that makes `household_id` nullable again (or drops it). If you instead want per-household categorization, add the column to the model and include household scoping in the service.

### Step 2 — Gate every core route on auth and household

In `app/api/routes.py`, add the import:

```python
from typing import Tuple
from app.models.user import User
from app.models.household import Household
from app.dependencies.auth import get_current_user_and_household
```

Then add to every endpoint signature:

```python
user_household: Tuple[User, Household] = Depends(get_current_user_and_household),
```

And inside each handler, unpack and pass `household.id` down:

```python
user, household = user_household
budgets = get_amounts_for_current_year(db, household.id)
```

Endpoints that need this: `/amounts`, `/monthly_budgets`, `/ledger`, `/category_map`, `/make_spending`, `/undo_spending/{uuid}`, `/sync_budgets`, `/sync_settings`, `/check_automations`, `/export_year`, `/archive_year`. (`/health` and `/` stay public.)

### Step 3 — Push `household_id` through the service layer

**`app/services/ledger_service.py`** — every function takes `household_id: UUID` and adds `.filter(LedgerEntry.household_id == household_id)`:

- `get_amounts_for_current_year(db, household_id, year=None)`:
  - `db.query(Budget).filter(Budget.household_id == household_id).all()`
  - `db.query(...).filter(LedgerEntry.year == year, LedgerEntry.household_id == household_id).group_by(...)`
- `get_ledger_for_month(db, household_id, month_str)`:
  - Add `LedgerEntry.household_id == household_id` to the filter.
- `get_category_map(db, household_id, month_str, budget_emoji)`:
  - Add `LedgerEntry.household_id == household_id` to the filter.
- `delete_ledger_entry(db, household_id, entry_uuid)`:
  - Filter by **both** `uuid` and `household_id` — otherwise user A can delete user B's entries by guessing UUIDs.
- `export_year_as_csv(db, household_id, year)`:
  - Add `LedgerEntry.household_id == household_id` to the filter.

**`app/api/routes.py:171` (`/make_spending`)** — stamp `household_id` on insert:

```python
entry = LedgerEntry(
    household_id=household.id,
    amount=request.amount,
    ...
)
```

**`app/services/budget_service.py`** — both functions:
- `sync_budgets(db, household_id, budgets)`: change the upsert query to `Budget.query.filter_by(household_id=household_id, emoji=item.emoji).first()`, and pass `household_id=household_id` when constructing new `Budget(...)`.
- `get_all_budgets(db, household_id)`: filter by `household_id`.

**`app/services/automation_service.py`** — both functions need `household_id`:
- `check_and_run_monthly_automation(db, household_id)`: replace `Settings.filter_by(id=1)` with `Settings.filter_by(household_id=household_id)`. Iterate budgets filtered by household. Stamp `household_id` on every `LedgerEntry(...)` insert (line 55).
- `archive_year(db, household_id, year)`: same pattern.

**`app/api/routes.py:261` (`/sync_settings`)** — replace `db.query(SettingsModel).filter_by(id=1)` with `filter_by(household_id=household.id)`. New row construction: `SettingsModel(household_id=household.id, currency_symbol=request.currency_symbol)`. Drop the `id=1` reference entirely.

### Step 4 — Frontend/backend contract: deprecate `/sync_budgets`

The new frontend uses `/budgets` (CRUD endpoints in `app/api/budgets.py`) — see `tuppence/Services/APIService.swift:100` (`listBudgets`). The old `/sync_budgets` endpoint is no longer needed. Either:
- Delete `/sync_budgets` and its service function, **or**
- Leave it for the legacy widget path but make sure the iOS Widget (`tuppence/Widget/TuppenceWidget.swift`) is also moved to the new auth'd endpoints. Worth confirming with the frontend before deleting.

### Step 5 — Verify migrations have actually run in production

The fact that the model says `user_id` but migrations dropped it suggests one of two states in prod:
1. Migrations never ran → DB schema is pre-migration → `/budgets` endpoints (which expect `household_id` NOT NULL) would also be broken.
2. Migrations ran → ledger/settings writes have been failing all along.

After redeploying, run `alembic current` against the prod DB and confirm it's at `008`. If not, run `alembic upgrade head`.

### Step 6 — Production redeploy

The Railway app at `tuppence-production-8de5.up.railway.app` returns Railway's "Application not found" 404, which means the service slug itself is gone (not just sleeping/down). Either:
- Redeploy to Railway and update the URL in `tuppence/Models/AppSettings.swift:16` if it changes, or
- Confirm the deployment was moved elsewhere and provide the new URL.

---

## Test Plan

Two users in different households is the minimum viable check:

```bash
# 1. Register two users
curl -X POST $BASE/auth/register -H 'Content-Type: application/json' \
  -d '{"email":"a@test.com","password":"password123"}'
curl -X POST $BASE/auth/register -H 'Content-Type: application/json' \
  -d '{"email":"b@test.com","password":"password123"}'

# Save TOKEN_A and TOKEN_B from the responses

# 2. User A creates a budget and a spending
curl -X POST $BASE/budgets -H "Authorization: Bearer $TOKEN_A" -H 'Content-Type: application/json' \
  -d '{"emoji":"🛒","label":"Groceries","monthly_amount":50000}'
curl -X POST $BASE/make_spending -H "Authorization: Bearer $TOKEN_A" -H 'Content-Type: application/json' \
  -d '{"amount":-500,"currency":"USD","budget_emoji":"🛒","description_text":"milk"}'

# 3. User B fetches data — should see NOTHING from A
curl $BASE/amounts -H "Authorization: Bearer $TOKEN_B"   # → empty budgets
curl $BASE/ledger  -H "Authorization: Bearer $TOKEN_B"   # → empty list

# 4. Unauthenticated request → should be 401
curl -i $BASE/amounts                                      # expect HTTP/1.1 401
```

Bonus: try `DELETE /undo_spending/{A's uuid}` as user B → expect 404, not 200.

---

## Why this matters

Until step 2 is done, the app is a data-leak: any signed-in user sees every other user's spending. Until step 1 is done, the production backend is likely throwing 500s on writes (and probably reads), which matches the Railway 404 symptom the iOS app is seeing.
