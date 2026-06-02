"""Command-line chat interface for the Outreach Operations Agent.

Run it with:  python main.py

It wires the ADK ``root_agent`` to an in-memory session and a ``Runner``, then
loops: read a line from you, send it to the agent, and stream back everything the
agent does — its text, the tools it calls (including the MongoDB MCP tools), and
the results. Database writes pause for your y/n confirmation (handled inside the
agent's before-tool callback).

Type 'quit' or 'exit' (or Ctrl-C) to leave.
"""

from __future__ import annotations

import asyncio
import warnings

# ADK emits noisy "[EXPERIMENTAL] feature ... is enabled" UserWarnings while it
# connects the MongoDB MCP server. They're informational, not errors — hide them
# so the chat output stays clean.
warnings.filterwarnings("ignore", message=r"\[EXPERIMENTAL\].*")

from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.genai import types

from outreach_agent.agent import root_agent
from outreach_agent.config import settings

APP_NAME = "outreach_operations_agent"
USER_ID = "local_user"
SESSION_ID = "local_session"


def _print_event(event) -> None:
    """Pretty-print a single ADK event: tool calls, tool results, and text."""
    content = getattr(event, "content", None)
    if not content or not getattr(content, "parts", None):
        return

    for part in content.parts:
        # The model decided to call a tool.
        if getattr(part, "function_call", None):
            call = part.function_call
            print(f"  [tool call] {call.name}({dict(call.args or {})})")
        # A tool returned a result.
        elif getattr(part, "function_response", None):
            resp = part.function_response
            preview = str(resp.response)
            if len(preview) > 300:
                preview = preview[:300] + " ..."
            print(f"  [tool result] {resp.name} -> {preview}")
        # Plain model text.
        elif getattr(part, "text", None) and part.text.strip():
            print(f"\nAgent: {part.text.strip()}")


def _print_banner() -> None:
    print("=" * 64)
    print("  Outreach Operations Agent  (Gemini 3 + MongoDB MCP via ADK)")
    print("=" * 64)
    print(f"  {settings.describe()}")
    if not settings.mongo_connection_string:
        print("\n  WARNING: MDB_MCP_CONNECTION_STRING is empty. MongoDB tools")
        print("  will fail until you set it in .env. Custom tools still work.")
    print("\n  Try: \"Find product managers at US AI startups, store them,")
    print("        score them, draft a message for each, and queue them.\"")
    print("  Type 'quit' to exit.\n")


async def chat_loop() -> None:
    """Main async REPL."""
    session_service = InMemorySessionService()
    await session_service.create_session(
        app_name=APP_NAME, user_id=USER_ID, session_id=SESSION_ID
    )
    runner = Runner(
        app_name=APP_NAME,
        agent=root_agent,
        session_service=session_service,
    )

    _print_banner()

    while True:
        try:
            user_input = input("You: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nGoodbye.")
            return

        if not user_input:
            continue
        if user_input.lower() in ("quit", "exit"):
            print("Goodbye.")
            return

        message = types.Content(role="user", parts=[types.Part(text=user_input)])
        print("...working (first request can take ~30s to start MongoDB tools)\n")
        try:
            async for event in runner.run_async(
                user_id=USER_ID, session_id=SESSION_ID, new_message=message
            ):
                _print_event(event)
        except Exception as exc:  # keep the REPL alive on transient errors
            print(f"\n[error] {type(exc).__name__}: {exc}")
        print()


if __name__ == "__main__":
    try:
        asyncio.run(chat_loop())
    except KeyboardInterrupt:
        print("\nGoodbye.")
