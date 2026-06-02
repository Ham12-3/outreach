"""Custom function tools the agent can call alongside the MongoDB MCP tools.

These cover the parts of the workflow that are *our* business logic — loading
leads offline, scoring with the rubric, and drafting messages — and keep that
logic in plain, testable Python rather than asking the model to improvise it.

ADK turns each plain function below into a tool automatically: the type hints
and docstring become the schema the model sees, so the docstrings are written
for the model as much as for humans.
"""

from __future__ import annotations

import json
from typing import Any

from .config import SEED_LEADS_PATH
from .drafting import draft_message as _draft_message
from .live_leads import fetch_hn_hiring_leads as _fetch_hn_hiring_leads
from .scoring import score_lead as _score_lead


def load_seed_leads() -> dict[str, Any]:
    """Load the bundled sample leads from disk so the demo runs fully offline.

    Use this when the user asks you to find, fetch, or import leads and no other
    source is given. Each returned lead starts with status 'new'.

    Returns:
        A dict with 'count' and 'leads' (a list of lead objects). Each lead has
        name, title, company, industry, region, location, email, linkedin,
        source, and status.
    """
    with open(SEED_LEADS_PATH, "r", encoding="utf-8") as f:
        leads = json.load(f)

    for lead in leads:
        lead.setdefault("status", "new")

    return {"count": len(leads), "leads": leads}


def fetch_live_leads(keyword: str = "", limit: int = 20) -> dict[str, Any]:
    """Fetch REAL, live leads from the latest Hacker News 'Who is hiring?' thread.

    Use this when the user asks for real / live / fresh leads instead of the
    offline sample. Each lead is a real company posting (often with the public
    application email the company posted). If the network call fails, the result
    has an 'error' field and an empty list — fall back to load_seed_leads then.

    Args:
        keyword: optional filter, e.g. "product" or "AI"; only postings whose
            text contains it are returned.
        limit: max number of leads to return (default 20).

    Returns:
        A dict with 'count', 'leads', and either 'source_thread' or 'error'.
    """
    return _fetch_hn_hiring_leads(limit=limit, keyword=keyword)


def score_lead(
    title: str,
    industry: str,
    region: str,
    name: str = "",
    company: str = "",
) -> dict[str, Any]:
    """Score one lead 0–100 and assign a Hot/Warm/Cold segment.

    Apply this to each lead before drafting so you can prioritise. The score is
    explainable: the 'reasons' list says exactly why each point was awarded.

    Args:
        title: the lead's job title (drives title-fit and seniority points).
        industry: the company's industry (drives industry-fit points).
        region: the lead's region/country (drives region-fit points).
        name: optional, echoed back for convenience.
        company: optional, echoed back for convenience.

    Returns:
        A dict with score (int), segment (str), and reasons (list of str).
    """
    result = _score_lead({"title": title, "industry": industry, "region": region})
    result["name"] = name
    result["company"] = company
    return result


def draft_message(
    name: str,
    title: str,
    company: str,
    segment: str = "Warm",
) -> dict[str, Any]:
    """Draft a short first-touch outreach message (opener + bridge + CTA).

    Use this after a lead is scored. The message is plain English and kept under
    60 words. The 'structure' field breaks out the three parts so you can show
    your work.

    Args:
        name: the lead's full name (the first name is used in the greeting).
        title: the lead's job title.
        company: the lead's company.
        segment: Hot, Warm, or Cold — lightly tunes the bridge sentence.

    Returns:
        A dict with message (str), word_count (int), and structure (dict).
    """
    return _draft_message(
        {"name": name, "title": title, "company": company, "segment": segment}
    )
