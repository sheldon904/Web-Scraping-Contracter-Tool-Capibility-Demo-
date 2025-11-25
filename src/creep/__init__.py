"""CREEP - Contractor Risk Evaluation and Exploration Platform."""

__version__ = "0.1.0"


def main():
    """CLI entry point."""
    from creep.cli.commands import app
    app()
