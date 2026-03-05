# SaaS MVP Production Layer — Design Document

**Date:** 2026-03-05
**Status:** Approved
**Scope:** Deploy + Auth + Stripe + Multi-tenant data isolation + Rate limiting. No background jobs, contact integrations, or landing page in this phase.

---

## Decision Log

| Question | Decision |
|---|---|
| Phasing approach | MVP-first: ship revenue-ready subset now, layer rest on top |
| Infrastructure | Vercel (frontend) + Railway (FastAPI backend) + Supabase (Auth + PostgreSQL) + Stripe |
| Auth provider | Supabase Auth — JWT issued by Supabase, verified by FastAPI |
| Database migration | SQLite → Supabase PostgreSQL (asyncpg). SQLite stays for tests only. |
| Multi-tenancy | Row-level: user_id on companies/memos/pipeline_runs + PostgreSQL RLS |
| Plan storage | users table in PostgreSQL (not in JWT) |
| Stripe approach | Hosted Checkout + Customer Portal webhooks |

---

## Section 1: Architecture

```
Browser
  └─▶ Vercel (React + Vite, static)        ← free tier
        │
        ├─▶ Railway (FastAPI, $5/mo)        ← existing app + new auth/billing
        │     ├─▶ Supabase PostgreSQL       ← replaces SQLite in production
        │     └─▶ Stripe SDK               ← billing
        │
        └─▶ Supabase Auth                  ← JWT issued here, verified by FastAPI
```

**What changes:** SQLite → Supabase PG in prod, JWT middleware in FastAPI, AuthContext + login pages in React, user_id on data tables, Stripe checkout/webhook endpoints.

**What stays untouched:** All 8 FastAPI routers (except adding `user_id` filter), all agents (OSMScout, YPScraper, ScoringEngine, DossierGenerator, Orchestrator), all 84 backend tests (run against SQLite via TEST_DATABASE_URL).

---

## Section 2: Authentication

### Frontend

- `@supabase/supabase-js` client initialized with `VITE_SUPABASE_URL` + `VITE_SUPABASE_ANON_KEY`
- `AuthContext` + `useAuth` hook wraps the entire app
- Three new pages: `/login`, `/register`, `/reset-password`
- `ProtectedRoute` component wraps all dashboard routes — redirects to `/login` if no session
- Single axios interceptor in `frontend/src/api/client.ts` injects `Authorization: Bearer <jwt>` on every request

### Backend

- `backend/auth.py` — `get_current_user` FastAPI dependency:
  1. Reads `Authorization: Bearer <token>` header
  2. Verifies JWT signature against Supabase JWKS (fetched once at startup, cached)
  3. Extracts `sub` (= user_id) and `email` from token
  4. Looks up `users` table for `plan` and `scans_used_this_month`
  5. Returns `CurrentUser(user_id, email, plan, scans_used_this_month)`
  6. Raises `401` if token invalid or missing

- All data-touching routes add `user: CurrentUser = Depends(get_current_user)`
- Health check and public stats routes remain unauthenticated

### Session handling

- Supabase refreshes tokens automatically on the frontend
- Backend is fully stateless — no server-side sessions
- Logout: `supabase.auth.signOut()` → React clears context → redirect to `/login`

---

## Section 3: Database

### New `users` table

```sql
CREATE TABLE users (
    id                     TEXT PRIMARY KEY,  -- = Supabase auth.uid()
    email                  TEXT,              -- cached copy from JWT
    plan                   TEXT NOT NULL DEFAULT 'starter',
    stripe_customer_id     TEXT,
    stripe_subscription_id TEXT,
    scans_used_this_month  INTEGER NOT NULL DEFAULT 0,
    scans_reset_at         TIMESTAMP,
    created_at             TIMESTAMP DEFAULT NOW()
);
```

### Multi-tenancy columns added

| Table | Column | Index |
|---|---|---|
| `companies` | `user_id TEXT REFERENCES users(id)` | `(user_id, conviction_score)` |
| `memos` (if table exists) | `user_id TEXT REFERENCES users(id)` | `(user_id)` |
| `pipeline_runs` (new) | `user_id TEXT REFERENCES users(id)` | `(user_id, created_at)` |

### New `pipeline_runs` table

```sql
CREATE TABLE pipeline_runs (
    id          TEXT PRIMARY KEY,
    user_id     TEXT REFERENCES users(id),
    cities      JSON,
    status      TEXT DEFAULT 'running',
    companies_found INTEGER DEFAULT 0,
    started_at  TIMESTAMP DEFAULT NOW(),
    completed_at TIMESTAMP
);
```

### Driver swap

```python
# config.py — production uses DATABASE_URL env var
database_url: str = os.getenv("DATABASE_URL", "sqlite+aiosqlite:///./hvac_intel.db")

# Tests always use SQLite via TEST_DATABASE_URL or the default
```

SQLAlchemy async engine is already in place — only the connection string changes. Alembic manages all schema migrations.

### PostgreSQL RLS (defense-in-depth)

Applied to `companies`, `memos`, `pipeline_runs` after Alembic migration:

```sql
ALTER TABLE companies ENABLE ROW LEVEL SECURITY;
CREATE POLICY user_isolation ON companies
    USING (user_id = current_setting('app.current_user_id'));
```

FastAPI sets `SET LOCAL app.current_user_id = '<user_id>'` at the start of each request transaction.

---

## Section 4: Multi-Tenancy

**Rule:** every query on business data adds `.where(Model.user_id == user.user_id)`.

**Affected routers:** `companies.py`, `dealdesk.py`, `dossiers.py`, `pipeline.py`

**Pipeline writes:** when OSMScout/YPScraper returns results, orchestrator stamps every Company with the triggering user's `user_id` before DB insert.

**New user experience:** empty Deal Desk, zero companies — clean workspace per account.

---

## Section 5: Stripe Billing

### Plans

| Plan | Price | Scan limit |
|---|---|---|
| Starter | $49/month | 10 pipeline scans/month |
| Professional | $149/month | Unlimited |
| Enterprise | Contact sales | Unlimited + priority |

### Flow

1. User clicks "Upgrade" in Settings → POST `/api/billing/create-checkout` → returns Stripe Checkout URL → redirect
2. User completes payment on Stripe's hosted page → Stripe fires `checkout.session.completed` webhook
3. Webhook handler at `POST /api/billing/webhook` updates `users.plan` + `users.stripe_customer_id`
4. User clicks "Manage Billing" → POST `/api/billing/portal` → returns Stripe Customer Portal URL → redirect
5. Subscription changes (upgrade/downgrade/cancel) fire `customer.subscription.updated` webhook → update `users.plan`

### Backend endpoints

```
POST /api/billing/create-checkout    → creates Stripe Checkout session
POST /api/billing/webhook            → Stripe webhook (no auth header, uses Stripe signature)
POST /api/billing/portal             → creates Customer Portal session
GET  /api/billing/status             → returns current plan + usage for Settings page
```

### Stripe products to create (manual one-time setup in Stripe dashboard)

- Product: "Starter" → Price: $49/month recurring
- Product: "Professional" → Price: $149/month recurring
- Store Price IDs in Railway env vars: `STRIPE_STARTER_PRICE_ID`, `STRIPE_PRO_PRICE_ID`

---

## Section 6: Rate Limiting

**Enforced server-side in `pipeline.py`** before the pipeline runs:

```python
PLAN_LIMITS = {
    "starter": 10,
    "professional": None,   # unlimited
    "enterprise": None,
}

def check_scan_quota(user: CurrentUser):
    limit = PLAN_LIMITS[user.plan]
    if limit and user.scans_used_this_month >= limit:
        raise HTTPException(429, "Monthly scan limit reached. Upgrade to Professional.")
```

Monthly reset: `scans_used_this_month` resets to 0 when `scans_reset_at` is more than 30 days ago (checked on each scan attempt). No cron job needed for MVP.

---

## Section 7: Deployment Configs

### Vercel (`frontend/vercel.json`)
```json
{
  "rewrites": [{ "source": "/(.*)", "destination": "/index.html" }]
}
```
Env vars: `VITE_SUPABASE_URL`, `VITE_SUPABASE_ANON_KEY`, `VITE_API_URL`

### Railway (backend)
Start command: `uvicorn main:app --host 0.0.0.0 --port $PORT`
Env vars: `DATABASE_URL`, `SUPABASE_JWT_SECRET`, `STRIPE_SECRET_KEY`, `STRIPE_WEBHOOK_SECRET`, `STRIPE_STARTER_PRICE_ID`, `STRIPE_PRO_PRICE_ID`

### CORS update
`cors_origins` in config expands to include the Vercel production domain.

---

## First Deploy Checklist (manual steps for user)

1. Create Supabase project → copy `SUPABASE_URL`, `SUPABASE_ANON_KEY`, `SUPABASE_JWT_SECRET`, `DATABASE_URL`
2. Create Stripe account → create Starter + Professional products → copy Price IDs and `STRIPE_SECRET_KEY`
3. Set Stripe webhook endpoint to `https://<railway-domain>/api/billing/webhook` → copy `STRIPE_WEBHOOK_SECRET`
4. Deploy backend to Railway → set all env vars
5. Deploy frontend to Vercel → set `VITE_SUPABASE_URL`, `VITE_SUPABASE_ANON_KEY`, `VITE_API_URL`
6. Run Alembic migration: `alembic upgrade head` (Railway can run this as a release command)
7. Enable RLS policies in Supabase SQL editor

---

## Out of Scope (Phase 2)

- Background job system (Redis + Celery)
- SendGrid email outreach
- Twilio phone/SMS integration
- Automated 24-hour pipeline scans
- Public landing page / marketing site
- Sentry error monitoring
