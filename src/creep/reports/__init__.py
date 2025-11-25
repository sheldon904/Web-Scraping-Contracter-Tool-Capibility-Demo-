"""Report generation module for CREEP.

Provides HTML and PDF report generation for contractor risk assessments.
"""

from creep.reports.charts import (
    ChartSegment,
    generate_donut_chart,
    generate_horizontal_bar_chart,
    generate_score_gauge,
    get_risk_color,
    get_risk_level,
)
from creep.reports.generator import ReportGenerator

__all__ = [
    "ChartSegment",
    "ReportGenerator",
    "generate_donut_chart",
    "generate_horizontal_bar_chart",
    "generate_score_gauge",
    "get_risk_color",
    "get_risk_level",
]
