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

### Phase 8: Full Pipeline ✅ COMPLETE

**CLI Command:**
```bash
creep scan "Company Name" --state FL --output report.pdf --format pdf
```

**Features:**
- Orchestrated full scan running all scrapers in parallel
- Risk score calculation
- Report generation

---

## Web Application Migration

The following phases transform CREEP from a CLI tool into a Vercel-deployable web application.

### Phase 9: Next.js Foundation ✅ COMPLETE

**Goal:** Create base Next.js application with database connectivity

**Completed 2025-11-25:**
- ✅ Next.js 14.2.15 initialized in `web/` directory
- ✅ Tailwind CSS + shadcn/ui configured with CSS variables
- ✅ Drizzle ORM schema created (10 tables matching Python models)
- ✅ Landing page with search form UI
- ✅ Health check API endpoint (`/api/health`)
- ✅ Build verified successful

**Files created:**
```
web/
├── app/
│   ├── layout.tsx              # ✅ Root layout with Inter font
│   ├── page.tsx                # ✅ Landing page with search form
│   ├── globals.css             # ✅ Tailwind + CSS variables
│   └── api/health/route.ts     # ✅ Health check endpoint
├── lib/
│   ├── db.ts                   # ✅ Neon/Drizzle connection
│   └── utils.ts                # ✅ cn() utility for shadcn
├── db/
│   └── schema.ts               # ✅ Complete Drizzle schema
├── components/ui/
│   └── button.tsx              # ✅ shadcn Button component
├── package.json                # ✅ All dependencies
├── tailwind.config.ts          # ✅ shadcn theme config
├── drizzle.config.ts           # ✅ Drizzle kit config
├── components.json             # ✅ shadcn config
└── .env.local.example          # ✅ Environment template
```

**To run:**
```bash
cd web && npm run dev
# Visit http://localhost:3000
```

---

### Phase 10: Core API Routes ⏳ NEXT UP

**Goal:** Port scrapers and create REST API endpoints

**Prerequisites (do these first!):**
1. **Create Neon account** → https://neon.tech (free tier)
   - Create a project, get connection string
   - Add to `web/.env.local` as `DATABASE_URL`
   - Run `npm run db:push` to create tables

2. **Create Browserless account** → https://browserless.io (free tier: 6 hrs/mo)
   - Get API token
   - Add to `web/.env.local` as `BROWSERLESS_TOKEN`

3. **(Optional) CourtListener API token** → https://courtlistener.com
   - Improves search results
   - Add to `web/.env.local` as `COURTLISTENER_API_TOKEN`

**Critical Constraint:** Playwright does not work on Vercel serverless. Use Browserless.io for browser-based scraping.

| Scraper | Method | Strategy |
|---------|--------|----------|
| Florida DBPR | Playwright | Browserless.io |
| BBB | httpx + parsing | Direct fetch, Browserless fallback |
| CourtListener | REST API | Direct fetch |
| Florida UCC | Playwright | Browserless.io |

**Files to create:**
```
web/lib/scrapers/
├── base.ts              # Port from src/creep/scrapers/base.py
├── browser.ts           # Browserless.io connection wrapper
├── florida-dbpr.ts      # Port from src/creep/scrapers/florida_dbpr.py
├── bbb.ts               # Port from src/creep/scrapers/bbb.py
├── courtlistener.ts     # Port from src/creep/scrapers/courtlistener.py
└── florida-ucc.ts       # Port from src/creep/scrapers/florida_ucc.py

web/app/api/
├── companies/
│   ├── route.ts         # GET (list), POST (create)
│   └── [id]/route.ts    # GET, DELETE single company
└── search/
    ├── license/route.ts # POST - DBPR search
    ├── reviews/route.ts # POST - BBB search
    ├── courts/route.ts  # POST - CourtListener search
    ├── liens/route.ts   # POST - UCC search
    └── full/route.ts    # POST - All sources
```

**API Endpoints:**
```
POST /api/search/license     - DBPR search
POST /api/search/reviews     - BBB search
POST /api/search/courts      - CourtListener search
POST /api/search/liens       - UCC search
POST /api/search/full        - All sources
GET  /api/companies          - List companies
POST /api/companies          - Create company
GET  /api/companies/:id      - Get company with data
```

**Reference Python files for porting:**
- `src/creep/scrapers/base.py` → Rate limiting, stealth headers
- `src/creep/scrapers/florida_dbpr.py` → DBPR scraper logic
- `src/creep/scrapers/bbb.py` → BBB parsing (`__PRELOADED_STATE__`)
- `src/creep/scrapers/courtlistener.py` → API client
- `src/creep/scrapers/florida_ucc.py` → UCC with MUI dialog handling

---

### Phase 11: Risk Scoring Engine ⏳ NOT STARTED

**Goal:** Port risk calculation logic to TypeScript

**Files:**
```
web/lib/scoring/
├── features.ts    # Feature extraction (port from features.py)
├── scorer.ts      # Weighted risk scorer (port from scorer.py)
└── types.ts       # TypeScript interfaces
```

**API Endpoints:**
```
POST /api/companies/:id/risk-score  - Calculate risk score
GET  /api/companies/:id/risk-score  - Get latest score
```

---

### Phase 12: Report Generation ⏳ NOT STARTED

**Goal:** PDF reports using @react-pdf/renderer (replaces WeasyPrint for serverless compatibility)

**Files:**
```
web/lib/reports/
├── template.tsx              # React-PDF document
├── components/               # Report sections
└── charts.tsx                # SVG chart generation
```

**API Endpoints:**
```
POST /api/reports        - Generate report
GET  /api/reports/:id    - Download PDF
```

---

### Phase 13: Frontend UI ⏳ NOT STARTED

**Goal:** Complete user interface

**Pages:**
- `/` - Search landing page
- `/results` - Search results display
- `/companies/:id` - Company detail + risk score

**Components:**
- SearchForm, SearchResults, CompanyCard
- RiskScoreDisplay, RiskBreakdownChart
- LoadingStates, ErrorBoundary

---

### Phase 14: Polish & Deploy ⏳ NOT STARTED

**Goal:** Final touches and Vercel deployment

**Tasks:**
- Rate limiting to protect Browserless quota
- SEO meta tags
- Performance optimization
- Vercel deployment configuration
- Environment variables in Vercel dashboard

**Free Tier Budget:**
| Service | Limit | Expected |
|---------|-------|----------|
| Vercel | 100GB bandwidth | ~5GB/mo |
| Neon | 0.5GB storage | ~100MB |
| Browserless | 6 hrs/month | ~2-3 hrs |

---

## Project Structure

```
CREEP/
├── src/creep/                 # Python CLI (preserved)
│   ├── __init__.py
│   ├── __main__.py
│   ├── config.py              # ✅ Pydantic settings
│   ├── cli/
│   │   └── commands.py        # ✅ Typer CLI
│   ├── db/
│   │   ├── engine.py          # ✅ Async SQLAlchemy
│   │   ├── models.py          # ✅ ORM models
│   │   └── repository.py      # ✅ Repository pattern
│   ├── scrapers/
│   │   ├── base.py            # ✅ Base scraper class
│   │   ├── schemas.py         # ✅ Pydantic schemas
│   │   ├── florida_dbpr.py    # ✅ FL license scraper
│   │   ├── bbb.py             # ✅ BBB scraper
│   │   ├── courtlistener.py   # ✅ Court records scraper
│   │   └── florida_ucc.py     # ✅ UCC liens scraper
│   ├── scoring/
│   │   ├── features.py        # ✅ Feature extractor
│   │   └── scorer.py          # ✅ Risk scorer
│   ├── reports/
│   │   ├── generator.py       # ✅ Report generator
│   │   ├── charts.py          # ✅ SVG charts
│   │   └── templates/         # ✅ Jinja2 templates
│   └── utils/
│       └── __init__.py
├── web/                       # Next.js Web App (Phase 9+)
│   ├── app/
│   │   ├── layout.tsx
│   │   ├── page.tsx
│   │   └── api/               # API routes
│   ├── lib/
│   │   ├── db.ts              # Neon connection
│   │   ├── scrapers/          # TypeScript scrapers
│   │   ├── scoring/           # Risk scoring
│   │   └── reports/           # PDF generation
│   ├── db/
│   │   └── schema.ts          # Drizzle ORM schema
│   ├── components/            # React components
│   ├── package.json
│   └── drizzle.config.ts
├── alembic/                   # ✅ Database migrations
├── tests/
├── pyproject.toml             # ✅ Python project config
├── docker-compose.yml         # Local PostgreSQL
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

**CLI Tool (Phases 1-8): ✅ COMPLETE**

**Web Application Migration:**

1. **Phase 9: Next.js Foundation** ✅ COMPLETE (2025-11-25)
   - Next.js 14 initialized in `web/`
   - Tailwind + shadcn/ui configured
   - Drizzle ORM schema created
   - Health check API working

2. **Phase 10: Core API Routes** ⏳ NEXT UP
   - [ ] Set up Neon PostgreSQL (get connection string)
   - [ ] Set up Browserless.io (get API token)
   - [ ] Port scrapers to TypeScript
   - [ ] Create REST API endpoints
   - [ ] Implement database caching

3. **Phase 11-14: Scoring, Reports, UI, Deploy**
   - See detailed phase descriptions above

---

## Quick Reference

**Start web dev server:**
```bash
cd web && npm run dev
```

**Push schema to Neon (after setting DATABASE_URL):**
```bash
cd web && npm run db:push
```

**View database (Drizzle Studio):**
```bash
cd web && npm run db:studio
```

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
