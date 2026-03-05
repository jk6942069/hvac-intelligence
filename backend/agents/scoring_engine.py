"""
Agent 4 -- Scoring Engine (v2)
Produces 3 underwriting sub-scores + an explanation object with thesis bullets and key risks.

Sub-scores:
  1. Transition Pressure   (0-40): How likely is the owner to want to exit?
  2. Business Quality      (0-35): Is this a good business to acquire?
  3. Platform Fit          (0-25): How well does it fit a roll-up / PE platform?

Acquisition Conviction Score = sum of all three (0-100)
"""
import logging
from datetime import date
from typing import Optional

logger = logging.getLogger(__name__)

CURRENT_YEAR = date.today().year

# -- Sun Belt / high-growth HVAC markets ----------------------------------------
PREMIUM_MARKETS = {"AZ","TX","FL","TN","NC","GA","SC","NV","CO","VA"}
SECONDARY_MARKETS = {"AL","MS","AR","OK","KY","WV","LA","NM","UT","ID"}


def _transition_pressure(company: dict) -> tuple:
    """Score 0-40. Returns (score, factor_labels)."""
    factors = []
    score = 0

    domain_age = company.get("domain_age_years") or 0
    ssl_valid = company.get("ssl_valid")
    website_active = company.get("website_active")
    has_facebook = company.get("has_facebook", False)
    has_instagram = company.get("has_instagram", False)
    signals = company.get("signals") or []
    signal_types = {s["type"] for s in signals}
    rating = company.get("google_rating") or 0
    review_count = company.get("google_review_count") or 0

    # Domain age -- strongest transition signal
    if domain_age >= 20:
        score += 30
        factors.append(f"{int(domain_age)}-year domain -- owner likely in retirement window")
    elif domain_age >= 15:
        score += 22
        factors.append(f"{int(domain_age)}-year domain -- long-tenured ownership approaching succession")
    elif domain_age >= 10:
        score += 12
        factors.append(f"{int(domain_age)}-year domain -- established business, potential succession horizon")
    elif domain_age >= 7:
        score += 5
        factors.append(f"{int(domain_age)}-year domain -- mid-stage ownership")

    # Website neglect = owner not investing in future
    if website_active is False:
        score += 12
        factors.append("Website offline -- critical digital neglect signal")
    elif ssl_valid is False:
        score += 8
        factors.append("No SSL certificate -- infrastructure not maintained")

    # Social absence
    if not has_facebook and not has_instagram:
        score += 7
        factors.append("No social media presence -- owner not investing in growth")
    elif not has_facebook or not has_instagram:
        score += 3
        factors.append("Limited social presence -- minimal digital investment")

    # Legacy brand composite
    if "OLD_BRAND" in signal_types:
        score += 6
        factors.append("Legacy brand profile -- multiple aging signals converge")

    # Declining engagement
    if 0 < rating < 3.5 and review_count > 10:
        score += 5
        factors.append("Declining rating trend -- possible service fatigue or owner disengagement")

    # Content signal augmentation
    is_family_owned = company.get("is_family_owned_likely")
    years_claimed = company.get("years_in_business_claimed")

    # Family ownership → key-man / succession pressure
    if is_family_owned is True:
        score = min(40, score + 4)
        factors.append("Family-owned -- succession planning is a common exit trigger")

    # Claimed tenure supplements domain age signal
    if years_claimed and years_claimed >= 20:
        bonus = 5 if years_claimed >= 30 else 3
        score = min(40, score + bonus)
        factors.append(
            f"In business {years_claimed}+ years (stated on website) -- founding-generation operator"
        )

    return min(score, 40), factors


def _business_quality(company: dict) -> tuple:
    """Score 0-35. Returns (score, factor_labels)."""
    factors = []
    score = 0

    rating = company.get("google_rating") or 0
    review_count = company.get("google_review_count") or 0
    domain_age = company.get("domain_age_years") or 0
    website_active = company.get("website_active")
    ssl_valid = company.get("ssl_valid")

    # Rating quality -- proxy for service excellence and customer retention
    if rating >= 4.5 and review_count >= 100:
        # +27 (not +30) intentionally — the 3-point gap allows offers_24_7 and
        # service_count bonuses to register for top-tier companies rather than
        # being silently absorbed by the cap.
        score += 27
        factors.append(f"{rating}★ rating with {review_count}+ reviews -- exceptional service track record")
    elif rating >= 4.5 and review_count >= 50:
        score += 26
        factors.append(f"{rating}★ with {review_count} reviews -- strong quality signal, scalable base")
    elif rating >= 4.5 and review_count >= 20:
        score += 20
        factors.append(f"{rating}★ with {review_count} reviews -- high quality, growing customer base")
    elif rating >= 4.0 and review_count >= 100:
        score += 25
        factors.append(f"{rating}★ with {review_count}+ reviews -- solid reputation, large customer base")
    elif rating >= 4.0 and review_count >= 50:
        score += 20
        factors.append(f"{rating}★ with {review_count} reviews -- good reputation, established base")
    elif rating >= 4.0 and review_count >= 20:
        score += 14
        factors.append(f"{rating}★ with {review_count} reviews -- good quality signal")
    elif rating >= 3.5 and review_count >= 50:
        score += 10
        factors.append(f"{rating}★ with {review_count} reviews -- acceptable quality, room for improvement")
    elif rating >= 3.5 and review_count >= 20:
        score += 7
        factors.append(f"{rating}★ with {review_count} reviews -- average quality")
    elif rating >= 3.0 and review_count >= 100:
        score += 8
        factors.append(f"{rating}★ with {review_count}+ reviews -- below average but large installed base")
    elif rating > 0:
        score += 2
        factors.append(f"{rating}★ with {review_count} reviews -- limited data")

    # Established longevity = proven ability to survive
    if domain_age >= 10:
        score += 5
        factors.append(f"{int(domain_age)}-year operating history -- proven business durability")
    elif domain_age >= 5:
        score += 3
        factors.append(f"{int(domain_age)}-year operating history -- established operation")

    # Basic digital infrastructure
    if website_active and ssl_valid:
        score += 2
        factors.append("Active website with SSL -- basic digital infrastructure in place")

    # Content signal augmentation
    offers_24_7 = company.get("offers_24_7")
    service_count = company.get("service_count_estimated") or 0

    if offers_24_7 is True:
        score = min(35, score + 3)
        factors.append("24/7 emergency service -- systemized operations, not a lifestyle business")

    if service_count >= 5:
        score = min(35, score + 3)
        factors.append(f"{service_count} service lines -- diversified revenue, lower single-service churn risk")
    elif service_count >= 3:
        score = min(35, score + 1)
        factors.append(f"{service_count} service lines -- moderate diversification")

    return min(score, 35), factors


def _platform_fit(company: dict) -> tuple:
    """Score 0-25. Returns (score, factor_labels)."""
    factors = []
    score = 0

    review_count = company.get("google_review_count") or 0
    state = (company.get("state") or "").upper()
    domain_age = company.get("domain_age_years") or 0
    website_active = company.get("website_active")
    tech_stack = set(company.get("tech_stack") or [])

    # Customer base size proxy
    if review_count >= 200:
        score += 12
        factors.append(f"{review_count}+ reviews -- large established customer base, significant ACV potential")
    elif review_count >= 100:
        score += 9
        factors.append(f"{review_count}+ reviews -- material customer base for roll-up synergies")
    elif review_count >= 50:
        score += 6
        factors.append(f"{review_count} reviews -- meaningful customer base")
    elif review_count >= 20:
        score += 3
        factors.append(f"{review_count} reviews -- modest customer base")

    # Geography premium
    if state in PREMIUM_MARKETS:
        score += 8
        factors.append(f"{state} -- premium HVAC market (high cooling demand, population growth)")
    elif state in SECONDARY_MARKETS:
        score += 4
        factors.append(f"{state} -- secondary HVAC market with growth potential")
    elif state:
        score += 2
        factors.append(f"{state} -- established HVAC market")

    # Outdated tech = easier to standardize post-acquisition
    OUTDATED = {"Unknown/Custom HTML","Joomla","Drupal"}
    if tech_stack & OUTDATED:
        score += 3
        factors.append("Outdated tech stack -- low integration lift, easy to standardize")
    elif not tech_stack and website_active:
        score += 2
        factors.append("Minimal tech footprint -- clean slate for platform systems")

    # Longevity = predictable recurring revenue
    if domain_age >= 15:
        score += 2
        factors.append("Long tenure suggests recurring customer relationships and word-of-mouth pipeline")

    # Content signal augmentation
    is_recruiting = company.get("is_recruiting")
    serves_commercial = company.get("serves_commercial")
    tech_count = company.get("technician_count_estimated") or 0

    if serves_commercial is True:
        score = min(25, score + 4)
        factors.append("Commercial HVAC services -- higher ACV, stronger PE roll-up fit")

    if is_recruiting is True:
        score = min(25, score + 3)
        factors.append("Actively hiring technicians -- operational capacity for scale")

    if tech_count >= 8:
        score = min(25, score + 3)
        factors.append(f"Team of {tech_count} technicians -- not founder-dependent, transferable")
    elif tech_count >= 4:
        score = min(25, score + 1)
        factors.append(f"{tech_count} technicians -- small but scalable team in place")

    return min(score, 25), factors


def _generate_thesis(
    company: dict,
    trans_factors: list,
    quality_factors: list,
    platform_factors: list,
) -> list:
    """Generate 3-6 bullet thesis points."""
    bullets = []
    name = company.get("name", "This company")

    # Prefer content-derived thesis bullets when available
    if company.get("is_family_owned_likely") and company.get("years_in_business_claimed"):
        years = company["years_in_business_claimed"]
        bullets.append(
            f"Family-owned since {CURRENT_YEAR - years} ({years}yr) -- "
            f"founding-generation operator, succession pressure confirmed on website"
        )

    # Best 2 transition factors
    for f in trans_factors[:2]:
        bullets.append(f)

    # Best quality factor
    for f in quality_factors[:1]:
        bullets.append(f)

    # Best platform factor
    for f in platform_factors[:1]:
        bullets.append(f)

    # Generic HVAC thesis if we have few points
    if len(bullets) < 3:
        rating = company.get("google_rating") or 0
        review_count = company.get("google_review_count") or 0
        city = company.get("city") or ""
        state = company.get("state") or ""
        if rating > 0:
            bullets.append(
                f"{rating}★ average across {review_count} reviews in {city}, {state} -- "
                "transferable service reputation with established local trust"
            )

    return bullets[:6]


def _generate_risks(company: dict, trans_score: int, quality_score: int) -> list:
    """Generate 3-5 key risk bullets."""
    risks = []
    rating = company.get("google_rating") or 0
    review_count = company.get("google_review_count") or 0
    domain_age = company.get("domain_age_years") or 0
    website_active = company.get("website_active")

    if 0 < rating < 3.5:
        risks.append("Sub-3.5★ rating -- service quality issues may require operational remediation")
    if review_count < 15:
        risks.append("Very low review count -- limited data to validate customer base depth")
    if review_count < 50 and review_count > 0:
        risks.append("Small review base -- customer concentration risk, verify recurring revenue")
    if website_active is False:
        risks.append("Website offline -- potential sign of business winding down")
    if domain_age < 5:
        risks.append("Young business -- limited track record, higher operating risk")
    if quality_score < 10:
        risks.append("Low business quality signals -- increased post-acquisition risk")
    if trans_score < 10:
        risks.append("Low transition pressure -- seller motivation may be low")

    # Always include key HVAC-specific risks
    risks.append("Owner-operator dependency -- key man risk to be assessed in diligence")
    risks.append("Seasonal revenue concentration -- validate 12-month cash flow stability")

    return risks[:5]


def _estimate_valuation(company: dict, conviction: int) -> dict:
    """Estimate a valuation band using review-count proxy for business size."""
    review_count = company.get("google_review_count") or 0
    rating = company.get("google_rating") or 0
    state = (company.get("state") or "").upper()

    # Estimate revenue tier based on review count
    if review_count >= 300:
        rev_low, rev_high = 3_000_000, 8_000_000
        sde_margin = 0.22
    elif review_count >= 150:
        rev_low, rev_high = 1_500_000, 4_000_000
        sde_margin = 0.20
    elif review_count >= 75:
        rev_low, rev_high = 800_000, 2_500_000
        sde_margin = 0.18
    elif review_count >= 30:
        rev_low, rev_high = 400_000, 1_200_000
        sde_margin = 0.17
    elif review_count >= 10:
        rev_low, rev_high = 200_000, 600_000
        sde_margin = 0.16
    else:
        rev_low, rev_high = 100_000, 350_000
        sde_margin = 0.15

    # SDE estimate
    sde_low = rev_low * sde_margin
    sde_high = rev_high * sde_margin

    # Multiple range
    multiple_low = 3.0
    multiple_high = 5.5

    # Adjustments
    if rating >= 4.5 and review_count >= 50:
        multiple_high += 1.0  # premium quality
    if rating < 3.5:
        multiple_low -= 0.5  # quality discount
    if state in PREMIUM_MARKETS:
        multiple_high += 0.5  # geo premium

    # Valuation band
    val_low = int(sde_low * multiple_low)
    val_high = int(sde_high * multiple_high)
    val_mid = int((val_low + val_high) / 2)

    return {
        "low": val_low,
        "mid": val_mid,
        "high": val_high,
        "multipleRange": f"{multiple_low:.1f}x – {multiple_high:.1f}x SDE",
        "basis": f"Proxy comps: {review_count} reviews → est. ${rev_low//1000}K–${rev_high//1000}K revenue; {sde_margin*100:.0f}% SDE margin",
        "disclaimer": "Proxy estimate only. Verify with seller financials in diligence.",
    }


def _recommended_action(
    company: dict, trans_score: int, quality_score: int, workflow_status=None
) -> str:
    """Return a recommended next action string."""
    if workflow_status and workflow_status not in ("not_contacted",):
        status_map = {
            "contacted": "Follow up -- check response status",
            "responded": "Schedule intro call -- seller engaged",
            "interested": "Submit LOI -- move to diligence",
            "follow_up": "Re-engage -- send follow-up message",
            "not_interested": "Monitor -- revisit in 6 months",
        }
        return status_map.get(workflow_status, "Update workflow status")

    rating = company.get("google_rating") or 0
    domain_age = company.get("domain_age_years") or 0

    if trans_score >= 25:
        return "Legacy succession outreach -- lead with retirement planning angle"
    elif trans_score >= 15 and quality_score >= 20:
        return "Growth capital outreach -- lead with operational lift and expansion angle"
    elif quality_score >= 25:
        return "Strategic acquisition outreach -- lead with roll-up integration thesis"
    else:
        return "Initial research -- gather more data before outreach"


class ScoringEngine:
    def __init__(self, learned_weights: dict = None):
        self.learned_weights = learned_weights or {}

    @staticmethod
    def _risk_adjustment(company: dict) -> tuple[int, list[str]]:
        """Score 0-20. Starts at 20, deductions for risk signals."""
        score = 20
        factors: list[str] = []

        website = company.get("website")
        website_active = company.get("website_active")
        has_website = bool(website) or (website_active is True)
        if not has_website:
            score -= 8
            factors.append("No website")
        elif not website_active:
            score -= 5
            factors.append("Website offline")

        reviews = company.get("google_review_count") or 0
        if reviews < 10:
            score -= 6
            factors.append("Fewer than 10 reviews")
        elif reviews < 25:
            score -= 3
            factors.append("Limited review count (<25)")

        rating = company.get("google_rating") or 0.0
        if 0 < rating < 3.5:
            score -= 5
            factors.append(f"Below-3.5\u2605 rating ({rating}\u2605)")

        if not company.get("ssl_valid"):
            score -= 3
            factors.append("No SSL certificate")

        if not company.get("has_facebook") and not company.get("has_instagram"):
            score -= 2
            factors.append("No social media presence")

        return max(0, score), factors

    def score(self, company: dict) -> tuple:
        """Return (conviction_score 0-100, breakdown, trans_score, quality_score, platform_score, explanation)."""
        trans_score, trans_factors = _transition_pressure(company)
        quality_score, quality_factors = _business_quality(company)
        platform_score, platform_factors = _platform_fit(company)
        risk_score, risk_factors = self._risk_adjustment(company)

        raw_total = trans_score + quality_score + platform_score + risk_score

        if raw_total > 100:
            # Scale each subscore proportionally so they sum to 100
            scale = 100 / raw_total
            trans_score = round(trans_score * scale)
            quality_score = round(quality_score * scale)
            platform_score = round(platform_score * scale)
            risk_score = round(risk_score * scale)
            # Fix rounding error: adjust the largest subscore to ensure exact sum of 100
            current_sum = trans_score + quality_score + platform_score + risk_score
            if current_sum != 100:
                # Add/subtract the difference from the largest score
                largest_idx = max(
                    range(4),
                    key=lambda i: [trans_score, quality_score, platform_score, risk_score][i]
                )
                adjustments = [trans_score, quality_score, platform_score, risk_score]
                adjustments[largest_idx] += 100 - current_sum
                trans_score, quality_score, platform_score, risk_score = adjustments

        conviction = trans_score + quality_score + platform_score + risk_score
        # conviction now equals exactly 100 if it was capped, or the raw total if under 100
        # No min(100, ...) needed — it's already capped via scaling

        # Recompute the 5D breakdown from the (possibly scaled) 3D scores
        op_score = trans_score // 4                    # operational signals (~25% of transition score)
        longevity_score = trans_score - op_score       # ensures op_score + longevity_score == trans_score
        market_score = platform_score                  # Platform Fit -> Market Strength
        reputation_score = quality_score               # Business Quality -> Customer Reputation

        # Sub-score breakdown for legacy compatibility
        breakdown = {
            "operating_age": min(trans_score, 25),
            "digital_health": min(quality_score, 30),
            "review_signals": min(platform_score, 25),
            "lifecycle_signals": 0,
        }

        thesis = _generate_thesis(company, trans_factors, quality_factors, platform_factors)
        risks = _generate_risks(company, trans_score, quality_score)
        valuation = _estimate_valuation(company, conviction)
        action = _recommended_action(
            company, trans_score, quality_score,
            company.get("workflow_status")
        )

        explanation = {
            "transitionFactors": trans_factors,
            "qualityFactors": quality_factors,
            "platformFactors": platform_factors,
            "thesisBullets": thesis,
            "keyRisks": risks,
            "valuationBand": valuation,
            "recommendedAction": action,
            "riskFactors": risk_factors,
            "subscores": {
                # Legacy keys (kept for backward compat with existing DB records)
                "transition": trans_score,
                "quality": quality_score,
                "platform": platform_score,
                # New 5-dimension keys (used by v2 UI)
                "market": market_score,
                "reputation": reputation_score,
                "longevity": longevity_score,
                "operational": op_score,
                "risk": risk_score,
            },
        }

        return conviction, breakdown, trans_score, quality_score, platform_score, explanation

    def score_batch(self, companies: list) -> list:
        for company in companies:
            conviction, breakdown, ts, qs, ps, explanation = self.score(company)
            company["score"] = conviction          # backward compat
            company["conviction_score"] = conviction
            company["score_breakdown"] = breakdown
            company["transition_score"] = ts
            company["quality_score"] = qs
            company["platform_score"] = ps
            company["score_explanation"] = explanation
        return companies

    def adjust_weights_from_feedback(self, feedback_records: list) -> dict:
        """Learn from outcomes (basic version -- returns weight adjustments)."""
        signal_outcomes: dict = {}
        for record in feedback_records:
            signals = record.get("signals") or []
            outcome = record.get("outcome", "")
            positive = outcome in ("responded", "already_selling", "interested")
            for sig in signals:
                st = sig["type"]
                if st not in signal_outcomes:
                    signal_outcomes[st] = {"pos": 0, "neg": 0}
                if positive:
                    signal_outcomes[st]["pos"] += 1
                else:
                    signal_outcomes[st]["neg"] += 1

        adjustments = {}
        for sig_type, counts in signal_outcomes.items():
            total_fb = counts["pos"] + counts["neg"]
            if total_fb < 3:
                continue
            pos_rate = counts["pos"] / total_fb
            adjustments[sig_type] = round(0.5 + pos_rate, 2)

        return adjustments
