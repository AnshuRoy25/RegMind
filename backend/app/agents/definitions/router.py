from google.adk.agents import Agent

from regmind.backend.app.agents.prompts import load_prompt
from regmind.backend.app.agents.tools.obligation_tools import (
    add_obligation_from_amendment,
    find_obligation_by_section,
    get_circular_clauses,
)
from regmind.backend.app.agents.tools.task_tools import apply_amendment, get_task_for_obligation
from regmind.backend.app.core.config import settings

router_agent = Agent(
    name="regmind_router",
    model=settings.gemini_model,
    description="Applies amendment circulars to existing obligations and tasks, based on each task's live status.",
    instruction=load_prompt("router"),
    tools=[get_circular_clauses, find_obligation_by_section, get_task_for_obligation,
           apply_amendment, add_obligation_from_amendment],
)
