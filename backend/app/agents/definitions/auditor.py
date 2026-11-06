from google.adk.agents import Agent

from regmind.backend.app.agents.prompts import load_prompt
from regmind.backend.app.agents.tools.github_tools import get_pr_diff
from regmind.backend.app.agents.tools.task_tools import get_task, mark_task_done, record_verification
from regmind.backend.app.core.config import settings

auditor_agent = Agent(
    name="regmind_auditor",
    model=settings.gemini_model,
    description="Verifies a finished task by checking the pull request diff against the task's evidence checklist.",
    instruction=load_prompt("auditor"),
    tools=[mark_task_done, get_task, get_pr_diff, record_verification],
)
