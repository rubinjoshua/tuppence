# Tuppence Backend

FastAPI backend for Tuppence personal budgeting app with AI-powered spending categorization.

## Features

- Single source of truth ledger with SQL-derived totals
- AI-powered categorization using OpenAI gpt-4o-mini with intelligent caching
- Monthly budget automation (runs on first of each month)
- Year-end CSV export for archival
- 150 predefined categories with Wes Anderson-inspired pastel colors

## Quick Start (Local Development)

### Prerequisites

- Python 3.9+
- PostgreSQL database
- OpenAI API key

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

## API Endpoints

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

- **Database:** PostgreSQL with single source of truth ledger table
- **ORM:** SQLAlchemy 2.0
- **API:** FastAPI with async support
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

- **ledger** - Single source of truth for all transactions
- **budgets** - Monthly budget definitions
- **categories** - Predefined categories with colors (seeded on init)
- **text_category_cache** - Caches AI categorization results
- **settings** - Global settings (single row)

## License

Private project for personal use.
