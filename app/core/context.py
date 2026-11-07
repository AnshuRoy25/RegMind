import uuid
from contextvars import ContextVar

current_org_id: ContextVar[uuid.UUID | None] = ContextVar("current_org_id", default=None)
current_room_id: ContextVar[str | None] = ContextVar("current_room_id", default=None)
current_agent_id: ContextVar[str | None] = ContextVar("current_agent_id", default=None)
current_sender: ContextVar[str | None] = ContextVar("current_sender", default=None)
current_switch_agent_pk: ContextVar[uuid.UUID | None] = ContextVar(
    "current_switch_agent_pk", default=None
)
