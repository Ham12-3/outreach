"""Human-in-the-loop write gate.

This is the "keep me in control" requirement: before the agent performs ANY
MongoDB write (insert / update / delete / drop / rename / create), we intercept
the tool call, print a plain-English summary of exactly what's about to happen,
and wait for the user to type 'y'. If they don't confirm, the write is skipped
and the model is told it was cancelled.

ADK calls ``before_tool_callback`` right before a tool runs. The contract:
  • return None              -> let the tool run as normal
  • return a dict (result)   -> SKIP the tool; use this dict as its result

We use the dict-return path to cancel un-confirmed writes.
"""

from __future__ import annotations

import json
import os
from typing import Any, Optional

from google.adk.tools import BaseTool
from google.adk.tools.tool_context import ToolContext

# Substrings that mark a MongoDB MCP tool as a *write*. Matching on substrings
# (rather than an exact list) keeps this robust across MCP server versions, where
# tool names like "insert-many", "update-one", or "delete-many" can vary.
WRITE_TOOL_MARKERS = (
    "insert",
    "update",
    "delete",
    "drop",
    "rename",
    "create-collection",
    "create-index",
    "bulk",
    "replace",
)

# Reads we explicitly never gate, even if a marker ever appeared in the name.
SAFE_TOOL_NAMES = {
    "find",
    "aggregate",
    "count",
    "list-databases",
    "list-collections",
    "collection-schema",
    "collection-indexes",
    "db-stats",
    "explain",
    # our own custom tools are always safe (they don't touch the DB)
    "load_seed_leads",
    "fetch_live_leads",
    "score_lead",
    "draft_message",
}


def is_write_tool(tool_name: str) -> bool:
    """True if the tool would modify the database and needs confirmation."""
    name = tool_name.lower()
    if name in SAFE_TOOL_NAMES:
        return False
    return any(marker in name for marker in WRITE_TOOL_MARKERS)


def _summarise(tool_name: str, args: dict[str, Any]) -> str:
    """Build a short, human-readable description of the pending write."""
    collection = args.get("collection") or args.get("name") or "?"
    database = args.get("database") or args.get("db") or "?"

    # Show the most relevant payload compactly, without dumping huge blobs.
    detail_keys = ("filter", "update", "document", "documents", "replacement")
    details = {k: args[k] for k in detail_keys if k in args}
    if "documents" in details and isinstance(details["documents"], list):
        details["documents"] = f"<{len(details['documents'])} document(s)>"

    detail_str = json.dumps(details, default=str)[:400] if details else "(no payload)"
    return (
        f"  Tool:       {tool_name}\n"
        f"  Database:   {database}\n"
        f"  Collection: {collection}\n"
        f"  Details:    {detail_str}"
    )


def confirm_before_write(
    tool: BaseTool,
    args: dict[str, Any],
    tool_context: ToolContext,
) -> Optional[dict[str, Any]]:
    """ADK before_tool_callback: confirm writes, allow reads through untouched."""
    if not is_write_tool(tool.name):
        return None  # read or custom tool -> proceed silently

    print("\n" + "=" * 64)
    print("CONFIRM WRITE — the agent wants to change the database:")
    print(_summarise(tool.name, args))
    print("=" * 64)

    # Non-interactive automation mode (CI, smoke tests). Off by default so the
    # human y/n gate is the normal behaviour.
    if os.environ.get("OUTREACH_AUTO_CONFIRM", "").lower() in ("1", "true", "yes"):
        print("-> Auto-confirmed (OUTREACH_AUTO_CONFIRM is set). Writing...\n")
        return None

    try:
        answer = input("Proceed with this write? [y/N] ").strip().lower()
    except EOFError:
        answer = "n"

    if answer in ("y", "yes"):
        print("-> Confirmed. Writing...\n")
        return None  # proceed with the real tool

    print("-> Cancelled. No changes made.\n")
    return {
        "status": "cancelled",
        "reason": "The user declined this write. Do not retry it; ask how to proceed.",
    }
