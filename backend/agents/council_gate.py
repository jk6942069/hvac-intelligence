"""
Council Qualification Gate.

Hard guardrail that prevents the LLM Council from running on companies
with thin data briefs — which would cause hallucination and waste API credits.

ALL criteria must pass for a company to qualify.
"""
from config import settings

CONTENT_SIGNAL_KEYS = [
    "is_family_owned_likely",
    "offers_24_7",
    "service_count_estimated",
    "years_in_business_claimed",
    "is_recruiting",
    "technician_count_estimated",
    "serves_commercial",
]


def count_populated_signals(company: dict) -> int:
    """Count content signal fields that are not None (False and 0 count as populated).

    Semantic distinction:
    - None: field was never enriched (we don't know the answer)
    - False/0: enrichment ran and found the answer is "no" or "zero" (valid information)
    """
    return sum(
        1 for key in CONTENT_SIGNAL_KEYS
        if company.get(key) is not None
    )


def qualifies_for_council(
    company: dict,
    min_conviction: int = None,
    min_signals: int = None,
) -> bool:
    """
    Return True only if ALL qualification criteria are met.

    Args:
        company: Company dict with all scoring and enrichment fields.
        min_conviction: Override settings.council_min_conviction if provided.
        min_signals: Override settings.council_min_signals if provided.

    Returns:
        True if company should proceed to council analysis.
    """
    threshold = min_conviction if min_conviction is not None else settings.council_min_conviction
    sig_min = min_signals if min_signals is not None else settings.council_min_signals

    # Gate 1: Conviction score threshold
    if (company.get("conviction_score") or 0) < threshold:
        return False

    # Gate 2: Must have an active website (council needs real-world context)
    if not company.get("website_active"):
        return False

    # Gate 3: Content enrichment must have run
    if not company.get("content_enriched"):
        return False

    # Gate 4: Must not have been analyzed already (avoid re-burning API credits)
    if company.get("council_analyzed"):
        return False

    # Gate 5: Minimum populated content signals (prevents thin briefs)
    if count_populated_signals(company) < sig_min:
        return False

    return True
