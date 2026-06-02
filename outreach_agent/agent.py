"""The ADK agent definition.

This is the heart of the project: a single Gemini 3 ``LlmAgent`` that is handed
two kinds of tools —

  1. The **MongoDB MCP server** (the partner "superpower"), connected as an ADK
     ``McpToolset`` over stdio. We launch it with ``npx mongodb-mcp-server`` and
     pass the Atlas connection string through the ``MDB_MCP_CONNECTION_STRING``
     environment variable. This gives the agent live read/write tools for the
     cluster (find, insert-many, update-many, ...).

  2. A few **custom Python function tools** (load_seed_leads, score_lead,
     draft_message) for the explainable business logic.

A ``before_tool_callback`` gates every database write behind a human y/n
confirmation, so nothing is written without the user's say-so.

Exposing ``root_agent`` at module level lets ``adk run``/``adk web`` discover it
and lets main.py import it for the CLI.
"""

from __future__ import annotations

import os
import sys

from google.adk.agents import LlmAgent
from google.adk.tools.mcp_tool import McpToolset
from google.adk.tools.mcp_tool.mcp_session_manager import StdioConnectionParams
from mcp import StdioServerParameters

from .config import settings
from .confirmation import confirm_before_write
from .prompts import INSTRUCTION
from .tools import draft_message, fetch_live_leads, load_seed_leads, score_lead


def _npx_command() -> str:
    """Resolve the npx executable name for the current platform.

    On Windows the launcher is ``npx.cmd``; elsewhere it's ``npx``.
    """
    return "npx.cmd" if sys.platform == "win32" else "npx"


def _build_mongodb_toolset() -> McpToolset:
    """Create the MongoDB MCP toolset, launched on demand via npx.

    The connection string is passed through the environment (never on the command
    line) so the secret doesn't show up in process listings.
    """
    # Start from the current environment so npx/node can find PATH, etc., then
    # inject the MongoDB connection string the MCP server expects.
    child_env = {
        **os.environ,
        "MDB_MCP_CONNECTION_STRING": settings.mongo_connection_string,
    }

    return McpToolset(
        connection_params=StdioConnectionParams(
            server_params=StdioServerParameters(
                command=_npx_command(),
                args=["-y", "mongodb-mcp-server@latest"],
                env=child_env,
            ),
            # npx may need to download the package on first run; give it room.
            timeout=60.0,
        ),
    )


# The single agent that powers the whole experience.
root_agent = LlmAgent(
    model=settings.model,
    name="outreach_operations_agent",
    description=(
        "Manages a sales/outreach lead pipeline in MongoDB: finds, stores, "
        "scores, drafts messages for, and tracks the status of leads — with a "
        "human confirmation before every database write."
    ),
    instruction=INSTRUCTION,
    tools=[
        _build_mongodb_toolset(),  # the MongoDB MCP superpower
        load_seed_leads,           # custom: offline lead source
        fetch_live_leads,          # custom: real leads from Hacker News
        score_lead,                # custom: explainable scoring
        draft_message,             # custom: message drafting
    ],
    # Human-in-the-loop: confirm every write before it touches the database.
    before_tool_callback=confirm_before_write,
)
