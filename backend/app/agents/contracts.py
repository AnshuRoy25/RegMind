"""
The agreement between the agents layer (Anshu) and the services layer (Aayush).

Agent tools only ever call these methods. Aayush implements them in app/services/
on top of Postgres; until then app/agents/fakes.py implements them in memory.

Rules both sides follow:
- Every method is async.
- Everything returned is a plain dict (or list of dicts), never an ORM object,
  so it can be handed straight to the LLM.
- IDs are human readable strings: OBL-001, TSK-001. Circular IDs are ints.
"""

from typing import Protocol


# Allowed values, shared by both sides
CIRCULAR_KINDS = ("master", "amendment")
OBLIGATION_CATEGORIES = ("technical", "business", "prohibitive", "governance", "informational")
URGENCY_TIERS = ("urgent", "recurring", "conditional")
TASK_STATUSES = ("open", "ongoing", "paused", "done", "complete", "deprecated")


class CircularService(Protocol):
    async def save(self, title: str, kind: str, applies: bool, raw_text: str) -> int: ...
    async def get(self, circular_id: int) -> dict | None: ...


class ObligationService(Protocol):
    async def save_many(self, circular_id: int, items: list[dict]) -> list[str]:
        """items: [{section_ref, raw_text, summary, actionable, category, urgency}]"""
        ...

    async def get(self, obligation_id: str) -> dict | None: ...
    async def list_by_circular(self, circular_id: int) -> list[dict]: ...
    async def find_by_section(self, section_ref: str) -> dict | None:
        """Latest approved obligation with this section reference, if any."""
        ...

    async def approve_all(self, circular_id: int) -> list[str]: ...


class TaskService(Protocol):
    async def create(self, obligation_id: str, spec_summary: str, checklist: list[str],
                     urgency: str, assignee: str) -> str: ...
    async def get(self, task_id: str) -> dict | None: ...
    async def get_by_obligation(self, obligation_id: str) -> dict | None:
        """The live (non-deprecated) task for this obligation, newest first."""
        ...

    async def set_status(self, task_id: str, status: str) -> None: ...
    async def update_spec(self, task_id: str, spec_summary: str, checklist: list[str]) -> None: ...
    async def create_delta(self, parent_id: str, spec_summary: str, checklist: list[str]) -> str: ...


class AuditService(Protocol):
    async def log(self, actor: str, action: str, ref_id: str, detail: dict) -> None: ...
