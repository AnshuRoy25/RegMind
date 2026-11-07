from google.adk.agents import Agent

from app.agents.prompts import load_prompt
from app.agents.tools.obligation_tools import approve_obligations, get_circular_clauses, save_obligations
from app.core.config import settings

parser_agent = Agent(
    name="regmind_parser",
    model=settings.gemini_model,
    description="Splits a master circular into clauses, classifies each as an obligation and handles the officer's approval.",
    instruction=load_prompt("parser"),
    tools=[get_circular_clauses, save_obligations, approve_obligations],
)

