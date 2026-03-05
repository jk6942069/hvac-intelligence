"""
Agent 1 — Company Scout
Discovers HVAC companies via Google Places API or generates realistic mock data.
"""
import asyncio
import logging
import uuid
import random
from typing import Optional
from config import settings

logger = logging.getLogger(__name__)

# Known chains/franchises to exclude
EXCLUDED_CHAINS = [
    "one hour heating", "cool today", "service experts", "lennox", "carrier",
    "trane", "rheem", "york", "american standard", "amana", "goodman",
    "ars rescue rooter", "hiller", "four seasons", "comfort systems usa",
    "abm industries", "emcor", "home depot", "lowes", "sears",
]

MOCK_HVAC_NAMES = [
    "Air Masters HVAC", "Comfort Zone Heating & Cooling", "Pro Air Services",
    "Apex Climate Control", "ThermalTech HVAC", "Blue Ridge Air",
    "Premier Heating Solutions", "Valley HVAC Specialists", "SunState Air",
    "Heritage Cooling & Heating", "Advanced Air Systems", "Reliable HVAC Co",
    "Sun Country Air Conditioning", "Desert Comfort HVAC", "First Choice Cooling",
    "Total Comfort HVAC", "Precision Air Services", "Metro Climate Solutions",
    "All Seasons HVAC", "Eagle HVAC Services", "Summit Air Conditioning",
    "Central Valley Heating", "Hometown HVAC Pros", "Quality Air & Heat",
    "Superior Cooling Systems", "Classic HVAC Service", "Pinnacle Air Solutions",
    "Coastal Climate Control", "Independence Heating & Air", "Continental HVAC",
    "Redline Air Services", "Cardinal Heating & Cooling", "Keystone HVAC",
    "Patriot Air Conditioning", "Liberty Climate Experts", "Frontier HVAC",
    "Benchmark Air Systems", "Tri-State Heating & Cooling", "Capstone HVAC",
    "Evergreen Air Services", "Lakeside Cooling", "Mountainview Heating",
    "Riverside Air Solutions", "Sunset HVAC", "Clearwater Climate Control",
    "Bayview Heating & Air", "Harbor HVAC", "Westside Air Services",
    "Eastside Climate Solutions", "Paramount HVAC", "Crossroads Heating",
    "Golden State HVAC", "Skyline Air Services", "Broadview Heating & Cooling",
    "Apex Comfort Systems", "Ironwood HVAC", "Timberline Air",
    "Cornerstone Heating & Air", "Diamond HVAC Services", "Crown Cooling",
    "Prestige Heating Solutions", "Allied Air & Heat", "National Comfort Corp",
    "General Heating Services", "Standard HVAC Co", "Palmer Air Conditioning",
    "Davis Heating & Cooling", "Morgan Climate Services", "Mitchell HVAC",
    "Anderson Air Systems", "Thompson Heating & Air", "Jackson HVAC",
    "Williams Cooling Solutions", "Brown Heating Service", "Taylor Air",
    "Harris HVAC Experts", "Martin Climate Control", "Garcia Heating & Air",
    "Rodriguez Air Services", "Wilson HVAC", "Moore Heating Solutions",
    "Clark Air Conditioning", "Lewis Cooling Systems", "Lee HVAC",
    "Walker Heating & Cooling", "Hall Air Services", "Allen HVAC Pros",
    "Young Climate Experts", "King Heating & Air", "Wright HVAC",
    "Scott Air Solutions", "Green Heating Services", "Baker HVAC",
    "Adams Air Conditioning", "Nelson Cooling & Heating", "Carter Air",
    "Mitchell Comfort Systems", "Roberts HVAC Service", "Turner Heating",
    "Phillips Climate Control", "Campbell Air Solutions", "Parker HVAC",
    "Evans Heating & Cooling", "Edwards Air Service", "Collins HVAC",
    "Stewart Heating Experts", "Sanchez Air Conditioning", "Morris Cooling",
    "Rogers HVAC Solutions", "Reed Heating & Air", "Cook Climate Service",
    "Morgan Air Systems", "Bell Heating & Cooling", "Murphy HVAC",
]

STREETS = [
    "Main St", "Oak Ave", "Industrial Blvd", "Commerce Dr", "Service Rd",
    "Highway 1", "Business Park Dr", "Elm St", "Maple Ave", "Pine Rd",
    "Cedar Lane", "Central Ave", "Market St", "Church St", "Park Ave",
]

DEFAULT_CITIES = [
    ("Phoenix", "AZ"), ("Tucson", "AZ"), ("Mesa", "AZ"), ("Scottsdale", "AZ"),
    ("Nashville", "TN"), ("Memphis", "TN"), ("Knoxville", "TN"), ("Chattanooga", "TN"),
    ("Charlotte", "NC"), ("Raleigh", "NC"), ("Greensboro", "NC"), ("Durham", "NC"),
    ("Jacksonville", "FL"), ("Tampa", "FL"), ("Orlando", "FL"), ("Fort Lauderdale", "FL"),
    ("Atlanta", "GA"), ("Savannah", "GA"), ("Augusta", "GA"), ("Columbus", "GA"),
    ("Houston", "TX"), ("Dallas", "TX"), ("San Antonio", "TX"), ("Austin", "TX"),
    ("Las Vegas", "NV"), ("Reno", "NV"), ("Henderson", "NV"),
    ("Columbus", "OH"), ("Cincinnati", "OH"), ("Cleveland", "OH"), ("Akron", "OH"),
    ("Indianapolis", "IN"), ("Fort Wayne", "IN"), ("Evansville", "IN"),
    ("Louisville", "KY"), ("Lexington", "KY"),
    ("Birmingham", "AL"), ("Huntsville", "AL"), ("Montgomery", "AL"),
    ("Columbia", "SC"), ("Charleston", "SC"), ("Greenville", "SC"),
    ("Richmond", "VA"), ("Virginia Beach", "VA"), ("Norfolk", "VA"),
    ("Oklahoma City", "OK"), ("Tulsa", "OK"),
    ("Albuquerque", "NM"), ("Santa Fe", "NM"),
    ("Denver", "CO"), ("Colorado Springs", "CO"),
    ("Kansas City", "MO"), ("St. Louis", "MO"),
    ("Little Rock", "AR"), ("Fayetteville", "AR"),
    ("Baton Rouge", "LA"), ("New Orleans", "LA"),
    ("Jackson", "MS"), ("Gulfport", "MS"),
]


def _mock_company(idx: int, city: str, state: str) -> dict:
    name = MOCK_HVAC_NAMES[idx % len(MOCK_HVAC_NAMES)]
    suffix = idx // len(MOCK_HVAC_NAMES)
    if suffix > 0:
        name = f"{name} #{suffix + 1}"

    area = random.randint(200, 999)
    phone = f"({area}) {random.randint(200,999)}-{random.randint(1000,9999)}"
    domain_slug = name.lower().replace(" ", "").replace("&", "and").replace(",", "").replace("'", "")[:18]
    tlds = [".com", ".net", ".biz"]
    website = f"https://www.{domain_slug}{random.choice(tlds)}"
    rating = round(random.uniform(2.5, 5.0), 1)
    review_count = random.randint(2, 340)
    street_num = random.randint(100, 9999)
    address = f"{street_num} {random.choice(STREETS)}, {city}, {state}"

    return {
        "place_id": f"mock_{uuid.uuid4().hex[:14]}",
        "name": name,
        "address": address,
        "city": city,
        "state": state,
        "phone": phone,
        "website": website,
        "google_rating": rating,
        "google_review_count": review_count,
        "category": "HVAC",
        "raw_google_data": {"mock": True},
    }


class ScoutAgent:
    def __init__(self):
        self.gmaps = None
        if settings.google_places_api_key and not settings.use_mock_data:
            try:
                import googlemaps
                self.gmaps = googlemaps.Client(key=settings.google_places_api_key)
                logger.info("Google Maps client initialized.")
            except Exception as e:
                logger.warning(f"Google Maps client init failed: {e}")

    def _is_excluded(self, name: str) -> bool:
        name_lower = name.lower()
        return any(chain in name_lower for chain in EXCLUDED_CHAINS)

    async def search_city(self, city: str, state: str, max_results: int = 40) -> list[dict]:
        if settings.use_mock_data or not self.gmaps:
            return await self._mock_search(city, state, max_results)
        return await self._google_search(city, state, max_results)

    async def _mock_search(self, city: str, state: str, max_results: int) -> list[dict]:
        await asyncio.sleep(0.02)
        # clamp so randint(a,b) always has a <= b
        upper = max(min(max_results, 18), 1)
        lower = min(6, upper)
        count = random.randint(lower, upper)
        seen_names = set()
        results = []
        attempts = 0
        while len(results) < count and attempts < 200:
            attempts += 1
            idx = random.randint(0, len(MOCK_HVAC_NAMES) * 2 - 1)
            c = _mock_company(idx, city, state)
            if c["name"] not in seen_names:
                seen_names.add(c["name"])
                results.append(c)
        return results

    async def _google_search(self, city: str, state: str, max_results: int) -> list[dict]:
        import googlemaps
        results = []
        queries = [
            f"HVAC contractor {city} {state}",
            f"air conditioning repair {city} {state}",
            f"heating cooling service {city} {state}",
        ]
        seen_ids = set()

        for query in queries:
            if len(results) >= max_results:
                break
            try:
                response = self.gmaps.places(query=query)
                for place in response.get("results", []):
                    place_id = place.get("place_id")
                    if not place_id or place_id in seen_ids:
                        continue
                    name = place.get("name", "")
                    if self._is_excluded(name):
                        continue
                    seen_ids.add(place_id)
                    await asyncio.sleep(settings.google_api_delay_ms / 1000)
                    detail = await self._get_place_details(place_id)
                    if detail:
                        results.append(detail)
                    if len(results) >= max_results:
                        break
            except Exception as e:
                logger.error(f"Google Places search error for {city}, {state}: {e}")
        return results

    async def _get_place_details(self, place_id: str) -> Optional[dict]:
        try:
            fields = [
                "name", "formatted_address", "formatted_phone_number",
                "website", "rating", "user_ratings_total",
                "address_components", "business_status",
            ]
            detail = self.gmaps.place(place_id=place_id, fields=fields)
            result = detail.get("result", {})
            if result.get("business_status") != "OPERATIONAL":
                return None

            city, state = "", ""
            for comp in result.get("address_components", []):
                types = comp.get("types", [])
                if "locality" in types:
                    city = comp.get("long_name", "")
                if "administrative_area_level_1" in types:
                    state = comp.get("short_name", "")

            return {
                "place_id": place_id,
                "name": result.get("name", ""),
                "address": result.get("formatted_address", ""),
                "city": city,
                "state": state,
                "phone": result.get("formatted_phone_number", ""),
                "website": result.get("website", ""),
                "google_rating": result.get("rating"),
                "google_review_count": result.get("user_ratings_total", 0),
                "category": "HVAC",
                "raw_google_data": result,
            }
        except Exception as e:
            logger.error(f"Place details error for {place_id}: {e}")
            return None

    async def run_batch(
        self,
        cities: list[tuple[str, str]],
        max_per_city: int = 15,
        progress_callback=None,
    ) -> list[dict]:
        all_companies = []
        seen_names = set()
        total = len(cities)

        for i, (city, state) in enumerate(cities):
            if progress_callback:
                await progress_callback(f"Scouting {city}, {state}", i / total)
            try:
                companies = await self.search_city(city, state, max_per_city)
                for c in companies:
                    key = c["name"].lower().strip()
                    if key not in seen_names:
                        seen_names.add(key)
                        all_companies.append(c)
                logger.info(f"Scouted {city}, {state}: {len(companies)} companies found")
            except Exception as e:
                logger.error(f"Scout failed for {city}, {state}: {e}")

        return all_companies
