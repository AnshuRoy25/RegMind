from google.adk.agents import Agent

from regmind.backend.app.agents.prompts import load_prompt
from regmind.backend.app.agents.tools.circular_tools import read_circular, register_circular
from regmind.backend.app.core.config import settings

intake_agent = Agent(
    name="regmind_intake",
    model=settings.gemini_model,
    description="Reads new SEBI circulars, checks if they apply to the firm and whether they are a master circular or an amendment.",
    instruction=load_prompt("intake"),
    tools=[read_circular, register_circular],
)
