# Tuppence Backend

FastAPI backend for Tuppence personal budgeting app with AI-powered spending categorization.

## Features

- **Multi-tenant Authentication:** Session-based auth with household sharing
- **Stripe Subscriptions:** Three-tier pricing (Free, Premium, Pro) with Stripe integration
- **Single Source of Truth:** Ledger with SQL-derived totals
- **AI Categorization:** OpenAI gpt-4o-mini with intelligent caching
- **Budget Automation:** Monthly budget additions (runs on first of month)
- **Year-End Export:** CSV export for archival
- **150+ Categories:** Predefined categories with Wes Anderson-inspired pastel colors

## Quick Start (Local Development)

### Prerequisites

- Python 3.9+
- PostgreSQL database
- OpenAI API key
- Stripe account (for subscription features)

### Installation

```bash
# Install dependencies
pip install -r requirements.txt

# Set up environment variables
cp .env.example .env
# Edit .env with your DATABASE_URL and OPENAI_API_KEY

# Run database migrations
alembic upgrade head

# Initialize database (seeds categories and settings)
python -c "from app.database import init_db; init_db()"

# Start development server
uvicorn app.main:app --reload
```

Server runs at http://localhost:8000

API documentation available at http://localhost:8000/docs

## Deployment to Railway

### Why Railway?

- Free tier includes backend hosting + PostgreSQL database
- One-click deploy from GitHub
- Automatic HTTPS and environment variable management
- Perfect for single-user apps

### Steps

1. **Create Railway Account:** Sign up at [railway.app](https://railway.app) (free)

2. **Create New Project:**
   - Click "New Project"
   - Select "Deploy from GitHub repo"
   - Connect GitHub account and select tuppence repository
   - Set root directory to `/backend`

3. **Add PostgreSQL:**
   - In project, click "New"
   - Select "Database" → "PostgreSQL"
   - Railway automatically provisions database and sets `DATABASE_URL`

4. **Configure Environment Variables:**
   - Click on backend service → "Variables"
   - Add `OPENAI_API_KEY` (get from platform.openai.com)
   - `DATABASE_URL` is automatically set by Railway

5. **Deploy:**
   - Railway auto-deploys on git push
   - Get public URL from "Settings" → "Generate Domain"
   - URL format: `https://tuppence-backend-production.up.railway.app`

6. **Initialize Database:**
   - First request to any endpoint triggers `init_db()`
   - Or run manually via Railway CLI: `railway run python -c "from app.database import init_db; init_db()"`

7. **Test Backend:**
   ```bash
   curl https://your-railway-url.railway.app/amounts
   ```

## Authentication

### Session-Based Authentication

Tuppence uses **session-based authentication** with UUID tokens (not JWT) for immediate revocation capability and simplified security model.

**Key Features:**
- UUID-based session tokens stored in database
- Argon2id password hashing (64MB memory, 3 iterations, 4 threads)
- 30-day sliding window expiration (extends on each request)
- Immediate session revocation on logout
- Rate limiting (5 requests/minute on auth endpoints)
- Multi-tenant household isolation

### Authentication Endpoints

#### Register New User
```bash
POST /auth/register
Content-Type: application/json

{
  "email": "user@example.com",
  "password": "SecurePass123",
  "full_name": "John Doe",           // Optional
  "household_token": "abc123..."     // Optional - join existing household
}
```

**Response (201 Created):**
```json
{
  "sessionToken": "550e8400-e29b-41d4-a716-446655440000",
  "userId": "123e4567-e89b-12d3-a456-426614174000",
  "householdId": "789e4567-e89b-12d3-a456-426614174000",
  "email": "user@example.com",
  "householdName": "My Household"
}
```

**Behavior:**
- Without `household_token`: Creates new household named "My Household" (user is owner)
- With `household_token`: Joins existing household (user is member)
- Password requirements: 8+ chars, uppercase, lowercase, digit
- Returns session token to use as Bearer token

#### Login
```bash
POST /auth/login
Content-Type: application/json

{
  "email": "user@example.com",
  "password": "SecurePass123"
}
```

**Response (200 OK):**
```json
{
  "sessionToken": "550e8400-e29b-41d4-a716-446655440000",
  "userId": "123e4567-e89b-12d3-a456-426614174000",
  "householdId": "789e4567-e89b-12d3-a456-426614174000",
  "email": "user@example.com",
  "householdName": "My Household"
}
```

#### Logout
```bash
POST /auth/logout
Authorization: Bearer 550e8400-e29b-41d4-a716-446655440000
```

**Response (200 OK):**
```json
{
  "message": "Successfully logged out"
}
```

**Effect:** Immediately deletes session from database. Subsequent requests with that token will fail with 401.

### Using the Session Token

Include the session token in all authenticated requests:

```bash
GET /amounts
Authorization: Bearer 550e8400-e29b-41d4-a716-446655440000
```

**Session Behavior:**
- Expires after 30 days of inactivity
- Each request extends expiration by 30 days (sliding window)
- Invalid/expired sessions return 401 Unauthorized

### Household Sharing

To share your household with another user:

1. **Generate Sharing Token** (owner only):
```bash
POST /households/generate_token
Authorization: Bearer <owner-session-token>
```

Returns a cryptographically secure token (256-bit) that expires in 7 days.

2. **Share Token** with new user (via secure channel)

3. **New User Registers** with the token:
```bash
POST /auth/register
{
  "email": "newuser@example.com",
  "password": "SecurePass123",
  "household_token": "abc123..."
}
```

Token can only be used once and expires after 7 days.

### Security Features

- **Argon2id Hashing:** Industry-standard password hashing (OWASP recommended)
- **Rate Limiting:** 5 requests/minute on auth endpoints (prevents brute force)
- **Session Isolation:** Each session tied to specific user + household
- **Immediate Revocation:** Logout deletes session (zero vulnerability window)
- **Sliding Expiration:** Active users stay logged in, inactive sessions expire
- **Database Isolation:** Middleware enforces household-level data isolation

## Subscriptions

### Subscription Tiers

Tuppence offers three subscription tiers:

**FREE (Default)**
- Basic expense tracking
- Up to 3 budgets
- Single user only
- 7 days of history

**PREMIUM ($4.99/month or $49/year)**
- Unlimited budgets
- Advanced analytics
- Unlimited history
- CSV export
- Priority support

**PRO ($9.99/month or $99/year)**
- All Premium features
- Household sharing (unlimited members)
- API access
- Custom categories
- White-label reports

### Stripe Integration

Subscriptions are managed via Stripe with the following flow:

1. **Frontend** → `GET /subscriptions/pricing` → Shows available tiers
2. **User selects tier** → `POST /subscriptions/checkout` → Returns Stripe checkout URL
3. **User completes payment** on Stripe-hosted checkout page
4. **Stripe webhook** → `POST /subscriptions/webhook` → Updates subscription in database
5. **Frontend** → `GET /subscriptions/status` → Shows updated tier

### Environment Variables

Required Stripe configuration:

```bash
STRIPE_SECRET_KEY=sk_live_...                    # From Stripe dashboard
STRIPE_PUBLISHABLE_KEY=pk_live_...              # For frontend Stripe.js
STRIPE_WEBHOOK_SECRET=whsec_...                 # From webhook configuration
STRIPE_PREMIUM_MONTHLY_PRICE_ID=price_...       # Create in Stripe dashboard
STRIPE_PREMIUM_YEARLY_PRICE_ID=price_...        # Create in Stripe dashboard
STRIPE_PRO_MONTHLY_PRICE_ID=price_...           # Create in Stripe dashboard
STRIPE_PRO_YEARLY_PRICE_ID=price_...            # Create in Stripe dashboard
```

### Webhook Setup

Configure webhook in Stripe dashboard:

**Webhook URL:** `https://your-domain.com/subscriptions/webhook`

**Events to subscribe:**
- `checkout.session.completed`
- `customer.subscription.created`
- `customer.subscription.updated`
- `customer.subscription.deleted`
- `invoice.payment_succeeded`
- `invoice.payment_failed`

### Subscription Management

- Only household **owners** can manage subscriptions
- Members share subscription benefits
- Subscription is **household-level** (not per-user)
- Customer portal allows payment method updates and cancellation

For detailed implementation guide, see:
- `STRIPE_IMPLEMENTATION.md` - Backend implementation details
- `SUBSCRIPTION_SCHEMA_DESIGN.md` - Database schema documentation
- `SUBSCRIPTION_TESTS.md` - Test suite documentation

## API Endpoints

### Authentication
- `POST /auth/register` - Register new user (creates household or joins existing)
- `POST /auth/login` - Login with email/password
- `POST /auth/logout` - Logout and invalidate session
- `POST /auth/apple` - Sign in with Apple (iOS)

### Household Sharing
- `POST /households/generate_token` - Generate sharing token (owner only)
- `POST /households/join` - Join household via token

### Subscriptions (Stripe)
- `GET /subscriptions/status` - Get current subscription tier and status
- `GET /subscriptions/pricing` - Get available pricing tiers and features
- `POST /subscriptions/checkout` - Create Stripe checkout session (owner only)
- `POST /subscriptions/portal` - Create customer portal session (owner only)
- `POST /subscriptions/webhook` - Stripe webhook endpoint (signature verified)
- `GET /subscriptions/publishable-key` - Get Stripe publishable key for frontend

### Core Data
- `GET /amounts` - Total amount left per budget for current year
- `GET /monthly_budgets` - Monthly increment amounts per budget
- `GET /ledger?month=YYYY-MM` - Spending history for specified month
- `GET /category_map?month=YYYY-MM&budget_emoji=🛒` - Category breakdown for pie chart

### Spending Management
- `POST /make_spending` - Log new spending with AI categorization
- `DELETE /undo_spending/{uuid}` - Remove ledger entry

### Configuration
- `POST /sync_budgets` - Sync budgets from iOS Settings
- `POST /sync_settings` - Sync currency and other settings

### Automations
- `POST /check_automations` - Check and run monthly budget additions

### Year-End
- `GET /export_year?year=YYYY` - Export year as CSV
- `POST /archive_year?year=YYYY` - Mark year as archived

## Architecture

- **Authentication:** Session-based with UUID tokens (not JWT)
- **Multi-Tenancy:** Household-level data isolation via middleware
- **Database:** PostgreSQL with single source of truth ledger table
- **ORM:** SQLAlchemy 2.0
- **API:** FastAPI with async support
- **Security:** Argon2id password hashing, rate limiting, session management
- **AI:** OpenAI gpt-4o-mini for categorization with text-based caching
- **Migrations:** Alembic for database versioning

## Testing

```bash
# Run all tests
pytest tests/

# Run with coverage
pytest --cov=app tests/
```

## Database Schema

### Authentication & Multi-Tenancy
- **users** - User accounts (email, Argon2id password hash, metadata)
- **households** - Household/family groups for data sharing
- **household_members** - Many-to-many relationship (user ↔ household) with roles
- **sessions** - Active session tokens (UUID, sliding 30-day expiration)
- **sharing_tokens** - One-time tokens for joining households (7-day expiration)

### Subscriptions (Stripe)
- **subscriptions** - Household subscription status (tier, Stripe IDs, billing period)
- **webhook_events** - Stripe webhook event log (idempotent processing)

### Budget & Spending Data
- **ledger** - Single source of truth for all transactions (household-scoped)
- **budgets** - Monthly budget definitions (household-scoped)
- **categories** - Predefined categories with colors (global, seeded on init)
- **text_category_cache** - AI categorization cache (household-scoped)
- **settings** - Global settings (single row)

## License

Private project for personal use.
