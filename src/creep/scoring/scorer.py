"""Weighted risk scoring engine.

Calculates overall risk scores from category features using configurable
weights with dynamic redistribution for missing data.
"""

from dataclasses import dataclass, field
from typing import Any

from creep.config import get_settings
from creep.scoring.features import CategoryFeatures, RiskFactor


@dataclass
class RiskScoreResult:
    """Complete risk assessment result."""

    overall_score: float  # 0-100, higher = better
    category_scores: dict[str, float | None]  # Each category's raw score
    confidence: float  # 0.0-1.0 based on data completeness
    top_factors: list[RiskFactor]  # Top contributing factors
    data_completeness: dict[str, bool]  # Which categories had data
    breakdown: dict[str, Any]  # Full calculation details for storage

    @property
    def risk_level(self) -> str:
        """Human-readable risk level based on score."""
        if self.overall_score >= 80:
            return "Low Risk"
        elif self.overall_score >= 60:
            return "Moderate-Low Risk"
        elif self.overall_score >= 40:
            return "Moderate Risk"
        elif self.overall_score >= 20:
            return "Elevated Risk"
        else:
            return "High Risk"

    @property
    def risk_color(self) -> str:
        """Color hex code for risk visualization."""
        if self.overall_score >= 80:
            return "#22c55e"  # green
        elif self.overall_score >= 60:
            return "#84cc16"  # lime
        elif self.overall_score >= 40:
            return "#eab308"  # yellow
        elif self.overall_score >= 20:
            return "#f97316"  # orange
        else:
            return "#ef4444"  # red


class WeightedRiskScorer:
    """Calculate weighted risk score with dynamic weight redistribution.

    When a category has no data available, its weight is redistributed
    proportionally to the remaining categories. The confidence level
    reflects what percentage of the original weights were actually used.

    Score direction: Higher = Better (70-100 = Trustworthy, 0-30 = High Risk)
    """

    # Default weights from plan (total = 1.0)
    DEFAULT_WEIGHTS = {
        "license": 0.35,
        "reputation": 0.25,
        "litigation": 0.25,
        "financial": 0.15,
    }

    def __init__(self, weights: dict[str, float] | None = None):
        """Initialize scorer with weights.

        Args:
            weights: Optional custom weights. If not provided, uses settings
                    or defaults.
        """
        if weights:
            self.weights = weights
        else:
            # Try to get from settings
            settings = get_settings()
            self.weights = {
                "license": settings.weight_license,
                "reputation": settings.weight_reputation,
                "litigation": settings.weight_litigation,
                "financial": settings.weight_financial,
            }

    def calculate(self, features: dict[str, CategoryFeatures]) -> RiskScoreResult:
        """Calculate weighted risk score from category features.

        Args:
            features: Dict with keys 'license', 'reputation', 'litigation', 'financial'
                     Each value is a CategoryFeatures object.

        Returns:
            RiskScoreResult with overall score, category scores, and confidence.
        """
        # Determine which categories have data
        data_completeness = {
            category: features[category].available
            for category in self.weights.keys()
        }

        # Calculate effective weights (redistribute from unavailable categories)
        available_weight_sum = sum(
            self.weights[cat] for cat, available in data_completeness.items() if available
        )

        if available_weight_sum == 0:
            # No data at all - return minimal confidence result
            return RiskScoreResult(
                overall_score=50.0,  # Neutral when no data
                category_scores={cat: None for cat in self.weights.keys()},
                confidence=0.0,
                top_factors=[],
                data_completeness=data_completeness,
                breakdown={
                    "method": "no_data",
                    "message": "No data available for any category",
                },
            )

        # Calculate effective weights for available categories
        effective_weights = {}
        for category, weight in self.weights.items():
            if data_completeness[category]:
                # Redistribute: new_weight = original_weight / sum_of_available_weights
                effective_weights[category] = weight / available_weight_sum
            else:
                effective_weights[category] = 0.0

        # Calculate weighted score
        weighted_sum = 0.0
        category_scores: dict[str, float | None] = {}

        for category, feat in features.items():
            if feat.available:
                category_scores[category] = feat.raw_score
                weighted_sum += feat.raw_score * effective_weights[category]
            else:
                category_scores[category] = None

        # Confidence is based on how much of original weight we used
        confidence = available_weight_sum

        # Collect and sort risk factors by absolute impact
        all_factors: list[RiskFactor] = []
        for feat in features.values():
            if feat.available:
                all_factors.extend(feat.factors)

        # Sort by absolute impact (most significant first)
        top_factors = sorted(all_factors, key=lambda f: abs(f.impact), reverse=True)[:10]

        # Build detailed breakdown for storage
        breakdown = {
            "method": "weighted_average",
            "version": "1.0",
            "original_weights": self.weights,
            "effective_weights": effective_weights,
            "category_details": {},
        }

        for category, feat in features.items():
            breakdown["category_details"][category] = {
                "available": feat.available,
                "raw_score": feat.raw_score if feat.available else None,
                "effective_weight": effective_weights[category],
                "contribution": (
                    feat.raw_score * effective_weights[category]
                    if feat.available else 0
                ),
                "factors": [
                    {
                        "name": f.name,
                        "impact": f.impact,
                        "source": f.source,
                        "details": f.details,
                    }
                    for f in feat.factors
                ] if feat.available else [],
                "data_sources": feat.data_sources if feat.available else [],
            }

        return RiskScoreResult(
            overall_score=round(weighted_sum, 1),
            category_scores=category_scores,
            confidence=round(confidence, 2),
            top_factors=top_factors,
            data_completeness=data_completeness,
            breakdown=breakdown,
        )

    @classmethod
    def get_weight_redistribution_example(cls) -> str:
        """Get example of weight redistribution for documentation."""
        return """
Weight Redistribution Examples:

1. All data present:
   license=35%, reputation=25%, litigation=25%, financial=15%
   Confidence: 1.0

2. No BBB profile (reputation missing):
   license = 0.35 / 0.75 = 46.7%
   litigation = 0.25 / 0.75 = 33.3%
   financial = 0.15 / 0.75 = 20.0%
   Confidence: 0.75

3. Only license data:
   license = 0.35 / 0.35 = 100%
   Confidence: 0.35
"""
