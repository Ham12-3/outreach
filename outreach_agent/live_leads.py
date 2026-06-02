"""Live lead ingestion from Hacker News "Who is hiring?" threads.

This is a legitimate, ToS-friendly real-data source: it uses the official
Hacker News Algolia API (https://hn.algolia.com/api), which is public and
returns the monthly "Ask HN: Who is hiring?" thread. Each top-level comment is a
real company's job posting, and many include the public application email the
company posted themselves.

We turn each posting into a lead that matches our schema (name/title/company/
industry/region/email/...). The HTML parsing is kept in a small pure function
(`parse_hn_comment`) so it can be unit-tested offline without any network.

Why not scrape LinkedIn/Apollo's site directly? That violates their terms of
service and privacy law for cold outreach. HN postings are public and explicitly
meant for contact, which makes this a safe, demo-friendly real source.
"""

from __future__ import annotations

import html
import json
import re
import urllib.parse
import urllib.request
from typing import Any, Optional

ALGOLIA_BASE = "https://hn.algolia.com/api/v1"
_USER_AGENT = "outreach-operations-agent/1.0 (hackathon demo)"

# Role keywords we try to recognise in a posting, most specific first.
ROLE_KEYWORDS = [
    "Product Manager",
    "Product Lead",
    "Product Designer",
    "Data Scientist",
    "Machine Learning Engineer",
    "ML Engineer",
    "AI Engineer",
    "Software Engineer",
    "Backend Engineer",
    "Frontend Engineer",
    "Full Stack Engineer",
    "DevOps Engineer",
    "Engineering Manager",
    "Designer",
    "Researcher",
    "Developer Advocate",
    "Founding Engineer",
    "Marketing",
    "Sales",
    "Recruiter",
    "Engineer",
    "Developer",
]

# If any of these appear, we tag the company's industry as AI.
AI_KEYWORDS = (
    "ai",
    "a.i.",
    "ml",
    "machine learning",
    "artificial intelligence",
    "llm",
    "genai",
    "generative",
    "deep learning",
    "nlp",
    "agents",
)

EMAIL_RE = re.compile(r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}")


def _strip_html(raw: str) -> str:
    """Turn HN comment HTML into clean, single-spaced text."""
    text = re.sub(r"<[^>]+>", " ", raw)
    text = html.unescape(text)
    return re.sub(r"\s+", " ", text).strip()


def _detect_region(text: str) -> str:
    """Best-effort region from a posting's text."""
    t = f" {text.lower()} "
    if "remote" in t:
        return "Remote"
    if any(x in t for x in ("united states", "usa", " us ", " u.s.", " sf ", "new york", "san francisco")):
        return "United States"
    if any(x in t for x in ("united kingdom", "london", " uk ")):
        return "United Kingdom"
    if "canada" in t or "toronto" in t:
        return "Canada"
    if "europe" in t or " eu " in t or "berlin" in t or "amsterdam" in t:
        return "Europe"
    return "Unknown"


def _detect_role(text: str) -> str:
    """Pick the first recognised role keyword, else 'Unknown'."""
    for kw in ROLE_KEYWORDS:
        if re.search(r"\b" + re.escape(kw) + r"\b", text, re.IGNORECASE):
            return kw
    return "Unknown"


def parse_hn_comment(raw_text: str, author: str = "") -> Optional[dict[str, Any]]:
    """Parse a single HN hiring comment into a lead dict (or None if unusable).

    HN hiring posts almost always lead with a header like
    ``Company | Location | Role | REMOTE | ...``; we take the company from the
    first ``|``-separated field and recognise the role/region/email from the
    full text.
    """
    clean = _strip_html(raw_text)
    if not clean or len(clean) < 15:
        return None

    # Header = the first sentence-ish chunk; company is the first | field.
    header = re.split(r"[.\n]", clean, maxsplit=1)[0]
    company = header.split("|")[0].strip()[:80]
    if not company:
        return None

    email_match = EMAIL_RE.search(clean)
    region = _detect_region(clean)
    industry = (
        "Artificial Intelligence"
        if any(k in clean.lower() for k in AI_KEYWORDS)
        else "Technology"
    )

    return {
        # The HN handle is the real person who posted the role.
        "name": author or "",
        "title": _detect_role(clean),
        "company": company,
        "industry": industry,
        "region": region,
        "location": region,
        "email": email_match.group(0) if email_match else "",
        "linkedin": "",
        "source": "hackernews",
        "status": "new",
    }


def _get_json(url: str, timeout: float = 15.0) -> dict[str, Any]:
    """Fetch and decode a JSON document from the HN API."""
    req = urllib.request.Request(url, headers={"User-Agent": _USER_AGENT})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))


def fetch_hn_hiring_leads(
    limit: int = 20, keyword: str = ""
) -> dict[str, Any]:
    """Fetch real leads from the latest HN 'Who is hiring?' thread.

    Args:
        limit: max number of leads to return.
        keyword: optional case-insensitive filter; only postings whose text
            contains this keyword are kept (e.g. "product", "AI").

    Returns:
        {"count": int, "leads": list, "source_thread": str} on success, or
        {"count": 0, "leads": [], "error": str} if the network call fails.
    """
    try:
        search_url = (
            f"{ALGOLIA_BASE}/search_by_date?tags=story,author_whoishiring"
            f"&query={urllib.parse.quote('Ask HN: Who is hiring?')}&hitsPerPage=3"
        )
        hits = _get_json(search_url).get("hits", [])
        if not hits:
            return {"count": 0, "leads": [], "error": "No hiring thread found."}

        story_id = str(hits[0]["objectID"])
        item = _get_json(f"{ALGOLIA_BASE}/items/{story_id}")
        children = item.get("children") or []

        leads: list[dict[str, Any]] = []
        for child in children:
            text = child.get("text") or ""
            if keyword and keyword.lower() not in text.lower():
                continue
            lead = parse_hn_comment(text, child.get("author", ""))
            if lead:
                leads.append(lead)
            if len(leads) >= limit:
                break

        return {"count": len(leads), "leads": leads, "source_thread": story_id}
    except Exception as exc:  # network/parse failures degrade gracefully
        return {
            "count": 0,
            "leads": [],
            "error": f"{type(exc).__name__}: {exc}",
        }
