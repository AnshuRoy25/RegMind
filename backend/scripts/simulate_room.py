"""
Simulate the #regmind chat room in the terminal, without Switch.

Runs the full demo story through the real orchestrator, real agents and fake
services, and prints every message as it would appear in the chat.

Usage (from backend/):
    python -m scripts.simulate_room            # demo script, press Enter between steps
    python -m scripts.simulate_room --auto     # demo script, no pauses
    python -m scripts.simulate_room --chat     # type messages yourself: "name: message"

For the auditor steps, set DEMO_DIFFS_DIR=samples/diffs in .env.
"""

import asyncio
import logging
import sys

from regmind.backend.app.agents import orchestrator
from regmind.backend.app.agents.gateway import services

ROOM = "regmind"

DEMO = [
    ("priya", "@regmind-intake new SEBI circular: samples/master_circular.txt"),
    ("priya", "@regmind-parser approved"),
    ("aayush", "@regmind-spec starting TSK-001"),
    ("priya", "@regmind-intake SEBI just issued an amendment: samples/amendment_circular.txt"),
    ("aayush", "@regmind-spec resuming TSK-001"),
    ("aayush", "@regmind-auditor done TSK-001, PR #4"),
    ("aayush", "@regmind-auditor fixed it, done TSK-001, PR #5"),
]


async def post(agent_name: str, room_id: str, text: str) -> None:
    print(f"\n🤖 {agent_name}:\n{text}\n")


async def say(sender: str, text: str) -> None:
    print("─" * 70)
    print(f"👤 {sender}: {text}")
    await orchestrator.handle_message(ROOM, sender, text, post)


async def print_tasks() -> None:
    rows = getattr(services.tasks, "rows", None)
    if not rows:
        return
    print("📋 tasks table:")
    for task in rows.values():
        print(f"   {task['id']}  {task['status']:<10} {task['assignee']:<10} {task['spec_summary'][:60]}")


async def run_demo(auto: bool) -> None:
    for sender, text in DEMO:
        if not auto:
            input(f"\n[Enter] → {sender}: {text}")
        await say(sender, text)
        await print_tasks()


async def run_chat() -> None:
    print('Type messages as  name: text   (Ctrl+C to quit)')
    while True:
        line = await asyncio.to_thread(input, "> ")
        if ":" not in line:
            print('Format is  name: text')
            continue
        sender, text = line.split(":", 1)
        await say(sender.strip(), text.strip())
        await print_tasks()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="   · %(message)s")
    logging.getLogger("google").setLevel(logging.WARNING)
    logging.getLogger("httpx").setLevel(logging.WARNING)
    if "--chat" in sys.argv:
        asyncio.run(run_chat())
    else:
        asyncio.run(run_demo(auto="--auto" in sys.argv))
