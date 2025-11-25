"""Florida DBPR (Department of Business and Professional Regulation) scraper.

Scrapes contractor license information from https://www.myfloridalicense.com
"""

import re
from datetime import datetime

from bs4 import BeautifulSoup
from playwright.async_api import Page, TimeoutError as PlaywrightTimeout

from creep.scrapers.base import BaseScraper
from creep.scrapers.schemas import DBPRDisciplinaryAction, DBPRLicenseDetail, DBPRLicenseResult


class FloridaDBPRScraper(BaseScraper[DBPRLicenseResult]):
    """Scraper for Florida DBPR license verification."""

    source_name = "FL_DBPR"
    base_url = "https://www.myfloridalicense.com"
    rate_limit_delay = 3.0  # Be conservative with government sites

    async def search(
        self,
        company_name: str,
        license_number: str | None = None,
        **kwargs,
    ) -> list[DBPRLicenseResult]:
        """Search DBPR for licenses by company name or license number.

        Args:
            company_name: Business/organization name to search
            license_number: Optional specific license number

        Returns:
            List of license results
        """
        await self._rate_limit()
        page = await self._get_browser_page()

        try:
            if license_number:
                return await self._search_by_license_number(page, license_number)
            else:
                return await self._search_by_name(page, company_name)
        finally:
            await page.close()

    async def _search_by_name(self, page: Page, company_name: str) -> list[DBPRLicenseResult]:
        """Search by organization/business name."""
        # Go directly to the name search page with extended timeout
        try:
            await page.goto(
                f"{self.base_url}/wl11.asp?mode=1&search=Name&SID=&brd=&typ=",
                timeout=60000,
                wait_until="domcontentloaded",
            )
        except PlaywrightTimeout:
            # If page doesn't load, return empty
            return []

        try:
            await page.wait_for_load_state("domcontentloaded", timeout=30000)
        except PlaywrightTimeout:
            pass

        # Wait a moment for JavaScript to initialize
        await page.wait_for_timeout(1000)

        # Fill in the organization name field - try multiple possible selectors
        org_name_filled = False
        for selector in [
            'input[name="OrgName"]',
            '#OrgName',
            'input[id*="org" i]',
            'input[placeholder*="organization" i]',
        ]:
            try:
                await page.fill(selector, company_name, timeout=3000)
                org_name_filled = True
                break
            except Exception:
                continue

        if not org_name_filled:
            # Try to find any text input and fill it
            inputs = await page.query_selector_all('input[type="text"]')
            for inp in inputs:
                try:
                    name_attr = await inp.get_attribute("name")
                    if name_attr and "name" in name_attr.lower():
                        await inp.fill(company_name)
                        org_name_filled = True
                        break
                except Exception:
                    continue

        if not org_name_filled:
            return []

        # Submit the form - try multiple selectors
        submitted = False
        for selector in [
            'input[type="submit"][value="Search"]',
            'input[value="Search"]',
            'button:has-text("Search")',
            'input[type="submit"]',
        ]:
            try:
                await page.click(selector, timeout=3000)
                submitted = True
                break
            except Exception:
                continue

        if not submitted:
            return []

        try:
            await page.wait_for_load_state("networkidle", timeout=20000)
        except PlaywrightTimeout:
            pass

        # Wait for content to render
        await page.wait_for_timeout(2000)

        content = await page.content()

        # Check for "no records found" message
        if "No Records" in content or "no records" in content.lower():
            return []

        return self._parse_search_results(content)

    async def _search_by_license_number(
        self, page: Page, license_number: str
    ) -> list[DBPRLicenseResult]:
        """Search by license number."""
        # Go directly to the license number search page with extended timeout
        try:
            await page.goto(
                f"{self.base_url}/wl11.asp?mode=1&search=LicNbr&SID=&brd=&typ=",
                timeout=60000,
                wait_until="domcontentloaded",
            )
        except PlaywrightTimeout:
            return []

        try:
            await page.wait_for_load_state("domcontentloaded", timeout=30000)
        except PlaywrightTimeout:
            pass

        await page.wait_for_timeout(1000)

        # Fill in the license number field
        filled = False
        for selector in [
            'input[name="LicNbr"]',
            '#LicNbr',
            'input[id*="lic" i]',
        ]:
            try:
                await page.fill(selector, license_number, timeout=3000)
                filled = True
                break
            except Exception:
                continue

        if not filled:
            return []

        # Submit the form
        submitted = False
        for selector in [
            'input[type="submit"][value="Search"]',
            'input[value="Search"]',
            'button:has-text("Search")',
            'input[type="submit"]',
        ]:
            try:
                await page.click(selector, timeout=3000)
                submitted = True
                break
            except Exception:
                continue

        if not submitted:
            return []

        try:
            await page.wait_for_load_state("networkidle", timeout=20000)
        except PlaywrightTimeout:
            pass

        await page.wait_for_timeout(2000)

        content = await page.content()
        if "No Records" in content or "no records" in content.lower():
            return []

        return self._parse_search_results(content)

    def _parse_search_results(self, html: str) -> list[DBPRLicenseResult]:
        """Parse search results page to extract license data.

        The DBPR results table has columns:
        - License Type (e.g., "Certified General Contractor")
        - Name (clickable link to details)
        - Name Type (e.g., "DBA", "Primary")
        - License Number/Rank (e.g., "CGC1506793<br>Cert General")
        - Status/Expires (e.g., "Current, Active<br>08/31/2026")
        """
        soup = BeautifulSoup(html, "html.parser")
        results = []
        seen_licenses = set()

        # License number pattern - matches DBPR format like CGC1506793, CBC123456
        license_pattern = re.compile(r"^([A-Z]{2,4}\d{5,8})$")

        # Find all table rows - look specifically for rows with height="40" (data rows)
        # or rows that contain exactly 5 cells with license data
        for row in soup.find_all("tr", height="40"):
            cells = row.find_all("td")

            # DBPR data rows have exactly 5 columns
            if len(cells) != 5:
                continue

            # Extract text from each cell
            cell_texts = []
            for cell in cells:
                # Get text, preserving <br> as separator
                text = cell.get_text(separator="|", strip=True)
                cell_texts.append(text)

            # Column 3 (index 3) should contain license number
            # Format: "CGC1506793|Cert General"
            license_col = cell_texts[3] if len(cell_texts) > 3 else ""
            license_parts = license_col.split("|")

            license_number = None
            rank = None
            for part in license_parts:
                part = part.strip()
                if license_pattern.match(part):
                    license_number = part
                elif part and not license_number:
                    continue  # Skip until we find license number
                elif part:
                    rank = part

            if not license_number or license_number in seen_licenses:
                continue

            seen_licenses.add(license_number)

            # Column 0: License Type (e.g., "Certified General Contractor")
            license_type = cell_texts[0] if cell_texts[0] else None

            # Column 1: Name (has a link to LicenseDetail.asp)
            licensee_name = None
            if len(cells) > 1:
                name_link = cells[1].find("a", href=lambda h: h and "LicenseDetail" in h)
                if name_link:
                    licensee_name = name_link.get_text(strip=True)

            # Column 4: Status/Expires (e.g., "Current, Active|08/31/2026")
            status = None
            expiration = None
            if len(cell_texts) > 4:
                status_col = cell_texts[4]
                status_parts = status_col.split("|")
                status = status_parts[0].strip() if status_parts else None
                # Look for date
                for part in status_parts:
                    date_match = re.search(r"(\d{1,2}/\d{1,2}/\d{2,4})", part)
                    if date_match:
                        expiration = date_match.group(1)
                        break

            if licensee_name:
                results.append(
                    DBPRLicenseResult(
                        license_number=license_number,
                        licensee_name=licensee_name,
                        license_type=license_type,
                        status=status or "Unknown",
                        rank=rank,
                        expiration_date=expiration,
                    )
                )

        return results

    def _parse_result_row(
        self, cells: list, raw_html: str
    ) -> DBPRLicenseResult | None:
        """Parse a single result row from the search results table."""
        try:
            cell_texts = [cell.get_text(strip=True) for cell in cells]

            # Skip header rows or empty rows
            if not cell_texts or all(not t for t in cell_texts):
                return None

            # Skip if this looks like a header
            header_words = ["name", "license", "status", "number", "type", "county"]
            first_cell_lower = cell_texts[0].lower() if cell_texts else ""
            if any(word == first_cell_lower for word in header_words):
                return None

            # Look for a license number in any cell
            # License number must be EXACTLY the pattern - not containing extra text
            license_pattern = re.compile(r"^([A-Z]{2,4}\d{5,8})$")

            license_number = None
            licensee_name = None
            license_type = None
            status = None
            expiration = None

            for i, text in enumerate(cell_texts):
                text = text.strip()
                if not text:
                    continue

                # Check for exact license number match
                match = license_pattern.match(text)
                if match and not license_number:
                    license_number = match.group(1)
                # Status keywords
                elif text.upper() in [
                    "ACTIVE",
                    "INACTIVE",
                    "REVOKED",
                    "SUSPENDED",
                    "EXPIRED",
                    "CURRENT",
                    "NULL & VOID",
                    "CURRENT,ACTIVE",
                ]:
                    status = text.replace(",", " - ")
                # Date pattern for expiration
                elif re.match(r"^\d{1,2}/\d{1,2}/\d{2,4}$", text):
                    expiration = text
                # If it's longer text and we don't have a name yet, it's probably the name
                elif len(text) > 5 and not licensee_name and not text.startswith("http"):
                    # Exclude navigation-like text
                    if "apply for" not in text.lower() and "verify" not in text.lower():
                        licensee_name = text

            # If we found at least a license number, create a result
            if license_number:
                if not licensee_name:
                    for text in cell_texts:
                        if text != license_number and len(text) > 3:
                            if "apply for" not in text.lower() and "verify" not in text.lower():
                                licensee_name = text
                                break

                return DBPRLicenseResult(
                    license_number=license_number,
                    licensee_name=licensee_name or "Unknown",
                    license_type=license_type,
                    status=status or "Unknown",
                    expiration_date=expiration,
                    raw_html=raw_html,
                )

        except Exception:
            pass

        return None

    def _parse_alternative_format(self, soup: BeautifulSoup) -> list[DBPRLicenseResult]:
        """Parse results in alternative HTML format."""
        results = []

        # Look for license numbers in the page
        # DBPR license numbers typically follow patterns like: CGC123456, CBC123456, etc.
        # Must be followed by word boundary (not more text)
        license_pattern = re.compile(r"\b([A-Z]{2,4}\d{5,8})\b(?![A-Za-z])")

        # Find all links containing license numbers (most reliable)
        links = soup.find_all("a")
        seen = set()

        for link in links:
            link_text = link.get_text(strip=True)
            match = license_pattern.match(link_text)
            if match:
                license_num = match.group(1)
                if license_num in seen:
                    continue
                seen.add(license_num)

                # Get the parent row to extract more info
                parent_row = link.find_parent("tr")
                if parent_row:
                    row_text = parent_row.get_text(separator=" ", strip=True)

                    # Try to find status
                    status = "Unknown"
                    for s in ["Current", "Active", "Inactive", "Revoked", "Suspended", "Expired"]:
                        if s.lower() in row_text.lower():
                            status = s
                            break

                    # Try to find name (usually after license number in the row)
                    name = "Unknown"
                    cells = parent_row.find_all("td")
                    for cell in cells:
                        cell_text = cell.get_text(strip=True)
                        # Skip if it's the license number or status
                        if cell_text == license_num or cell_text.upper() in ["CURRENT", "ACTIVE", "INACTIVE"]:
                            continue
                        # Skip short text
                        if len(cell_text) > 5 and not cell_text.startswith("http"):
                            name = cell_text
                            break

                    results.append(
                        DBPRLicenseResult(
                            license_number=license_num,
                            licensee_name=name[:100] if len(name) > 100 else name,
                            status=status,
                        )
                    )

        # If no links found, try text content as fallback
        if not results:
            text_content = soup.get_text()
            license_matches = license_pattern.findall(text_content)

            for license_num in license_matches[:5]:  # Limit to first 5
                if license_num in seen:
                    continue
                seen.add(license_num)

                results.append(
                    DBPRLicenseResult(
                        license_number=license_num,
                        licensee_name="See DBPR website for details",
                        status="Unknown",
                    )
                )

        return results

    async def get_details(self, license_number: str) -> DBPRLicenseDetail | None:
        """Get detailed license information."""
        await self._rate_limit()
        page = await self._get_browser_page()

        try:
            # Search for the specific license
            await page.goto(f"{self.base_url}/wl11.asp?mode=1&search=LicNbr&SID=&brd=&typ=")

            try:
                await page.wait_for_load_state("domcontentloaded", timeout=30000)
            except PlaywrightTimeout:
                pass

            await page.wait_for_timeout(1000)

            # Fill license number
            filled = False
            for selector in ['input[name="LicNbr"]', '#LicNbr']:
                try:
                    await page.fill(selector, license_number, timeout=3000)
                    filled = True
                    break
                except Exception:
                    continue

            if not filled:
                return None

            # Submit
            try:
                await page.click('input[value="Search"]', timeout=5000)
            except Exception:
                return None

            try:
                await page.wait_for_load_state("networkidle", timeout=20000)
            except PlaywrightTimeout:
                pass

            await page.wait_for_timeout(2000)

            # Try to click on the license number link to get details
            try:
                await page.click(f'a:has-text("{license_number}")', timeout=5000)
                await page.wait_for_load_state("networkidle", timeout=15000)
                await page.wait_for_timeout(1000)
            except Exception:
                pass  # If no clickable link, parse from search results

            content = await page.content()

            # Create a basic result for reference
            basic_result = DBPRLicenseResult(
                license_number=license_number,
                licensee_name="Unknown",
                status="Unknown",
            )

            return self._parse_detail_page(content, basic_result)

        finally:
            await page.close()

    def _parse_detail_page(
        self, html: str, basic_result: DBPRLicenseResult
    ) -> DBPRLicenseDetail:
        """Parse the license detail page."""
        soup = BeautifulSoup(html, "html.parser")
        detail_data = {}
        text_content = soup.get_text()

        # Common labels on DBPR detail pages
        labels = [
            "License Number",
            "Licensee Name",
            "Name",
            "DBA Name",
            "License Type",
            "Rank",
            "Status",
            "Original Date",
            "Issue Date",
            "Expiration Date",
            "Expires",
            "Address",
            "City",
            "State",
            "Zip",
            "County",
            "Primary Status",
            "Secondary Status",
        ]

        for label in labels:
            pattern = rf"{label}[:\s]+([^\n]+)"
            match = re.search(pattern, text_content, re.IGNORECASE)
            if match:
                detail_data[label.lower().replace(" ", "_")] = match.group(1).strip()

        # Parse dates
        issue_date = None
        expiration_date = None

        for key in ["issue_date", "original_date"]:
            if key in detail_data:
                try:
                    issue_date = datetime.strptime(
                        detail_data[key].split()[0], "%m/%d/%Y"
                    ).date()
                except ValueError:
                    pass

        for key in ["expiration_date", "expires"]:
            if key in detail_data:
                try:
                    expiration_date = datetime.strptime(
                        detail_data[key].split()[0], "%m/%d/%Y"
                    ).date()
                except ValueError:
                    pass

        return DBPRLicenseDetail(
            license_number=detail_data.get("license_number", basic_result.license_number),
            licensee_name=detail_data.get("licensee_name") or detail_data.get("name") or basic_result.licensee_name,
            dba_name=detail_data.get("dba_name"),
            license_type=detail_data.get("license_type", basic_result.license_type),
            rank=detail_data.get("rank", basic_result.rank),
            status=detail_data.get("status", basic_result.status),
            issue_date=issue_date,
            expiration_date=expiration_date,
            address=detail_data.get("address"),
            city=detail_data.get("city"),
            state=detail_data.get("state"),
            zip_code=detail_data.get("zip"),
            county=detail_data.get("county", basic_result.county),
            primary_status=detail_data.get("primary_status", basic_result.primary_status),
            secondary_status=detail_data.get("secondary_status", basic_result.secondary_status),
            raw_data=detail_data,
        )

    async def get_disciplinary_actions(
        self, license_number: str
    ) -> list[DBPRDisciplinaryAction]:
        """Get disciplinary actions for a license.

        Note: For now, returns empty list. DBPR disciplinary data
        requires navigating to a separate enforcement search.
        """
        # Disciplinary actions are on a separate system
        # For MVP, we'll return empty and note this limitation
        return []

    def _parse_disciplinary_actions(self, html: str) -> list[DBPRDisciplinaryAction]:
        """Parse disciplinary actions from the page."""
        soup = BeautifulSoup(html, "html.parser")
        actions = []

        text_content = soup.get_text().lower()

        # Check if there are no actions
        no_action_phrases = [
            "no disciplinary",
            "no complaints",
            "no violations",
            "clean record",
            "no actions",
        ]
        if any(phrase in text_content for phrase in no_action_phrases):
            return []

        tables = soup.find_all("table")
        for table in tables:
            rows = table.find_all("tr")
            for row in rows:
                cells = row.find_all("td")
                if len(cells) >= 2:
                    action = self._parse_disciplinary_row(cells)
                    if action:
                        actions.append(action)

        return actions

    def _parse_disciplinary_row(
        self, cells: list
    ) -> DBPRDisciplinaryAction | None:
        """Parse a single disciplinary action row."""
        try:
            cell_texts = [cell.get_text(strip=True) for cell in cells]

            if not cell_texts or not any(cell_texts):
                return None

            case_number = None
            action_type = None
            action_date = None
            description = None

            for text in cell_texts:
                if re.match(r"^[A-Z0-9\-]+$", text) and len(text) > 5:
                    case_number = text
                elif re.match(r"\d{1,2}/\d{1,2}/\d{2,4}", text):
                    try:
                        action_date = datetime.strptime(text, "%m/%d/%Y").date()
                    except ValueError:
                        pass
                elif any(
                    word in text.lower()
                    for word in ["fine", "revoke", "suspend", "warn", "probation", "reprimand"]
                ):
                    action_type = text
                elif len(text) > 20:
                    description = text

            if case_number or action_type or description:
                return DBPRDisciplinaryAction(
                    case_number=case_number,
                    action_type=action_type,
                    action_date=action_date,
                    description=description,
                )

        except Exception:
            pass

        return None
