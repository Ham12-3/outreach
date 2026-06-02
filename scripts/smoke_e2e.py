"""Non-interactive end-to-end smoke test.

Runs ONE goal through the real agent (live Gemini + the MongoDB MCP server +
your Atlas cluster), auto-confirming writes via OUTREACH_AUTO_CONFIRM so it can
run unattended. Use it to prove the full pipeline works before driving the
interactive CLI.

    OUTREACH_AUTO_CONFIRM=1 python scripts/smoke_e2e.py

It deliberately works on a small number of leads to keep the run quick and the
database tidy.
"""

from __future__ import annotations

import asyncio
import os
import sys
from pathlib import Path

# Make the project root importable when run as `python scripts/smoke_e2e.py`.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

os.environ.setdefault("OUTREACH_AUTO_CONFIRM", "1")

from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.genai import types

from outreach_agent.agent import root_agent
from outreach_agent.config import settings

GOAL = (
    "Use fetch_live_leads with keyword 'engineer' and limit 3 to get real leads. "
    "Store them in MongoDB, score each one, draft a message for each, and set "
    "their status to queued. Then read them back from MongoDB and give me a "
    "one-line summary with the segment breakdown."
)


def _print_event(event) -> None:
    content = getattr(event, "content", None)
    if not content or not getattr(content, "parts", None):
        return
    for part in content.parts:
        if getattr(part, "function_call", None):
            print(f"  [tool call] {part.function_call.name}")
        elif getattr(part, "function_response", None):
            preview = str(part.function_response.response)
            if len(preview) > 200:
                preview = preview[:200] + " ..."
            print(f"  [tool result] {part.function_response.name} -> {preview}")
        elif getattr(part, "text", None) and part.text.strip():
            print(f"\nAgent: {part.text.strip()}")


async def main() -> None:
    print("Settings:", settings.describe())
    session_service = InMemorySessionService()
    await session_service.create_session(
        app_name="smoke", user_id="smoke", session_id="smoke"
    )
    runner = Runner(app_name="smoke", agent=root_agent, session_service=session_service)
    message = types.Content(role="user", parts=[types.Part(text=GOAL)])
    async for event in runner.run_async(
        user_id="smoke", session_id="smoke", new_message=message
    ):
        _print_event(event)


if __name__ == "__main__":
    asyncio.run(main())
