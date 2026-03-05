# HVAC Deal Intelligence — Real Data Stack Design
**Date:** 2026-03-04
**Status:** Approved
**Scope:** Transform synthetic-data prototype into a real acquisition-sourcing terminal

---

## Problem Statement

The existing platform discovers fake HVAC companies generated from name templates, assigns scores to random data, and produces memos with no basis in reality. The terminal looks correct but is empty of signal. The goal is to wire real data sources into every stage of the pipeline so a PE analyst looking at the output is reading about actual businesses they could call tomorrow.

---

## Approved Approach: Full Intelligence Stack Upgrade

Extend the existing 7-agent pipeline with three new agents. Nothing is deleted. The `FirecrawlScout` replaces the mock Scout when an API key is present; the mock falls back automatically when it is not. The two new downstream agents (ContentEnrichment, Council) slot in after the existing stages.

### Pipeline Before vs. After

```
BEFORE:
Scout → Enrich → Signals → Score → Rank → Dossier

AFTER:
FirecrawlScout → Enrich → ContentEnrich → Signals → Score → Rank → [Council if qualified] → Dossier
```

Orchestrator stages and progress percentages will be adjusted to fit the two new stages.

---

## Section 1: Discovery Engine

### New Agent: `backend/agents/firecrawl_scout.py`

Uses the `firecrawl-py` Python SDK. Replaces the mock Scout when `FIRECRAWL_API_KEY` is set in `.env`. Falls back to existing mock Scout otherwise.

### Data Sources (per city)

**Tier 1 — Web search (primary, stable):**
```python
app.search(f"HVAC contractor {city} {state}", limit=20)
```
Returns Google-indexed business websites. Stable because it does not depend on any single directory's HTML layout.

**Tier 2 — Yellow Pages structured extract (secondary):**
```python
app.scrape_url(
    f"https://www.yellowpages.com/search?search_terms=hvac+contractor&geo_location_terms={city}+{state}",
    formats=["extract"],
    extract={"schema": BusinessListSchema}
)
```
Firecrawl handles JS rendering server-side and returns clean JSON. Yellow Pages is secondary: if its layout changes, the system degrades gracefully to Tier 1 results only, without crashing.

### Deduplication

Normalize and hash: `slugify(name) + phone[-7:] + street_number`. Skip if hash already exists in the DB for this city. This handles branches, name variations, and companies appearing on multiple directories.

### Fields Collected

| Field | Source |
|-------|--------|
| name | Directory listing |
| city, state | Query context |
| phone | Directory listing |
| address | Directory listing |
| google_rating | Directory listing |
| google_review_count | Directory listing |
| website | Directory listing |
| discovery_source | Set by agent: "firecrawl_search" \| "yellowpages" \| "mock" |

### Config Changes

```python
# backend/config.py
firecrawl_api_key: str = ""
```

```env
# backend/.env
FIRECRAWL_API_KEY=fc-your-key-here
```

---

## Section 2: Content Enrichment Layer

### New Agent: `backend/agents/content_enrichment.py`

Runs after the existing `EnrichmentAgent` (which handles domain age, SSL, tech stack via HTTPX + WHOIS). The `ContentEnrichmentAgent` visits the company website using Firecrawl's `extract` endpoint to pull semantic business signals.

### Extraction Schema

```python
ContentSignalSchema = {
    "type": "object",
    "properties": {
        "years_in_business": {"type": "integer"},        # "Serving Phoenix since 1987" → 37
        "is_family_owned": {"type": "boolean"},           # "family-owned and operated"
        "offers_24_7": {"type": "boolean"},               # "24/7 emergency service"
        "service_count": {"type": "integer"},             # count of distinct service lines
        "is_recruiting": {"type": "boolean"},             # "Join our team" / "Now hiring"
        "technician_count": {"type": "integer"},          # "fleet of 12 certified technicians"
        "serves_commercial": {"type": "boolean"},         # commercial/industrial clients mentioned
        "has_financing": {"type": "boolean"},             # financing options mentioned
        "mentions_decades": {"type": "boolean"}           # "decades of experience" language
    }
}
```

Firecrawl uses its AI extraction layer to find these values anywhere on the page (including dynamically rendered content). If the website returns an error or the company has no website, all content signals default to `None` — the scoring engine handles sparse data gracefully.

### New Database Columns

Added to the `companies` table via `migrate_db()`. All nullable to preserve backward compatibility with existing records.

| Column | Type | Description |
|--------|------|-------------|
| `is_family_owned_likely` | Boolean | Family ownership detected |
| `offers_24_7` | Boolean | 24/7 service advertised |
| `service_count_estimated` | Integer | Number of distinct services listed |
| `years_in_business_claimed` | Integer | Years stated on website |
| `is_recruiting` | Boolean | Hiring language detected |
| `technician_count_estimated` | Integer | Technicians mentioned |
| `serves_commercial` | Boolean | Commercial service mentioned |
| `discovery_source` | String | "firecrawl_search" / "yellowpages" / "mock" |
| `content_enriched` | Boolean | Whether content enrichment ran |
| `council_analyzed` | Boolean | Whether LLM Council has reviewed |

---

## Section 3: Scoring Model Enhancement

The existing 3-subscore model (Transition 0–40, Quality 0–35, Platform 0–25) is preserved. Content signals add additional points to each subscore, raising the ceiling for companies that also have rich website data.

### Content Signal Scoring Additions

| Signal | Subscore | Points | Rationale |
|--------|----------|--------|-----------|
| `years_in_business > 20` | Transition | +5 | Founding-generation operator near retirement |
| `is_family_owned == True` | Transition | +4 | Key-man risk; succession planning is common trigger |
| `is_recruiting == True` | Platform | +3 | Has operational capacity for growth |
| `serves_commercial == True` | Platform | +4 | Higher ACV, better roll-up fit |
| `offers_24_7 == True` | Quality | +3 | Systemized operations, not lifestyle business |
| `service_count >= 5` | Quality | +3 | Diversified revenue lines, lower single-service churn |
| `technician_count >= 8` | Platform | +3 | Team already in place, not founder-dependent |

### Scoring Explanation Enhancement

Thesis bullets now prefer content-derived language over domain-age proxies:

**Before:** `"17-year domain — long-tenured ownership approaching succession"`
**After:** `"Family-owned since 1987 (37yr) — founding-generation operator, succession pressure confirmed on website"`

When content signals are missing (company has no website), the existing domain-age and review-count signals remain the explanation basis, clearly labeled as proxies.

---

## Section 4: Council Qualification Gate (Cost/Latency Guardrail)

**This gate is mandatory before every council run.** It prevents hallucination on thin briefs and controls OpenRouter API cost.

### Qualification Criteria (ALL must pass)

| Criterion | Threshold | Reason |
|-----------|-----------|--------|
| Conviction score | ≥ 60 | Below this, the brief is too weak to produce credible analysis |
| Has website | `website_active == True` | Without a website there is no real-world context for the council |
| Content enrichment ran | `content_enriched == True` | Council needs structured signals, not just review count |
| Minimum populated signals | ≥ 4 of 9 content signals non-null | Fewer than 4 signals → brief will be too thin, council will speculate |
| Not already analyzed | `council_analyzed == False` | Avoid redundant API calls on re-runs |

### What Happens to Disqualified Companies

Disqualified companies are **not penalized in scoring** — they remain in the ranked feed with their conviction score. They simply do not receive a council thesis. The right panel for these companies shows the existing template-generated thesis with a `"PRELIMINARY — Council analysis pending"` label.

### Cost Envelope

Typical council run per company: ~3,000 tokens Stage 1 (3 models) + ~2,000 tokens Stage 2 + ~1,500 tokens Stage 3 = ~12,000 tokens total across all calls.
At OpenRouter pricing (~$0.0003/1K tokens for fast models), cost per company ≈ **$0.004**.
For 10 companies: **~$0.04 per full pipeline run**.
The guardrail ensures we never run council on companies that would waste these credits.

---

## Section 5: LLM Council Integration

### New Agent: `backend/agents/council.py`

Replicates the llm-council deliberation logic directly in the HVAC backend using OpenRouter. Does not depend on the `llm-council` service running on port 8001. Self-contained.

### Input Per Company (Investment Brief)

A structured 400-word brief constructed from:
- Company name, city, state, age, rating, review count
- Content signals (family-owned, 24/7, years stated, recruiting, services, technicians)
- All four subscores with their contributing factors
- Valuation band (low / mid / high) and multiple range
- Top 2 comparable HVAC deals from the comp table
- Current workflow status

### Three-Stage Process

**Stage 1 — Independent analysis (parallel, `asyncio.gather`):**
Three models receive the brief and each produce an independent "buy / monitor / pass" recommendation with reasoning. Models: `anthropic/claude-sonnet-4-5`, `openai/gpt-4o-mini`, `google/gemini-flash-1.5`.

**Stage 2 — Peer review:**
Each model receives the three anonymous responses labeled Response A / B / C. Each ranks them by reasoning quality. Aggregate ranking computed (lower average rank = stronger response).

**Stage 3 — Chairman synthesis:**
`anthropic/claude-sonnet-4-5` receives all Stage 1 responses, all Stage 2 rankings, and synthesizes the final investment thesis. Produces structured JSON output:

```json
{
    "investment_thesis": "...",
    "key_strengths": ["...", "...", "..."],
    "key_risks": ["...", "..."],
    "valuation_estimate": "$1.2M–$3.8M",
    "recommended_action": "Owner outreach — lead with succession planning angle",
    "council_consensus": "strong buy | moderate interest | split | pass"
}
```

### Storage

Council output stored in the existing `memos` table:
- `model_used = "council-v1"`
- `version = 2` (version 1 = template memo, version 2 = council)
- `title = "Council Investment Thesis — {company_name}"`
- `content` = full markdown-formatted thesis (rendered in right panel)
- `status = "final"`

`Company.council_analyzed` set to `True` after successful run.

### Config

```python
# backend/config.py
openrouter_api_key: str = ""
council_models: list = ["anthropic/claude-sonnet-4-5", "openai/gpt-4o-mini", "google/gemini-flash-1.5"]
council_chairman: str = "anthropic/claude-sonnet-4-5"
council_min_conviction: int = 60       # gate: minimum conviction score
council_min_signals: int = 4           # gate: minimum non-null content signals
```

---

## Section 6: Terminal Display Changes

### Right Panel — Primary Change

When a company has a council memo (`model_used = "council-v1"`), the **Thesis tab** shows the council output as the primary content:
- `COUNCIL ANALYSIS` header badge with consensus indicator (color-coded: green = strong buy, amber = moderate, red = pass/split)
- Full investment thesis paragraph (chairman synthesis)
- Strengths and Risks in two columns
- Valuation estimate with comp range
- Recommended next action (bold, prominent)

When no council memo exists, the Thesis tab shows the existing template-generated content with a `PRELIMINARY` label.

### Deal Feed (Center Panel)

Companies with a council analysis get a small `⚖` icon in the deal feed row. Investors immediately see which targets have full deliberation vs. preliminary scoring only.

### Screener Panel (Left Panel) — Language Cleanup

| Before | After |
|--------|-------|
| `DEAL SCREENER` header | `DEAL FILTER` |
| `MATCHING TARGETS: 128` | `128 targets · 10 council-reviewed` |
| `PIPELINE STATUS` anywhere | Remove entirely from DealDesk |

No new pages. No new routes. The Ops page retains pipeline controls. DealDesk remains the primary surface.

---

## Section 7: Files Changed

### New Files

| File | Purpose |
|------|---------|
| `backend/agents/firecrawl_scout.py` | Firecrawl-based real company discovery |
| `backend/agents/content_enrichment.py` | Website semantic signal extraction via Firecrawl |
| `backend/agents/council.py` | LLM Council deliberation engine (self-contained) |

### Modified Files

| File | Change |
|------|--------|
| `backend/config.py` | Add `firecrawl_api_key`, `openrouter_api_key`, council settings |
| `backend/database.py` | Add 10 new columns to `migrate_db()` |
| `backend/models.py` | Add new nullable Company columns |
| `backend/agents/orchestrator.py` | Add ContentEnrich stage + Council stage (with gate check) |
| `backend/agents/scoring_engine.py` | Add content signal inputs to all three subscore functions |
| `backend/main.py` | Import new agents; no routing changes needed |
| `frontend/src/pages/DealDesk.tsx` | Council thesis in right panel; language cleanup |
| `frontend/src/types/index.ts` | Add content signal fields to Deal type |
| `backend/requirements.txt` | Add `firecrawl-py`, `openai` |
| `backend/.env` | Add `FIRECRAWL_API_KEY`, `OPENROUTER_API_KEY` |

---

## Section 8: New Python Dependencies

```
firecrawl-py>=1.0.0    # Firecrawl Python SDK for discovery + content extraction
openai>=1.0.0          # OpenAI-compatible client for OpenRouter API calls
```

---

## Section 9: Backward Compatibility

- All new DB columns are nullable — existing 128 mock companies are unaffected
- `use_mock_data=True` (default) preserves the full mock pipeline for development without API keys
- The mock Scout, mock Enrichment, and template Memos continue to work exactly as before
- No existing API endpoints are removed or changed in signature
- Frontend gracefully renders missing council memos with the existing thesis view

---

## Out of Scope (Explicit)

- No new pages or routes
- No CRM sync (Salesforce, HubSpot)
- No multi-user auth
- No email outreach integration
- No BuiltWith API (configured but still unused)
- No changes to the `llm-council` repo itself
- No Playwright usage (Firecrawl handles JS rendering server-side; Playwright is not needed)

---

## Success Criteria

1. A pipeline run with real API keys discovers actual HVAC businesses from real directories
2. Content enrichment successfully extracts at least 4 signals from ≥70% of companies that have a working website
3. Companies scoring ≥60 with sufficient signals receive a council thesis that reads like a PE investment memo — not a template
4. The right panel for a council-reviewed company contains no placeholder text, no "lorem ipsum," and no signals that contradict the company's actual website
5. The terminal language is entirely investor-facing: no "pipeline runs," no "database records," no developer terminology on the DealDesk screen
