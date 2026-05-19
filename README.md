# Tender Extractor API

A production-grade AI backend service that extracts structured information from tender documents using OpenAI with automatic provider fallback, full observability, async task processing, and JWT authentication.

---

## Architecture Overview

```
Client
  └─▶ JWT Auth (SimpleJWT)
        └─▶ DRF View (thin — validate + delegate only)
              └─▶ TenderExtractionService
                    ├─▶ PromptBuilder      (builds system + user prompts)
                    ├─▶ LLMOrchestrator    (retry + fallback logic)
                    │     ├─▶ OpenAIProvider [gpt-4o-mini]  ← primary
                    │     └─▶ OpenAIProvider [gpt-5.2]      ← fallback
                    ├─▶ LLMJSONValidator   (4-stage: parse → strip → extract → pydantic)
                    ├─▶ TenderSchema       (pydantic v2 normalization)
                    └─▶ Celery tasks (async)
                          ├─▶ log_api_request_task   → PostgreSQL (Supabase)
                          └─▶ send_slack_alert_task  → Slack webhook (on failure)
```

### Design Decisions

**Django as infrastructure shell only.** All business logic lives in `apps/tenders/` and is entirely framework-agnostic. Views are ~30 lines. Serializers do I/O shape only.

**4-stage JSON validation.** LLMs sometimes wrap output in markdown fences or add prose. The validator tries direct parse → strip fences → regex extract → pydantic normalization. This maximises recovery before triggering a retry.

**Pydantic v2 as the contract.** `TenderSchema` normalises dates (any format → ISO 8601), coerces budget amounts (strips currency symbols, commas), defaults all list fields to `[]`, and nullifies logically impossible dates (deadline < publication). The schema is the single source of truth.

**Always HTTP 200.** The endpoint never returns a 5xx for LLM failures. On total failure it returns a null-filled payload and dispatches a Slack alert asynchronously. This makes the API safe to integrate — callers always get a parseable response.

**Correlation IDs everywhere.** `CorrelationIDMiddleware` reads or generates `X-Request-ID` on every request and binds it to structlog context vars. Every log line in the request lifecycle — including Celery tasks — carries the same ID.

**Cost accounting.** Every `LLMResult` computes `cost_usd` from token counts using a static pricing table. Costs are aggregated across all provider attempts (including retries and fallback) and returned in the response `meta` block.

---

## Tech Stack

| Layer | Technology |
|---|---|
| Framework | Django 4.2 + DRF |
| Auth | djangorestframework-simplejwt |
| Database | PostgreSQL via Supabase |
| Cache / Broker | Redis |
| Async Tasks | Celery |
| LLM (primary) | OpenAI gpt-4o-mini |
| LLM (fallback) | OpenAI gpt-5.2 |
| Validation | Pydantic v2 |
| Logging | structlog (JSON) |
| API Docs | drf-spectacular (Swagger + ReDoc) |
| Containerisation | Docker + Docker Compose |

---

## Project Structure

```
tender_extractor/
├── app/
│   ├── config/                  # Django settings, urls, celery, wsgi
│   │   └── settings/
│   │       ├── base.py
│   │       ├── development.py
│   │       └── production.py
│   ├── apps/
│   │   ├── api/                 # Thin DRF layer (views, serializers, urls)
│   │   ├── authentication/      # JWT token endpoints
│   │   ├── tenders/             # Core domain
│   │   │   ├── domain/          # Pydantic schemas, LLMResult
│   │   │   ├── prompts/         # PromptBuilder
│   │   │   ├── llm/             # Orchestrator + providers
│   │   │   ├── validators/      # JSON validator
│   │   │   ├── services/        # TenderExtractionService
│   │   │   ├── repositories/    # DB access layer
│   │   │   ├── models/          # APIRequestLog, UsageAggregation, ProviderFailureLog
│   │   │   └── tasks/           # Celery tasks (logging, Slack, aggregation)
│   │   ├── observability/       # Structlog setup, correlation ID, request logging
│   │   └── common/              # Exception handler, shared utilities
│   └── manage.py
├── tests/
│   ├── api/                     # API endpoint tests
│   ├── llm/                     # Orchestrator tests (mocked)
│   └── validators/              # JSON validator + Pydantic schema tests
├── docker/
│   ├── Dockerfile
│   └── docker-compose.yml
├── requirements/
│   ├── base.txt
│   ├── development.txt
│   └── production.txt
└── .env.example
```

---

## Local Setup (Without Docker)

### Prerequisites

- Python 3.12.10+ (*NOTE*: some dependecies in this project don't yet have wheels for Python 3.14+. It's recommended to use Python 3.12.13)
- Redis running locally (`redis-server` or `brew services start redis`). For Windows machines, make sure you have Redis for windows or run Redis inside WSL.
- Supabase project with PostgreSQL credentials. (Use session pooler connection if your ISP doesn't support IPv6).

### 1. Clone and create virtualenv

```bash
git clone https://github.com/madatef/tender-extractor.git
cd tender_extractor
python -m venv .venv --prompt tender-extractor
source venv/bin/activate          # Windows: venv\Scripts\Activate, Git Bash on Windows: source .venv\Scripts\Activate
pip install -r requirements/development.txt # Or production.txt if you want to mimic prod env
```

### 2. Configure environment

```bash
cp .env.example .env
# Edit .env and fill in your Supabase credentials, OpenAI key, Slack webhook, etc.
```

### 3. Run migrations

```bash
cd app
python manage.py createmigrations # You can skip this part and fall back to the latest migration file in this repo
python manage.py migrate
```

### 4. Create a superuser (for admin + token generation)

```bash
python manage.py createsuperuser # Note that the terminal will hide password characters
```

### 5. Start Django

```bash
python manage.py runserver
# → http://localhost:8000
```

### 6. Start Celery worker (separate terminal, SAME virtual env)

```bash
cd app
celery -A config.celery worker --loglevel=info # Use --pool=solo flag on windows for better performance
```

---

## Docker Setup

### Prerequisites

- Docker Desktop (or Engine + Compose v2)
- `.env` file configured (copy from `.env.example` and use nano to edit)

### Start all services

```bash
# From the tender_extractor/ (root dir)
cd docker
docker compose up --build
```

This starts:
- `web` — Django + Gunicorn on port 8000
- `celery` — Celery worker
- `redis` — Redis broker on port 6379

Supabase remains external — configure credentials in `.env`. If you use a local PostgreSQL DB, make sure to update Dockerized deployment accordingly.

### Run migrations inside Docker

```bash
# From tender_extractor/docker
docker compose exec web python manage.py migrate
docker compose exec web python manage.py createsuperuser
```

---

## API Usage

### Authentication

All endpoints require a JWT Bearer token.

**1. Obtain token**

```bash
curl -X POST http://localhost:8000/api/token/ \
  -H "Content-Type: application/json" \
  -d '{"username": "your_user", "password": "your_password"}'
```

Response:
```json
{
  "access": "eyJ...",
  "refresh": "eyJ..."
}
```

**2. Refresh token**

```bash
curl -X POST http://localhost:8000/api/token/refresh/ \
  -H "Content-Type: application/json" \
  -d '{"refresh": "eyJ..."}'
```

---

### POST /api/v1/tender-extractor/

**Request**

```bash
curl -X POST http://localhost:8000/api/v1/tender-extractor/ \
  -H "Authorization: Bearer eyJ..." \
  -H "Content-Type: application/json" \
  -d '{
    "request_id": "req-001",
    "text": "Tender Notice No. 2024/055\nIssuer: Ministry of Finance\nDeadline: 30 June 2024\nBudget: EGP 1,500,000\nScope: Supply of office furniture...",
    "output_language": "Arabic"
  }'
```

**Response**

```json
{
  "request_id": "req-001",
  "tender": {
    "title": "إشعار مناقصة رقم 2024/055",
    "issuer": "وزارة المالية",
    "reference_number": "2024/055",
    "publication_date": null,
    "submission_deadline": "2024-06-30",
    "budget": {
      "amount": 1500000.0,
      "currency": "EGP"
    },
    "scope_of_work": "توريد أثاث مكتبي",
    "key_requirements": [],
    "eligibility_criteria": [],
    "evaluation_criteria": [],
    "deliverables": [],
    "contact": {
      "name": null,
      "email": null,
      "phone": null
    }
  },
  "meta": {
    "success": true,
    "provider_used": "openai_mini",
    "model_used": "gpt-4o-mini",
    "input_tokens": 512,
    "output_tokens": 198,
    "cost_usd": 0.000196,
    "latency_ms": 1340.5
  }
}
```

**Request fields**

| Field | Type | Required | Description |
|---|---|---|---|
| `text` | string | Yes | Tender document text (10–50,000 chars) |
| `output_language` | string | No | `"Arabic"` (default) or `"English"` |
| `request_id` | string | No | Client correlation ID. Auto-generated if omitted. |

---

## API Documentation

| URL | Description |
|---|---|
| `http://localhost:8000/api/docs/` | Swagger UI |
| `http://localhost:8000/api/redoc/` | ReDoc |
| `http://localhost:8000/api/schema/` | Raw OpenAPI JSON |

In development, Swagger is open. In production, it requires JWT auth.

---

## Running Tests

```bash
# from project root directory
pytest
```

Test coverage includes:
- JSON validator: direct parse, markdown fence recovery, Pydantic normalization, edge cases
- TenderSchema: date coercion, budget parsing, deadline validation, empty defaults
- Orchestrator: primary success, fallback triggering, retry exhaustion, cost accumulation
- API: auth enforcement, request validation, response shape, graceful failure

---

## Environment Variables Reference

| Variable | Required | Default | Description |
|---|---|---|---|
| `SECRET_KEY` | Yes | — | Django secret key |
| `DEBUG` | No | `False` | Debug mode |
| `ALLOWED_HOSTS` | No | `localhost,127.0.0.1` | Comma-separated hosts |
| `SUPABASE_DB_HOST` | Yes | — | Supabase DB hostname |
| `SUPABASE_DB_PORT` | No | `5432` | DB port |
| `SUPABASE_DB_NAME` | No | `postgres` | DB name |
| `SUPABASE_DB_USER` | No | `postgres` | DB user |
| `SUPABASE_DB_PASSWORD` | Yes | — | DB password |
| `REDIS_URL` | No | `redis://localhost:6379/0` | Redis connection URL |
| `OPENAI_API_KEY` | Yes | — | OpenAI API key |
| `PRIMARY_LLM_PROVIDER` | No | `openai_mini` | Primary provider key |
| `FALLBACK_LLM_PROVIDER` | No | `openai_full` | Fallback provider key |
| `LLM_MAX_RETRIES` | No | `2` | Retries per provider |
| `LLM_TIMEOUT_SECONDS` | No | `60` | Provider timeout |
| `SLACK_WEBHOOK_URL` | No | `""` | Slack incoming webhook URL |
| `JWT_ACCESS_TOKEN_LIFETIME_MINUTES` | No | `60` | Access token TTL |
| `JWT_REFRESH_TOKEN_LIFETIME_DAYS` | No | `7` | Refresh token TTL |
| `THROTTLE_RATE_USER` | No | `30/minute` | Per-user rate limit |
| `LOG_LEVEL` | No | `INFO` | Logging level |

---

## Tradeoffs & Notes

- **Synchronous extraction.** The LLM call blocks the HTTP request. This is intentional — the response contains the extracted data, so async extraction would require polling or webhooks, adding significant complexity for minimal gain at this scale.

- **Cost table is static.** `LLMResult.COST_TABLE` hardcodes token pricing. Update it when OpenAI changes prices. For production, consider fetching prices from a config store.

- **No LangChain used.** The spec lists LangChain but the extraction pipeline doesn't benefit from it — a direct OpenAI SDK call is simpler, faster, and easier to debug. LangChain would add value if chains, agents, or RAG were needed.

- **gpt-5.2 pricing estimate.** The cost table uses an estimated rate for gpt-5.2. Update `LLMResult.COST_TABLE` with actual pricing once confirmed.
