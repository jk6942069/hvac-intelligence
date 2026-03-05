# HVAC Intelligence Engine

> Deal origination intelligence for HVAC acquisition targets

A 7-agent AI pipeline that discovers, enriches, scores, and ranks off-market HVAC companies by their likelihood of ownership transition — producing investor-ready acquisition dossiers for search funds, PE firms, and roll-up platforms.

---

## Quick Start

### Prerequisites
- Python 3.11+
- Node.js 18+

### 1. Setup Backend
```bash
cd backend
pip install -r requirements.txt

# Copy and configure environment
cp ../.env.example .env
# Edit .env — set USE_MOCK_DATA=true to test without API keys
```

### 2. Setup Frontend
```bash
cd frontend
npm install
```

### 3. Run Everything
```bash
# Windows — double-click:
start.bat

# Or manually:
# Terminal 1:
cd backend && python main.py

# Terminal 2:
cd frontend && npm run dev
```

Open: **http://localhost:5173**

---

## The 7-Agent Pipeline

| Agent | Purpose |
|-------|---------|
| **1 — Scout** | Discovers HVAC companies via Google Places API across US cities |
| **2 — Enrichment** | Checks SSL, domain age (WHOIS), tech stack, website health, social presence |
| **3 — Signal Analyst** | Detects 12 ownership lifecycle signals (OLD_DOMAIN, WEBSITE_DOWN, etc.) |
| **4 — Scoring Engine** | Converts signals into 0–100 transition probability score |
| **5 — Ranking Engine** | Sorts all companies, assigns tiers (Top Candidate / Watch List) |
| **6 — Dossier Generator** | Claude AI writes investor-ready 500-word acquisition reports |
| **7 — Orchestrator** | Coordinates all agents, streams real-time progress via WebSocket |

---

## Scoring Model

Scores range 0–100 across 4 categories:

| Category | Max Points | Key Signals |
|----------|-----------|-------------|
| Operating Age | 25 | Domain 15+ years → strong retirement signal |
| Digital Health | 30 | No SSL, website down, outdated tech |
| Review Signals | 25 | Low review count, below-average rating |
| Lifecycle Signals | 20 | No social presence, composite OLD_BRAND flag |

**Top Candidates**: Score ≥ 65 or top 10% of dataset

---

## Configuration

### Demo Mode (default)
`USE_MOCK_DATA=true` — generates 100+ realistic HVAC companies with simulated signals. No API keys needed. Perfect for demos and testing.

### Live Mode
Set `USE_MOCK_DATA=false` in `.env` and add:

- **`GOOGLE_PLACES_API_KEY`** — [Google Cloud Console](https://console.cloud.google.com/apis/library/places-backend.googleapis.com)
- **`ANTHROPIC_API_KEY`** — [Anthropic Console](https://console.anthropic.com/)

---

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/api/stats/dashboard` | Dashboard statistics |
| `GET` | `/api/companies` | List companies (paginated, filterable) |
| `GET` | `/api/companies/{id}` | Company detail + dossier |
| `PUT` | `/api/companies/{id}/feedback` | Submit outcome feedback |
| `GET` | `/api/companies/export/csv` | Export full dataset as CSV |
| `POST` | `/api/pipeline/run` | Start pipeline run |
| `GET` | `/api/pipeline/status` | Current pipeline status |
| `WS` | `/api/pipeline/ws` | Real-time pipeline updates |
| `GET` | `/api/dossiers` | List all dossiers |
| `POST` | `/api/dossiers/{id}/generate` | Generate dossier for company |
| `GET` | `/api/docs` | Interactive API documentation |

---

## Revenue Model

This system generates deal flow that can be monetized via:

- **Retained sourcing contracts** — charge buyers $2k–$5k/month for proprietary pipeline access
- **Proprietary deal lists** — sell curated lists of top 50–100 targets per region
- **Consulting/intelligence access** — advisory relationships with HVAC roll-up platforms

---

## Feedback Learning Loop

Record outcomes on each company (owner responded, not interested, already selling). The scoring engine learns which signals correlate with real conversations and adjusts signal weights automatically over time.

---

## Tech Stack

**Backend**: FastAPI · SQLAlchemy · SQLite · Anthropic SDK · HTTPX
**Frontend**: React 18 · TypeScript · Tailwind CSS · Recharts · React Query
**AI**: Claude claude-sonnet-4-6 for dossier generation and signal reasoning
