"""SVG chart generation for risk reports.

Generates WeasyPrint-compatible SVG charts for PDF reports.
No JavaScript dependencies - pure SVG.
"""

import math
from dataclasses import dataclass


@dataclass
class ChartSegment:
    """A segment in a donut/pie chart."""

    label: str
    value: float
    color: str
    percentage: float = 0.0


def generate_donut_chart(
    segments: list[ChartSegment],
    center_text: str = "",
    center_subtext: str = "",
    width: int = 300,
    height: int = 300,
    inner_radius: float = 0.6,
) -> str:
    """Generate an SVG donut chart.

    Args:
        segments: List of ChartSegment objects with label, value, color
        center_text: Main text in center (e.g., score)
        center_subtext: Secondary text below center (e.g., "Overall Score")
        width: SVG width in pixels
        height: SVG height in pixels
        inner_radius: Inner radius as fraction of outer (0.6 = 60%)

    Returns:
        SVG string
    """
    cx = width / 2
    cy = height / 2
    outer_r = min(width, height) / 2 - 20  # Leave margin
    inner_r = outer_r * inner_radius

    # Calculate percentages
    total = sum(s.value for s in segments if s.value > 0)
    if total == 0:
        total = 1  # Prevent division by zero

    for seg in segments:
        seg.percentage = (seg.value / total) * 100 if seg.value > 0 else 0

    # Build SVG paths
    paths = []
    current_angle = -90  # Start at top

    for seg in segments:
        if seg.percentage <= 0:
            continue

        # Calculate arc
        angle_span = (seg.percentage / 100) * 360
        end_angle = current_angle + angle_span

        # Convert to radians
        start_rad = math.radians(current_angle)
        end_rad = math.radians(end_angle)

        # Calculate points
        x1_outer = cx + outer_r * math.cos(start_rad)
        y1_outer = cy + outer_r * math.sin(start_rad)
        x2_outer = cx + outer_r * math.cos(end_rad)
        y2_outer = cy + outer_r * math.sin(end_rad)

        x1_inner = cx + inner_r * math.cos(end_rad)
        y1_inner = cy + inner_r * math.sin(end_rad)
        x2_inner = cx + inner_r * math.cos(start_rad)
        y2_inner = cy + inner_r * math.sin(start_rad)

        # Large arc flag
        large_arc = 1 if angle_span > 180 else 0

        # Build path
        path = f"""
        <path d="M {x1_outer:.2f} {y1_outer:.2f}
                 A {outer_r:.2f} {outer_r:.2f} 0 {large_arc} 1 {x2_outer:.2f} {y2_outer:.2f}
                 L {x1_inner:.2f} {y1_inner:.2f}
                 A {inner_r:.2f} {inner_r:.2f} 0 {large_arc} 0 {x2_inner:.2f} {y2_inner:.2f}
                 Z"
              fill="{seg.color}"
              stroke="white"
              stroke-width="2"/>
        """
        paths.append(path)

        current_angle = end_angle

    # Build legend
    legend_y = height + 20
    legend_items = []
    legend_x = 10

    for i, seg in enumerate(segments):
        if seg.value <= 0:
            continue
        item = f"""
        <rect x="{legend_x}" y="{legend_y + i * 25}" width="16" height="16" fill="{seg.color}" rx="2"/>
        <text x="{legend_x + 22}" y="{legend_y + i * 25 + 13}" font-size="12" font-family="Arial, sans-serif" fill="#374151">
            {seg.label}: {seg.value:.0f} ({seg.percentage:.0f}%)
        </text>
        """
        legend_items.append(item)

    # Calculate total height including legend
    total_height = height + 20 + len([s for s in segments if s.value > 0]) * 25 + 10

    # Build complete SVG
    svg = f"""
    <svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{total_height}" viewBox="0 0 {width} {total_height}">
        <!-- Donut segments -->
        {''.join(paths)}

        <!-- Center text -->
        <text x="{cx}" y="{cy - 5}" text-anchor="middle" font-size="36" font-weight="bold" font-family="Arial, sans-serif" fill="#1f2937">
            {center_text}
        </text>
        <text x="{cx}" y="{cy + 20}" text-anchor="middle" font-size="12" font-family="Arial, sans-serif" fill="#6b7280">
            {center_subtext}
        </text>

        <!-- Legend -->
        {''.join(legend_items)}
    </svg>
    """

    return svg.strip()


def generate_horizontal_bar_chart(
    items: list[tuple[str, float, str]],
    max_value: float = 100,
    width: int = 400,
    bar_height: int = 30,
    spacing: int = 10,
) -> str:
    """Generate a horizontal bar chart.

    Args:
        items: List of (label, value, color) tuples
        max_value: Maximum value for scaling
        width: SVG width
        bar_height: Height of each bar
        spacing: Space between bars

    Returns:
        SVG string
    """
    label_width = 100
    bar_width = width - label_width - 60  # Leave room for value text
    height = len(items) * (bar_height + spacing) + spacing

    bars = []
    for i, (label, value, color) in enumerate(items):
        y = spacing + i * (bar_height + spacing)
        bar_length = (value / max_value) * bar_width if max_value > 0 else 0

        bar = f"""
        <text x="{label_width - 10}" y="{y + bar_height / 2 + 5}" text-anchor="end" font-size="12" font-family="Arial, sans-serif" fill="#374151">
            {label}
        </text>
        <rect x="{label_width}" y="{y}" width="{bar_length:.1f}" height="{bar_height}" fill="{color}" rx="4"/>
        <text x="{label_width + bar_length + 8}" y="{y + bar_height / 2 + 5}" font-size="12" font-family="Arial, sans-serif" fill="#374151">
            {value:.0f}
        </text>
        """
        bars.append(bar)

    svg = f"""
    <svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">
        {''.join(bars)}
    </svg>
    """

    return svg.strip()


def generate_score_gauge(
    score: float,
    max_score: float = 100,
    width: int = 200,
    height: int = 120,
) -> str:
    """Generate a semi-circular gauge for score display.

    Args:
        score: Current score value
        max_score: Maximum possible score
        width: SVG width
        height: SVG height

    Returns:
        SVG string
    """
    cx = width / 2
    cy = height - 10
    radius = min(width / 2, height) - 20

    # Calculate angle (0 = left, 180 = right)
    percentage = min(score / max_score, 1.0)
    angle = percentage * 180

    # Color based on score
    if score >= 80:
        color = "#22c55e"  # green
    elif score >= 60:
        color = "#84cc16"  # lime
    elif score >= 40:
        color = "#eab308"  # yellow
    elif score >= 20:
        color = "#f97316"  # orange
    else:
        color = "#ef4444"  # red

    # Background arc (gray)
    bg_path = _arc_path(cx, cy, radius, 0, 180)

    # Score arc
    score_path = _arc_path(cx, cy, radius, 0, angle) if angle > 0 else ""

    svg = f"""
    <svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">
        <!-- Background arc -->
        <path d="{bg_path}" fill="none" stroke="#e5e7eb" stroke-width="12" stroke-linecap="round"/>

        <!-- Score arc -->
        <path d="{score_path}" fill="none" stroke="{color}" stroke-width="12" stroke-linecap="round"/>

        <!-- Score text -->
        <text x="{cx}" y="{cy - 15}" text-anchor="middle" font-size="28" font-weight="bold" font-family="Arial, sans-serif" fill="{color}">
            {score:.0f}
        </text>
        <text x="{cx}" y="{cy + 5}" text-anchor="middle" font-size="10" font-family="Arial, sans-serif" fill="#6b7280">
            out of {max_score:.0f}
        </text>
    </svg>
    """

    return svg.strip()


def _arc_path(cx: float, cy: float, r: float, start_angle: float, end_angle: float) -> str:
    """Generate SVG arc path for semi-circle gauge."""
    # Convert to radians (0 degrees = left, 180 = right for semi-circle)
    start_rad = math.radians(180 - start_angle)
    end_rad = math.radians(180 - end_angle)

    x1 = cx + r * math.cos(start_rad)
    y1 = cy - r * math.sin(start_rad)
    x2 = cx + r * math.cos(end_rad)
    y2 = cy - r * math.sin(end_rad)

    large_arc = 1 if (end_angle - start_angle) > 180 else 0

    return f"M {x1:.2f} {y1:.2f} A {r:.2f} {r:.2f} 0 {large_arc} 1 {x2:.2f} {y2:.2f}"


def get_risk_color(score: float) -> str:
    """Get color hex code based on risk score.

    Args:
        score: Risk score 0-100 (higher = better)

    Returns:
        Hex color code
    """
    if score >= 80:
        return "#22c55e"  # green - Low Risk
    elif score >= 60:
        return "#84cc16"  # lime - Moderate-Low Risk
    elif score >= 40:
        return "#eab308"  # yellow - Moderate Risk
    elif score >= 20:
        return "#f97316"  # orange - Elevated Risk
    else:
        return "#ef4444"  # red - High Risk


def get_risk_level(score: float) -> str:
    """Get risk level text based on score.

    Args:
        score: Risk score 0-100 (higher = better)

    Returns:
        Risk level string
    """
    if score >= 80:
        return "Low Risk"
    elif score >= 60:
        return "Moderate-Low Risk"
    elif score >= 40:
        return "Moderate Risk"
    elif score >= 20:
        return "Elevated Risk"
    else:
        return "High Risk"
