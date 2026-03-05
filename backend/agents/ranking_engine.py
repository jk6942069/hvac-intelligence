"""
Agent 5 — Ranking Engine
Sorts companies by score and assigns acquisition-tier classifications.
"""
import logging

logger = logging.getLogger(__name__)

TOP_PERCENTILE = 0.10          # Top 10% → top_candidate
HIGH_SCORE_THRESHOLD = 65      # Score ≥ 65 → top_candidate regardless of rank
WATCH_LIST_THRESHOLD = 45      # Score ≥ 45 → watch_list


class RankingEngine:
    def rank(self, companies: list[dict]) -> list[dict]:
        """Sort by score descending, assign ranks and tiers."""
        sorted_companies = sorted(
            companies, key=lambda c: c.get("score", 0), reverse=True
        )
        top_n = max(1, int(len(sorted_companies) * TOP_PERCENTILE))

        for i, company in enumerate(sorted_companies):
            company["rank"] = i + 1
            score = company.get("score", 0)
            if i < top_n or score >= HIGH_SCORE_THRESHOLD:
                company["status"] = "top_candidate"
            elif score >= WATCH_LIST_THRESHOLD:
                company["status"] = "watch_list"
            else:
                company["status"] = "ranked"

        return sorted_companies

    def get_top_candidates(self, companies: list[dict], n: int = 50) -> list[dict]:
        ranked = self.rank(companies)
        return [c for c in ranked if c.get("status") == "top_candidate"][:n]
