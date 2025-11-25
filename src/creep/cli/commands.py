"""CLI commands for CREEP using Typer."""

import asyncio
from typing import Annotated

import typer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from rich.progress import Progress, SpinnerColumn, TextColumn

from creep.config import get_settings
from creep.db.engine import close_db, get_session, init_db
from creep.db.repository import CompanyRepository, LicenseRepository

app = typer.Typer(
    name="creep",
    help="Contractor Risk Evaluation and Exploration Platform",
    no_args_is_help=True,
)
console = Console()


@app.command()
def init():
    """Initialize the database (create tables)."""
    console.print("[bold blue]Initializing database...[/]")

    async def _init():
        await init_db()
        await close_db()

    asyncio.run(_init())
    console.print("[bold green]Database initialized successfully![/]")


@app.command()
def config():
    """Show current configuration."""
    settings = get_settings()
    table = Table(title="CREEP Configuration")
    table.add_column("Setting", style="cyan")
    table.add_column("Value", style="green")

    table.add_row("Database URL", settings.database_url[:50] + "...")
    table.add_row("Rate Limit", f"{settings.scraper_rate_limit}s")
    table.add_row("Max Retries", str(settings.scraper_max_retries))
    table.add_row("Timeout", f"{settings.scraper_timeout}s")
    table.add_row("Headless", str(settings.playwright_headless))
    table.add_row("Weight: License", f"{settings.weight_license:.0%}")
    table.add_row("Weight: Reputation", f"{settings.weight_reputation:.0%}")
    table.add_row("Weight: Litigation", f"{settings.weight_litigation:.0%}")
    table.add_row("Weight: Financial", f"{settings.weight_financial:.0%}")

    console.print(table)


@app.command()
def scan(
    company_name: Annotated[str, typer.Argument(help="Company name to scan")],
    state: Annotated[str, typer.Option(help="State to search")] = "FL",
    license_number: Annotated[str | None, typer.Option(help="Known license number")] = None,
    output: Annotated[str, typer.Option(help="Output file path")] = "report.pdf",
    format: Annotated[str, typer.Option(help="Output format: pdf, html, json")] = "pdf",
):
    """Run complete risk scan for a contractor."""
    console.print(
        Panel(
            f"[bold]Scanning contractor:[/] {company_name}\n"
            f"[bold]State:[/] {state}\n"
            f"[bold]Output:[/] {output}",
            title="CREEP Risk Scan",
            border_style="blue",
        )
    )

    # TODO: Implement full scan pipeline
    console.print("[yellow]Full scan not yet implemented. Use individual scan commands.[/]")


@app.command(name="scan-license")
def scan_license(
    company_name: Annotated[str, typer.Argument(help="Company name to scan")],
    license_number: Annotated[str | None, typer.Option("--license", "-l", help="License number")] = None,
    state: Annotated[str, typer.Option(help="State to search")] = "FL",
    save: Annotated[bool, typer.Option(help="Save results to database")] = True,
):
    """Scan license information from state licensing board."""
    from creep.scrapers.florida_dbpr import FloridaDBPRScraper

    async def _scan():
        # Get or create company
        async with get_session() as session:
            company_repo = CompanyRepository(session)
            company, created = await company_repo.get_or_create(company_name, state)
            company_id = company.id

            if created:
                console.print(f"[dim]Created new company record: {company.id}[/]")

        # Run the scraper
        async with FloridaDBPRScraper() as scraper:
            if license_number:
                console.print(f"[bold blue]Searching by license number:[/] {license_number}")
                results = await scraper.search(company_name, license_number=license_number)
            else:
                console.print(f"[bold blue]Searching by company name:[/] {company_name}")
                results = await scraper.search(company_name)

            if not results:
                console.print("[yellow]No licenses found.[/]")
                return []

            console.print(f"[green]Found {len(results)} license(s)[/]")

            # Get detailed info for each license
            detailed_results = []
            for result in results:
                console.print(f"[dim]Getting details for {result.license_number}...[/]")
                detail = await scraper.get_details(result.license_number)
                if detail:
                    detailed_results.append(detail)
                else:
                    detailed_results.append(result)

                # Check for disciplinary actions
                actions = await scraper.get_disciplinary_actions(result.license_number)
                if actions:
                    console.print(
                        f"[red]Found {len(actions)} disciplinary action(s) for {result.license_number}[/]"
                    )

            # Save to database if requested
            if save and detailed_results:
                from datetime import datetime

                async with get_session() as session:
                    license_repo = LicenseRepository(session)
                    for detail in detailed_results:
                        # Parse expiration date if it's a string
                        exp_date = None
                        if hasattr(detail, "expiration_date") and detail.expiration_date:
                            if isinstance(detail.expiration_date, str):
                                try:
                                    exp_date = datetime.strptime(detail.expiration_date, "%m/%d/%Y").date()
                                except ValueError:
                                    pass
                            else:
                                exp_date = detail.expiration_date

                        # Handle both DBPRLicenseDetail and DBPRLicenseResult
                        if hasattr(detail, "issue_date"):
                            await license_repo.create(
                                company_id=company_id,
                                license_number=detail.license_number,
                                license_type=detail.license_type,
                                status=detail.status,
                                issue_date=detail.issue_date,
                                expiration_date=exp_date,
                                licensee_name=detail.licensee_name,
                                address=detail.address if hasattr(detail, "address") else None,
                                source="FL_DBPR",
                                raw_data=detail.raw_data if hasattr(detail, "raw_data") else None,
                            )
                        else:
                            await license_repo.create(
                                company_id=company_id,
                                license_number=detail.license_number,
                                license_type=detail.license_type,
                                status=detail.status,
                                expiration_date=exp_date,
                                licensee_name=detail.licensee_name,
                                source="FL_DBPR",
                            )
                console.print("[green]Results saved to database.[/]")

            return detailed_results

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
    ) as progress:
        progress.add_task("Scanning Florida DBPR...", total=None)
        results = asyncio.run(_scan())

    # Display results
    if results:
        table = Table(title="License Search Results")
        table.add_column("License #", style="cyan")
        table.add_column("Name", style="white")
        table.add_column("Type", style="dim")
        table.add_column("Status", style="green")
        table.add_column("Expiration", style="yellow")

        for r in results:
            status_style = "green" if r.status and r.status.upper() == "ACTIVE" else "red"
            exp = ""
            if hasattr(r, "expiration_date") and r.expiration_date:
                exp = str(r.expiration_date)
            table.add_row(
                r.license_number,
                r.licensee_name[:40] if r.licensee_name else "N/A",
                r.license_type or "N/A",
                f"[{status_style}]{r.status}[/{status_style}]" if r.status else "Unknown",
                exp,
            )

        console.print(table)


@app.command(name="scan-reviews")
def scan_reviews(
    company_name: Annotated[str, typer.Argument(help="Company name to scan")],
    city: Annotated[str, typer.Option(help="City to search in")] = "miami",
    state: Annotated[str, typer.Option(help="State to search")] = "FL",
    save: Annotated[bool, typer.Option(help="Save results to database")] = True,
):
    """Scan BBB profile and reviews for a company."""
    from creep.scrapers.bbb import BBBScraper
    from creep.db.repository import BBBProfileRepository

    async def _scan():
        # Get or create company
        async with get_session() as session:
            company_repo = CompanyRepository(session)
            company, created = await company_repo.get_or_create(company_name, state)
            company_id = company.id

            if created:
                console.print(f"[dim]Created new company record: {company.id}[/]")

        # Run the BBB scraper
        async with BBBScraper() as scraper:
            console.print(f"[bold blue]Searching BBB for:[/] {company_name} in {city}, {state}")
            results = await scraper.search_and_get_details(company_name, city, state)

            if not results:
                console.print("[yellow]No BBB profiles found.[/]")
                return []

            console.print(f"[green]Found {len(results)} BBB profile(s)[/]")

            # Save to database if requested
            if save and results:
                async with get_session() as session:
                    bbb_repo = BBBProfileRepository(session)
                    for profile in results:
                        await bbb_repo.create(
                            company_id=company_id,
                            bbb_rating=profile.bbb_rating,
                            accredited=profile.accredited,
                            years_in_business=profile.years_in_business,
                            complaint_count=profile.complaint_count,
                            complaint_resolved_count=profile.complaints_closed_last_3_years,
                            profile_url=profile.profile_url,
                            raw_data=profile.raw_data,
                        )
                console.print("[green]Results saved to database.[/]")

            return results

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
    ) as progress:
        progress.add_task("Scanning BBB...", total=None)
        results = asyncio.run(_scan())

    # Display results
    if results:
        table = Table(title="BBB Profile Results")
        table.add_column("Business Name", style="cyan", max_width=30)
        table.add_column("Rating", style="green", justify="center")
        table.add_column("Accredited", justify="center")
        table.add_column("Years", justify="center")
        table.add_column("Complaints", style="yellow", justify="center")
        table.add_column("Reviews", justify="center")
        table.add_column("Avg Rating", justify="center")

        for r in results:
            accredited_style = "green" if r.accredited else "dim"
            accredited_text = "[green]Yes[/]" if r.accredited else "[dim]No[/]"

            rating_style = "green"
            if r.bbb_rating in ["F", "D+", "D", "D-"]:
                rating_style = "red"
            elif r.bbb_rating in ["C+", "C", "C-"]:
                rating_style = "yellow"

            complaints = str(r.complaint_count) if r.complaint_count is not None else "N/A"
            reviews = str(r.customer_reviews_count) if r.customer_reviews_count is not None else "N/A"
            avg_rating = f"{r.average_customer_rating:.1f}" if r.average_customer_rating else "N/A"
            years = str(r.years_in_business) if r.years_in_business else "N/A"

            table.add_row(
                r.business_name[:30] if r.business_name else "N/A",
                f"[{rating_style}]{r.bbb_rating or 'N/A'}[/{rating_style}]",
                accredited_text,
                years,
                complaints,
                reviews,
                avg_rating,
            )

        console.print(table)

        # Show profile URLs
        console.print("\n[dim]Profile URLs:[/]")
        for r in results:
            if r.profile_url:
                console.print(f"  [link={r.profile_url}]{r.business_name}[/link]")


@app.command(name="scan-courts")
def scan_courts(
    company_name: Annotated[str, typer.Argument(help="Company name to scan")],
    state: Annotated[str, typer.Option(help="State to search")] = "FL",
    save: Annotated[bool, typer.Option(help="Save results to database")] = True,
    limit: Annotated[int, typer.Option(help="Maximum results to return")] = 20,
):
    """Scan federal court records from CourtListener."""
    from creep.scrapers.courtlistener import CourtListenerScraper
    from creep.db.repository import CourtCaseRepository

    async def _scan():
        # Get or create company
        async with get_session() as session:
            company_repo = CompanyRepository(session)
            company, created = await company_repo.get_or_create(company_name, state)
            company_id = company.id

            if created:
                console.print(f"[dim]Created new company record: {company.id}[/]")

        # Check for API token
        settings = get_settings()
        if not settings.courtlistener_api_token:
            console.print("[yellow]Note: No CourtListener API token configured.[/]")
            console.print("[dim]Set COURTLISTENER_API_TOKEN in .env for better results.[/]")
            console.print("[dim]Get a free token at: https://www.courtlistener.com/sign-in/[/]\n")

        # Run the CourtListener scraper
        async with CourtListenerScraper() as scraper:
            console.print(f"[bold blue]Searching CourtListener for:[/] {company_name}")
            results = await scraper.search(company_name)

            if not results:
                console.print("[yellow]No court cases found.[/]")
                return []

            # Limit results
            results = results[:limit]
            console.print(f"[green]Found {len(results)} court case(s)[/]")

            # Save to database if requested
            if save and results:
                async with get_session() as session:
                    court_repo = CourtCaseRepository(session)
                    for case in results:
                        await court_repo.create(
                            company_id=company_id,
                            source="CourtListener",
                            case_number=case.case_number,
                            case_type=case.nature_of_suit or case.cause,
                            court_name=case.court,
                            filing_date=case.filing_date,
                            status="Terminated" if case.date_terminated else "Active",
                            case_summary=case.case_name,
                            external_url=case.docket_url,
                            raw_data=case.raw_data,
                        )
                console.print("[green]Results saved to database.[/]")

            return results

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
    ) as progress:
        progress.add_task("Scanning CourtListener...", total=None)
        results = asyncio.run(_scan())

    # Display results
    if results:
        table = Table(title="Court Case Results")
        table.add_column("Case Name", style="cyan", max_width=35)
        table.add_column("Docket #", style="dim")
        table.add_column("Court", max_width=20)
        table.add_column("Filed", style="yellow")
        table.add_column("Status", justify="center")
        table.add_column("Type", max_width=20)

        for case in results:
            # Determine status
            if case.date_terminated:
                status = "[dim]Terminated[/]"
            else:
                status = "[green]Active[/]"

            # Format date
            filed = str(case.filing_date) if case.filing_date else "N/A"

            # Truncate long fields
            case_name = case.case_name[:35] if case.case_name else "N/A"
            court = (case.court[:20] if case.court else "N/A")
            case_type = (case.nature_of_suit[:20] if case.nature_of_suit else "N/A")

            table.add_row(
                case_name,
                case.case_number or "N/A",
                court,
                filed,
                status,
                case_type,
            )

        console.print(table)

        # Show docket URLs
        console.print("\n[dim]Docket URLs:[/]")
        for case in results[:5]:  # Show first 5 URLs
            if case.docket_url:
                short_name = case.case_name[:50] if case.case_name else "Case"
                console.print(f"  [link={case.docket_url}]{short_name}[/link]")


@app.command(name="scan-liens")
def scan_liens(
    company_name: Annotated[str, typer.Argument(help="Company name to scan")],
    state: Annotated[str, typer.Option(help="State to search")] = "FL",
    save: Annotated[bool, typer.Option(help="Save results to database")] = True,
):
    """Scan UCC liens and filings from Florida Secured Transaction Registry."""
    from creep.scrapers.florida_ucc import FloridaUCCScraper
    from creep.db.repository import LienRepository

    async def _scan():
        # Get or create company
        async with get_session() as session:
            company_repo = CompanyRepository(session)
            company, created = await company_repo.get_or_create(company_name, state)
            company_id = company.id

            if created:
                console.print(f"[dim]Created new company record: {company.id}[/]")

        # Run the UCC scraper
        async with FloridaUCCScraper() as scraper:
            console.print(f"[bold blue]Searching Florida UCC filings for:[/] {company_name}")
            results = await scraper.search(company_name)

            if not results:
                console.print("[yellow]No UCC filings found.[/]")
                return []

            console.print(f"[green]Found {len(results)} UCC filing(s)[/]")

            # Save to database if requested
            if save and results:
                async with get_session() as session:
                    lien_repo = LienRepository(session)
                    for filing in results:
                        await lien_repo.create(
                            company_id=company_id,
                            lien_type=filing.filing_type or "UCC",
                            filing_number=filing.filing_number,
                            filing_date=filing.filing_date,
                            secured_party=filing.secured_party_name,
                            collateral_description=filing.collateral,
                            status=filing.status,
                            source="FL_FSTR",
                            raw_data=filing.raw_data,
                        )
                console.print("[green]Results saved to database.[/]")

            return results

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
    ) as progress:
        progress.add_task("Scanning Florida UCC filings...", total=None)
        results = asyncio.run(_scan())

    # Display results
    if results:
        table = Table(title="UCC Filing Results")
        table.add_column("Filing #", style="cyan")
        table.add_column("Type", style="dim")
        table.add_column("Debtor", max_width=25)
        table.add_column("Secured Party", max_width=25)
        table.add_column("Filed", style="yellow")
        table.add_column("Lapse", style="red")
        table.add_column("Status", justify="center")

        for f in results:
            # Determine status style
            status_style = "green" if f.status and f.status.lower() == "active" else "dim"

            filed = str(f.filing_date) if f.filing_date else "N/A"
            lapse = str(f.lapse_date) if f.lapse_date else "N/A"

            table.add_row(
                f.filing_number or "N/A",
                f.filing_type or "UCC",
                (f.debtor_name[:25] if f.debtor_name else "N/A"),
                (f.secured_party_name[:25] if f.secured_party_name else "N/A"),
                filed,
                lapse,
                f"[{status_style}]{f.status or 'Unknown'}[/{status_style}]",
            )

        console.print(table)

        # Show collateral info if available
        filings_with_collateral = [f for f in results if f.collateral]
        if filings_with_collateral:
            console.print("\n[dim]Collateral Descriptions:[/]")
            for f in filings_with_collateral[:3]:  # Show first 3
                console.print(f"  {f.filing_number}: {f.collateral[:100]}...")


@app.command(name="calculate-risk")
def calculate_risk(
    company_name: Annotated[str, typer.Argument(help="Company name")],
):
    """Calculate risk score from stored data."""
    console.print(f"[bold blue]Calculating risk for:[/] {company_name}")

    # TODO: Implement risk calculation
    console.print("[yellow]Risk calculation not yet implemented (Phase 6)[/]")


@app.command()
def report(
    company_name: Annotated[str, typer.Argument(help="Company name")],
    format: Annotated[str, typer.Option(help="Output format: pdf, html")] = "pdf",
    output: Annotated[str | None, typer.Option(help="Output file path")] = None,
):
    """Generate report from stored data."""
    console.print(f"[bold blue]Generating {format} report for:[/] {company_name}")

    # TODO: Implement report generation
    console.print("[yellow]Report generation not yet implemented (Phase 7)[/]")


@app.command(name="list-companies")
def list_companies(
    limit: Annotated[int, typer.Option(help="Maximum companies to show")] = 20,
):
    """List all companies in the database."""

    async def _list():
        async with get_session() as session:
            repo = CompanyRepository(session)
            companies = await repo.list_all(limit=limit)
            return companies

    companies = asyncio.run(_list())

    if not companies:
        console.print("[yellow]No companies found in database.[/]")
        return

    table = Table(title=f"Companies ({len(companies)} shown)")
    table.add_column("ID", style="dim")
    table.add_column("Name", style="cyan")
    table.add_column("State", style="green")
    table.add_column("Created", style="magenta")

    for company in companies:
        table.add_row(
            str(company.id)[:8] + "...",
            company.name,
            company.state,
            company.created_at.strftime("%Y-%m-%d %H:%M"),
        )

    console.print(table)


@app.command(name="add-company")
def add_company(
    name: Annotated[str, typer.Argument(help="Company name")],
    state: Annotated[str, typer.Option(help="State")] = "FL",
):
    """Add a company to the database."""

    async def _add():
        async with get_session() as session:
            repo = CompanyRepository(session)
            company, created = await repo.get_or_create(name, state)
            return company, created

    company, created = asyncio.run(_add())

    if created:
        console.print(f"[bold green]Created company:[/] {company.name} (ID: {company.id})")
    else:
        console.print(f"[yellow]Company already exists:[/] {company.name} (ID: {company.id})")


@app.command()
def version():
    """Show CREEP version."""
    console.print("[bold]CREEP[/] version [cyan]0.1.0[/]")
    console.print("Contractor Risk Evaluation and Exploration Platform")


def main():
    """Entry point for CLI."""
    app()


if __name__ == "__main__":
    main()
