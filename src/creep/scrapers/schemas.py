"""Pydantic schemas for scraped data validation."""

from datetime import date
from decimal import Decimal

from pydantic import BaseModel, Field


class DBPRLicenseResult(BaseModel):
    """License data from Florida DBPR search results."""

    license_number: str = Field(..., description="License number")
    licensee_name: str = Field(..., description="Name of licensee")
    license_type: str | None = Field(None, description="Type of license")
    status: str = Field(..., description="License status (Active, Inactive, etc.)")
    rank: str | None = Field(None, description="License rank/classification")
    expiration_date: str | None = Field(None, description="Expiration date as string")
    primary_status: str | None = Field(None, description="Primary status")
    secondary_status: str | None = Field(None, description="Secondary status")
    county: str | None = Field(None, description="County")
    raw_html: str | None = Field(None, description="Raw HTML of the result row", exclude=True)


class DBPRLicenseDetail(BaseModel):
    """Detailed license information from DBPR detail page."""

    license_number: str
    licensee_name: str
    dba_name: str | None = None
    license_type: str | None = None
    rank: str | None = None
    status: str
    issue_date: date | None = None
    expiration_date: date | None = None
    address: str | None = None
    city: str | None = None
    state: str | None = None
    zip_code: str | None = None
    county: str | None = None
    primary_status: str | None = None
    secondary_status: str | None = None
    qualifier: str | None = None
    alternate_number: str | None = None
    raw_data: dict | None = None


class DBPRDisciplinaryAction(BaseModel):
    """Disciplinary action from DBPR."""

    case_number: str | None = None
    action_type: str | None = None
    action_date: date | None = None
    effective_date: date | None = None
    description: str | None = None
    fine_amount: Decimal | None = None
    status: str | None = None
    raw_data: dict | None = None


class BBBProfileResult(BaseModel):
    """BBB profile data."""

    business_name: str
    bbb_rating: str | None = None
    accredited: bool = False
    years_in_business: int | None = None
    business_started: str | None = None
    complaint_count: int | None = None
    complaints_closed_last_3_years: int | None = None
    complaints_closed_last_12_months: int | None = None
    customer_reviews_count: int | None = None
    average_customer_rating: Decimal | None = None
    profile_url: str | None = None
    address: str | None = None
    phone: str | None = None
    raw_data: dict | None = None


class CourtListenerCase(BaseModel):
    """Court case from CourtListener API."""

    case_name: str
    case_number: str | None = None
    court: str | None = None
    court_id: str | None = None
    filing_date: date | None = None
    date_terminated: date | None = None
    nature_of_suit: str | None = None
    cause: str | None = None
    jury_demand: str | None = None
    jurisdiction_type: str | None = None
    docket_url: str | None = None
    parties: list[str] = Field(default_factory=list)
    raw_data: dict | None = None


class UCCFilingResult(BaseModel):
    """UCC filing from Florida UCC search."""

    filing_number: str
    filing_type: str | None = None
    filing_date: date | None = None
    lapse_date: date | None = None
    status: str | None = None
    debtor_name: str | None = None
    debtor_address: str | None = None
    secured_party_name: str | None = None
    secured_party_address: str | None = None
    collateral: str | None = None
    raw_data: dict | None = None
