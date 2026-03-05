# SaaS Product Polish — Design Document

**Date:** 2026-03-05
**Status:** Approved
**Scope:** Product experience overhaul — free-tier data source, scoring transparency, memo generator, Deal Desk redesign, Pipeline UI cleanup, Settings redesign. Auth, PostgreSQL, and deployment are out of scope for this phase.

---

## Goal

Transform the HVAC Deal Intelligence Platform from a developer prototype into a commercial intelligence product that works out-of-the-box without API keys, with Firecrawl and LLM Council activating as optional premium upgrades.

---

## Decision Log

| Question | Decision |
|---|---|
| How does this relate to the Firecrawl/LLM Council work? | Keep as premium layer — OSM + templates are the free default path |
| SaaS infrastructure (auth, PostgreSQL, deployment)? | Deferred — product experience first |
| OSM data quality fallback? | OSM + Yellow Pages scraping for free tier coverage |
| PDF generation? | Client-side (jsPDF) — no server dependencies |
| OSM discovery trigger? | On-demand only — runs when user clicks Run Pipeline |

---

## Section 1: Data Sources & Pipeline

### Free Tier (default, no API keys required)

**`OSMScout`** replaces `ScoutAgent`:
- Queries Overpass API with HVAC tags: `shop=hvac`, `craft=hvac`, `craft=heating`, `craft=plumber`
- Maps OSM nodes/ways → Company model (name, address, city, state, phone, website, lat/lon)
- Typically returns 5–40 companies per city

**`YPScraper`** runs as fallback when OSM returns < 5 results:
- HTTPX GET `https://www.yellowpages.com/search?search_terms=hvac&geo_location={city}+{state}`
- BeautifulSoup parses: `.organic .result`, `.business-name`, `.phones`, `.street-address`
- No API key required

### Premium Tier (activates with optional keys)

- `FirecrawlScout` activates instead of `OSMScout` when `FIRECRAWL_API_KEY` is set
- LLM Council activates when `OPENROUTER_API_KEY` is set
- Both are already implemented on `feature/real-data-intelligence-stack`

### Removals

| Item | Action |
|---|---|
| `ScoutAgent` (mock data generator) | Deleted |
| `USE_MOCK_DATA` config flag | Removed |
| `google_places_api_key` config field | Removed |
| Google Places scout code | Removed |
| Demo Mode toggle (frontend) | Removed |

### Pipeline Flow (updated)

```
OSMScout / YPScraper (free) OR FirecrawlScout (premium)
  ↓
EnrichmentAgent (domain age, SSL, tech stack, website health)
  ↓
ContentEnrichmentAgent (premium — Firecrawl key required)
  ↓
SignalAnalyst
  ↓
ScoringEngine (enhanced with new signals)
  ↓
RankingEngine
  ↓
DossierGenerator (template-based by default, Claude optional)
  ↓
CouncilAgent (premium — OpenRouter key required)
```

---

## Section 2: Scoring System

### New 5-Dimension Model (0–100)

Replaces the Transition/Quality/Platform labeling. Math is preserved and extended.

| Dimension | Weight | Max Points | Previous Label |
|---|---|---|---|
| Market Strength | 25% | 25 | Platform Fit |
| Customer Reputation | 20% | 20 | Business Quality (simplified) |
| Business Longevity | 20% | 20 | Partial Transition + Quality |
| Operational Signals | 15% | 15 | New (was implicit) |
| Risk Adjustment | 20% | 20 | New explicit negative dimension |

**Formula:**
```
Conviction Score = (0.25 × Market Strength) + (0.20 × Customer Reputation)
                 + (0.20 × Business Longevity) + (0.15 × Operational Signals)
                 + (0.20 × Risk Adjustment)
```

### New Positive Signals

| Signal | Points | Dimension |
|---|---|---|
| Years in business ≥ 20 (from OSM/YP data) | +6 | Business Longevity |
| Years in business ≥ 10 | +3 | Business Longevity |
| "Emergency service" or "24/7" detected on website | +5 | Operational Signals |
| Multiple technician mentions on site | +4 | Operational Signals |
| Owner name visible on site (owner-operated signal) | +4 | Business Longevity |
| Sun Belt / high-demand region (AZ, TX, FL, TN, NC, GA, SC, NV) | +8 | Market Strength |

### New Risk Signals (deductions from Risk Adjustment base of 20)

| Signal | Deduction |
|---|---|
| No website or website offline | −8 |
| Fewer than 10 reviews | −6 |
| Rating below 3.5★ | −5 |
| No SSL certificate | −3 |
| No social media presence | −2 |

Risk Adjustment starts at 20 and deductions are applied. Minimum is 0.

### Score Tiers (unchanged)

- **Top Candidates**: conviction ≥ 65 OR top 10% of dataset
- **Watch List**: conviction 40–64
- **Monitor**: conviction < 40

---

## Section 3: UI Changes

### 3a. Signals Tab — Score Transparency

Two clearly separated sections replace the current flat signals list:

**Positive Signals (green):**
Each row shows:
- Signal label and description
- Point impact (e.g., "+8 pts")
- Dimension it contributes to (e.g., "Market Strength")
- Severity badge: High / Medium / Low

**Risk Signals (red):**
Same structure, negative impact shown in red.

**Conviction Score Breakdown Bar:**
Visual horizontal bar at the bottom showing each dimension's contribution as a proportional segment. Formula shown explicitly below: `Conviction = 25% Market + 20% Reputation + 20% Longevity + 15% Operations + 20% Risk`.

### 3b. Valuation Tab — Calculation Inputs

Full transparency on every assumption:

```
REVENUE ESTIMATE
  Review count:            [n] reviews
  Jobs per review ratio:   8× (industry avg)
  Estimated annual jobs:   [n × 8]
  Avg HVAC ticket size:    $385
  Estimated Revenue:       ~$[calculated]

EBITDA ESTIMATE
  EBITDA margin:           20% (HVAC industry avg 15–25%)
  Estimated EBITDA:        ~$[calculated]

VALUATION RANGE
  Multiple range:          3.5× – 5.5× EBITDA
  Low / Mid / High:        $[x] / $[y] / $[z]

⚠ Proxy estimate only. Verify with seller financials in diligence.
```

Assumption values (margin %, multiple range, ticket size, jobs-per-review ratio) shown as editable constants — users can override them in Settings.

### 3c. Memo Generator — Template-Based

Replaces Claude-powered dossier with instant template generation. Eight sections populated from company data:

1. Executive Summary
2. Market Overview
3. Company Signals
4. Financial Estimate
5. Valuation Range
6. Investment Thesis
7. Risk Factors
8. Next Steps

**Export options:**
- **Download PDF** — jsPDF renders memo client-side
- **Download Markdown** — `.md` file download via browser anchor
- **Copy Link** — copies `{host}/memo/{id}` to clipboard (public URL, no auth required)

Generation is instant — no API call. Clicking "Generate Memo" fills the template synchronously from existing score/signal/valuation data already in the database.

---

## Section 4: Deal Desk

### Workflow States (updated)

Replaces current CRM states with acquisition-pipeline-specific states:

```
Not Contacted → Contacted → Conversation Started → Meeting Scheduled
                                                          ↓
                              Passed ← LOI Considered ← Under Review
```

**Migration map for existing records:**

| Old State | New State |
|---|---|
| `not_contacted` | `Not Contacted` |
| `contacted` | `Contacted` |
| `responded` | `Contacted` |
| `interested` | `Conversation Started` |
| `follow_up` | `Conversation Started` |
| `closed_won` | `LOI Considered` |
| `closed_lost` | `Passed` |
| `not_interested` | `Passed` |

### One-Click Export

"Export Briefing" button in the tearsheet panel generates a single investor briefing PDF containing:
- Company contact info (name, address, phone, website)
- Conviction score + 5-dimension breakdown
- All positive and risk signals with point impacts
- Valuation summary with all assumptions shown
- Investment thesis bullets
- Current workflow status + notes

Single PDF via jsPDF — one document for partner review or pre-call printing.

---

## Section 5: Pipeline / Ops Page

Replaces developer console with a clean 4-step progress UI:

```
◉  Scanning City Markets           ← animated pulse when active
◉  Discovering HVAC Companies      ← fills with checkmark on complete
○  Analyzing Business Signals
○  Ranking Acquisition Targets
```

**Run Pipeline interface:**
- City/state text input
- Max companies slider (10–100, default 50)
- "Run Pipeline" button

**Completion state:**
- All 4 steps show checkmarks
- Summary line: *"Pipeline complete — 47 companies added to Deal Desk."*
- No raw logs, no stage names (`scout`, `enrich`), no WebSocket debug output

**Progress label mapping (internal → user-facing):**

| Internal Stage | User-Facing Label |
|---|---|
| `scout` | Discovering HVAC Companies |
| `enrich` | Analyzing Business Signals |
| `content_enrich` | Analyzing Business Signals |
| `signals` | Analyzing Business Signals |
| `scoring` | Ranking Acquisition Targets |
| `ranking` | Ranking Acquisition Targets |
| `council` | Ranking Acquisition Targets |
| `dossiers` | Ranking Acquisition Targets |
| `complete` | Pipeline Complete |

---

## Section 6: Settings Page

### Structure

```
Account Settings
  — Display name, email (placeholder for future auth)

Team Members
  — Placeholder UI, "Coming soon" badge

Deal Export Preferences
  — Default export format: PDF | Markdown
  — Memo header: company logo upload slot

Report Format Preferences
  — Currency: USD | GBP | EUR | CAD
  — Valuation multiple range: [Low] × – [High] × EBITDA
  — Avg HVAC ticket size: $[default 385]
  — EBITDA margin assumption: [default 20]%
  — Jobs per review ratio: [default 8]×

Notifications
  — Placeholder toggles ("Coming soon")

─── Advanced Integrations ───────────────────────────────────────
  Firecrawl API Key     [optional — enables real-time web discovery]
  OpenRouter API Key    [optional — enables LLM Council analysis]
```

**What's removed:**
- Demo Mode toggle
- Google Places API key
- Anthropic API key field
- All developer-facing config

The Advanced Integrations section is at the bottom, visually de-emphasized. Users who don't scroll past Notifications never see API key inputs.

---

## Companies Page — Filter Additions

New filter controls added to the companies list:

| Filter | Type | Options |
|---|---|---|
| State | Multi-select dropdown | All US states |
| Conviction Score | Range slider | 0–100 |
| Years in Business | Range slider | 0–40+ |
| Review Rating | Min dropdown | ≥3.0 / ≥3.5 / ≥4.0 / ≥4.5 |
| Estimated Revenue | Range | <$500K / $500K–$1M / $1M–$3M / $3M+ |

Existing search bar and sort-by controls are preserved.

---

## Out of Scope (This Phase)

- User authentication / login system
- Multi-user accounts
- PostgreSQL migration
- Vercel / Railway deployment config
- Email outreach integration
- Real-time notification system

These are the follow-up SaaS infrastructure phase.

---

## Files Affected

### Backend
- `backend/agents/scout.py` — replaced by `osm_scout.py` + `yp_scraper.py`
- `backend/agents/orchestrator.py` — remove mock mode branching, add OSM/YP agents
- `backend/agents/scoring_engine.py` — add new signals, rename dimensions
- `backend/agents/dossier_generator.py` — pure template mode (no Claude default)
- `backend/config.py` — remove `USE_MOCK_DATA`, `google_places_api_key`; add valuation assumption defaults
- `backend/routers/dealdesk.py` — update workflow state enum
- `backend/routers/pipeline.py` — stage label mapping
- `backend/database.py` — workflow state migration

### Frontend
- `frontend/src/pages/Pipeline.tsx` — new 4-step progress UI
- `frontend/src/pages/Settings.tsx` — full redesign
- `frontend/src/pages/DealDesk.tsx` — new workflow states, export briefing button
- `frontend/src/pages/Companies.tsx` — new filter controls
- `frontend/src/pages/CompanyDetail.tsx` — Signals tab redesign, Valuation tab redesign, Memo tab with export buttons
- `frontend/src/types/index.ts` — updated workflow state enum, new signal types
- `frontend/src/components/MemoExport.tsx` — new component (PDF/MD/link export)
