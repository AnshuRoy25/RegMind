from app.agents.definitions.auditor import auditor_agent
from app.agents.definitions.intake import intake_agent
from app.agents.definitions.parser import parser_agent
from app.agents.definitions.router import router_agent
from app.agents.definitions.spec import spec_agent

# chat name (as people @mention it) -> ADK agent
AGENTS = {
    "regmind-intake": intake_agent,
    "regmind-parser": parser_agent,
    "regmind-spec": spec_agent,
    "regmind-router": router_agent,
    "regmind-auditor": auditor_agent,
}

