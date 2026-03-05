"""
Agent 3 — Signal Analyst
Detects ownership lifecycle and operational transition signals.
"""
import logging
from datetime import datetime

logger = logging.getLogger(__name__)

SIGNAL_DEFINITIONS = {
    "OLD_DOMAIN": {
        "label": "Long-Established Domain (15+ yrs)",
        "severity": "high",
        "description": "Domain registered 15+ years ago — strong indicator of legacy ownership nearing retirement horizon",
        "points": 15,
    },
    "ESTABLISHED_BUSINESS": {
        "label": "Established Business (10–15 yrs)",
        "severity": "medium",
        "description": "Domain registered 10–15 years ago — potential retirement window approaching",
        "points": 10,
    },
    "NO_SSL": {
        "label": "No SSL Certificate",
        "severity": "medium",
        "description": "Website lacks HTTPS — indicates digital neglect or deferred maintenance by owner",
        "points": 8,
    },
    "SSL_EXPIRY_SOON": {
        "label": "SSL Certificate Expiring",
        "severity": "low",
        "description": "SSL certificate expires within 60 days — owner not monitoring infrastructure",
        "points": 3,
    },
    "WEBSITE_DOWN": {
        "label": "Website Inaccessible",
        "severity": "high",
        "description": "Website is offline or unreachable — strong digital neglect signal",
        "points": 12,
    },
    "OUTDATED_TECH": {
        "label": "Outdated Website Technology",
        "severity": "medium",
        "description": "Site uses outdated tech stack (Joomla, Drupal, custom HTML) — not actively maintained",
        "points": 7,
    },
    "SLOW_WEBSITE": {
        "label": "Slow Website (>4s)",
        "severity": "low",
        "description": "Website loads slowly — infrastructure not being optimized or maintained",
        "points": 4,
    },
    "LOW_REVIEW_COUNT": {
        "label": "Low Review Volume (<15)",
        "severity": "medium",
        "description": "Fewer than 15 Google reviews — low digital engagement or declining customer activity",
        "points": 8,
    },
    "DECLINING_RATING": {
        "label": "Below-Average Rating (<3.5★)",
        "severity": "high",
        "description": "Google rating below 3.5 — possible service quality issues or owner disengagement",
        "points": 10,
    },
    "BELOW_AVERAGE_RATING": {
        "label": "Marginally Below-Average (3.5–3.8★)",
        "severity": "medium",
        "description": "Google rating 3.5–3.8 — showing signs of service fatigue",
        "points": 5,
    },
    "NO_SOCIAL_PRESENCE": {
        "label": "No Social Media Presence",
        "severity": "medium",
        "description": "No Facebook or Instagram detected — owner not investing in digital growth",
        "points": 6,
    },
    "OLD_BRAND": {
        "label": "Legacy Brand Profile",
        "severity": "high",
        "description": "Multiple aging signals combined — classic ownership fatigue pattern",
        "points": 15,
    },
}

OUTDATED_TECH_INDICATORS = {"Unknown/Custom HTML", "Joomla", "Drupal"}


class SignalAnalyst:
    def analyze(self, company: dict) -> list[dict]:
        signals = []

        domain_age = company.get("domain_age_years") or 0
        ssl_valid = company.get("ssl_valid")
        ssl_expiry = company.get("ssl_expiry")
        website_active = company.get("website_active")
        tech_stack = set(company.get("tech_stack") or [])
        load_time = company.get("website_load_time_ms") or 0
        review_count = company.get("google_review_count") or 0
        rating = company.get("google_rating") or 0
        has_facebook = company.get("has_facebook", False)
        has_instagram = company.get("has_instagram", False)

        # Domain age
        if domain_age >= 15:
            signals.append(self._sig("OLD_DOMAIN"))
        elif domain_age >= 10:
            signals.append(self._sig("ESTABLISHED_BUSINESS"))

        # SSL
        if ssl_valid is False:
            signals.append(self._sig("NO_SSL"))
        elif ssl_valid and ssl_expiry:
            try:
                expiry = datetime.fromisoformat(ssl_expiry)
                days_left = (expiry - datetime.utcnow()).days
                if 0 < days_left < 60:
                    signals.append(self._sig("SSL_EXPIRY_SOON"))
            except Exception:
                pass

        # Website
        if website_active is False:
            signals.append(self._sig("WEBSITE_DOWN"))
        else:
            if tech_stack & OUTDATED_TECH_INDICATORS:
                signals.append(self._sig("OUTDATED_TECH"))
            if load_time > 4000:
                signals.append(self._sig("SLOW_WEBSITE"))

        # Reviews
        if 0 < review_count < 15:
            signals.append(self._sig("LOW_REVIEW_COUNT"))
        if 0 < rating < 3.5:
            signals.append(self._sig("DECLINING_RATING"))
        elif 3.5 <= rating < 3.8:
            signals.append(self._sig("BELOW_AVERAGE_RATING"))

        # Social
        if not has_facebook and not has_instagram:
            signals.append(self._sig("NO_SOCIAL_PRESENCE"))

        # Composite: OLD_BRAND
        signal_types = {s["type"] for s in signals}
        is_old_brand = (
            domain_age >= 12
            and (
                (ssl_valid is False and review_count < 40)
                or (bool(tech_stack & OUTDATED_TECH_INDICATORS) and domain_age >= 14)
                or ("NO_SOCIAL_PRESENCE" in signal_types and domain_age >= 15)
            )
        )
        if is_old_brand and "OLD_BRAND" not in signal_types:
            signals.append(self._sig("OLD_BRAND"))

        return signals

    def _sig(self, signal_type: str) -> dict:
        d = SIGNAL_DEFINITIONS[signal_type]
        return {
            "type": signal_type,
            "label": d["label"],
            "severity": d["severity"],
            "description": d["description"],
            "points": d["points"],
        }

    def analyze_batch(self, companies: list[dict]) -> list[dict]:
        for company in companies:
            company["signals"] = self.analyze(company)
        return companies
