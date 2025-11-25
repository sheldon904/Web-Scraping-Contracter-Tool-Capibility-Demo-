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
):
    """Scan reviews from BBB and other sources."""
    console.print(f"[bold blue]Scanning reviews for:[/] {company_name}")

    # TODO: Implement review scanning
    console.print("[yellow]Review scanning not yet implemented (Phase 3)[/]")


@app.command(name="scan-courts")
def scan_courts(
    company_name: Annotated[str, typer.Argument(help="Company name to scan")],
):
    """Scan court records from CourtListener."""
    console.print(f"[bold blue]Scanning court records for:[/] {company_name}")

    # TODO: Implement court record scanning
    console.print("[yellow]Court record scanning not yet implemented (Phase 4)[/]")


@app.command(name="scan-liens")
def scan_liens(
    company_name: Annotated[str, typer.Argument(help="Company name to scan")],
):
    """Scan UCC liens and filings."""
    console.print(f"[bold blue]Scanning liens for:[/] {company_name}")

    # TODO: Implement lien scanning
    console.print("[yellow]Lien scanning not yet implemented (Phase 5)[/]")


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
