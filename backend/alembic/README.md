# Database Migrations

This directory contains Alembic database migrations for the Tuppence backend.

## Migration Overview

The migrations add multi-tenant authentication and household support to Tuppence.

### Migration Files

1. **001_initial_schema.py** - Captures current single-tenant database state
   - Creates: categories, budgets, ledger, settings, text_category_cache
   - This is the baseline before multi-tenancy

2. **002_add_multi_tenant_tables.py** - Adds authentication and household tables
   - Creates: users, households, household_members, sharing_tokens
   - Enables user authentication and household sharing

3. **003_add_household_id_columns.py** - Prepares existing tables for multi-tenancy
   - Adds household_id to: ledger, budgets, settings, text_category_cache
   - Columns are nullable to allow data migration

4. **004_migrate_to_default_household.py** - Migrates existing data
   - Creates default "My Household"
   - Assigns all existing data to default household
   - Preserves existing user data

5. **005_enforce_household_constraints.py** - Finalizes multi-tenancy
   - Makes household_id NOT NULL
   - Drops old user_id columns
   - Enables Row-Level Security (RLS)
   - Creates RLS policies for data isolation

## Running Migrations

### Apply All Migrations

```bash
cd backend
alembic upgrade head
```

### Rollback One Migration

```bash
alembic downgrade -1
```

### Rollback All Migrations

```bash
alembic downgrade base
```

### Check Current Version

```bash
alembic current
```

### View Migration History

```bash
alembic history
```

## Migration Strategy

### Development Environment

1. Start with empty database
2. Run `alembic upgrade head`
3. Database is now multi-tenant ready

### Production Migration (Existing Data)

**IMPORTANT**: These migrations are designed for backwards compatibility.

1. **Backup database** before running migrations
2. Run migrations in order: `alembic upgrade head`
3. All existing data is preserved in "My Household"
4. First user to register can claim the legacy household

### Rollback Plan

If issues arise after migration:

```bash
# Rollback RLS and constraints
alembic downgrade 004

# This reverts to state where:
# - Multi-tenant tables exist
# - household_id columns exist but are nullable
# - RLS is disabled
# - Old user_id columns are restored
```

## Row-Level Security (RLS)

Migration 005 enables PostgreSQL Row-Level Security for automatic data isolation.

### How RLS Works

1. Each request sets `app.current_user_id` in PostgreSQL session
2. RLS policies automatically filter queries by household membership
3. Users can only see data from households they belong to

### RLS Policies Created

- **household_isolation_policy**: Applied to ledger, budgets, settings, text_category_cache, households
  - Users see only data from their households
- **household_members_policy**: Applied to household_members
  - Users see members of households they belong to
- **sharing_tokens_policy**: Applied to sharing_tokens
  - Users see tokens for their households

### Testing RLS

To test RLS in psql:

```sql
-- Set user context
SET app.current_user_id = 'user-uuid-here';

-- Query should only return data for user's households
SELECT * FROM ledger;
SELECT * FROM budgets;
```

## Database Schema

After all migrations, the schema includes:

### Authentication Tables
- `users` - User accounts (email/password or Apple Sign In)
- `households` - Budget household groups
- `household_members` - User-household relationships (many-to-many)
- `sharing_tokens` - One-time tokens for household invitations

### Data Tables (Household-Scoped)
- `ledger` - Transaction entries (with household_id)
- `budgets` - Budget definitions (with household_id)
- `settings` - Household settings (with household_id)
- `text_category_cache` - AI categorization cache (with household_id)

### Global Tables
- `categories` - Predefined category list (shared across all households)

## Security Notes

1. **RLS Enforcement**: All household-scoped tables have RLS enabled
2. **Foreign Keys**: All household_id columns have CASCADE delete
3. **Unique Constraints**: Budget emojis are unique per household (not globally)
4. **Password Security**: Passwords are hashed with bcrypt (not stored in migrations)
5. **Token Security**: Sharing tokens are cryptographically secure random strings

## Troubleshooting

### Migration Fails

If a migration fails:

1. Check PostgreSQL logs for error details
2. Verify database connection in `app/config.py`
3. Ensure PostgreSQL version supports UUID and RLS (PostgreSQL 9.5+)
4. Check that gen_random_uuid() extension is available

### Enable UUID Extension

If gen_random_uuid() is not available:

```sql
CREATE EXTENSION IF NOT EXISTS "pgcrypto";
```

### RLS Not Working

If RLS policies don't filter correctly:

1. Verify `app.current_user_id` is set in session:
   ```sql
   SHOW app.current_user_id;
   ```
2. Check RLS is enabled:
   ```sql
   SELECT tablename, rowsecurity FROM pg_tables WHERE schemaname = 'public';
   ```
3. View active policies:
   ```sql
   SELECT * FROM pg_policies;
   ```

## Development Tips

### Creating New Migrations

To create a new migration:

```bash
alembic revision -m "description_of_changes"
```

For autogeneration (compares models to database):

```bash
alembic revision --autogenerate -m "description"
```

### Testing Migrations

Always test migrations on a development database first:

1. Create test database
2. Run migrations: `alembic upgrade head`
3. Verify data integrity
4. Test rollback: `alembic downgrade -1`
5. Verify rollback succeeded: `alembic upgrade head`
