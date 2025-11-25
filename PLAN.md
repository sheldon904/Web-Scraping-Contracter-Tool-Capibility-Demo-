# CREEP Development Plan

**Contractor Risk Evaluation and Exploration Platform**

Last Updated: 2025-11-25

---

## System Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                     CONTRACTOR RISK SCANNER                      │
├─────────────────────────────────────────────────────────────────┤
│  INPUT: Company Name, State, License # (optional)               │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐          │
│  │   Scraper    │  │   Scraper    │  │   Scraper    │          │
│  │  Licensing   │  │   Courts     │  │   Reviews    │          │
│  └──────┬───────┘  └──────┬───────┘  └──────┬───────┘          │
│         │                 │                 │                   │
│         ▼                 ▼                 ▼                   │
│  ┌─────────────────────────────────────────────────────┐       │
│  │            Data Normalization Layer                  │       │
│  │   (Standardizes dates, names, amounts, categories)   │       │
│  └─────────────────────────┬───────────────────────────┘       │
│                            │                                    │
│                            ▼                                    │
│  ┌─────────────────────────────────────────────────────┐       │
│  │              PostgreSQL Database                     │       │
│  │    (Caches results, enables historical tracking)     │       │
│  └─────────────────────────┬───────────────────────────┘       │
│                            │                                    │
│                            ▼                                    │
│  ┌─────────────────────────────────────────────────────┐       │
│  │           Risk Scoring Engine                        │       │
│  │   - Feature extraction from normalized data          │       │
│  │   - Weighted linear model / logistic regression      │       │
│  │   - Confidence intervals                             │       │
│  └─────────────────────────┬───────────────────────────┘       │
│                            │                                    │
│                            ▼                                    │
│  ┌─────────────────────────────────────────────────────┐       │
│  │              Report Generator                        │       │
│  │   - Risk score (0-100) with breakdown               │       │
│  │   - Citations for each finding                       │       │
│  │   - Confidence level                                 │       │
│  │   - PDF/HTML output                                  │       │
│  └─────────────────────────────────────────────────────┘       │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

---

## Data Sources & Risk Signals

| Source | Data Points | Risk Signals |
|--------|-------------|--------------|
| **FL DBPR (Licensing)** | License status, issue date, expiration, disciplinary actions | Expired/suspended license, violations, short tenure |
| **BBB** | Rating, complaint count, complaint resolution | Poor resolution rate, complaint trends, low rating |
| **CourtListener** | Federal court cases, bankruptcy, civil suits | Litigation patterns, bankruptcy history |
| **Florida UCC** | UCC liens, secured transactions | Unpaid debts, disputes with suppliers |
| **Secretary of State** | Business registration, formation date *(not implemented)* | Recent formation, frequent changes |
| **Google/Yelp Reviews** | Rating, review count, sentiment *(not implemented)* | Low ratings, review authenticity |
| **OSHA** | Workplace violations *(not implemented)* | Safety culture issues |

---

## Implementation Status

### Phase 1: Foundation ✅ COMPLETE

**Files:**
- `src/creep/config.py` - Pydantic settings with environment variables
- `src/creep/db/models.py` - SQLAlchemy ORM models (Company, License, Review, BBBProfile, CourtCase, Lien, RiskScore, ScrapeJob, Report)
- `src/creep/db/engine.py` - Async database engine and session management
- `src/creep/db/repository.py` - Repository pattern for database operations
- `src/creep/scrapers/base.py` - Base scraper class with rate limiting, retries, browser automation
- `alembic/` - Database migrations

**CLI Commands:**
- `creep init` - Initialize database
- `creep config` - Show configuration
- `creep list-companies` - List companies in database
- `creep add-company` - Add company to database

---

### Phase 2: Florida DBPR License Scraper ✅ COMPLETE

**Files:**
- `src/creep/scrapers/florida_dbpr.py` - Florida DBPR license scraper
- `src/creep/scrapers/schemas.py` - Pydantic schemas (DBPRLicenseResult, DBPRLicenseDetail, DBPRDisciplinaryAction)

**Features:**
- Search by company name or license number
- Extract: license number, status, issue date, expiration, licensee name, type, rank
- Disciplinary action lookup
- Playwright browser automation for JavaScript-rendered pages

**CLI Command:**
```bash
creep scan-license "Company Name" --state FL --license ABC123
```

---

### Phase 3: BBB Reviews Scraper ✅ COMPLETE

**Files:**
- `src/creep/scrapers/bbb.py` - Better Business Bureau scraper
- `src/creep/scrapers/schemas.py` - BBBProfileResult schema

**Features:**
- Search by company name and location
- Extract: BBB rating, accreditation status, years in business, complaint counts, customer reviews
- Detailed profile scraping from `__PRELOADED_STATE__` JSON
- Stealth headers to avoid blocking

**CLI Command:**
```bash
creep scan-reviews "Company Name" --city miami --state FL
```

---

### Phase 4: CourtListener Federal Courts ✅ COMPLETE

**Files:**
- `src/creep/scrapers/courtlistener.py` - CourtListener API scraper
- `src/creep/scrapers/schemas.py` - CourtListenerCase schema

**Features:**
- Search federal court dockets by party name
- RECAP archive search
- Extract: case name, docket number, court, filing date, nature of suit, parties
- Supports API token authentication (optional)
- Fallback to HTML scraping if unauthenticated

**CLI Command:**
```bash
creep scan-courts "Company Name" --state FL --limit 20
```

**Configuration:**
```bash
# .env
COURTLISTENER_API_TOKEN=your_token_here  # Optional, get from courtlistener.com
```

---

### Phase 5: Florida UCC Liens ✅ COMPLETE

**Files:**
- `src/creep/scrapers/florida_ucc.py` - Florida Secured Transaction Registry scraper
- `src/creep/scrapers/schemas.py` - UCCFilingResult schema

**Features:**
- Search UCC filings by debtor/organization name
- Terms acceptance dialog handling (MUI-based React SPA)
- Extract: filing number, type, dates, debtor, secured party, collateral
- Filing detail lookup

**CLI Command:**
```bash
creep scan-liens "Company Name" --state FL
```

**Technical Notes:**
- Site uses React/Material-UI with dynamic rendering
- Terms checkbox requires special handling (`aria-label` selectors, force clicks)
- Search button is an IconButton with `aria-label="search"`

---

### Phase 6: Risk Scoring Engine ✅ COMPLETE

**Location:** `src/creep/scoring/`

**Planned Implementation:**

#### 6.1 Feature Extractor
```python
# src/creep/scoring/features.py
class FeatureExtractor:
    """Extract risk features from scraped data."""

    def extract(self, company_id: UUID) -> dict:
        """Return standardized feature vector."""
        return {
            # Licensing (0-25 points of risk)
            'license_expired': bool,
            'license_disciplinary_actions': int,
            'years_licensed': float,

            # Financial Stability (0-30 points)
            'bankruptcy_filed': bool,
            'active_liens_count': int,
            'total_lien_amount': float,

            # Litigation History (0-20 points)
            'lawsuits_defendant_count': int,
            'lawsuits_plaintiff_count': int,

            # Reputation (0-15 points)
            'bbb_rating': str,
            'avg_review_score': float,
            'complaint_resolution_rate': float,

            # Business Stability (0-10 points)
            'years_in_business': float,
        }
```

#### 6.2 Weighted Risk Scorer
```python
# src/creep/scoring/scorer.py
class WeightedRiskScorer:
    """Calculate risk score using configurable weights."""

    # Default weights (from config.py)
    DEFAULT_WEIGHTS = {
        'license': 0.35,      # 35%
        'reputation': 0.25,   # 25%
        'litigation': 0.25,   # 25%
        'financial': 0.15,    # 15%
    }

    def calculate(self, features: dict) -> RiskScoreResult:
        """
        Returns:
            - overall_score: 0-100 (higher = more risky)
            - category_scores: dict of category -> score
            - top_risk_factors: list of (factor, contribution, citation)
            - confidence: 0-1 based on data completeness
        """
```

#### 6.3 Risk Factor Calculations

**Licensing Risk (0-35 points):**
- License expired: +25 points
- Each disciplinary action: +10 points (max 35)
- Licensed < 2 years: +15 points
- License suspended/revoked: +35 points

**Reputation Risk (0-25 points):**
- BBB rating F: +15 points, D: +10, C: +5
- Not BBB accredited: +5 points
- Avg review < 3.0: +10 points
- Unresolved complaints > 5: +5 points

**Litigation Risk (0-25 points):**
- Each lawsuit as defendant: +4 points (max 20)
- Active lawsuit: +5 points
- Bankruptcy in last 7 years: +15 points

**Financial Risk (0-15 points):**
- Each active UCC lien: +3 points (max 15)
- High-value liens (>$100k): +5 additional

**CLI Command:**
```bash
creep calculate-risk "Company Name"
```

---

### Phase 7: Report Generation ✅ COMPLETE

**Location:** `src/creep/reports/`

**Planned Implementation:**

#### 7.1 Report Generator
```python
# src/creep/reports/generator.py
class ReportGenerator:
    """Generate risk reports in multiple formats."""

    def generate_html(self, company_id: UUID) -> str:
        """Generate HTML report using Jinja2 templates."""

    def generate_pdf(self, company_id: UUID, output_path: str) -> Path:
        """Generate PDF report using WeasyPrint."""

    def generate_json(self, company_id: UUID) -> dict:
        """Generate JSON export for API consumers."""
```

#### 7.2 HTML Template Structure
```
src/creep/reports/templates/
├── base.html           # Base template with CSS
├── report.html         # Main report template
├── partials/
│   ├── executive_summary.html
│   ├── risk_breakdown.html
│   ├── license_findings.html
│   ├── court_findings.html
│   ├── lien_findings.html
│   └── reputation_findings.html
└── static/
    └── chart.js        # Risk breakdown visualization
```

#### 7.3 Report Contents
- Executive Summary (score, recommendation, confidence)
- Risk Breakdown Visualization (donut/bar chart)
- Detailed Findings by Category with Source Citations
- Data Freshness Indicators
- Disclaimers

**CLI Commands:**
```bash
creep report "Company Name" --format pdf --output report.pdf
creep report "Company Name" --format html --output report.html
```

---

### Phase 8: Full Pipeline & ML Enhancement ⏳ NOT STARTED

#### 8.1 Full Scan Pipeline
```python
# Orchestrate all scrapers and generate report
async def full_scan(company_name: str, state: str = "FL") -> Report:
    # 1. Run all scrapers in parallel
    license_results = await scan_license(company_name, state)
    bbb_results = await scan_reviews(company_name, state)
    court_results = await scan_courts(company_name)
    lien_results = await scan_liens(company_name)

    # 2. Calculate risk score
    risk_score = calculate_risk(company_id)

    # 3. Generate report
    report = generate_report(company_id, format="pdf")

    return report
```

**CLI Command:**
```bash
creep scan "Company Name" --state FL --output report.pdf --format pdf
```

#### 8.2 ML Enhancement (Future)
- Synthetic training data generation based on weighted rules
- sklearn pipeline: StandardScaler → LogisticRegression
- Feature importance / SHAP values
- A/B comparison with weighted scorer
- Feedback loop for labeling actual outcomes

---

## Project Structure

```
CREEP/
├── src/creep/
│   ├── __init__.py
│   ├── __main__.py
│   ├── config.py              # ✅ Pydantic settings
│   ├── cli/
│   │   ├── __init__.py
│   │   └── commands.py        # ✅ Typer CLI
│   ├── db/
│   │   ├── __init__.py
│   │   ├── engine.py          # ✅ Async SQLAlchemy
│   │   ├── models.py          # ✅ ORM models
│   │   └── repository.py      # ✅ Repository pattern
│   ├── scrapers/
│   │   ├── __init__.py
│   │   ├── base.py            # ✅ Base scraper class
│   │   ├── schemas.py         # ✅ Pydantic schemas
│   │   ├── florida_dbpr.py    # ✅ FL license scraper
│   │   ├── bbb.py             # ✅ BBB scraper
│   │   ├── courtlistener.py   # ✅ Court records scraper
│   │   └── florida_ucc.py     # ✅ UCC liens scraper
│   ├── scoring/
│   │   ├── __init__.py        # ⏳ Empty stub
│   │   ├── features.py        # ⏳ TODO: Feature extractor
│   │   └── scorer.py          # ⏳ TODO: Risk scorer
│   ├── reports/
│   │   ├── __init__.py        # ⏳ Empty stub
│   │   ├── generator.py       # ⏳ TODO: Report generator
│   │   └── templates/         # ⏳ TODO: Jinja2 templates
│   └── utils/
│       └── __init__.py
├── alembic/                   # ✅ Database migrations
├── tests/
│   └── __init__.py
├── pyproject.toml             # ✅ Project config
├── .env                       # Environment variables (not in git)
├── PLAN.md                    # This file
└── README.md
```

---

## Configuration

### Environment Variables (.env)
```bash
# Database
DATABASE_URL=postgresql+asyncpg://localhost/creep

# Scraping
SCRAPER_RATE_LIMIT=2.0
SCRAPER_MAX_RETRIES=3
SCRAPER_TIMEOUT=30
PLAYWRIGHT_HEADLESS=true

# API Keys
COURTLISTENER_API_TOKEN=          # Optional

# Risk Scoring Weights
WEIGHT_LICENSE=0.35
WEIGHT_REPUTATION=0.25
WEIGHT_LITIGATION=0.25
WEIGHT_FINANCIAL=0.15
```

---

## Quick Start

```bash
# Install dependencies
uv sync

# Install Playwright browsers
uv run playwright install chromium

# Initialize database (requires PostgreSQL running)
uv run creep init

# Scan a contractor
uv run creep scan-license "ABC Construction" --state FL
uv run creep scan-reviews "ABC Construction" --city miami
uv run creep scan-courts "ABC Construction"
uv run creep scan-liens "ABC Construction"

# Calculate risk (Phase 6 - not yet implemented)
uv run creep calculate-risk "ABC Construction"

# Generate report (Phase 7 - not yet implemented)
uv run creep report "ABC Construction" --format pdf
```

---

## Next Steps

1. **Phase 6: Risk Scoring Engine**
   - Implement `src/creep/scoring/features.py` - Feature extractor
   - Implement `src/creep/scoring/scorer.py` - Weighted risk calculator
   - Update CLI `calculate-risk` command
   - Add unit tests with synthetic test cases

2. **Phase 7: Report Generation**
   - Create Jinja2 templates for HTML reports
   - Implement PDF generation with WeasyPrint
   - Add risk breakdown visualization (Chart.js)
   - Update CLI `report` command

3. **Phase 8: Full Pipeline**
   - Implement orchestrated `scan` command
   - Parallel scraper execution with asyncio
   - Batch processing from CSV
   - Error handling and retry logic

---

## Notes

### Scraper Resilience
- All scrapers use multiple selector strategies for robustness
- Rate limiting prevents blocking (2+ seconds between requests)
- Browser automation with Playwright for JavaScript-heavy sites
- Debug HTML saved to `~/ucc_debug.html` etc. for troubleshooting

### Database
- PostgreSQL with async SQLAlchemy
- UUID primary keys
- JSONB for raw scraped data
- Proper indexes on frequently queried fields

### Known Issues
- Florida UCC: Secured party name sometimes captures address instead of name (parsing improvement needed)
- CourtListener: Better results with API token (free registration required)
- DBPR: Site occasionally slow, may need increased timeout
