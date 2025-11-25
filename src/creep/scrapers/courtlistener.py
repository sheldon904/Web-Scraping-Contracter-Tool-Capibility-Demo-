"""CourtListener court records scraper.

Scrapes federal court case data from https://www.courtlistener.com
Uses the CourtListener REST API (requires API token).
"""

import re
from datetime import datetime
from urllib.parse import urlencode

import httpx

from creep.config import get_settings
from creep.scrapers.base import BaseScraper
from creep.scrapers.schemas import CourtListenerCase

settings = get_settings()


class CourtListenerScraper(BaseScraper[CourtListenerCase]):
    """Scraper for CourtListener federal court records.

    Requires a CourtListener API token. Get one at:
    https://www.courtlistener.com/sign-in/
    """

    source_name = "CourtListener"
    base_url = "https://www.courtlistener.com"
    api_base = "https://www.courtlistener.com/api/rest/v4"
    rate_limit_delay = 1.0  # CourtListener allows reasonable rate

    def __init__(self, api_token: str | None = None):
        """Initialize with optional API token.

        Args:
            api_token: CourtListener API token. If not provided,
                      will try to get from settings.
        """
        super().__init__()
        self.api_token = api_token or getattr(settings, "courtlistener_api_token", None)

    def _get_auth_headers(self) -> dict:
        """Get headers with authentication."""
        headers = {
            "User-Agent": "CREEP/1.0 (Contractor Risk Scanner)",
            "Accept": "application/json",
        }
        if self.api_token:
            headers["Authorization"] = f"Token {self.api_token}"
        return headers

    async def search(
        self,
        company_name: str,
        **kwargs,
    ) -> list[CourtListenerCase]:
        """Search CourtListener for cases involving a company.

        Args:
            company_name: Company/party name to search for

        Returns:
            List of court cases
        """
        await self._rate_limit()

        # Try multiple search strategies
        results = []

        # Strategy 1: Search dockets with party name
        docket_results = await self._search_dockets(company_name)
        results.extend(docket_results)

        # Strategy 2: Full text search in RECAP archive
        if not results:
            recap_results = await self._search_recap(company_name)
            results.extend(recap_results)

        # Deduplicate by case number
        seen = set()
        unique_results = []
        for case in results:
            key = (case.case_number, case.court)
            if key not in seen:
                seen.add(key)
                unique_results.append(case)

        return unique_results

    async def _search_dockets(self, party_name: str) -> list[CourtListenerCase]:
        """Search dockets by party name."""
        try:
            # Build search URL - use the search API
            params = {
                "q": f'party:"{party_name}"',
                "type": "r",  # RECAP/dockets
                "order_by": "dateFiled desc",
            }

            url = f"{self.api_base}/search/?{urlencode(params)}"

            async with httpx.AsyncClient(
                headers=self._get_auth_headers(),
                timeout=30.0,
                follow_redirects=True,
            ) as client:
                response = await client.get(url)

                # Handle rate limiting
                if response.status_code == 429:
                    return []

                # Handle auth errors gracefully
                if response.status_code in (401, 403):
                    # Try unauthenticated search
                    return await self._search_unauthenticated(party_name)

                if response.status_code != 200:
                    return []

                data = response.json()
                return self._parse_search_results(data)

        except httpx.HTTPError:
            return []

    async def _search_recap(self, query: str) -> list[CourtListenerCase]:
        """Search RECAP archive with full text query."""
        try:
            params = {
                "q": query,
                "type": "r",  # RECAP dockets
                "order_by": "dateFiled desc",
            }

            url = f"{self.api_base}/search/?{urlencode(params)}"

            async with httpx.AsyncClient(
                headers=self._get_auth_headers(),
                timeout=30.0,
                follow_redirects=True,
            ) as client:
                response = await client.get(url)

                if response.status_code != 200:
                    return []

                data = response.json()
                return self._parse_search_results(data)

        except httpx.HTTPError:
            return []

    async def _search_unauthenticated(self, query: str) -> list[CourtListenerCase]:
        """Fallback search without API token using web search."""
        try:
            # Use the web search interface which doesn't require auth
            params = {
                "q": query,
                "type": "r",
            }

            url = f"{self.base_url}/?" + urlencode(params)

            async with httpx.AsyncClient(
                headers={
                    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
                    "Accept": "text/html,application/xhtml+xml",
                },
                timeout=30.0,
                follow_redirects=True,
            ) as client:
                response = await client.get(url)

                if response.status_code != 200:
                    return []

                # Parse HTML response
                return self._parse_html_results(response.text)

        except httpx.HTTPError:
            return []

    def _parse_search_results(self, data: dict) -> list[CourtListenerCase]:
        """Parse API search results."""
        results = []

        # Handle both v3 and v4 API response formats
        items = data.get("results", [])
        if not items:
            items = data.get("objects", [])

        for item in items[:20]:  # Limit to first 20 results
            try:
                case = self._parse_case_item(item)
                if case:
                    results.append(case)
            except Exception:
                continue

        return results

    def _parse_case_item(self, item: dict) -> CourtListenerCase | None:
        """Parse a single case from API response."""
        try:
            # Extract case name
            case_name = item.get("caseName") or item.get("case_name", "")
            if not case_name:
                case_name = item.get("caseNameFull") or item.get("case_name_full", "Unknown")

            # Extract docket number
            docket_number = item.get("docketNumber") or item.get("docket_number", "")

            # Extract court info
            court = item.get("court") or item.get("court_id", "")
            court_name = item.get("court_citation_string") or item.get("courtName", court)

            # Extract dates
            date_filed = None
            date_filed_str = item.get("dateFiled") or item.get("date_filed")
            if date_filed_str:
                try:
                    if isinstance(date_filed_str, str):
                        date_filed = datetime.strptime(date_filed_str[:10], "%Y-%m-%d").date()
                except ValueError:
                    pass

            date_terminated = None
            date_term_str = item.get("dateTerminated") or item.get("date_terminated")
            if date_term_str:
                try:
                    if isinstance(date_term_str, str):
                        date_terminated = datetime.strptime(date_term_str[:10], "%Y-%m-%d").date()
                except ValueError:
                    pass

            # Extract nature of suit
            nature_of_suit = item.get("natureOfSuit") or item.get("nature_of_suit", "")
            cause = item.get("cause", "")

            # Build docket URL
            docket_id = item.get("docket_id") or item.get("id")
            docket_url = None
            if docket_id:
                docket_url = f"{self.base_url}/docket/{docket_id}/"
            elif item.get("absolute_url"):
                docket_url = f"{self.base_url}{item['absolute_url']}"

            # Extract parties if available
            parties = []
            party_data = item.get("parties", [])
            if party_data:
                for party in party_data[:10]:
                    if isinstance(party, dict):
                        party_name = party.get("name", "")
                        party_type = party.get("party_type", "")
                        if party_name:
                            parties.append(f"{party_name} ({party_type})" if party_type else party_name)
                    elif isinstance(party, str):
                        parties.append(party)

            return CourtListenerCase(
                case_name=case_name,
                case_number=docket_number,
                court=court_name,
                court_id=court,
                filing_date=date_filed,
                date_terminated=date_terminated,
                nature_of_suit=nature_of_suit,
                cause=cause,
                docket_url=docket_url,
                parties=parties,
                raw_data=item,
            )

        except Exception:
            return None

    def _parse_html_results(self, html: str) -> list[CourtListenerCase]:
        """Parse search results from HTML (fallback for unauthenticated)."""
        from bs4 import BeautifulSoup

        results = []
        soup = BeautifulSoup(html, "html.parser")

        # Find result items - CourtListener uses article tags for results
        for article in soup.find_all("article", class_="v-card")[:20]:
            try:
                # Extract case name from title link
                title_link = article.find("a", class_="visitable")
                if not title_link:
                    continue

                case_name = title_link.get_text(strip=True)
                docket_url = title_link.get("href", "")
                if docket_url and not docket_url.startswith("http"):
                    docket_url = f"{self.base_url}{docket_url}"

                # Extract docket number
                docket_num = ""
                docket_span = article.find("span", class_="docket-num")
                if docket_span:
                    docket_num = docket_span.get_text(strip=True)

                # Extract court
                court = ""
                court_span = article.find("span", class_="court")
                if court_span:
                    court = court_span.get_text(strip=True)

                # Extract date
                date_filed = None
                date_span = article.find("span", class_="date-filed")
                if date_span:
                    date_text = date_span.get_text(strip=True)
                    # Try to parse various date formats
                    for fmt in ["%b. %d, %Y", "%B %d, %Y", "%Y-%m-%d"]:
                        try:
                            date_filed = datetime.strptime(date_text, fmt).date()
                            break
                        except ValueError:
                            continue

                results.append(
                    CourtListenerCase(
                        case_name=case_name,
                        case_number=docket_num,
                        court=court,
                        filing_date=date_filed,
                        docket_url=docket_url,
                    )
                )

            except Exception:
                continue

        return results

    async def get_details(self, docket_id: str) -> CourtListenerCase | None:
        """Get detailed docket information.

        Args:
            docket_id: The docket ID or URL path

        Returns:
            Detailed case information or None
        """
        await self._rate_limit()

        # Extract numeric ID if URL provided
        if "/" in docket_id:
            match = re.search(r"/docket/(\d+)/", docket_id)
            if match:
                docket_id = match.group(1)

        try:
            url = f"{self.api_base}/dockets/{docket_id}/"

            async with httpx.AsyncClient(
                headers=self._get_auth_headers(),
                timeout=30.0,
                follow_redirects=True,
            ) as client:
                response = await client.get(url)

                if response.status_code != 200:
                    return None

                data = response.json()
                return self._parse_docket_detail(data)

        except httpx.HTTPError:
            return None

    def _parse_docket_detail(self, data: dict) -> CourtListenerCase | None:
        """Parse detailed docket information."""
        try:
            case_name = data.get("case_name", "")
            if not case_name:
                case_name = data.get("case_name_full", "Unknown")

            # Extract dates
            date_filed = None
            if data.get("date_filed"):
                try:
                    date_filed = datetime.strptime(data["date_filed"], "%Y-%m-%d").date()
                except ValueError:
                    pass

            date_terminated = None
            if data.get("date_terminated"):
                try:
                    date_terminated = datetime.strptime(data["date_terminated"], "%Y-%m-%d").date()
                except ValueError:
                    pass

            # Extract parties
            parties = []
            for party in data.get("parties", [])[:20]:
                if isinstance(party, dict):
                    name = party.get("name", "")
                    party_type = party.get("party_type", {})
                    if isinstance(party_type, dict):
                        party_type = party_type.get("name", "")
                    if name:
                        parties.append(f"{name} ({party_type})" if party_type else name)

            # Build URL
            docket_url = f"{self.base_url}/docket/{data.get('id')}/"

            return CourtListenerCase(
                case_name=case_name,
                case_number=data.get("docket_number", ""),
                court=data.get("court", {}).get("full_name", "") if isinstance(data.get("court"), dict) else str(data.get("court", "")),
                court_id=data.get("court", {}).get("id", "") if isinstance(data.get("court"), dict) else "",
                filing_date=date_filed,
                date_terminated=date_terminated,
                nature_of_suit=data.get("nature_of_suit", ""),
                cause=data.get("cause", ""),
                jurisdiction_type=data.get("jurisdiction_type", ""),
                jury_demand=data.get("jury_demand", ""),
                docket_url=docket_url,
                parties=parties,
                raw_data=data,
            )

        except Exception:
            return None

    async def get_docket_entries(self, docket_id: str, limit: int = 50) -> list[dict]:
        """Get docket entries for a case.

        Args:
            docket_id: The docket ID
            limit: Maximum number of entries to return

        Returns:
            List of docket entry dictionaries
        """
        await self._rate_limit()

        try:
            url = f"{self.api_base}/docket-entries/?docket={docket_id}&page_size={limit}"

            async with httpx.AsyncClient(
                headers=self._get_auth_headers(),
                timeout=30.0,
                follow_redirects=True,
            ) as client:
                response = await client.get(url)

                if response.status_code != 200:
                    return []

                data = response.json()
                return data.get("results", [])

        except httpx.HTTPError:
            return []
