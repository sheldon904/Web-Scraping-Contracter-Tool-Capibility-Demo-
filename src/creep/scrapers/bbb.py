"""Better Business Bureau (BBB) scraper.

Scrapes business profiles, ratings, complaints, and reviews from https://www.bbb.org
"""

import json
import re
from decimal import Decimal
from urllib.parse import quote_plus

import httpx

from creep.scrapers.base import BaseScraper
from creep.scrapers.schemas import BBBProfileResult


class BBBScraper(BaseScraper[BBBProfileResult]):
    """Scraper for Better Business Bureau business profiles."""

    source_name = "BBB"
    base_url = "https://www.bbb.org"
    rate_limit_delay = 2.0  # Be respectful to BBB servers

    # State name to abbreviation mapping for URL construction
    STATE_ABBREVS = {
        "florida": "fl",
        "california": "ca",
        "texas": "tx",
        "new york": "ny",
        "georgia": "ga",
        "north carolina": "nc",
        "arizona": "az",
        "colorado": "co",
        "illinois": "il",
        "ohio": "oh",
        "pennsylvania": "pa",
        "michigan": "mi",
        "virginia": "va",
        "washington": "wa",
        "massachusetts": "ma",
        "tennessee": "tn",
        "indiana": "in",
        "missouri": "mo",
        "maryland": "md",
        "wisconsin": "wi",
        "minnesota": "mn",
        "south carolina": "sc",
        "alabama": "al",
        "louisiana": "la",
        "kentucky": "ky",
        "oregon": "or",
        "oklahoma": "ok",
        "connecticut": "ct",
        "iowa": "ia",
        "nevada": "nv",
        "utah": "ut",
        "arkansas": "ar",
        "kansas": "ks",
        "mississippi": "ms",
        "new mexico": "nm",
        "nebraska": "ne",
        "idaho": "id",
        "west virginia": "wv",
        "hawaii": "hi",
        "new hampshire": "nh",
        "maine": "me",
        "montana": "mt",
        "rhode island": "ri",
        "delaware": "de",
        "south dakota": "sd",
        "north dakota": "nd",
        "alaska": "ak",
        "vermont": "vt",
        "wyoming": "wy",
    }

    # City coordinates for common Florida cities (for search)
    FLORIDA_CITIES = {
        "miami": {"lat": 25.7617, "lng": -80.1918},
        "orlando": {"lat": 28.5383, "lng": -81.3792},
        "tampa": {"lat": 27.9506, "lng": -82.4572},
        "jacksonville": {"lat": 30.3322, "lng": -81.6557},
        "fort lauderdale": {"lat": 26.1224, "lng": -80.1373},
        "west palm beach": {"lat": 26.7153, "lng": -80.0534},
        "tallahassee": {"lat": 30.4383, "lng": -84.2807},
        "gainesville": {"lat": 29.6516, "lng": -82.3248},
        "naples": {"lat": 26.1420, "lng": -81.7948},
        "sarasota": {"lat": 27.3364, "lng": -82.5307},
    }

    async def search(
        self,
        company_name: str,
        city: str = "miami",
        state: str = "FL",
        **kwargs,
    ) -> list[BBBProfileResult]:
        """Search BBB for business profiles.

        Args:
            company_name: Business name to search for
            city: City to search in (default: miami)
            state: State abbreviation (default: FL)

        Returns:
            List of matching BBB profiles
        """
        await self._rate_limit()

        # Get coordinates for the city
        city_lower = city.lower()
        coords = self.FLORIDA_CITIES.get(city_lower, self.FLORIDA_CITIES["miami"])

        # Build search URL
        search_url = (
            f"{self.base_url}/search?"
            f"find_country=USA"
            f"&find_latlng={coords['lat']}%2C{coords['lng']}"
            f"&find_loc={quote_plus(city)}%2C%20{state}"
            f"&find_text={quote_plus(company_name)}"
            f"&page=1"
            f"&sort=Relevance"
        )

        try:
            async with httpx.AsyncClient(
                headers=self._get_stealth_headers(),
                timeout=30.0,
                follow_redirects=True,
            ) as client:
                response = await client.get(search_url)
                response.raise_for_status()

                # Extract __PRELOADED_STATE__ from HTML
                preloaded_state = self._extract_preloaded_state(response.text)
                if not preloaded_state:
                    return []

                # Parse search results
                return self._parse_search_results(preloaded_state)

        except httpx.HTTPError as e:
            # Log error but don't crash
            return []

    def _extract_preloaded_state(self, html: str) -> dict | None:
        """Extract __PRELOADED_STATE__ JSON from HTML."""
        # Pattern to find the preloaded state script
        pattern = r'window\.__PRELOADED_STATE__\s*=\s*({.*?});?\s*</script>'
        match = re.search(pattern, html, re.DOTALL)

        if not match:
            # Try alternative pattern
            pattern2 = r'__PRELOADED_STATE__\s*=\s*({.*?})\s*;?\s*window\.'
            match = re.search(pattern2, html, re.DOTALL)

        if match:
            try:
                return json.loads(match.group(1))
            except json.JSONDecodeError:
                return None

        return None

    def _parse_search_results(self, state: dict) -> list[BBBProfileResult]:
        """Parse search results from preloaded state."""
        results = []

        # Navigate to search results in the state object
        search_result = state.get("searchResult", {})
        businesses = search_result.get("results", [])

        for biz in businesses:
            try:
                profile = self._parse_business_result(biz)
                if profile:
                    results.append(profile)
            except Exception:
                continue

        return results

    def _parse_business_result(self, biz: dict) -> BBBProfileResult | None:
        """Parse a single business result from search."""
        try:
            business_name = biz.get("businessName", "")
            if not business_name:
                return None

            # Clean HTML tags from business name (search highlighting)
            business_name = re.sub(r"<[^>]+>", "", business_name)

            # Extract phone (comes as a list)
            phones = biz.get("phone", [])
            phone = phones[0] if phones else None

            # Build address
            address_parts = []
            if biz.get("address"):
                address_parts.append(biz["address"])
            city = biz.get("city", "")
            state = biz.get("state", "")
            postal = biz.get("postalcode", "")
            if city or state or postal:
                address_parts.append(f"{city}, {state} {postal}".strip())
            address = ", ".join(address_parts) if address_parts else None

            # Build profile URL
            report_url = biz.get("reportUrl", "")
            profile_url = f"{self.base_url}{report_url}" if report_url else None

            return BBBProfileResult(
                business_name=business_name,
                bbb_rating=biz.get("rating"),
                accredited=biz.get("accreditationStatus") == "ACCREDITED",
                profile_url=profile_url,
                address=address,
                phone=phone,
                raw_data=biz,
            )

        except Exception:
            return None

    async def get_profile_details(
        self, profile_url: str
    ) -> BBBProfileResult | None:
        """Get detailed profile information from a BBB profile page.

        Args:
            profile_url: Full URL to the BBB profile page

        Returns:
            Detailed BBB profile or None if not found
        """
        await self._rate_limit()

        try:
            async with httpx.AsyncClient(
                headers=self._get_stealth_headers(),
                timeout=30.0,
                follow_redirects=True,
            ) as client:
                response = await client.get(profile_url)
                response.raise_for_status()

                # Extract __PRELOADED_STATE__
                preloaded_state = self._extract_preloaded_state(response.text)
                if not preloaded_state:
                    return None

                return self._parse_profile_details(preloaded_state, profile_url)

        except httpx.HTTPError:
            return None

    def _parse_profile_details(
        self, state: dict, profile_url: str
    ) -> BBBProfileResult | None:
        """Parse detailed profile from preloaded state."""
        try:
            # The business profile is nested in the state
            profile = state.get("businessProfile", {})
            if not profile:
                return None

            # Get display section which contains most info
            display = profile.get("display", {})

            # Business name from names.primary
            names = profile.get("names", {})
            business_name = names.get("primary", "")
            if not business_name:
                business_name = profile.get("businessName", "")
            if not business_name:
                return None

            # Clean HTML tags from business name
            business_name = re.sub(r"<[^>]+>", "", business_name)

            # Extract contact info from display section
            contact = display.get("contactInformation", {})
            phone = contact.get("primaryPhone")

            # Extract address from display section
            address_data = contact.get("primaryAddress", {})
            address_parts = []
            if address_data.get("addressLine1"):
                address_parts.append(address_data["addressLine1"])
            city = address_data.get("city", "")
            state_abbr = address_data.get("state", "")
            postal = address_data.get("postalCode", "")
            if city or state_abbr or postal:
                address_parts.append(f"{city}, {state_abbr} {postal}".strip())
            address = ", ".join(address_parts) if address_parts else None

            # Extract rating information - try multiple paths
            rating_data = profile.get("rating", {})
            bbb_rating = rating_data.get("bbbRating")
            if not bbb_rating or bbb_rating == "NR":
                # Try display path as fallback
                display_rating = display.get("ratingIconInformation", {})
                bbb_rating = display_rating.get("rating") or bbb_rating

            # Accreditation status - try multiple paths
            accred_info = profile.get("accreditationInformation", {})
            is_accredited = accred_info.get("isAccredited", False)
            if not is_accredited:
                # Try display path as fallback
                is_accredited = display.get("isAccredited", False)

            # Business age - from display section
            business_started = display.get("businessStartDate")
            years_in_business = None
            if business_started:
                try:
                    from datetime import datetime

                    # businessStarted can be a year or a date string
                    if isinstance(business_started, int):
                        years_in_business = datetime.now().year - business_started
                    elif isinstance(business_started, str):
                        # Try to extract year from string
                        year_match = re.search(r"(\d{4})", business_started)
                        if year_match:
                            years_in_business = datetime.now().year - int(year_match.group(1))
                except (ValueError, TypeError):
                    pass

            # Complaint and review information from reviewsComplaintsSummary
            summary = display.get("reviewsComplaintsSummary", {})
            complaint_count = summary.get("complaintsTotal", 0)
            complaints_3_years = summary.get("totalClosedComplaintsPastThreeYears", 0)
            complaints_12_months = summary.get("complaintsClosedInLast12Months", 0)

            # Review information
            review_count = summary.get("reviewsTotal", 0)
            avg_rating = summary.get("averageOfReviewStarRatings")

            # Convert average rating to Decimal
            avg_rating_decimal = None
            if avg_rating is not None and avg_rating > 0:
                try:
                    avg_rating_decimal = Decimal(str(avg_rating))
                except (ValueError, TypeError):
                    pass

            return BBBProfileResult(
                business_name=business_name,
                bbb_rating=bbb_rating,
                accredited=is_accredited,
                years_in_business=years_in_business,
                business_started=str(business_started) if business_started else None,
                complaint_count=complaint_count,
                complaints_closed_last_3_years=complaints_3_years,
                complaints_closed_last_12_months=complaints_12_months,
                customer_reviews_count=review_count,
                average_customer_rating=avg_rating_decimal,
                profile_url=profile_url,
                address=address,
                phone=phone,
                raw_data={
                    "profile": profile,
                    "display": display,
                    "summary": summary,
                },
            )

        except Exception:
            return None

    async def get_details(self, identifier: str) -> BBBProfileResult | None:
        """Get detailed profile information.

        Args:
            identifier: Profile URL or business ID

        Returns:
            Detailed BBB profile or None if not found
        """
        # If identifier is a full URL, use it directly
        if identifier.startswith("http"):
            return await self.get_profile_details(identifier)
        # Otherwise, construct URL (assuming it's a path)
        return await self.get_profile_details(f"{self.base_url}{identifier}")

    async def search_and_get_details(
        self,
        company_name: str,
        city: str = "miami",
        state: str = "FL",
    ) -> list[BBBProfileResult]:
        """Search for businesses and get detailed profiles for matches.

        This is a convenience method that combines search and detail retrieval.

        Args:
            company_name: Business name to search for
            city: City to search in
            state: State abbreviation

        Returns:
            List of detailed BBB profiles
        """
        # First, search for the business
        search_results = await self.search(company_name, city, state)

        if not search_results:
            return []

        # Get detailed info for each result (limit to top 5)
        detailed_results = []
        for result in search_results[:5]:
            if result.profile_url:
                detailed = await self.get_profile_details(result.profile_url)
                if detailed:
                    detailed_results.append(detailed)
                else:
                    # If detail fetch fails, keep the basic result
                    detailed_results.append(result)
            else:
                detailed_results.append(result)

        return detailed_results

    def _get_stealth_headers(self) -> dict:
        """Get headers that look like a real browser."""
        return {
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9",
            "Accept-Encoding": "gzip, deflate, br",
            "Cache-Control": "no-cache",
            "Pragma": "no-cache",
            "Sec-Ch-Ua": '"Not_A Brand";v="8", "Chromium";v="120", "Google Chrome";v="120"',
            "Sec-Ch-Ua-Mobile": "?0",
            "Sec-Ch-Ua-Platform": '"macOS"',
            "Sec-Fetch-Dest": "document",
            "Sec-Fetch-Mode": "navigate",
            "Sec-Fetch-Site": "none",
            "Sec-Fetch-User": "?1",
            "Upgrade-Insecure-Requests": "1",
        }
