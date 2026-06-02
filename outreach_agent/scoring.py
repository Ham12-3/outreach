"""Lead scoring rubric — deliberately simple and fully explainable.

The goal is a transparent 0–100 score that a human (or a hackathon judge) can
read and immediately understand. Every point awarded comes with a reason string,
so the agent can show its work.

Rubric (max 100):
  • Title fit       up to 40  — is this a product/decision-maker role?
  • Seniority       up to 25  — how senior is the title?
  • Industry fit    up to 20  — is the company in our target space (AI/ML)?
  • Region fit      up to 15  — are they in our target region (US)?

Segments:
  • Hot   >= 70
  • Warm  45–69
  • Cold  < 45
"""

from __future__ import annotations

from typing import Any

# Keywords that indicate the person owns product decisions (our ideal buyer).
TITLE_FIT_KEYWORDS = ("product", "growth")

# Seniority tiers, checked in order (most senior first). Each maps to points.
SENIORITY_TIERS: list[tuple[tuple[str, ...], int, str]] = [
    (("chief", "cpo", "founder", "ceo", "vp", "vice president"), 25, "executive / founder"),
    (("head", "director", "principal"), 20, "senior leadership"),
    (("lead", "group", "senior", "staff"), 14, "senior individual contributor"),
    (("manager",), 10, "manager-level"),
    (("associate", "junior", "apm"), 5, "junior"),
]

# Industries we consider a strong fit, with the points they earn.
INDUSTRY_FIT_KEYWORDS = (
    "ai",
    "artificial intelligence",
    "machine learning",
    "ml",
    "generative",
    "agents",
    "robotics",
)

# Regions we're targeting for this campaign.
TARGET_REGIONS = ("united states", "usa", "us")


def _title_fit_points(title: str) -> tuple[int, str | None]:
    """Up to 40 points if the title is a product/decision-making role."""
    lowered = title.lower()
    if any(kw in lowered for kw in TITLE_FIT_KEYWORDS):
        return 40, f"title '{title}' matches target role (product/growth)"
    return 0, None


def _seniority_points(title: str) -> tuple[int, str | None]:
    """Up to 25 points based on how senior the title is."""
    lowered = title.lower()
    for keywords, points, label in SENIORITY_TIERS:
        if any(kw in lowered for kw in keywords):
            return points, f"seniority: {label} (+{points})"
    return 0, None


def _industry_fit_points(industry: str) -> tuple[int, str | None]:
    """Up to 20 points if the company is in our target (AI/ML) space."""
    lowered = industry.lower()
    if any(kw in lowered for kw in INDUSTRY_FIT_KEYWORDS):
        return 20, f"industry '{industry}' is a target (AI/ML) space"
    return 0, None


def _region_fit_points(region: str) -> tuple[int, str | None]:
    """Up to 15 points if the lead is in our target region (US)."""
    lowered = region.lower()
    if any(r in lowered for r in TARGET_REGIONS):
        return 15, f"region '{region}' is in target market (US)"
    return 0, f"region '{region}' is outside target market (US)"


def segment_for_score(score: int) -> str:
    """Map a numeric score to a Hot / Warm / Cold segment."""
    if score >= 70:
        return "Hot"
    if score >= 45:
        return "Warm"
    return "Cold"


def score_lead(lead: dict[str, Any]) -> dict[str, Any]:
    """Score a single lead and return the score, segment, and reasons.

    Args:
        lead: a dict with at least 'title', 'industry', and 'region' keys.

    Returns:
        A dict: {"score": int, "segment": str, "reasons": list[str]}.
    """
    title = str(lead.get("title", ""))
    industry = str(lead.get("industry", ""))
    region = str(lead.get("region", ""))

    reasons: list[str] = []
    total = 0
    for points, reason in (
        _title_fit_points(title),
        _seniority_points(title),
        _industry_fit_points(industry),
        _region_fit_points(region),
    ):
        total += points
        if reason:
            reasons.append(reason)

    total = max(0, min(100, total))
    return {
        "score": total,
        "segment": segment_for_score(total),
        "reasons": reasons,
    }
