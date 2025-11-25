"""Data access layer for CREEP database operations."""

import re
import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from creep.db.models import (
    BBBProfile,
    Company,
    CourtCase,
    DisciplinaryAction,
    License,
    Lien,
    Review,
    RiskScore,
    ScrapeJob,
)


def normalize_company_name(name: str) -> str:
    """Normalize company name for consistent matching."""
    # Lowercase
    normalized = name.lower()
    # Remove common suffixes
    suffixes = [" inc", " llc", " corp", " ltd", " co", " company", " incorporated"]
    for suffix in suffixes:
        if normalized.endswith(suffix):
            normalized = normalized[: -len(suffix)]
    # Remove punctuation and extra whitespace
    normalized = re.sub(r"[^\w\s]", "", normalized)
    normalized = re.sub(r"\s+", " ", normalized).strip()
    return normalized


class CompanyRepository:
    """Repository for company operations."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_by_id(self, company_id: uuid.UUID) -> Company | None:
        """Get company by ID with all related data."""
        stmt = (
            select(Company)
            .where(Company.id == company_id)
            .options(
                selectinload(Company.licenses).selectinload(License.disciplinary_actions),
                selectinload(Company.reviews),
                selectinload(Company.bbb_profiles),
                selectinload(Company.court_cases),
                selectinload(Company.liens),
                selectinload(Company.risk_scores),
            )
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_by_name(self, name: str, state: str = "FL") -> Company | None:
        """Get company by name (normalized)."""
        normalized = normalize_company_name(name)
        stmt = select(Company).where(
            Company.normalized_name == normalized,
            Company.state == state,
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def create(self, name: str, state: str = "FL") -> Company:
        """Create a new company."""
        company = Company(
            name=name,
            normalized_name=normalize_company_name(name),
            state=state,
        )
        self.session.add(company)
        await self.session.flush()
        return company

    async def get_or_create(self, name: str, state: str = "FL") -> tuple[Company, bool]:
        """Get existing company or create new one. Returns (company, created)."""
        existing = await self.get_by_name(name, state)
        if existing:
            return existing, False
        company = await self.create(name, state)
        return company, True

    async def list_all(self, limit: int = 100, offset: int = 0) -> list[Company]:
        """List all companies."""
        stmt = select(Company).limit(limit).offset(offset).order_by(Company.created_at.desc())
        result = await self.session.execute(stmt)
        return list(result.scalars().all())


class LicenseRepository:
    """Repository for license operations."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def create(
        self,
        company_id: uuid.UUID,
        license_number: str,
        **kwargs,
    ) -> License:
        """Create a new license record."""
        license_record = License(
            company_id=company_id,
            license_number=license_number,
            **kwargs,
        )
        self.session.add(license_record)
        await self.session.flush()
        return license_record

    async def get_by_company(self, company_id: uuid.UUID) -> list[License]:
        """Get all licenses for a company."""
        stmt = (
            select(License)
            .where(License.company_id == company_id)
            .options(selectinload(License.disciplinary_actions))
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def add_disciplinary_action(
        self,
        license_id: uuid.UUID,
        **kwargs,
    ) -> DisciplinaryAction:
        """Add a disciplinary action to a license."""
        action = DisciplinaryAction(license_id=license_id, **kwargs)
        self.session.add(action)
        await self.session.flush()
        return action


class ReviewRepository:
    """Repository for review operations."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def create(self, company_id: uuid.UUID, source: str, **kwargs) -> Review:
        """Create a new review record."""
        review = Review(company_id=company_id, source=source, **kwargs)
        self.session.add(review)
        await self.session.flush()
        return review

    async def get_by_company(
        self, company_id: uuid.UUID, source: str | None = None
    ) -> list[Review]:
        """Get reviews for a company, optionally filtered by source."""
        stmt = select(Review).where(Review.company_id == company_id)
        if source:
            stmt = stmt.where(Review.source == source)
        result = await self.session.execute(stmt)
        return list(result.scalars().all())


class BBBProfileRepository:
    """Repository for BBB profile operations."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def create(self, company_id: uuid.UUID, **kwargs) -> BBBProfile:
        """Create a new BBB profile."""
        profile = BBBProfile(company_id=company_id, **kwargs)
        self.session.add(profile)
        await self.session.flush()
        return profile

    async def get_by_company(self, company_id: uuid.UUID) -> BBBProfile | None:
        """Get the most recent BBB profile for a company."""
        stmt = (
            select(BBBProfile)
            .where(BBBProfile.company_id == company_id)
            .order_by(BBBProfile.scraped_at.desc())
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()


class CourtCaseRepository:
    """Repository for court case operations."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def create(self, company_id: uuid.UUID, **kwargs) -> CourtCase:
        """Create a new court case record."""
        case = CourtCase(company_id=company_id, **kwargs)
        self.session.add(case)
        await self.session.flush()
        return case

    async def get_by_company(self, company_id: uuid.UUID) -> list[CourtCase]:
        """Get all court cases for a company."""
        stmt = select(CourtCase).where(CourtCase.company_id == company_id)
        result = await self.session.execute(stmt)
        return list(result.scalars().all())


class LienRepository:
    """Repository for lien operations."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def create(self, company_id: uuid.UUID, **kwargs) -> Lien:
        """Create a new lien record."""
        lien = Lien(company_id=company_id, **kwargs)
        self.session.add(lien)
        await self.session.flush()
        return lien

    async def get_by_company(self, company_id: uuid.UUID) -> list[Lien]:
        """Get all liens for a company."""
        stmt = select(Lien).where(Lien.company_id == company_id)
        result = await self.session.execute(stmt)
        return list(result.scalars().all())


class RiskScoreRepository:
    """Repository for risk score operations."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def create(self, company_id: uuid.UUID, **kwargs) -> RiskScore:
        """Create a new risk score."""
        score = RiskScore(company_id=company_id, **kwargs)
        self.session.add(score)
        await self.session.flush()
        return score

    async def get_latest(self, company_id: uuid.UUID) -> RiskScore | None:
        """Get the most recent risk score for a company."""
        stmt = (
            select(RiskScore)
            .where(RiskScore.company_id == company_id)
            .order_by(RiskScore.calculated_at.desc())
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()


class ScrapeJobRepository:
    """Repository for scrape job operations."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def create(
        self,
        company_id: uuid.UUID,
        source: str,
        status: str = "pending",
    ) -> ScrapeJob:
        """Create a new scrape job."""
        job = ScrapeJob(company_id=company_id, source=source, status=status)
        self.session.add(job)
        await self.session.flush()
        return job

    async def update_status(
        self,
        job_id: uuid.UUID,
        status: str,
        error_message: str | None = None,
    ) -> None:
        """Update job status."""
        stmt = select(ScrapeJob).where(ScrapeJob.id == job_id)
        result = await self.session.execute(stmt)
        job = result.scalar_one_or_none()
        if job:
            job.status = status
            if error_message:
                job.error_message = error_message
            await self.session.flush()
