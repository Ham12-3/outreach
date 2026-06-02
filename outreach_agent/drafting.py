"""Outreach message drafting — short, plain English, opener + bridge + CTA.

The structure is intentionally fixed and explainable so every message reads
consistently and stays under the 60-word limit:

  • Opener — greet the person by first name and name something specific (their
    role + company) so it doesn't feel like a blast.
  • Bridge — one sentence connecting why we're reaching out to what they do.
  • CTA    — a single, low-friction ask.

We keep this deterministic (template-based) rather than free-form so the demo is
reliable and the output is easy to audit. The lead's segment lightly tunes the
bridge so Hot leads get a more direct value proposition.
"""

from __future__ import annotations

from typing import Any

WORD_LIMIT = 60


def _first_name(full_name: str) -> str:
    """Best-effort first name; falls back to 'there'."""
    parts = full_name.strip().split()
    return parts[0] if parts else "there"


def _bridge_for_segment(segment: str, company: str) -> str:
    """Pick a one-line bridge tuned to the lead's segment."""
    if segment == "Hot":
        return (
            f"Teams like {company} are shipping AI features fast, and we help "
            "them keep outreach personal at scale."
        )
    if segment == "Warm":
        return (
            f"I've been following what {company} is building and thought our "
            "approach to lead outreach might be useful."
        )
    return (
        "We help teams turn a list of prospects into personalised, ready-to-send "
        "messages in minutes."
    )


def _trim_to_word_limit(text: str, limit: int = WORD_LIMIT) -> str:
    """Guarantee the message stays within the word limit."""
    words = text.split()
    if len(words) <= limit:
        return text
    return " ".join(words[:limit]).rstrip(",.;:") + "."


def draft_message(lead: dict[str, Any]) -> dict[str, Any]:
    """Draft a first-touch outreach message for a lead.

    Args:
        lead: a dict with 'name', 'title', 'company', and optionally 'segment'.

    Returns:
        A dict: {"message": str, "word_count": int, "structure": {...}}.
    """
    first = _first_name(str(lead.get("name", "")))
    title = str(lead.get("title", "your role")).strip()
    company = str(lead.get("company", "your team")).strip()
    segment = str(lead.get("segment", "Warm"))

    opener = f"Hi {first}, I came across your work as {title} at {company}."
    bridge = _bridge_for_segment(segment, company)
    cta = "Open to a quick 15-minute call next week?"

    message = _trim_to_word_limit(f"{opener} {bridge} {cta}")
    return {
        "message": message,
        "word_count": len(message.split()),
        "structure": {"opener": opener, "bridge": bridge, "cta": cta},
    }
