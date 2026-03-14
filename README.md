# uwazi-backend

Backend API for Uwazi - Kenya's AI-powered procurement monitoring and anti-corruption system. Detects price inflation, ghost suppliers, tailored specifications, and corrupt networks in public tenders worth KSh 1.5T annually. Saves taxpayers billions through intelligent oversight. Built with FastAPI, PostgreSQL, spaCy, NetworkX, Redis.

## Install required packages

### 1. Install uv (if not already installed)

```bash
pip install uv
```

### 2. Install dependencies

`uv` automatically manages virtual environments and dependencies.

```bash
uv sync
```

This will create a virtual environment and install all packages from your `pyproject.toml` or `requirements.txt`.

### 3. Set up environment variables

Create a `.env` file in the project root with your database configuration:

```bash
DATABASE_URL=postgresql://user:password@localhost:5432/your_database
SECRET_KEY=your-secret-key-here
ACCESS_TOKEN_EXPIRE_MINUTES=30
```

### 4. Initialize Alembic (First time only)

If Alembic is not yet set up in the project:

```bash
alembic init alembic
```

Then configure `alembic/env.py` to import your models and database settings.

### 5. Run database migrations

Apply all pending migrations to set up your database schema:

```bash
alembic upgrade head
```

**Note:** Always run migrations before starting the application, especially after pulling new code or creating new models.

## 6. Running project in your dev machine

Run

```bash
uv run fastapi dev app/main.py
```

Access it at `localhost:8000`

## Working with Database Migrations

### Creating a new migration after model changes

```bash
alembic revision --autogenerate -m "description of changes"
```

### Applying migrations

```bash
alembic upgrade head
```

### Rolling back a migration

```bash
alembic downgrade -1
```

### Check current migration status

```bash
alembic current
```

For more Alembic commands, see the [Alembic documentation](https://alembic.sqlalchemy.org/).


# AI Procurement Monitoring System — Backend

FastAPI backend for real-time detection and prevention of fraudulent practices in Kenya's public procurement.

---

## Architecture

```
┌─────────────────────────────────────────┐
│           Next.js Frontend              │
└──────────────────┬──────────────────────┘
                   │ REST API
┌──────────────────▼──────────────────────┐
│            FastAPI Backend              │
│  /api/tenders  /api/suppliers           │
│  /api/dashboard  /api/whistleblower     │
│  /api/benchmarks  /api/analyze          │
└──────┬──────────────────────────────────┘
       │
  ┌────▼────┐    ┌───────────┐   ┌────────┐
  │ Postgres│    │  Redis    │   │ Claude │
  │  (data) │    │ (queue)   │   │  API   │
  └─────────┘    └─────┬─────┘   └────────┘
                       │
              ┌────────▼────────┐
              │  Celery Workers │
              │  (scraping,     │
              │   AI batch)     │
              └─────────────────┘
```

## AI Features

| Feature | Endpoint | Description |
|---|---|---|
| Risk Narrative | `POST /api/tenders/{id}/analyze-risk` | Claude analyzes a tender and writes an investigation-ready report |
| Spec Analysis | `POST /api/analyze/specifications` | Detects restrictive/anti-competitive specifications |
| Whistleblower Triage | `POST /api/whistleblower/submit` | AI triages anonymous reports, assigns credibility score |
| Investigation Package | `GET /api/tenders/{id}/investigation-package` | Full EACC investigation briefing document |
| Natural Language Query | `POST /api/dashboard/ai-query` | Ask questions about procurement data in plain English |

---

## Quick Start

### 1. Clone and configure

```bash
cp .env.example .env
# Edit .env and set:
#   DATABASE_URL
#   ANTHROPIC_API_KEY   ← required for AI features
```

### 2. Run with Docker (recommended)

```bash
docker-compose up -d

# Run migrations and seed data
docker-compose exec backend alembic upgrade head
docker-compose exec backend python -m app.seed
```

### 3. Or run locally

```bash
# PostgreSQL and Redis must be running
pip install -r requirements.txt

# Apply migrations
alembic upgrade head

# Seed price benchmarks + admin user
python -m app.seed

# Start API server
uvicorn app.main:app --reload --port 8000
```

API docs available at: http://localhost:8000/docs

---

## API Reference

### Public Endpoints (no auth)

| Method | Endpoint | Description |
|---|---|---|
| GET | `/api/tenders` | List tenders with filters |
| GET | `/api/tenders/{id}` | Tender detail + risk score + red flags |
| GET | `/api/dashboard/stats` | Dashboard metrics |
| GET | `/api/dashboard/heatmap` | County risk heatmap |
| GET | `/api/benchmarks` | Price benchmarks |
| POST | `/api/whistleblower/submit` | Submit anonymous report |
| POST | `/api/analyze/specifications` | Analyze spec text |
| POST | `/api/analyze/price-check` | Price vs benchmark check |

### Authenticated Endpoints

| Method | Endpoint | Role | Description |
|---|---|---|---|
| POST | `/api/tenders/{id}/analyze-risk` | investigator | Trigger AI risk analysis |
| GET | `/api/tenders/{id}/investigation-package` | investigator | AI investigation briefing |
| POST | `/api/dashboard/ai-query` | any | NL query interface |
| GET | `/api/whistleblower/reports` | investigator | View all reports |
| POST | `/api/scraper/run` | admin | Trigger manual scrape |
| POST | `/api/suppliers` | investigator | Add supplier |
| POST | `/api/benchmarks` | admin | Add price benchmark |

### Auth

```bash
# Register
POST /api/auth/register
{"email": "...", "password": "...", "role": "investigator"}

# Login
POST /api/auth/login (form data: username, password)
→ {"access_token": "...", "token_type": "bearer"}

# Use token
Authorization: Bearer <token>
```

---

## Risk Scoring

| Score | Level | Action |
|---|---|---|
| 80-100 | CRITICAL | Automatic investigation flagged |
| 60-79 | HIGH | Review within 7 days |
| 40-59 | MEDIUM | Periodic audit |
| 0-39 | LOW | Routine monitoring |

### Score Components

```
Total = (Price Score × 40%) + (Supplier Score × 30%) + (Spec Score × 20%) + (Method Score × 10%)
```

---

## Project Structure

```
app/
├── main.py              # FastAPI app + router registration
├── config.py            # Settings from .env
├── database.py          # SQLAlchemy engine + session
├── seed.py              # DB seed (benchmarks, admin user)
├── models/              # ORM models (Tender, Supplier, RiskScore, ...)
├── schemas/             # Pydantic request/response schemas
├── routes/
│   ├── tenders.py       # CRUD + risk trigger + investigation package
│   ├── suppliers.py     # Supplier management
│   ├── dashboard.py     # Stats, heatmap, AI query
│   ├── whistleblower.py # Anonymous report submission + triage
│   ├── benchmarks.py    # Price benchmarks + spec analysis
│   ├── auth.py          # JWT auth
│   └── scraper.py       # Manual scrape trigger
├── services/
│   ├── ai_service.py    # Claude API — all LLM calls
│   ├── risk_engine.py   # Composite risk scoring
│   ├── price_analyzer.py# Price deviation detection
│   ├── supplier_checker.py # Ghost supplier detection
│   ├── spec_analyzer.py # Specification restrictiveness
│   └── auth.py          # JWT + password utils
├── scrapers/
│   └── ppip_scraper.py  # PPIP portal scraper
└── workers/
    ├── celery_app.py    # Celery + beat schedule
    └── tasks.py         # Background tasks
```

---

## Background Jobs (Celery)

| Task | Schedule | Description |
|---|---|---|
| `scrape_and_ingest_tenders` | Every 12h | Scrapes PPIP, saves new tenders |
| `batch_ai_risk_analysis` | Daily 2 AM | Runs AI analysis on unanalyzed high-risk tenders |
| `refresh_all_supplier_scores` | Weekly Sunday | Refreshes all supplier risk scores |

### Start workers manually

```bash
# Worker
celery -A app.workers.celery_app worker --loglevel=info

# Beat scheduler
celery -A app.workers.celery_app beat --loglevel=info
```

---

## Default Credentials (change immediately)

- Email: `admin@procurementmonitor.go.ke`
- Password: `ChangeMe@2024!`
