"""
Routes chat messages to agents and chains agent-to-agent handoffs.

The Switch integration (Aayush) calls ONE function for every HUMAN message:

    await orchestrator.handle_message(room_id, sender, text, post)

where `post(agent_name, room_id, text)` is an async function that posts a reply
into the room as that agent.

Important: the integration must NOT forward messages written by agents back
into handle_message. Agent-to-agent handoffs (e.g. intake's reply mentioning
@regmind-parser) are chained here, inside handle_message, with a hop limit so
agents can never loop forever.
"""

import logging
import re
from typing import Awaitable, Callable

from app.agents import runtime

log = logging.getLogger("regmind.agents")

PostFn = Callable[[str, str, str], Awaitable[None]]

MAX_HOPS = 6
_MENTION = re.compile(r"@(regmind-[a-z]+)")


def find_mentioned_agents(text: str, sender: str) -> list[str]:
    """Agents that should act on this message, in order, without duplicates or the sender.

    From a human, any @regmind-x mention counts.
    From an agent, only lines that START with @regmind-x count as a handoff. This way
    an agent can write 'reply "@regmind-spec starting TSK-001"' as advice to a human
    without accidentally triggering regmind-spec itself.
    """
    if runtime.is_agent(sender):
        handoff_lines = []
        for line in text.splitlines():
            if line.strip().startswith("@regmind-"):
                handoff_lines.append(line)
        text = "\n".join(handoff_lines)

    found = []
    for name in _MENTION.findall(text):
        if name == sender or not runtime.is_agent(name) or name in found:
            continue
        found.append(name)
    return found


async def handle_message(room_id: str, sender: str, text: str, post: PostFn, hops: int = 0) -> None:
    """Handle one message: run every mentioned agent, post its reply, follow its handoffs."""
    if hops >= MAX_HOPS:
        log.warning("Hop limit reached in room %s, stopping chain", room_id)
        return

    for agent_name in find_mentioned_agents(text, sender):
        reply = await runtime.run(agent_name, room_id, f"[{sender}] {text}")
        if not reply:
            continue
        await post(agent_name, room_id, reply)
        await handle_message(room_id, agent_name, reply, post, hops + 1)

