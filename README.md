# CREEP

**Contractor Risk Evaluation and Exploration Platform**

A tool for scanning and assessing risk for Florida contractors by aggregating data from multiple public sources.

## Features

- **License Verification** - Florida DBPR license status, disciplinary actions
- **Reputation Analysis** - BBB ratings, complaints, accreditation
- **Court Records** - Federal court cases via CourtListener
- **Financial Liens** - Florida UCC filings and secured transactions
- **Risk Scoring** - Weighted risk score with breakdown
- **Report Generation** - PDF/HTML reports with citations (in progress)

## Quick Start

```bash
# Install dependencies
uv sync

# Install Playwright browsers
uv run playwright install chromium

# Initialize database
uv run creep init

# Scan a contractor
uv run creep scan-license "ABC Construction"
uv run creep scan-reviews "ABC Construction" --city miami
uv run creep scan-courts "ABC Construction"
uv run creep scan-liens "ABC Construction"

# Calculate risk score
uv run creep calculate-risk "ABC Construction"
```

## Documentation

See [PLAN.md](PLAN.md) for detailed architecture, implementation status, and development roadmap.

## Status

| Phase | Component | Status |
|-------|-----------|--------|
| 1 | Foundation (DB, Config, Base Scraper) | Complete |
| 2 | Florida DBPR License Scraper | Complete |
| 3 | BBB Reviews Scraper | Complete |
| 4 | CourtListener Court Records | Complete |
| 5 | Florida UCC Liens | Complete |
| 6 | Risk Scoring Engine | Complete |
| 7 | Report Generation | Not Started |
| 8 | Full Pipeline & ML | Not Started |

## License

MIT
