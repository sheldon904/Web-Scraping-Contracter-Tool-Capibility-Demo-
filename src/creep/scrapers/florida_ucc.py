"""Florida UCC (Uniform Commercial Code) filing scraper.

Scrapes UCC lien filings from the Florida Secured Transaction Registry.
https://floridaucc.com
"""

import re
from datetime import datetime

from bs4 import BeautifulSoup
from playwright.async_api import Page, TimeoutError as PlaywrightTimeout

from creep.scrapers.base import BaseScraper
from creep.scrapers.schemas import UCCFilingResult


class FloridaUCCScraper(BaseScraper[UCCFilingResult]):
    """Scraper for Florida UCC filings (liens and secured transactions).

    Uses Playwright to interact with the JavaScript-based FSTR website.
    """

    source_name = "FL_UCC"
    base_url = "https://floridaucc.com"
    rate_limit_delay = 3.0  # Be conservative with government sites

    async def search(
        self,
        company_name: str,
        **kwargs,
    ) -> list[UCCFilingResult]:
        """Search Florida UCC filings by debtor name.

        Args:
            company_name: Debtor/company name to search for

        Returns:
            List of UCC filing results
        """
        await self._rate_limit()
        page = await self._get_browser_page()

        try:
            return await self._search_by_debtor_name(page, company_name)
        finally:
            await page.close()

    async def _search_by_debtor_name(
        self, page: Page, debtor_name: str
    ) -> list[UCCFilingResult]:
        """Search UCC filings by debtor organization name."""
        import os

        try:
            # Navigate to the search page
            await page.goto(
                f"{self.base_url}/search",
                timeout=60000,
                wait_until="domcontentloaded",
            )
        except PlaywrightTimeout:
            # Try alternative URL
            try:
                await page.goto(
                    f"{self.base_url}/uccweb/search.aspx",
                    timeout=60000,
                    wait_until="domcontentloaded",
                )
            except PlaywrightTimeout:
                return []

        # Wait for the page to load and JavaScript to execute
        await page.wait_for_timeout(5000)

        # Handle terms acceptance dialog if present (MUI-based)
        # Try multiple times in case the page is still loading
        for attempt in range(3):
            try:
                # Look for terms/agreement text to confirm we're on the dialog
                # The actual text is "I accept the terms in the agreement"
                terms_text = await page.query_selector('text="I accept the terms in the agreement"')
                if not terms_text:
                    terms_text = await page.query_selector('text="Terms of Use"')

                if terms_text:
                    # MUI checkbox - need special handling
                    checkbox_clicked = False

                    # First scroll the dialog into view
                    await page.evaluate('window.scrollTo(0, 0)')
                    await page.wait_for_timeout(500)

                    # Try using force click on checkbox - this bypasses visibility checks
                    checkbox_selectors = [
                        '.MuiCheckbox-root',
                        'span[class*="MuiCheckbox-root"]',
                        '[class*="MuiCheckbox-root"]',
                        'input[type="checkbox"]',
                    ]
                    for selector in checkbox_selectors:
                        try:
                            # Use force=True to click even if element is covered
                            await page.click(selector, force=True, timeout=2000)
                            checkbox_clicked = True
                            await page.wait_for_timeout(1000)
                            break
                        except Exception:
                            continue

                    # If direct click didn't work, try JavaScript dispatch event
                    if not checkbox_clicked:
                        try:
                            result = await page.evaluate('''() => {
                                const checkbox = document.querySelector('input[type="checkbox"]');
                                if (checkbox) {
                                    // Dispatch click event
                                    const event = new MouseEvent('click', {
                                        bubbles: true,
                                        cancelable: true,
                                        view: window
                                    });
                                    checkbox.dispatchEvent(event);
                                    // Also try setting checked directly
                                    checkbox.checked = true;
                                    // Dispatch change event
                                    checkbox.dispatchEvent(new Event('change', { bubbles: true }));
                                    return true;
                                }
                                return false;
                            }''')
                            if result:
                                checkbox_clicked = True
                                await page.wait_for_timeout(1000)
                        except Exception:
                            pass

                    # Now click the Next button - wait for it to become enabled
                    await page.wait_for_timeout(1000)

                    # Check if button is now enabled and click it
                    for _ in range(3):  # Try a few times
                        try:
                            # Use JavaScript to find and click enabled Next button
                            clicked = await page.evaluate('''() => {
                                const buttons = document.querySelectorAll('button');
                                for (const btn of buttons) {
                                    if (btn.textContent.includes('Next') && !btn.disabled) {
                                        btn.click();
                                        return true;
                                    }
                                }
                                return false;
                            }''')
                            if clicked:
                                await page.wait_for_timeout(3000)
                                break
                        except Exception:
                            pass
                        await page.wait_for_timeout(500)

                    break  # Exit retry loop if we found terms dialog
                else:
                    # No terms dialog found, might already be past it
                    break
            except Exception:
                await page.wait_for_timeout(2000)
                continue

        # Navigate to UCC Search if we're on a landing page
        try:
            for selector in [
                'text="UCC Search"',
                'a:has-text("UCC Search")',
                'button:has-text("UCC Search")',
                '[href*="search"]',
            ]:
                try:
                    await page.click(selector, timeout=3000)
                    await page.wait_for_timeout(3000)
                    break
                except Exception:
                    continue
        except Exception:
            pass

        # Wait for search page to fully load
        await page.wait_for_timeout(2000)

        # Try to find and fill the organization/debtor name search field
        # The FSTR site typically has tabs for different search types
        filled = False

        # Try to click on "Organization Name" or "Debtor" tab/option first
        for selector in [
            'text="Organization Name"',
            'text="Debtor Name"',
            'text="Organization"',
            'text="Debtor"',
            '[data-testid="org-name-tab"]',
            'button:has-text("Organization")',
            'a:has-text("Organization")',
            'label:has-text("Organization")',
        ]:
            try:
                await page.click(selector, timeout=3000)
                await page.wait_for_timeout(1000)
                break
            except Exception:
                continue

        # Save page state after navigation for debugging
        debug_content = await page.content()
        with open(os.path.expanduser("~/ucc_after_nav.html"), "w") as f:
            f.write(debug_content)

        # Find and fill the search input field
        for selector in [
            'input[name*="orgName" i]',
            'input[name*="organization" i]',
            'input[name*="debtor" i]',
            'input[placeholder*="organization" i]',
            'input[placeholder*="debtor" i]',
            'input[placeholder*="name" i]',
            'input[placeholder*="search" i]',
            '#organizationName',
            '#debtorName',
            '#orgName',
            '[class*="MuiInputBase-input"]',
            '[class*="MuiOutlinedInput-input"]',
            'input[type="text"]',
        ]:
            try:
                element = await page.query_selector(selector)
                if element:
                    await element.fill(debtor_name, timeout=3000)
                    filled = True
                    break
            except Exception:
                continue

        if not filled:
            # Try to find any visible text input (React/MUI often uses different patterns)
            inputs = await page.query_selector_all('input')
            for inp in inputs:
                try:
                    input_type = await inp.get_attribute("type") or "text"
                    if input_type in ["text", "search", ""]:
                        # Check if it's visible and not a checkbox
                        is_visible = await inp.is_visible()
                        if is_visible:
                            await inp.fill(debtor_name)
                            filled = True
                            break
                except Exception:
                    continue

        if not filled:
            return []

        # Submit the search - FSTR uses an icon button with aria-label
        submitted = False
        for selector in [
            'button[aria-label="search"]',  # MUI IconButton with search icon
            '.MuiIconButton-root[aria-label="search"]',
            'button[type="submit"]',
            'button:has-text("Search")',
            'input[type="submit"]',
            'button:has-text("Find")',
            '[data-testid="search-button"]',
        ]:
            try:
                await page.click(selector, timeout=3000)
                submitted = True
                break
            except Exception:
                continue

        if not submitted:
            # Try pressing Enter
            try:
                await page.keyboard.press("Enter")
                submitted = True
            except Exception:
                return []

        # Wait for results to load
        try:
            await page.wait_for_load_state("networkidle", timeout=30000)
        except PlaywrightTimeout:
            pass

        await page.wait_for_timeout(3000)

        # Get the page content and parse results
        content = await page.content()

        # Debug: save HTML to file
        import os
        debug_path = os.path.expanduser("~/ucc_debug.html")
        with open(debug_path, "w") as f:
            f.write(content)

        # Check for no results message
        no_results_patterns = [
            "no results",
            "no records",
            "no filings",
            "0 results",
            "nothing found",
        ]
        content_lower = content.lower()
        if any(pattern in content_lower for pattern in no_results_patterns):
            return []

        return self._parse_search_results(content)

    def _parse_search_results(self, html: str) -> list[UCCFilingResult]:
        """Parse UCC search results from HTML."""
        soup = BeautifulSoup(html, "html.parser")
        results = []
        seen_filings = set()

        # UCC filing numbers typically follow patterns like:
        # 202400123456, 2024-001234567, etc.
        filing_pattern = re.compile(r"\b(\d{4}[-]?\d{6,12})\b")

        # Try to find results in table format
        tables = soup.find_all("table")
        for table in tables:
            rows = table.find_all("tr")
            for row in rows[1:]:  # Skip header row
                cells = row.find_all(["td", "th"])
                if len(cells) >= 2:
                    result = self._parse_table_row(cells, str(row))
                    if result and result.filing_number not in seen_filings:
                        results.append(result)
                        seen_filings.add(result.filing_number)

        # Try to find results in card/div format (common in modern SPAs)
        if not results:
            results = self._parse_card_results(soup, seen_filings)

        # Fallback: extract any filing numbers from the page
        if not results:
            results = self._parse_fallback(soup, seen_filings)

        return results

    def _parse_table_row(
        self, cells: list, raw_html: str
    ) -> UCCFilingResult | None:
        """Parse a single result row from table format."""
        try:
            cell_texts = [cell.get_text(strip=True) for cell in cells]

            if not cell_texts or all(not t for t in cell_texts):
                return None

            # Skip header rows
            header_words = ["filing", "debtor", "secured", "date", "number", "status"]
            if any(word in cell_texts[0].lower() for word in header_words):
                if len(cell_texts[0]) < 20:  # Likely a header
                    return None

            # Look for filing number
            filing_number = None
            filing_pattern = re.compile(r"(\d{4}[-]?\d{6,12})")

            for text in cell_texts:
                match = filing_pattern.search(text)
                if match:
                    filing_number = match.group(1)
                    break

            if not filing_number:
                return None

            # Extract other fields based on common column orders
            debtor_name = None
            secured_party = None
            filing_date = None
            lapse_date = None
            status = None
            filing_type = None

            for i, text in enumerate(cell_texts):
                text_lower = text.lower()

                # Skip the filing number cell
                if filing_number in text:
                    continue

                # Status detection
                if text_lower in ["active", "lapsed", "terminated", "amended"]:
                    status = text
                # Date detection (MM/DD/YYYY or YYYY-MM-DD)
                elif re.match(r"^\d{1,2}/\d{1,2}/\d{2,4}$", text):
                    if not filing_date:
                        filing_date = self._parse_date(text)
                    else:
                        lapse_date = self._parse_date(text)
                elif re.match(r"^\d{4}-\d{2}-\d{2}$", text):
                    if not filing_date:
                        filing_date = self._parse_date(text)
                    else:
                        lapse_date = self._parse_date(text)
                # Filing type detection
                elif any(ft in text_lower for ft in ["ucc1", "ucc3", "initial", "amendment", "continuation", "termination"]):
                    filing_type = text
                # Name detection (longer text, likely debtor or secured party)
                elif len(text) > 3 and not text.isdigit():
                    if not debtor_name:
                        debtor_name = text
                    elif not secured_party:
                        secured_party = text

            return UCCFilingResult(
                filing_number=filing_number,
                filing_type=filing_type,
                filing_date=filing_date,
                lapse_date=lapse_date,
                status=status or "Active",
                debtor_name=debtor_name,
                secured_party_name=secured_party,
                raw_data={"cells": cell_texts},
            )

        except Exception:
            return None

    def _parse_card_results(
        self, soup: BeautifulSoup, seen_filings: set
    ) -> list[UCCFilingResult]:
        """Parse results from card/div-based layout."""
        results = []

        # Look for common card containers
        for selector in [".result-card", ".filing-card", ".ucc-result",
                        "[class*='result']", "[class*='filing']", "[class*='card']"]:
            cards = soup.select(selector)
            for card in cards:
                result = self._parse_card(card)
                if result and result.filing_number not in seen_filings:
                    results.append(result)
                    seen_filings.add(result.filing_number)

        return results

    def _parse_card(self, card) -> UCCFilingResult | None:
        """Parse a single result card."""
        try:
            text = card.get_text(separator=" ", strip=True)

            # Extract filing number
            filing_pattern = re.compile(r"(\d{4}[-]?\d{6,12})")
            match = filing_pattern.search(text)
            if not match:
                return None

            filing_number = match.group(1)

            # Extract dates
            date_pattern = re.compile(r"(\d{1,2}/\d{1,2}/\d{2,4})")
            dates = date_pattern.findall(text)

            filing_date = self._parse_date(dates[0]) if dates else None
            lapse_date = self._parse_date(dates[1]) if len(dates) > 1 else None

            # Extract status
            status = None
            for s in ["Active", "Lapsed", "Terminated", "Amended"]:
                if s.lower() in text.lower():
                    status = s
                    break

            # Extract names (look for labeled sections)
            debtor_name = None
            secured_party = None

            debtor_match = re.search(r"[Dd]ebtor[:\s]+([A-Z][^,\n]+)", text)
            if debtor_match:
                debtor_name = debtor_match.group(1).strip()

            secured_match = re.search(r"[Ss]ecured [Pp]arty[:\s]+([A-Z][^,\n]+)", text)
            if secured_match:
                secured_party = secured_match.group(1).strip()

            return UCCFilingResult(
                filing_number=filing_number,
                filing_date=filing_date,
                lapse_date=lapse_date,
                status=status or "Active",
                debtor_name=debtor_name,
                secured_party_name=secured_party,
            )

        except Exception:
            return None

    def _parse_fallback(
        self, soup: BeautifulSoup, seen_filings: set
    ) -> list[UCCFilingResult]:
        """Fallback parser - extract filing numbers from page text."""
        results = []
        text = soup.get_text()

        # Find all filing numbers
        filing_pattern = re.compile(r"\b(\d{4}[-]?\d{6,12})\b")
        matches = filing_pattern.findall(text)

        for filing_number in matches[:10]:  # Limit to first 10
            if filing_number in seen_filings:
                continue
            seen_filings.add(filing_number)

            results.append(
                UCCFilingResult(
                    filing_number=filing_number,
                    status="Unknown",
                    debtor_name="See FSTR for details",
                )
            )

        return results

    def _parse_date(self, date_str: str) -> "datetime.date | None":
        """Parse date string to date object."""
        if not date_str:
            return None

        for fmt in ["%m/%d/%Y", "%m/%d/%y", "%Y-%m-%d", "%d-%m-%Y"]:
            try:
                return datetime.strptime(date_str.strip(), fmt).date()
            except ValueError:
                continue

        return None

    async def get_details(self, filing_number: str) -> UCCFilingResult | None:
        """Get detailed information for a specific UCC filing.

        Args:
            filing_number: The UCC filing number

        Returns:
            Detailed filing information or None
        """
        await self._rate_limit()
        page = await self._get_browser_page()

        try:
            # Navigate to search page
            await page.goto(
                f"{self.base_url}/search",
                timeout=60000,
                wait_until="networkidle",
            )

            await page.wait_for_timeout(2000)

            # Try to find filing number search option
            for selector in [
                'text="Filing Number"',
                'text="Document Number"',
                '[data-testid="filing-number-tab"]',
                'button:has-text("Filing")',
            ]:
                try:
                    await page.click(selector, timeout=3000)
                    await page.wait_for_timeout(500)
                    break
                except Exception:
                    continue

            # Fill filing number
            filled = False
            for selector in [
                'input[name*="filing" i]',
                'input[name*="document" i]',
                'input[placeholder*="filing" i]',
                '#filingNumber',
                'input[type="text"]',
            ]:
                try:
                    await page.fill(selector, filing_number, timeout=3000)
                    filled = True
                    break
                except Exception:
                    continue

            if not filled:
                return None

            # Submit search
            for selector in [
                'button[type="submit"]',
                'button:has-text("Search")',
                'input[type="submit"]',
            ]:
                try:
                    await page.click(selector, timeout=3000)
                    break
                except Exception:
                    continue

            await page.wait_for_timeout(3000)

            # Try to click on the result to get details
            try:
                await page.click(f'text="{filing_number}"', timeout=5000)
                await page.wait_for_timeout(2000)
            except Exception:
                pass

            content = await page.content()
            return self._parse_detail_page(content, filing_number)

        finally:
            await page.close()

    def _parse_detail_page(
        self, html: str, filing_number: str
    ) -> UCCFilingResult | None:
        """Parse detailed filing information from detail page."""
        soup = BeautifulSoup(html, "html.parser")
        text = soup.get_text()

        # Extract all available information
        filing_date = None
        lapse_date = None
        status = None
        filing_type = None
        debtor_name = None
        debtor_address = None
        secured_party = None
        secured_party_address = None
        collateral = None

        # Common label patterns in detail pages
        labels = {
            "filing date": "filing_date",
            "file date": "filing_date",
            "lapse date": "lapse_date",
            "expiration": "lapse_date",
            "status": "status",
            "filing type": "filing_type",
            "type": "filing_type",
            "debtor": "debtor_name",
            "debtor name": "debtor_name",
            "secured party": "secured_party",
            "collateral": "collateral",
        }

        for label, field in labels.items():
            pattern = rf"{label}[:\s]+([^\n]+)"
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                value = match.group(1).strip()
                if field == "filing_date":
                    filing_date = self._parse_date(value)
                elif field == "lapse_date":
                    lapse_date = self._parse_date(value)
                elif field == "status":
                    status = value
                elif field == "filing_type":
                    filing_type = value
                elif field == "debtor_name":
                    debtor_name = value
                elif field == "secured_party":
                    secured_party = value
                elif field == "collateral":
                    collateral = value[:500]  # Limit collateral description

        # Extract addresses (look for patterns after name fields)
        address_pattern = re.compile(
            r"(\d+[^,\n]+,\s*[A-Z]{2}\s*\d{5}(?:-\d{4})?)",
            re.IGNORECASE
        )
        addresses = address_pattern.findall(text)
        if addresses:
            debtor_address = addresses[0] if len(addresses) > 0 else None
            secured_party_address = addresses[1] if len(addresses) > 1 else None

        return UCCFilingResult(
            filing_number=filing_number,
            filing_type=filing_type,
            filing_date=filing_date,
            lapse_date=lapse_date,
            status=status or "Active",
            debtor_name=debtor_name,
            debtor_address=debtor_address,
            secured_party_name=secured_party,
            secured_party_address=secured_party_address,
            collateral=collateral,
            raw_data={
                "source": "FSTR Detail Page",
                "filing_number": filing_number,
            },
        )
