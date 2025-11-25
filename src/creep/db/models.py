"""SQLAlchemy ORM models for CREEP database."""

import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Numeric,
    String,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    """Base class for all models."""

    type_annotation_map = {
        dict[str, Any]: JSONB,
    }


class Company(Base):
    """Contractor companies being researched."""

    __tablename__ = "companies"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    normalized_name: Mapped[str] = mapped_column(String(255), nullable=False)
    state: Mapped[str] = mapped_column(String(2), default="FL")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    # Relationships
    licenses: Mapped[list["License"]] = relationship(back_populates="company", cascade="all, delete-orphan")
    reviews: Mapped[list["Review"]] = relationship(back_populates="company", cascade="all, delete-orphan")
    bbb_profiles: Mapped[list["BBBProfile"]] = relationship(back_populates="company", cascade="all, delete-orphan")
    court_cases: Mapped[list["CourtCase"]] = relationship(back_populates="company", cascade="all, delete-orphan")
    liens: Mapped[list["Lien"]] = relationship(back_populates="company", cascade="all, delete-orphan")
    risk_scores: Mapped[list["RiskScore"]] = relationship(back_populates="company", cascade="all, delete-orphan")
    scrape_jobs: Mapped[list["ScrapeJob"]] = relationship(back_populates="company", cascade="all, delete-orphan")
    reports: Mapped[list["Report"]] = relationship(back_populates="company", cascade="all, delete-orphan")

    __table_args__ = (
        Index("idx_companies_normalized_name", "normalized_name"),
        {"schema": None},
    )


class License(Base):
    """License information from state licensing boards."""

    __tablename__ = "licenses"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    company_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("companies.id", ondelete="CASCADE"), nullable=False
    )
    license_number: Mapped[str] = mapped_column(String(50), nullable=False)
    license_type: Mapped[str | None] = mapped_column(String(100))
    status: Mapped[str | None] = mapped_column(String(50))
    issue_date: Mapped[date | None] = mapped_column(Date)
    expiration_date: Mapped[date | None] = mapped_column(Date)
    licensee_name: Mapped[str | None] = mapped_column(String(255))
    address: Mapped[str | None] = mapped_column(Text)
    source: Mapped[str] = mapped_column(String(50), default="FL_DBPR")
    raw_data: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    scraped_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    # Relationships
    company: Mapped["Company"] = relationship(back_populates="licenses")
    disciplinary_actions: Mapped[list["DisciplinaryAction"]] = relationship(
        back_populates="license", cascade="all, delete-orphan"
    )

    __table_args__ = (
        Index("idx_licenses_company", "company_id"),
        Index("idx_licenses_status", "status"),
        Index("idx_licenses_expiration", "expiration_date"),
        {"schema": None},
    )


class DisciplinaryAction(Base):
    """Disciplinary actions from licensing boards."""

    __tablename__ = "disciplinary_actions"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    license_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("licenses.id", ondelete="CASCADE"), nullable=False
    )
    action_type: Mapped[str | None] = mapped_column(String(100))
    action_date: Mapped[date | None] = mapped_column(Date)
    description: Mapped[str | None] = mapped_column(Text)
    fine_amount: Mapped[Decimal | None] = mapped_column(Numeric(10, 2))
    resolution: Mapped[str | None] = mapped_column(Text)
    case_number: Mapped[str | None] = mapped_column(String(100))
    raw_data: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    scraped_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    # Relationships
    license: Mapped["License"] = relationship(back_populates="disciplinary_actions")

    __table_args__ = (
        Index("idx_disciplinary_license", "license_id"),
        Index("idx_disciplinary_date", "action_date"),
        {"schema": None},
    )


class Review(Base):
    """Reviews from multiple sources (Google, Yelp, etc.)."""

    __tablename__ = "reviews"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    company_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("companies.id", ondelete="CASCADE"), nullable=False
    )
    source: Mapped[str] = mapped_column(String(50), nullable=False)
    rating: Mapped[Decimal | None] = mapped_column(Numeric(2, 1))
    review_count: Mapped[int | None] = mapped_column()
    review_text: Mapped[str | None] = mapped_column(Text)
    reviewer_name: Mapped[str | None] = mapped_column(String(255))
    review_date: Mapped[date | None] = mapped_column(Date)
    response_text: Mapped[str | None] = mapped_column(Text)
    external_id: Mapped[str | None] = mapped_column(String(255))
    raw_data: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    scraped_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    # Relationships
    company: Mapped["Company"] = relationship(back_populates="reviews")

    __table_args__ = (
        Index("idx_reviews_company", "company_id"),
        Index("idx_reviews_source", "source"),
        Index("idx_reviews_rating", "rating"),
        {"schema": None},
    )


class BBBProfile(Base):
    """BBB-specific profile data."""

    __tablename__ = "bbb_profiles"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    company_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("companies.id", ondelete="CASCADE"), nullable=False
    )
    bbb_rating: Mapped[str | None] = mapped_column(String(5))
    accredited: Mapped[bool] = mapped_column(Boolean, default=False)
    years_in_business: Mapped[int | None] = mapped_column()
    complaint_count: Mapped[int | None] = mapped_column()
    complaint_resolved_count: Mapped[int | None] = mapped_column()
    complaint_unresolved_count: Mapped[int | None] = mapped_column()
    government_actions_count: Mapped[int | None] = mapped_column()
    profile_url: Mapped[str | None] = mapped_column(Text)
    raw_data: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    scraped_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    # Relationships
    company: Mapped["Company"] = relationship(back_populates="bbb_profiles")

    __table_args__ = (
        Index("idx_bbb_company", "company_id"),
        {"schema": None},
    )


class CourtCase(Base):
    """Court cases from CourtListener and state courts."""

    __tablename__ = "court_cases"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    company_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("companies.id", ondelete="CASCADE"), nullable=False
    )
    source: Mapped[str | None] = mapped_column(String(50))
    case_number: Mapped[str | None] = mapped_column(String(100))
    case_type: Mapped[str | None] = mapped_column(String(100))
    court_name: Mapped[str | None] = mapped_column(String(255))
    filing_date: Mapped[date | None] = mapped_column(Date)
    status: Mapped[str | None] = mapped_column(String(100))
    plaintiff: Mapped[str | None] = mapped_column(String(500))
    defendant: Mapped[str | None] = mapped_column(String(500))
    case_summary: Mapped[str | None] = mapped_column(Text)
    judgment_amount: Mapped[Decimal | None] = mapped_column(Numeric(12, 2))
    external_url: Mapped[str | None] = mapped_column(Text)
    raw_data: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    scraped_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    # Relationships
    company: Mapped["Company"] = relationship(back_populates="court_cases")

    __table_args__ = (
        Index("idx_court_company", "company_id"),
        Index("idx_court_type", "case_type"),
        Index("idx_court_date", "filing_date"),
        {"schema": None},
    )


class Lien(Base):
    """UCC liens and filings."""

    __tablename__ = "liens"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    company_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("companies.id", ondelete="CASCADE"), nullable=False
    )
    lien_type: Mapped[str | None] = mapped_column(String(50))
    filing_number: Mapped[str | None] = mapped_column(String(100))
    filing_date: Mapped[date | None] = mapped_column(Date)
    secured_party: Mapped[str | None] = mapped_column(String(500))
    collateral_description: Mapped[str | None] = mapped_column(Text)
    amount: Mapped[Decimal | None] = mapped_column(Numeric(12, 2))
    status: Mapped[str | None] = mapped_column(String(50))
    source: Mapped[str | None] = mapped_column(String(50))
    raw_data: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    scraped_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    # Relationships
    company: Mapped["Company"] = relationship(back_populates="liens")

    __table_args__ = (
        Index("idx_liens_company", "company_id"),
        Index("idx_liens_status", "status"),
        {"schema": None},
    )


class RiskScore(Base):
    """Calculated risk scores with breakdown."""

    __tablename__ = "risk_scores"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    company_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("companies.id", ondelete="CASCADE"), nullable=False
    )
    overall_score: Mapped[int | None] = mapped_column()
    license_score: Mapped[int | None] = mapped_column()
    reputation_score: Mapped[int | None] = mapped_column()
    litigation_score: Mapped[int | None] = mapped_column()
    financial_score: Mapped[int | None] = mapped_column()
    confidence_level: Mapped[Decimal | None] = mapped_column(Numeric(3, 2))
    score_breakdown: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    data_completeness: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    calculated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    version: Mapped[str] = mapped_column(String(20), default="1.0")

    # Relationships
    company: Mapped["Company"] = relationship(back_populates="risk_scores")
    reports: Mapped[list["Report"]] = relationship(back_populates="risk_score")

    __table_args__ = (
        CheckConstraint("overall_score >= 0 AND overall_score <= 100", name="check_overall_score"),
        CheckConstraint("license_score >= 0 AND license_score <= 100", name="check_license_score"),
        CheckConstraint("reputation_score >= 0 AND reputation_score <= 100", name="check_reputation_score"),
        CheckConstraint("litigation_score >= 0 AND litigation_score <= 100", name="check_litigation_score"),
        CheckConstraint("financial_score >= 0 AND financial_score <= 100", name="check_financial_score"),
        Index("idx_risk_scores_company", "company_id"),
        Index("idx_risk_scores_overall", "overall_score"),
        Index("idx_risk_scores_date", "calculated_at"),
        {"schema": None},
    )


class ScrapeJob(Base):
    """Scrape job tracking for monitoring and retries."""

    __tablename__ = "scrape_jobs"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    company_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("companies.id", ondelete="CASCADE"), nullable=False
    )
    source: Mapped[str] = mapped_column(String(50), nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="pending")
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    error_message: Mapped[str | None] = mapped_column(Text)
    retry_count: Mapped[int] = mapped_column(default=0)
    job_metadata: Mapped[dict[str, Any] | None] = mapped_column(JSONB)

    # Relationships
    company: Mapped["Company"] = relationship(back_populates="scrape_jobs")

    __table_args__ = (
        Index("idx_scrape_jobs_company", "company_id"),
        Index("idx_scrape_jobs_status", "status"),
        {"schema": None},
    )


class Report(Base):
    """Generated report metadata."""

    __tablename__ = "reports"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    company_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("companies.id", ondelete="CASCADE"), nullable=False
    )
    risk_score_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("risk_scores.id")
    )
    format: Mapped[str] = mapped_column(String(10), nullable=False)
    file_path: Mapped[str | None] = mapped_column(Text)
    generated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    # Relationships
    company: Mapped["Company"] = relationship(back_populates="reports")
    risk_score: Mapped["RiskScore | None"] = relationship(back_populates="reports")

    __table_args__ = (
        Index("idx_reports_company", "company_id"),
        {"schema": None},
    )
