"""Report generation for CREEP risk assessments.

Generates HTML and PDF reports using Jinja2 templates and WeasyPrint.
"""

from datetime import datetime
from pathlib import Path
from uuid import UUID

from jinja2 import Environment, FileSystemLoader, select_autoescape
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from creep.db.models import (
    BBBProfile,
    Company,
    CourtCase,
    License,
    Lien,
    RiskScore,
)
from creep.reports.charts import (
    ChartSegment,
    generate_donut_chart,
    generate_horizontal_bar_chart,
    get_risk_color,
    get_risk_level,
)


class ReportGenerator:
    """Generate risk assessment reports in HTML and PDF formats."""

    def __init__(self, template_dir: Path | None = None):
        """Initialize report generator.

        Args:
            template_dir: Path to Jinja2 templates. Defaults to built-in templates.
        """
        if template_dir is None:
            template_dir = Path(__file__).parent / "templates"

        self.template_dir = template_dir
        self.env = Environment(
            loader=FileSystemLoader(str(template_dir)),
            autoescape=select_autoescape(["html", "xml"]),
        )

        # Register custom filters
        self.env.filters["risk_color"] = get_risk_color
        self.env.filters["risk_level"] = get_risk_level
        self.env.filters["format_date"] = self._format_date

    @staticmethod
    def _format_date(value, format: str = "%B %d, %Y") -> str:
        """Format a date for display."""
        if value is None:
            return "N/A"
        if isinstance(value, str):
            return value
        return value.strftime(format)

    async def generate_html(self, session: AsyncSession, company_id: UUID) -> str:
        """Generate HTML report for a company.

        Args:
            session: Database session
            company_id: UUID of company to report on

        Returns:
            HTML string
        """
        # Fetch all data
        context = await self._build_context(session, company_id)

        # Render template
        template = self.env.get_template("report.html")
        return template.render(**context)

    async def generate_pdf(
        self,
        session: AsyncSession,
        company_id: UUID,
        output_path: Path,
    ) -> Path:
        """Generate PDF report for a company.

        Args:
            session: Database session
            company_id: UUID of company to report on
            output_path: Where to save the PDF

        Returns:
            Path to generated PDF
        """
        from weasyprint import HTML

        html = await self.generate_html(session, company_id)
        HTML(string=html, base_url=str(self.template_dir)).write_pdf(output_path)
        return output_path

    async def _build_context(self, session: AsyncSession, company_id: UUID) -> dict:
        """Build template context with all report data."""
        # Fetch company with related data
        stmt = (
            select(Company)
            .where(Company.id == company_id)
            .options(
                selectinload(Company.licenses).selectinload(License.disciplinary_actions),
                selectinload(Company.bbb_profiles),
                selectinload(Company.court_cases),
                selectinload(Company.liens),
                selectinload(Company.risk_scores),
            )
        )
        result = await session.execute(stmt)
        company = result.scalar_one_or_none()

        if not company:
            raise ValueError(f"Company {company_id} not found")

        # Get latest risk score
        risk_score = None
        if company.risk_scores:
            risk_score = sorted(
                company.risk_scores,
                key=lambda s: s.calculated_at,
                reverse=True,
            )[0]

        # Get latest BBB profile
        bbb_profile = None
        if company.bbb_profiles:
            bbb_profile = sorted(
                company.bbb_profiles,
                key=lambda p: p.scraped_at,
                reverse=True,
            )[0]

        # Build category data for charts
        category_data = self._build_category_data(risk_score)

        # Generate charts
        donut_chart = self._generate_category_chart(category_data, risk_score)
        bar_chart = self._generate_bar_chart(category_data)

        # Build findings sections
        license_findings = self._build_license_findings(company.licenses)
        bbb_findings = self._build_bbb_findings(bbb_profile)
        court_findings = self._build_court_findings(company.court_cases)
        lien_findings = self._build_lien_findings(company.liens)

        # Build risk factors from score breakdown
        risk_factors = self._extract_risk_factors(risk_score)

        return {
            "company": company,
            "risk_score": risk_score,
            "bbb_profile": bbb_profile,
            "licenses": company.licenses,
            "court_cases": company.court_cases,
            "liens": company.liens,
            "category_data": category_data,
            "donut_chart": donut_chart,
            "bar_chart": bar_chart,
            "license_findings": license_findings,
            "bbb_findings": bbb_findings,
            "court_findings": court_findings,
            "lien_findings": lien_findings,
            "risk_factors": risk_factors,
            "generated_at": datetime.now(),
            "risk_color": get_risk_color(risk_score.overall_score) if risk_score else "#6b7280",
            "risk_level": get_risk_level(risk_score.overall_score) if risk_score else "Unknown",
        }

    def _build_category_data(self, risk_score: RiskScore | None) -> list[dict]:
        """Build category data for display."""
        categories = [
            {"name": "License", "key": "license", "weight": 35, "icon": "certificate"},
            {"name": "Reputation", "key": "reputation", "weight": 25, "icon": "star"},
            {"name": "Litigation", "key": "litigation", "weight": 25, "icon": "gavel"},
            {"name": "Financial", "key": "financial", "weight": 15, "icon": "dollar"},
        ]

        for cat in categories:
            if risk_score:
                score_attr = f"{cat['key']}_score"
                score = getattr(risk_score, score_attr, None)
                cat["score"] = score
                cat["available"] = score is not None
                cat["color"] = get_risk_color(score) if score else "#9ca3af"
            else:
                cat["score"] = None
                cat["available"] = False
                cat["color"] = "#9ca3af"

        return categories

    def _generate_category_chart(
        self,
        category_data: list[dict],
        risk_score: RiskScore | None,
    ) -> str:
        """Generate donut chart for category breakdown."""
        segments = []
        for cat in category_data:
            if cat["available"] and cat["score"] is not None:
                segments.append(
                    ChartSegment(
                        label=cat["name"],
                        value=cat["score"],
                        color=cat["color"],
                    )
                )

        if not segments:
            return ""

        center_text = str(int(risk_score.overall_score)) if risk_score else "N/A"
        return generate_donut_chart(
            segments,
            center_text=center_text,
            center_subtext="Overall Score",
        )

    def _generate_bar_chart(self, category_data: list[dict]) -> str:
        """Generate horizontal bar chart for categories."""
        items = []
        for cat in category_data:
            if cat["available"] and cat["score"] is not None:
                items.append((cat["name"], cat["score"], cat["color"]))

        if not items:
            return ""

        return generate_horizontal_bar_chart(items)

    def _build_license_findings(self, licenses: list[License]) -> list[dict]:
        """Build license findings for report."""
        findings = []
        for lic in licenses:
            finding = {
                "license_number": lic.license_number,
                "licensee_name": lic.licensee_name,
                "license_type": lic.license_type,
                "status": lic.status,
                "issue_date": lic.issue_date,
                "expiration_date": lic.expiration_date,
                "source": lic.source,
                "disciplinary_count": len(lic.disciplinary_actions),
                "disciplinary_actions": [
                    {
                        "action_type": a.action_type,
                        "action_date": a.action_date,
                        "description": a.description,
                        "fine_amount": a.fine_amount,
                    }
                    for a in lic.disciplinary_actions
                ],
            }

            # Determine status color
            status_lower = (lic.status or "").lower()
            if "active" in status_lower or "current" in status_lower:
                finding["status_color"] = "#22c55e"
            elif "expired" in status_lower:
                finding["status_color"] = "#f97316"
            elif "revoked" in status_lower or "suspended" in status_lower:
                finding["status_color"] = "#ef4444"
            else:
                finding["status_color"] = "#6b7280"

            findings.append(finding)

        return findings

    def _build_bbb_findings(self, bbb_profile: BBBProfile | None) -> dict | None:
        """Build BBB findings for report."""
        if not bbb_profile:
            return None

        # Rating color
        rating = (bbb_profile.bbb_rating or "").upper()
        if rating in ("A+", "A"):
            rating_color = "#22c55e"
        elif rating in ("B+", "B", "B-"):
            rating_color = "#84cc16"
        elif rating in ("C+", "C", "C-"):
            rating_color = "#eab308"
        else:
            rating_color = "#ef4444"

        return {
            "rating": bbb_profile.bbb_rating,
            "rating_color": rating_color,
            "accredited": bbb_profile.accredited,
            "years_in_business": bbb_profile.years_in_business,
            "complaint_count": bbb_profile.complaint_count,
            "complaint_resolved": bbb_profile.complaint_resolved_count,
            "complaint_unresolved": bbb_profile.complaint_unresolved_count,
            "profile_url": bbb_profile.profile_url,
            "scraped_at": bbb_profile.scraped_at,
        }

    def _build_court_findings(self, court_cases: list[CourtCase]) -> list[dict]:
        """Build court case findings for report."""
        findings = []
        for case in court_cases[:10]:  # Limit to 10 for report
            finding = {
                "case_name": case.case_summary or "Unknown Case",
                "case_number": case.case_number,
                "court": case.court_name,
                "case_type": case.case_type,
                "filing_date": case.filing_date,
                "status": case.status,
                "url": case.external_url,
            }

            # Status color
            status_lower = (case.status or "").lower()
            if "terminated" in status_lower or "closed" in status_lower:
                finding["status_color"] = "#6b7280"
            else:
                finding["status_color"] = "#f97316"

            findings.append(finding)

        return findings

    def _build_lien_findings(self, liens: list[Lien]) -> list[dict]:
        """Build lien findings for report."""
        findings = []
        for lien in liens[:10]:  # Limit to 10 for report
            finding = {
                "filing_number": lien.filing_number,
                "filing_type": lien.lien_type,
                "filing_date": lien.filing_date,
                "secured_party": lien.secured_party,
                "collateral": lien.collateral_description,
                "status": lien.status,
                "amount": lien.amount,
            }

            # Status color
            status_lower = (lien.status or "").lower()
            if "active" in status_lower:
                finding["status_color"] = "#f97316"
            else:
                finding["status_color"] = "#22c55e"

            findings.append(finding)

        return findings

    def _extract_risk_factors(self, risk_score: RiskScore | None) -> list[dict]:
        """Extract top risk factors from score breakdown."""
        if not risk_score or not risk_score.score_breakdown:
            return []

        factors = []
        breakdown = risk_score.score_breakdown

        # Extract factors from category details
        category_details = breakdown.get("category_details", {})
        for category, details in category_details.items():
            if not details.get("available"):
                continue

            for factor in details.get("factors", []):
                factors.append({
                    "name": factor.get("name", "Unknown"),
                    "impact": factor.get("impact", 0),
                    "source": factor.get("source", "Unknown"),
                    "details": factor.get("details", ""),
                    "category": category.title(),
                    "impact_color": "#22c55e" if factor.get("impact", 0) > 0 else "#ef4444",
                })

        # Sort by absolute impact
        factors.sort(key=lambda f: abs(f["impact"]), reverse=True)
        return factors[:10]  # Top 10
