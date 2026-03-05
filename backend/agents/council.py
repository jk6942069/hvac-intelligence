"""
CouncilAgent — LLM Council deliberation for HVAC acquisition analysis.

Replicates the llm-council 3-stage pattern directly using OpenRouter,
without requiring the llm-council service to be running.

Stage 1: 3 models produce independent investment analyses in parallel.
Stage 2: Each model anonymously reviews the other analyses.
Stage 3: Chairman synthesizes the final investment thesis.
"""
import asyncio
import re
import logging
from openai import AsyncOpenAI
from config import settings

logger = logging.getLogger(__name__)

COUNCIL_MODELS = [
    "anthropic/claude-sonnet-4-5",
    "openai/gpt-4o-mini",
    "google/gemini-flash-1.5",
]
CHAIRMAN_MODEL = "anthropic/claude-sonnet-4-5"


def build_company_brief(company: dict) -> str:
    """
    Construct a ~400-word investment brief for council deliberation.
    Structured to maximize signal density while staying under token limits.
    """
    exp = company.get("score_explanation") or {}
    vb = exp.get("valuationBand") or {}
    bullets = exp.get("thesisBullets") or []
    risks = exp.get("keyRisks") or []

    # Format content signals
    signals = []
    if company.get("is_family_owned_likely"):
        signals.append("Family-owned business")
    if company.get("years_in_business_claimed"):
        signals.append(f"In operation {company['years_in_business_claimed']} years (stated on website)")
    if company.get("offers_24_7"):
        signals.append("24/7 emergency service advertised")
    if company.get("is_recruiting"):
        signals.append("Actively recruiting technicians")
    if company.get("serves_commercial"):
        signals.append("Serves commercial clients")
    if company.get("technician_count_estimated"):
        signals.append(f"Team of {company['technician_count_estimated']} technicians")
    if company.get("service_count_estimated"):
        signals.append(f"~{company['service_count_estimated']} distinct services offered")
    if not signals:
        signals.append("Limited website data — scoring based on reviews and domain signals")

    # Format valuation
    if vb.get("mid"):
        mid = vb["mid"]
        val_str = f"${mid/1_000_000:.1f}M" if mid >= 1_000_000 else f"${mid/1_000:.0f}K"
        val_range = f"{vb.get('multipleRange', 'N/A')} SDE — est. midpoint {val_str}"
    else:
        val_range = "Not estimated (insufficient data)"

    return f"""ACQUISITION CANDIDATE BRIEF
============================
Company: {company.get('name', 'Unknown')}
Location: {company.get('city', '')}, {company.get('state', '')}
Google Rating: {company.get('google_rating', 'N/A')} ({company.get('google_review_count', 0)} reviews)
Domain Age: {round(company.get('domain_age_years') or 0)}yr
Conviction Score: {company.get('conviction_score', 0)}/100
  — Transition: {company.get('transition_score', 0)}/40
  — Quality: {company.get('quality_score', 0)}/35
  — Platform: {company.get('platform_score', 0)}/25

WEBSITE INTELLIGENCE
{chr(10).join(f"• {s}" for s in signals)}

PRELIMINARY THESIS SIGNALS
{chr(10).join(f"• {b}" for b in bullets[:4]) or "• No thesis generated yet"}

KEY DILIGENCE RISKS
{chr(10).join(f"• {r}" for r in risks[:3]) or "• Owner-operator dependency (standard for this sector)"}

PROXY VALUATION
{val_range}
Comparable HVAC transactions: 3.0x–7.0x SDE (market range)
Residential-focused operators typically 3.5x–5.5x; commercial mix commands premium.

CONTEXT
Target geography: {company.get('state', '')} — {'premium HVAC market' if company.get('state') in {'AZ','TX','FL','TN','NC','GA','SC','NV'} else 'secondary market'}
Discovery source: {company.get('discovery_source', 'unknown')}
"""


def parse_chairman_output(text: str) -> dict:
    """
    Parse structured sections from chairman synthesis markdown.
    Handles both ## headers and plain text fallback.
    """
    def extract_section(pattern: str) -> str:
        match = re.search(
            rf"##?\s*{pattern}\s*\n+(.*?)(?=##?\s|\Z)",
            text, re.S | re.I
        )
        return match.group(1).strip() if match else ""

    def extract_bullets(section_text: str) -> list[str]:
        lines = [l.strip().lstrip("-•*").strip() for l in section_text.split("\n")]
        return [l for l in lines if len(l) > 10]

    # Investment thesis — first substantial paragraph
    thesis_section = extract_section("investment thesis")
    if not thesis_section:
        # Fallback: first non-header paragraph > 50 chars
        paragraphs = [p.strip() for p in text.split("\n\n") if p.strip() and not p.startswith("#")]
        thesis_section = next((p for p in paragraphs if len(p) > 50), text[:500])

    # Consensus
    consensus_match = re.search(
        r"(?:council consensus|consensus)[:\s]*(strong buy|moderate interest|split|pass)",
        text, re.I
    )
    consensus = consensus_match.group(1).lower() if consensus_match else "moderate interest"

    # Recommended action
    action_section = extract_section("recommended action")
    action = action_section.split("\n")[0].strip() if action_section else "Monitor — gather additional data"

    # Valuation estimate
    val_match = re.search(r"\$[\d,\.]+[MK]?\s*[–—-]\s*\$[\d,\.]+[MK]?", text)
    val_estimate = val_match.group(0) if val_match else "See valuation tab for proxy estimate"

    return {
        "investment_thesis": thesis_section[:1000],
        "key_strengths": extract_bullets(extract_section("key strengths")),
        "key_risks": extract_bullets(extract_section("key risks")),
        "valuation_estimate": val_estimate,
        "recommended_action": action[:200],
        "council_consensus": consensus,
    }


STAGE1_PROMPT = """You are a private equity analyst evaluating an HVAC acquisition target.
Based on the brief below, provide your independent investment analysis.

{brief}

Provide:
1. Your investment recommendation: STRONG BUY / MODERATE INTEREST / PASS
2. Top 3 reasons supporting your recommendation
3. Top 2 risks an acquirer must diligence
4. Your valuation range estimate
Be specific. Cite specific signals from the brief. Max 300 words."""

STAGE2_PROMPT = """You are reviewing investment analyses of the same HVAC acquisition target.
Original brief: {brief}

Three analysts produced these assessments (anonymized):
{responses}

Rank these responses A, B, C by quality of reasoning and specificity.
Format exactly:
FINAL RANKING:
1. Response [X]
2. Response [Y]
3. Response [Z]

Briefly (1-2 sentences) explain your top choice."""

CHAIRMAN_PROMPT = """You are the chairman of an investment committee reviewing an HVAC acquisition opportunity.
Three analysts evaluated this target and peer-reviewed each other's work.

COMPANY BRIEF:
{brief}

ANALYST ASSESSMENTS:
{stage1_responses}

PEER RANKINGS (aggregate — lower rank = stronger analysis):
{rankings}

Synthesize a final investment thesis. Structure your response with these exact headings:
## Investment Thesis
## Key Strengths
## Key Risks
## Valuation Estimate
## Recommended Action
## Council Consensus
(one of: strong buy / moderate interest / split / pass)

Write as if presenting to a PE investment committee. Be specific, cite evidence, acknowledge uncertainty. Max 500 words."""


class CouncilAgent:
    """
    3-stage LLM Council deliberation for HVAC acquisition analysis.
    Uses OpenRouter to query multiple models in parallel.
    """

    def __init__(self, api_key: str):
        self.client = AsyncOpenAI(
            api_key=api_key,
            base_url="https://openrouter.ai/api/v1",
        )
        self.models = settings.council_models or COUNCIL_MODELS
        self.chairman = settings.council_chairman or CHAIRMAN_MODEL

    async def _query_model(self, model: str, prompt: str, max_tokens: int = 500) -> str:
        """Query a single model and return response text."""
        try:
            response = await self.client.chat.completions.create(
                model=model,
                messages=[{"role": "user", "content": prompt}],
                max_tokens=max_tokens,
                temperature=0.7,
            )
            return response.choices[0].message.content or ""
        except Exception as e:
            logger.warning(f"Council model {model} failed: {e}")
            return f"[{model} unavailable]"

    async def _stage1(self, brief: str) -> list[dict]:
        """Stage 1: All models produce independent analyses in parallel."""
        prompt = STAGE1_PROMPT.format(brief=brief)
        responses = await asyncio.gather(
            *[self._query_model(m, prompt, 400) for m in self.models]
        )
        return [
            {"model": model, "response": resp, "label": f"Response {chr(65 + i)}"}
            for i, (model, resp) in enumerate(zip(self.models, responses))
        ]

    async def _stage2(self, brief: str, stage1: list[dict]) -> list[dict]:
        """Stage 2: Each model anonymously reviews the other analyses."""
        anon_responses = "\n\n".join(
            f"--- {r['label']} ---\n{r['response']}" for r in stage1
        )
        prompt = STAGE2_PROMPT.format(brief=brief, responses=anon_responses)
        reviews = await asyncio.gather(
            *[self._query_model(m, prompt, 200) for m in self.models]
        )
        return [
            {"model": model, "review": review}
            for model, review in zip(self.models, reviews)
        ]

    async def _stage3(self, brief: str, stage1: list[dict], stage2: list[dict]) -> str:
        """Stage 3: Chairman synthesizes final thesis from all inputs."""
        formatted_s1 = "\n\n".join(
            f"Analyst {r['label']} ({r['model']}):\n{r['response']}" for r in stage1
        )
        formatted_s2 = "\n\n".join(
            f"Reviewer {r['model']}:\n{r['review']}" for r in stage2
        )
        prompt = CHAIRMAN_PROMPT.format(
            brief=brief,
            stage1_responses=formatted_s1,
            rankings=formatted_s2,
        )
        return await self._query_model(self.chairman, prompt, 700)

    async def analyze(self, company: dict) -> dict:
        """
        Run full 3-stage deliberation for a single company.
        Returns structured investment thesis dict.
        Falls back to a minimal dict on complete failure.
        """
        fallback = {
            "investment_thesis": "Council analysis unavailable — see preliminary scoring for context.",
            "key_strengths": [],
            "key_risks": [],
            "valuation_estimate": "See valuation tab",
            "recommended_action": "Monitor — run council when API keys configured",
            "council_consensus": "pass",
        }

        try:
            brief = build_company_brief(company)
            stage1 = await self._stage1(brief)
            stage2 = await self._stage2(brief, stage1)
            chairman_output = await self._stage3(brief, stage1, stage2)
            return parse_chairman_output(chairman_output)
        except Exception as e:
            logger.error(f"Council analysis failed for {company.get('name')}: {e}")
            return fallback

    async def analyze_batch(
        self,
        companies: list[dict],
        progress_callback=None,
    ) -> list[tuple[str, dict]]:
        """
        Analyze multiple companies concurrently (bounded concurrency to
        respect OpenRouter rate limits). Returns list of (company_id, thesis) tuples.
        """
        semaphore = asyncio.Semaphore(3)  # Max 3 concurrent council runs

        async def analyze_with_sem(company):
            async with semaphore:
                result = await self.analyze(company)
                if progress_callback:
                    await progress_callback(f"Council reviewed: {company.get('name')}", 0)
                return (company["id"], result)

        return await asyncio.gather(*[analyze_with_sem(c) for c in companies])
