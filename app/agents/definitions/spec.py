﻿from google.adk.agents import Agent

from regmind.app.agents.prompts import load_prompt
from regmind.app.agents.tools.obligation_tools import list_pending_technical_obligations
from regmind.app.agents.tools.task_tools import create_engineering_task, get_task, start_task
from regmind.app.core.config import settings

spec_agent = Agent(
    name="regmind_spec",
    model=settings.gemini_model,
    description="Turns approved technical obligations into engineering tasks with a spec and evidence checklist, and tracks when work starts.",
    instruction=load_prompt("spec").replace("DEFAULT_ASSIGNEE", settings.default_assignee),
    tools=[list_pending_technical_obligations, create_engineering_task, start_task, get_task],
)

