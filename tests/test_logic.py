"""Tests for the deterministic logic: scoring, drafting, seed loading, and the
write-gate classifier. These run fully offline (no MongoDB, no Gemini).

Run with:  pytest
"""

from __future__ import annotations

from outreach_agent.confirmation import is_write_tool
from outreach_agent.drafting import WORD_LIMIT, draft_message
from outreach_agent.live_leads import parse_hn_comment
from outreach_agent.scoring import score_lead, segment_for_score
from outreach_agent.tools import load_seed_leads


# ── Scoring ──────────────────────────────────────────────────────────────────

def test_hot_lead_scores_high():
    lead = {
        "title": "VP of Product",
        "industry": "Artificial Intelligence",
        "region": "United States",
    }
    result = score_lead(lead)
    # title fit (40) + executive seniority (25) + AI industry (20) + US (15) = 100
    assert result["score"] == 100
    assert result["segment"] == "Hot"
    assert result["reasons"]


def test_cold_lead_scores_low():
    lead = {
        "title": "Sales Director",
        "industry": "Data Analytics",
        "region": "United Kingdom",
    }
    result = score_lead(lead)
    assert result["segment"] == "Cold"
    assert result["score"] < 45


def test_region_penalty_reason_present_for_non_us():
    result = score_lead(
        {"title": "Product Manager", "industry": "AI", "region": "Canada"}
    )
    assert any("outside target market" in r for r in result["reasons"])


def test_segment_boundaries():
    assert segment_for_score(70) == "Hot"
    assert segment_for_score(69) == "Warm"
    assert segment_for_score(45) == "Warm"
    assert segment_for_score(44) == "Cold"


# ── Drafting ─────────────────────────────────────────────────────────────────

def test_draft_has_three_parts_and_uses_first_name():
    lead = {
        "name": "Maya Chen",
        "title": "Senior Product Manager",
        "company": "Driftwave AI",
        "segment": "Hot",
    }
    result = draft_message(lead)
    assert "Maya" in result["message"]
    assert set(result["structure"]) == {"opener", "bridge", "cta"}
    assert result["message"].endswith("?")


def test_draft_under_word_limit():
    lead = {
        "name": "Some Very Long Name Here",
        "title": "Principal Product Manager of Platform and Growth",
        "company": "A Company With A Very Long Name Indeed",
        "segment": "Warm",
    }
    result = draft_message(lead)
    assert result["word_count"] <= WORD_LIMIT


# ── Seed loading ─────────────────────────────────────────────────────────────

def test_seed_loads_about_twenty_leads_with_default_status():
    data = load_seed_leads()
    assert data["count"] >= 18
    assert all(lead["status"] == "new" for lead in data["leads"])
    assert all({"name", "title", "company"} <= set(lead) for lead in data["leads"])


# ── Live leads (HN parser, offline) ──────────────────────────────────────────

def test_parse_hn_comment_extracts_fields():
    raw = (
        "Driftwave AI | San Francisco, USA | Product Manager | REMOTE<p>"
        "We build AI agents. Apply at jobs@driftwave.ai"
    )
    lead = parse_hn_comment(raw, author="hiring_mgr")
    assert lead is not None
    assert lead["company"] == "Driftwave AI"
    assert lead["title"] == "Product Manager"
    assert lead["region"] == "Remote"  # 'REMOTE' wins
    assert lead["industry"] == "Artificial Intelligence"
    assert lead["email"] == "jobs@driftwave.ai"
    assert lead["source"] == "hackernews"
    assert lead["name"] == "hiring_mgr"


def test_parse_hn_comment_rejects_junk():
    assert parse_hn_comment("", author="x") is None
    assert parse_hn_comment("hi", author="x") is None


# ── Write gate classifier ────────────────────────────────────────────────────

def test_write_tools_are_gated():
    for name in ("insert-many", "update-one", "delete-many", "drop-collection"):
        assert is_write_tool(name) is True


def test_read_and_custom_tools_are_not_gated():
    for name in ("find", "aggregate", "count", "load_seed_leads", "score_lead"):
        assert is_write_tool(name) is False
