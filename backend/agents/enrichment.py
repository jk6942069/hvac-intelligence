"""
Agent 2 — Data Enrichment Analyst
Expands company intelligence: SSL, domain age, tech stack, social presence.
"""
import asyncio
import logging
import random
import ssl
import socket
from datetime import datetime
from typing import Optional
import httpx
from config import settings

logger = logging.getLogger(__name__)


async def check_ssl(domain: str) -> dict:
    """Check SSL certificate validity and expiry."""
    try:
        ctx = ssl.create_default_context()
        loop = asyncio.get_event_loop()

        def _check():
            conn = ctx.wrap_socket(socket.socket(socket.AF_INET), server_hostname=domain)
            conn.settimeout(5.0)
            conn.connect((domain, 443))
            cert = conn.getpeercert()
            conn.close()
            return cert

        cert = await loop.run_in_executor(None, _check)
        expiry_str = cert.get("notAfter", "")
        expiry_dt = None
        if expiry_str:
            try:
                expiry_dt = datetime.strptime(expiry_str, "%b %d %H:%M:%S %Y %Z")
            except Exception:
                pass
        return {
            "ssl_valid": True,
            "ssl_expiry": expiry_dt.isoformat() if expiry_dt else None,
        }
    except Exception:
        return {"ssl_valid": False, "ssl_expiry": None}


async def get_domain_age(domain: str) -> Optional[float]:
    """Get domain age in years via WHOIS."""
    try:
        import whois
        loop = asyncio.get_event_loop()
        w = await loop.run_in_executor(None, lambda: whois.whois(domain))
        creation_date = w.creation_date
        if isinstance(creation_date, list):
            creation_date = creation_date[0]
        if creation_date:
            age = (datetime.utcnow() - creation_date).days / 365.25
            return round(max(0.0, age), 1)
    except Exception:
        pass
    return None


def detect_tech_stack(html: str, headers: dict) -> list[str]:
    tech = []
    hl = html.lower()
    srv = headers.get("server", "").lower()
    px = headers.get("x-powered-by", "").lower()

    if "wp-content" in hl or "wp-includes" in hl:
        tech.append("WordPress")
    if "wix.com" in hl or "wixsite.com" in hl:
        tech.append("Wix")
    if "squarespace" in hl:
        tech.append("Squarespace")
    if "shopify" in hl:
        tech.append("Shopify")
    if "drupal" in hl:
        tech.append("Drupal")
    if "joomla" in hl:
        tech.append("Joomla")
    if "divi" in hl and "WordPress" in tech:
        tech.append("Divi")
    if "__next" in hl or "next.js" in hl:
        tech.append("Next.js")
    elif "react" in hl and "__reactfiber" in hl:
        tech.append("React")
    if "angular" in hl:
        tech.append("Angular")
    if "vue" in hl:
        tech.append("Vue.js")
    if "php" in px:
        tech.append("PHP")
    if "apache" in srv:
        tech.append("Apache")
    elif "nginx" in srv:
        tech.append("Nginx")
    if not tech:
        tech.append("Unknown/Custom HTML")
    return tech


def detect_social_links(html: str) -> dict:
    hl = html.lower()
    return {
        "has_facebook": "facebook.com/" in hl,
        "has_instagram": "instagram.com/" in hl,
    }


def estimate_outdated(html: str, tech_stack: list[str]) -> bool:
    hl = html.lower()
    signals = 0
    current_year = datetime.utcnow().year
    for year in range(2000, current_year - 4):
        if f"copyright {year}" in hl or f"© {year}" in hl or f"&copy; {year}" in hl:
            signals += 2
            break
    if ".swf" in hl or "flashplayer" in hl:
        signals += 3
    if "Unknown/Custom HTML" in tech_stack or "Joomla" in tech_stack or "Drupal" in tech_stack:
        signals += 1
    return signals >= 2


class EnrichmentAgent:
    def __init__(self):
        self.client = httpx.AsyncClient(
            timeout=httpx.Timeout(10.0),
            follow_redirects=True,
            headers={"User-Agent": "Mozilla/5.0 (compatible; HVACIntelBot/1.0)"},
        )

    async def enrich(self, company: dict) -> dict:
        if settings.use_mock_data:
            return await self._mock_enrich(company)
        return await self._real_enrich(company)

    async def _mock_enrich(self, company: dict) -> dict:
        await asyncio.sleep(0.01)
        domain_age = round(random.uniform(1.0, 24.0), 1)
        ssl_valid = random.random() > 0.22
        website_active = random.random() > 0.12

        tech_options = [
            ["WordPress"], ["Wix"], ["Squarespace"], ["Unknown/Custom HTML"],
            ["PHP", "Apache"], ["WordPress", "Divi"], ["Joomla"],
            ["Unknown/Custom HTML", "Apache"],
        ]
        tech = random.choice(tech_options)
        load_time = random.randint(600, 7000)
        has_facebook = random.random() > 0.38
        has_instagram = random.random() > 0.58

        website = company.get("website") or ""
        domain = website.replace("https://", "").replace("http://", "").split("/")[0]

        return {
            **company,
            "domain": domain,
            "domain_age_years": domain_age,
            "ssl_valid": ssl_valid,
            "ssl_expiry": f"202{random.randint(5,7)}-{random.randint(1,12):02d}-15" if ssl_valid else None,
            "tech_stack": tech,
            "website_active": website_active,
            "website_load_time_ms": load_time if website_active else None,
            "website_last_checked": datetime.utcnow().isoformat(),
            "has_facebook": has_facebook,
            "has_instagram": has_instagram,
            "website_outdated": domain_age > 9 and random.random() > 0.45,
        }

    async def _real_enrich(self, company: dict) -> dict:
        enriched = dict(company)
        website = (company.get("website") or "").strip()

        if not website:
            enriched["website_active"] = False
            enriched["website_last_checked"] = datetime.utcnow().isoformat()
            return enriched

        domain = website.replace("https://", "").replace("http://", "").split("/")[0].split("?")[0]
        enriched["domain"] = domain

        try:
            start_t = asyncio.get_event_loop().time()
            resp = await self.client.get(website)
            elapsed = int((asyncio.get_event_loop().time() - start_t) * 1000)
            enriched["website_active"] = resp.status_code < 400
            enriched["website_load_time_ms"] = elapsed

            if enriched["website_active"]:
                html = resp.text
                tech = detect_tech_stack(html, dict(resp.headers))
                social = detect_social_links(html)
                enriched["tech_stack"] = tech
                enriched["website_outdated"] = estimate_outdated(html, tech)
                enriched.update(social)
        except Exception as e:
            enriched["website_active"] = False
            logger.debug(f"Website check failed for {domain}: {e}")

        enriched["website_last_checked"] = datetime.utcnow().isoformat()

        ssl_data = await check_ssl(domain)
        enriched.update(ssl_data)

        await asyncio.sleep(settings.enrichment_delay_ms / 1000)
        domain_age = await get_domain_age(domain)
        enriched["domain_age_years"] = domain_age

        return enriched

    async def enrich_batch(self, companies: list[dict], progress_callback=None) -> list[dict]:
        results = []
        total = len(companies)
        for i, company in enumerate(companies):
            if progress_callback:
                await progress_callback(
                    f"Enriching: {company.get('name', 'Unknown')}", i / max(total, 1)
                )
            enriched = await self.enrich(company)
            results.append(enriched)
        return results

    async def close(self):
        await self.client.aclose()
