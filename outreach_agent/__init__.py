"""Outreach Operations Agent package.

Exposes ``root_agent`` so the agent can be discovered by the ADK tooling
(``adk run outreach_agent`` / ``adk web``) and imported by the CLI in main.py.
"""

from .agent import root_agent

__all__ = ["root_agent"]
