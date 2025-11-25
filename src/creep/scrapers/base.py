"""Base scraper class with rate limiting, retry logic, and stealth configuration."""

import asyncio
import random
from abc import ABC, abstractmethod
from datetime import datetime
from typing import Generic, TypeVar

import httpx
from playwright.async_api import Page, async_playwright

from creep.config import get_settings

T = TypeVar("T")
settings = get_settings()

# User agents for rotation
USER_AGENTS = [
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Safari/605.1.15",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:121.0) Gecko/20100101 Firefox/121.0",
]


def get_stealth_headers() -> dict[str, str]:
    """Get headers that help avoid bot detection."""
    return {
        "User-Agent": random.choice(USER_AGENTS),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.5",
        "Accept-Encoding": "gzip, deflate, br",
        "DNT": "1",
        "Connection": "keep-alive",
        "Upgrade-Insecure-Requests": "1",
        "Sec-Fetch-Dest": "document",
        "Sec-Fetch-Mode": "navigate",
        "Sec-Fetch-Site": "none",
        "Sec-Fetch-User": "?1",
    }


class BaseScraper(ABC, Generic[T]):
    """Abstract base class for all scrapers."""

    source_name: str = "base"
    base_url: str = ""
    rate_limit_delay: float = settings.scraper_rate_limit
    max_retries: int = settings.scraper_max_retries
    timeout: int = settings.scraper_timeout

    def __init__(self):
        self._last_request_time: datetime | None = None
        self._http_client: httpx.AsyncClient | None = None
        self._playwright = None
        self._browser = None

    async def __aenter__(self):
        """Async context manager entry."""
        await self.setup()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        await self.cleanup()

    async def setup(self) -> None:
        """Initialize resources."""
        self._http_client = httpx.AsyncClient(
            timeout=self.timeout,
            follow_redirects=True,
            headers=get_stealth_headers(),
            http2=True,
        )

    async def cleanup(self) -> None:
        """Release resources."""
        if self._http_client:
            await self._http_client.aclose()
            self._http_client = None
        if self._browser:
            await self._browser.close()
            self._browser = None
        if self._playwright:
            await self._playwright.stop()
            self._playwright = None

    async def _rate_limit(self) -> None:
        """Enforce rate limiting between requests."""
        if self._last_request_time:
            elapsed = (datetime.now() - self._last_request_time).total_seconds()
            # Add jitter (10-30% random variation)
            delay = self.rate_limit_delay * random.uniform(1.1, 1.3)
            if elapsed < delay:
                await asyncio.sleep(delay - elapsed)
        self._last_request_time = datetime.now()

    async def _get_browser_page(self) -> Page:
        """Get or create Playwright browser page with stealth configuration."""
        if not self._playwright:
            self._playwright = await async_playwright().start()
        if not self._browser:
            self._browser = await self._playwright.chromium.launch(
                headless=settings.playwright_headless,
                args=[
                    "--disable-blink-features=AutomationControlled",
                    "--no-sandbox",
                    "--disable-dev-shm-usage",
                ],
            )

        context = await self._browser.new_context(
            viewport={"width": 1920, "height": 1080},
            user_agent=random.choice(USER_AGENTS),
        )

        page = await context.new_page()

        # Add stealth scripts
        await page.add_init_script(
            """
            // Override navigator.webdriver
            Object.defineProperty(navigator, 'webdriver', {
                get: () => undefined
            });

            // Override plugins
            Object.defineProperty(navigator, 'plugins', {
                get: () => [1, 2, 3, 4, 5]
            });

            // Override languages
            Object.defineProperty(navigator, 'languages', {
                get: () => ['en-US', 'en']
            });
            """
        )

        return page

    async def _request_with_retry(
        self,
        method: str,
        url: str,
        **kwargs,
    ) -> httpx.Response:
        """Make HTTP request with retry logic."""
        if not self._http_client:
            raise RuntimeError("Scraper not initialized. Use async with.")

        last_error: Exception | None = None

        for attempt in range(self.max_retries):
            await self._rate_limit()
            try:
                response = await self._http_client.request(method, url, **kwargs)
                response.raise_for_status()
                return response
            except httpx.HTTPStatusError as e:
                last_error = e
                if e.response.status_code == 429:
                    # Rate limited - wait longer
                    wait_time = self.rate_limit_delay * (2**attempt)
                    await asyncio.sleep(wait_time)
                elif e.response.status_code >= 500:
                    # Server error - retry with backoff
                    await asyncio.sleep(self.rate_limit_delay * attempt)
                else:
                    # Client error - don't retry
                    raise
            except (httpx.ConnectError, httpx.TimeoutException) as e:
                last_error = e
                await asyncio.sleep(self.rate_limit_delay * attempt)

        raise last_error or RuntimeError("Request failed after retries")

    async def get(self, url: str, **kwargs) -> httpx.Response:
        """Make GET request with retry."""
        return await self._request_with_retry("GET", url, **kwargs)

    async def post(self, url: str, **kwargs) -> httpx.Response:
        """Make POST request with retry."""
        return await self._request_with_retry("POST", url, **kwargs)

    @abstractmethod
    async def search(self, company_name: str, **kwargs) -> list[T]:
        """Search for company data. Must be implemented by subclasses."""

    @abstractmethod
    async def get_details(self, identifier: str) -> T | None:
        """Get detailed information. Must be implemented by subclasses."""
