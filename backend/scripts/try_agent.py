"""
Talk to ONE agent from the terminal and watch its tool calls.

Usage (from backend/):
    python -m scripts.try_agent regmind-intake "@regmind-intake new circular: samples/master_circular.txt"

Note: each run starts with empty fake data, so agents that need earlier steps
(parser needs a circular from intake, etc.) are easier to test with simulate_room.
"""

import asyncio
import sys

from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.genai import types

from regmind.backend.app.agents.definitions import AGENTS


async def main(agent_name: str, message: str):
    agent = AGENTS[agent_name]
    sessions = InMemorySessionService()
    await sessions.create_session(app_name="regmind", user_id="terminal", session_id="s1")
    runner = Runner(agent=agent, app_name="regmind", session_service=sessions)

    msg = types.Content(role="user", parts=[types.Part(text=f"[terminal] {message}")])
    async for event in runner.run_async(user_id="terminal", session_id="s1", new_message=msg):
        for call in event.get_function_calls():
            print(f"  -> TOOL CALL  {call.name}({dict(call.args or {})})")
        for resp in event.get_function_responses():
            print(f"  <- RESULT     {resp.name}: {str(resp.response)[:300]}")
        if event.is_final_response() and event.content and event.content.parts:
            print(f"\n{agent_name}:\n{event.content.parts[0].text or ''}")


if __name__ == "__main__":
    if len(sys.argv) < 3 or sys.argv[1] not in AGENTS:
        print('Usage: python -m scripts.try_agent <agent> "<message>"')
        print("Agents:", ", ".join(AGENTS))
        sys.exit(1)
    asyncio.run(main(sys.argv[1], sys.argv[2]))
