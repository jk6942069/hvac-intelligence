"""
Agent 6 — Dossier Generator
Creates investor-ready acquisition intelligence reports using Claude AI.
"""
import asyncio
import logging
import random
from datetime import datetime
from config import settings

logger = logging.getLogger(__name__)

MOCK_TEMPLATE = """## Company Overview

{name} is an established HVAC service provider headquartered in {city}, {state}. Operating for over {age} years, the business has built its reputation through owner-operated management serving residential and light commercial customers in the local market. The company maintains a functional web presence and local community recognition consistent with a lifestyle business approaching ownership transition.

## Size & Operations Estimate

Based on available public signals, this operator appears to generate between $1.5M–$5M in annual revenue with an estimated workforce of 6–18 field technicians and support staff. The business model centers on service/repair calls and residential system replacements — a high-margin, recurring revenue profile typical of HVAC operators in this revenue band. Owner involvement in day-to-day operations is presumed high, based on digital patterns.

## Transition Signals Detected

{signals_text}

## Why This Company May Consider Selling

The convergence of a {age}+ year operating history with stagnant digital infrastructure strongly suggests a founder-owner in their late 50s or 60s who has not invested in growth-mode systems or succession planning. This operator profile — established, profitable, owner-operated, digitally neglected — is the textbook transition indicator seen in HVAC acquisitions. Without a clear successor or private equity relationship, sale is the most viable exit in the 1–3 year window.

## Acquisition Thesis

{name} represents a classic owner-operated HVAC business with stable, recurring cash flows and a geographically embedded customer base developed over multiple decades. A strategic or financial acquirer could unlock meaningful value through:

- **Digital modernization**: SEO, online booking, review generation, CRM deployment
- **Field management software**: Route optimization, dispatch efficiency, real-time tracking
- **Workforce expansion**: Structured technician recruitment and retention
- **Adjacent acquisitions**: Use as geographic anchor for a regional roll-up play

At current performance, this business likely commands a **3.5–5x EBITDA multiple**, with 15–25% upside potential post-professionalization within 18–24 months.

## Recommended Next Steps

1. **Identify owner name** via state contractor license database (cross-reference business address)
2. **Send personalized acquisition letter** referencing years in business and market position
3. **Follow up by phone** 10–14 days after letter — frame as advisory, not a hard offer
4. **Offer complimentary business valuation** — owners in this profile respond to curiosity about their company's worth
5. **Target Q1 or Q4** — HVAC off-season when owners have more time to think strategically
"""


def _build_signals_text(signals: list[dict]) -> str:
    if not signals:
        return "- No major negative signals detected — digital health appears adequate\n"
    lines = []
    for s in signals:
        icon = "🔴" if s["severity"] == "high" else "🟡" if s["severity"] == "medium" else "🔵"
        lines.append(f"- {icon} **{s['label']}**: {s['description']}")
    return "\n".join(lines)


def _mock_dossier(company: dict) -> str:
    name = company.get("name") or "This Company"
    city = company.get("city") or "the region"
    state = company.get("state") or ""
    age = max(5, round(company.get("domain_age_years") or random.randint(8, 20)))
    signals = company.get("signals") or []
    signals_text = _build_signals_text(signals)
    return MOCK_TEMPLATE.format(
        name=name, city=city, state=state, age=age, signals_text=signals_text
    )


class DossierGenerator:
    def __init__(self, api_key: str | None = None):
        self.api_key = api_key if api_key is not None else settings.anthropic_api_key
        self.client = None
        if self.api_key and not settings.use_mock_data:
            try:
                import anthropic
                self.client = anthropic.AsyncAnthropic(api_key=self.api_key)
                logger.info("Anthropic client initialized for dossier generation.")
            except Exception as e:
                logger.warning(f"Anthropic client init failed: {e}")

    def generate_template(self, company: dict) -> str:
        """Generate a structured investment memo from company data. No API key required."""
        from datetime import date

        name = company.get("name", "Unknown Company")
        city = company.get("city", "")
        state = company.get("state", "")
        conviction = company.get("conviction_score", 0)
        rating = company.get("google_rating") or "N/A"
        reviews = company.get("google_review_count") or 0
        domain_age = company.get("domain_age_years") or 0
        website = company.get("website") or "N/A"
        phone = company.get("phone") or "N/A"
        explanation = company.get("score_explanation") or {}
        thesis_bullets = explanation.get("thesisBullets") or []
        key_risks = explanation.get("keyRisks") or []
        valuation = explanation.get("valuationBand") or {}
        action = explanation.get("recommendedAction") or "Evaluate further"

        low = valuation.get("low", 0)
        mid = valuation.get("mid", 0)
        high = valuation.get("high", 0)

        thesis_lines = "\n".join(f"- {b}" for b in thesis_bullets) or "- Established local HVAC operator"
        risk_lines = "\n".join(f"- {r}" for r in key_risks) or "- Standard HVAC sector risks"

        tier = "Top Candidate" if conviction >= 65 else ("Watch List" if conviction >= 40 else "Monitor")

        return f"""# Investment Memo: {name}

**Conviction Score:** {conviction}/100 — {tier}
**Date:** {date.today().strftime("%B %d, %Y")}
**Location:** {city}, {state}

---

## Executive Summary

{name} is a {state}-based HVAC services company with a conviction score of {conviction}/100. {"With strong conviction signals, this company represents a compelling acquisition target." if conviction >= 65 else "This company warrants further monitoring as conviction signals develop."}

**Recommended Action:** {action}

---

## Market Overview

{city}, {state} represents {"a premium Sun Belt HVAC market with strong seasonal demand" if state in ["AZ","TX","FL","TN","NC","GA","SC","NV","CO","VA"] else "a regional HVAC market with stable residential and commercial demand"}. HVAC services remain a highly fragmented industry with significant roll-up opportunity for platform operators.

---

## Company Signals

**Reputation:** {rating}★ with {reviews} Google reviews
**Online Presence:** {website}
**Contact:** {phone}
**Estimated Tenure:** {int(domain_age)}+ years in market

**Positive Indicators:**
{thesis_lines}

---

## Financial Estimate

*Proxy estimate based on review count and industry benchmarks. Verify with seller financials.*

| Metric | Estimate |
|--------|----------|
| Est. Annual Jobs | {reviews * 8:,} |
| Avg Ticket Size | $385 |
| **Est. Revenue** | **${reviews * 8 * 385:,.0f}** |
| EBITDA Margin | 20% |
| **Est. EBITDA** | **${reviews * 8 * 385 * 0.20:,.0f}** |

---

## Valuation Range

| Scenario | Valuation |
|----------|-----------|
| Conservative (3.5× EBITDA) | ${low:,.0f} |
| Base Case (4.5× EBITDA) | ${mid:,.0f} |
| Optimistic (5.5× EBITDA) | ${high:,.0f} |

*Multiple range: 3.5×–5.5× EBITDA, consistent with PE platform acquisitions (source: internal comp database)*

---

## Investment Thesis

{thesis_lines}

---

## Risk Factors

{risk_lines}

---

## Next Steps

1. Initiate owner outreach via {phone}
2. Request trailing 3-year P&L and customer list
3. Commission independent market sizing for {city} metro
4. Engage M&A counsel for LOI preparation if diligence confirms financials

---

*Generated by HVAC Intelligence Platform · {date.today().strftime("%Y")}*
"""

    async def generate(self, company: dict) -> str:
        if not self.api_key:
            return self.generate_template(company)
        if settings.use_mock_data or not self.client:
            await asyncio.sleep(0.05)
            return _mock_dossier(company)
        return await self._claude_generate(company)

    async def _claude_generate(self, company: dict) -> str:
        signals = company.get("signals") or []
        signal_text = "\n".join(
            f"  [{s['severity'].upper()}] {s['label']}: {s['description']}"
            for s in signals
        ) or "  None detected"

        score = company.get("score", 0)
        breakdown = company.get("score_breakdown") or {}

        prompt = f"""You are a senior M&A analyst specializing in HVAC contractor acquisitions for private equity firms, search funds, and strategic roll-up platforms.

Generate a concise, investor-grade acquisition intelligence dossier for the company below. Write in professional markdown. Be specific, candid, and actionable — this is for sophisticated acquirers who evaluate 50+ deals per year. Do NOT use generic AI-sounding filler.

COMPANY DATA:
- Name: {company.get("name")}
- Location: {company.get("city")}, {company.get("state")}
- Phone: {company.get("phone", "N/A")}
- Website: {company.get("website", "N/A")}
- Google Rating: {company.get("google_rating", "N/A")} ({company.get("google_review_count", 0)} reviews)
- Domain Age: {company.get("domain_age_years", "Unknown")} years
- SSL Valid: {company.get("ssl_valid", "Unknown")}
- Tech Stack: {", ".join(company.get("tech_stack") or ["Unknown"])}
- Website Active: {company.get("website_active", "Unknown")}
- Social: Facebook={company.get("has_facebook", False)}, Instagram={company.get("has_instagram", False)}

TRANSITION PROBABILITY SCORE: {score}/100
Breakdown — Operating Age: {breakdown.get("operating_age", 0)}/25 | Digital Health: {breakdown.get("digital_health", 0)}/30 | Review Signals: {breakdown.get("review_signals", 0)}/25 | Lifecycle: {breakdown.get("lifecycle_signals", 0)}/20

DETECTED SIGNALS:
{signal_text}

Write a dossier using these exact ## headings:
## Company Overview
## Size & Operations Estimate
## Transition Signals Detected
## Why This Company May Consider Selling
## Acquisition Thesis
## Recommended Next Steps

Target 450–600 words total. Be direct. Include a realistic EBITDA multiple range. Make it something a deal sourcer would want to send to their LP."""

        try:
            await asyncio.sleep(settings.claude_api_delay_ms / 1000)
            response = await self.client.messages.create(
                model="claude-sonnet-4-6",
                max_tokens=1200,
                messages=[{"role": "user", "content": prompt}],
            )
            return response.content[0].text
        except Exception as e:
            logger.error(f"Claude dossier failed for {company.get('name')}: {e}")
            return _mock_dossier(company)

    async def generate_batch(
        self, companies: list[dict], progress_callback=None
    ) -> list[tuple[str, str]]:
        results = []
        total = len(companies)
        for i, company in enumerate(companies):
            if progress_callback:
                await progress_callback(
                    f"Writing dossier: {company.get('name', 'Unknown')}", i / max(total, 1)
                )
            content = await self.generate(company)
            results.append((company["id"], content))
        return results
