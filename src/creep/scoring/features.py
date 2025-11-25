"""Feature extraction for risk scoring.

Extracts risk-relevant features from scraped company data and computes
category scores for the risk scoring engine.
"""

from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from sqlalchemy import select

from creep.db.models import (
    BBBProfile,
    Company,
    CourtCase,
    DisciplinaryAction,
    License,
    Lien,
)


@dataclass
class RiskFactor:
    """Single risk signal with attribution."""

    name: str  # e.g., "License Expired"
    impact: float  # Points added/subtracted
    source: str  # e.g., "License #CGC1234567"
    details: str | None = None  # Additional context


@dataclass
class CategoryFeatures:
    """Features for a single scoring category."""

    available: bool  # Was data found for this category?
    raw_score: float  # 0-100 before weighting (higher = better)
    factors: list[RiskFactor] = field(default_factory=list)
    data_sources: list[str] = field(default_factory=list)


class FeatureExtractor:
    """Extract risk features from database records.

    Computes category scores (0-100, higher = better) for:
    - license: License status, tenure, disciplinary actions
    - reputation: BBB rating, accreditation, complaints, years in business
    - litigation: Court cases, bankruptcy
    - financial: UCC liens
    """

    def __init__(self, session: AsyncSession):
        self.session = session

    async def extract(self, company_id: UUID) -> dict[str, CategoryFeatures]:
        """Extract features from all data sources for a company.

        Args:
            company_id: UUID of the company to analyze

        Returns:
            Dict with keys: 'license', 'reputation', 'litigation', 'financial'
            Each value is a CategoryFeatures with raw_score 0-100.
        """
        # Fetch company with all related data
        company = await self._fetch_company_data(company_id)
        if not company:
            return {
                "license": CategoryFeatures(available=False, raw_score=0),
                "reputation": CategoryFeatures(available=False, raw_score=0),
                "litigation": CategoryFeatures(available=False, raw_score=0),
                "financial": CategoryFeatures(available=False, raw_score=0),
            }

        return {
            "license": self._extract_license_features(company.licenses),
            "reputation": self._extract_reputation_features(company.bbb_profiles),
            "litigation": self._extract_litigation_features(company.court_cases),
            "financial": self._extract_financial_features(company.liens),
        }

    async def _fetch_company_data(self, company_id: UUID) -> Company | None:
        """Fetch company with all related records for scoring."""
        stmt = (
            select(Company)
            .where(Company.id == company_id)
            .options(
                selectinload(Company.licenses).selectinload(License.disciplinary_actions),
                selectinload(Company.bbb_profiles),
                selectinload(Company.court_cases),
                selectinload(Company.liens),
            )
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    def _extract_license_features(self, licenses: list[License]) -> CategoryFeatures:
        """Extract license-related risk features.

        Scoring (0-100, higher = better):
        - Base score: +60 for active license
        - Status penalties: -40 for expired, -100 for revoked/suspended
        - Tenure bonuses: +20 for >5 years, +10 for 2-5 years
        - Disciplinary actions: -15 each (max -45)
        """
        if not licenses:
            return CategoryFeatures(
                available=False,
                raw_score=0,
                factors=[RiskFactor(
                    name="No License Found",
                    impact=0,
                    source="License Search",
                    details="No contractor license found in Florida DBPR database",
                )],
            )

        # Use the primary/most relevant license (first one, or could sort by status)
        primary_license = licenses[0]
        factors: list[RiskFactor] = []
        data_sources: list[str] = []
        score = 0.0

        # Track all licenses
        for lic in licenses:
            data_sources.append(f"License #{lic.license_number}")

        # Base score for having a license
        status = (primary_license.status or "").lower()

        # Status scoring
        if "active" in status or "current" in status:
            score += 60
            factors.append(RiskFactor(
                name="Active License",
                impact=60,
                source=f"License #{primary_license.license_number}",
                details=f"Status: {primary_license.status}",
            ))
        elif "expired" in status:
            score += 20  # Base 60 - 40 penalty = 20
            factors.append(RiskFactor(
                name="Expired License",
                impact=-40,
                source=f"License #{primary_license.license_number}",
                details=f"Status: {primary_license.status}",
            ))
        elif "revoked" in status or "suspended" in status or "null" in status:
            score += 0  # Severe penalty
            factors.append(RiskFactor(
                name="License Revoked/Suspended",
                impact=-100,
                source=f"License #{primary_license.license_number}",
                details=f"Status: {primary_license.status}",
            ))
        else:
            # Unknown status - treat as neutral
            score += 40
            factors.append(RiskFactor(
                name="License Status Unknown",
                impact=40,
                source=f"License #{primary_license.license_number}",
                details=f"Status: {primary_license.status or 'Not specified'}",
            ))

        # Tenure bonus
        if primary_license.issue_date:
            years_licensed = self._years_since(primary_license.issue_date)
            if years_licensed > 5:
                score += 20
                factors.append(RiskFactor(
                    name="Established License (>5 years)",
                    impact=20,
                    source=f"License #{primary_license.license_number}",
                    details=f"Licensed since {primary_license.issue_date} ({years_licensed:.1f} years)",
                ))
            elif years_licensed >= 2:
                score += 10
                factors.append(RiskFactor(
                    name="Moderate Tenure (2-5 years)",
                    impact=10,
                    source=f"License #{primary_license.license_number}",
                    details=f"Licensed since {primary_license.issue_date} ({years_licensed:.1f} years)",
                ))
            else:
                factors.append(RiskFactor(
                    name="New License (<2 years)",
                    impact=0,
                    source=f"License #{primary_license.license_number}",
                    details=f"Licensed since {primary_license.issue_date} ({years_licensed:.1f} years)",
                ))

        # Disciplinary actions penalty
        total_actions = sum(
            len(lic.disciplinary_actions) for lic in licenses
        )
        if total_actions > 0:
            penalty = min(total_actions * 15, 45)  # Max -45
            score -= penalty
            factors.append(RiskFactor(
                name="Disciplinary Actions",
                impact=-penalty,
                source="Disciplinary Records",
                details=f"{total_actions} action(s) on record",
            ))

        # Clamp score to 0-100
        score = max(0, min(100, score))

        return CategoryFeatures(
            available=True,
            raw_score=score,
            factors=factors,
            data_sources=data_sources,
        )

    def _extract_reputation_features(self, bbb_profiles: list[BBBProfile]) -> CategoryFeatures:
        """Extract reputation-related risk features from BBB data.

        Scoring (0-100, higher = better):
        - BBB Rating: A+/A=+40, B+/B/B-=+25, C+=+10, F/NR=0
        - Accreditation: +30 if accredited, +10 if not
        - Complaints (last 12mo): 0=+20, 1-3=+10, >3=0
        - Years in business: >10=+10
        """
        if not bbb_profiles:
            return CategoryFeatures(
                available=False,
                raw_score=0,
                factors=[RiskFactor(
                    name="No BBB Profile Found",
                    impact=0,
                    source="BBB Search",
                    details="No Better Business Bureau profile found",
                )],
            )

        # Use most recent profile
        profile = sorted(bbb_profiles, key=lambda p: p.scraped_at, reverse=True)[0]
        factors: list[RiskFactor] = []
        data_sources: list[str] = [profile.profile_url or "BBB Profile"]
        score = 0.0

        # BBB Rating scoring
        rating = (profile.bbb_rating or "").upper()
        if rating in ("A+", "A"):
            score += 40
            factors.append(RiskFactor(
                name=f"BBB Rating {rating}",
                impact=40,
                source="BBB Profile",
                details="Excellent BBB rating",
            ))
        elif rating in ("B+", "B", "B-"):
            score += 25
            factors.append(RiskFactor(
                name=f"BBB Rating {rating}",
                impact=25,
                source="BBB Profile",
                details="Good BBB rating",
            ))
        elif rating in ("C+", "C", "C-", "D+", "D", "D-"):
            score += 10
            factors.append(RiskFactor(
                name=f"BBB Rating {rating}",
                impact=10,
                source="BBB Profile",
                details="Below average BBB rating",
            ))
        elif rating in ("F", "NR", ""):
            score += 0
            factors.append(RiskFactor(
                name=f"BBB Rating {rating or 'Not Rated'}",
                impact=0,
                source="BBB Profile",
                details="Poor or no BBB rating",
            ))
        else:
            # Unknown rating format
            score += 15
            factors.append(RiskFactor(
                name=f"BBB Rating {rating}",
                impact=15,
                source="BBB Profile",
                details="Unrecognized rating format",
            ))

        # Accreditation scoring
        if profile.accredited:
            score += 30
            factors.append(RiskFactor(
                name="BBB Accredited",
                impact=30,
                source="BBB Profile",
                details="Business is BBB accredited",
            ))
        else:
            score += 10
            factors.append(RiskFactor(
                name="Not BBB Accredited",
                impact=10,
                source="BBB Profile",
                details="Business is not BBB accredited",
            ))

        # Complaints scoring
        complaints = profile.complaint_count or 0
        if complaints == 0:
            score += 20
            factors.append(RiskFactor(
                name="No Complaints",
                impact=20,
                source="BBB Profile",
                details="No complaints on record",
            ))
        elif complaints <= 3:
            score += 10
            factors.append(RiskFactor(
                name="Few Complaints",
                impact=10,
                source="BBB Profile",
                details=f"{complaints} complaint(s) on record",
            ))
        else:
            score += 0
            factors.append(RiskFactor(
                name="Multiple Complaints",
                impact=0,
                source="BBB Profile",
                details=f"{complaints} complaint(s) on record",
            ))

        # Years in business bonus
        years = profile.years_in_business or 0
        if years > 10:
            score += 10
            factors.append(RiskFactor(
                name="Long Business History",
                impact=10,
                source="BBB Profile",
                details=f"{years} years in business",
            ))

        # Clamp score to 0-100
        score = max(0, min(100, score))

        return CategoryFeatures(
            available=True,
            raw_score=score,
            factors=factors,
            data_sources=data_sources,
        )

    def _extract_litigation_features(self, court_cases: list[CourtCase]) -> CategoryFeatures:
        """Extract litigation-related risk features.

        Scoring (0-100, higher = better):
        - No cases: +80 base
        - 1-2 cases as defendant: +50
        - 3-5 cases as defendant: +30
        - 6+ cases as defendant: +10
        - Any bankruptcy: -30 penalty
        """
        factors: list[RiskFactor] = []
        data_sources: list[str] = []

        if not court_cases:
            return CategoryFeatures(
                available=True,  # No cases is still valid data
                raw_score=80,
                factors=[RiskFactor(
                    name="No Court Cases Found",
                    impact=80,
                    source="Court Records Search",
                    details="No federal court cases found involving this company",
                )],
                data_sources=["CourtListener Search"],
            )

        # Count cases and categorize
        defendant_count = 0
        has_bankruptcy = False

        for case in court_cases:
            data_sources.append(f"Case {case.case_number or case.id}")

            # Check if company is defendant (simple heuristic)
            case_summary = (case.case_summary or "").lower()
            defendant_field = (case.defendant or "").lower()
            case_type = (case.case_type or "").lower()

            # Check for bankruptcy
            if "bankrupt" in case_type or "bankrupt" in case_summary:
                has_bankruptcy = True

            # Count defendant appearances
            # This is a simplified heuristic - company being defendant is a risk signal
            if defendant_field:
                defendant_count += 1
            else:
                # If no explicit defendant field, count all cases
                defendant_count += 1

        # Base score based on defendant count
        if defendant_count == 0:
            score = 80.0
            factors.append(RiskFactor(
                name="No Defendant Cases",
                impact=80,
                source="Court Records",
                details=f"{len(court_cases)} case(s) found, none as defendant",
            ))
        elif defendant_count <= 2:
            score = 50.0
            factors.append(RiskFactor(
                name="Few Court Cases",
                impact=50,
                source="Court Records",
                details=f"{defendant_count} case(s) found as defendant",
            ))
        elif defendant_count <= 5:
            score = 30.0
            factors.append(RiskFactor(
                name="Moderate Litigation History",
                impact=30,
                source="Court Records",
                details=f"{defendant_count} case(s) found as defendant",
            ))
        else:
            score = 10.0
            factors.append(RiskFactor(
                name="Significant Litigation History",
                impact=10,
                source="Court Records",
                details=f"{defendant_count} case(s) found as defendant",
            ))

        # Bankruptcy penalty
        if has_bankruptcy:
            score -= 30
            factors.append(RiskFactor(
                name="Bankruptcy Case",
                impact=-30,
                source="Court Records",
                details="Bankruptcy case found on record",
            ))

        # Clamp score to 0-100
        score = max(0, min(100, score))

        return CategoryFeatures(
            available=True,
            raw_score=score,
            factors=factors,
            data_sources=data_sources,
        )

    def _extract_financial_features(self, liens: list[Lien]) -> CategoryFeatures:
        """Extract financial-related risk features from UCC liens.

        Scoring (0-100, higher = better):
        - No liens: +90 base (excellent)
        - All terminated/lapsed: +80
        - 1-2 active liens: +60
        - 3-5 active liens: +40
        - 6+ active liens: +20
        """
        factors: list[RiskFactor] = []
        data_sources: list[str] = []

        if not liens:
            return CategoryFeatures(
                available=True,  # No liens is still valid data
                raw_score=90,
                factors=[RiskFactor(
                    name="No UCC Liens Found",
                    impact=90,
                    source="UCC Search",
                    details="No UCC filings found in Florida registry",
                )],
                data_sources=["Florida UCC Registry"],
            )

        # Categorize liens by status
        active_count = 0
        terminated_count = 0

        for lien in liens:
            data_sources.append(f"Filing #{lien.filing_number or lien.id}")

            status = (lien.status or "").lower()
            if "active" in status or status == "":
                active_count += 1
            elif "terminated" in status or "lapsed" in status or "released" in status:
                terminated_count += 1
            else:
                # Unknown status - treat as active to be conservative
                active_count += 1

        # Score based on active lien count
        if active_count == 0:
            score = 80.0
            factors.append(RiskFactor(
                name="All Liens Terminated/Lapsed",
                impact=80,
                source="UCC Registry",
                details=f"{terminated_count} filing(s), all resolved",
            ))
        elif active_count <= 2:
            score = 60.0
            factors.append(RiskFactor(
                name="Few Active Liens",
                impact=60,
                source="UCC Registry",
                details=f"{active_count} active lien(s)",
            ))
        elif active_count <= 5:
            score = 40.0
            factors.append(RiskFactor(
                name="Moderate Active Liens",
                impact=40,
                source="UCC Registry",
                details=f"{active_count} active lien(s)",
            ))
        else:
            score = 20.0
            factors.append(RiskFactor(
                name="Many Active Liens",
                impact=20,
                source="UCC Registry",
                details=f"{active_count} active lien(s)",
            ))

        return CategoryFeatures(
            available=True,
            raw_score=score,
            factors=factors,
            data_sources=data_sources,
        )

    @staticmethod
    def _years_since(d: date) -> float:
        """Calculate years since a date."""
        today = date.today()
        days = (today - d).days
        return days / 365.25
