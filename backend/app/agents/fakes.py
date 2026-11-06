"""
In-memory implementation of app/agents/contracts.py.

Used while the real Postgres services are being built, and in tests.
Same method names, same return shapes, so switching is one setting.
"""

from datetime import datetime, timezone


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class FakeCircularService:
    def __init__(self):
        self.rows: dict[int, dict] = {}

    async def save(self, title: str, kind: str, applies: bool, raw_text: str) -> int:
        circular_id = len(self.rows) + 1
        self.rows[circular_id] = {
            "id": circular_id, "title": title, "kind": kind, "applies": applies,
            "raw_text": raw_text, "received_at": _now(),
        }
        return circular_id

    async def get(self, circular_id: int) -> dict | None:
        row = self.rows.get(circular_id)
        return dict(row) if row else None


class FakeObligationService:
    def __init__(self):
        self.rows: dict[str, dict] = {}

    async def save_many(self, circular_id: int, items: list[dict]) -> list[str]:
        ids = []
        for item in items:
            obligation_id = f"OBL-{len(self.rows) + 1:03d}"
            self.rows[obligation_id] = {
                "id": obligation_id,
                "circular_id": circular_id,
                "section_ref": item.get("section_ref", ""),
                "raw_text": item.get("raw_text", ""),
                "summary": item.get("summary", ""),
                "actionable": bool(item.get("actionable", False)),
                "category": item.get("category", "informational"),
                "urgency": item.get("urgency"),
                "approved": False,
                "created_at": _now(),
            }
            ids.append(obligation_id)
        return ids

    async def get(self, obligation_id: str) -> dict | None:
        row = self.rows.get(obligation_id)
        return dict(row) if row else None

    async def list_by_circular(self, circular_id: int) -> list[dict]:
        result = []
        for row in self.rows.values():
            if row["circular_id"] == circular_id:
                result.append(dict(row))
        return result

    async def find_by_section(self, section_ref: str) -> dict | None:
        match = None
        for row in self.rows.values():
            if row["section_ref"] == section_ref and row["approved"]:
                match = row  # later rows win, so we end up with the newest
        return dict(match) if match else None

    async def approve_all(self, circular_id: int) -> list[str]:
        approved = []
        for row in self.rows.values():
            if row["circular_id"] == circular_id and not row["approved"]:
                row["approved"] = True
                approved.append(row["id"])
        return approved


class FakeTaskService:
    def __init__(self):
        self.rows: dict[str, dict] = {}

    def _new_id(self) -> str:
        return f"TSK-{len(self.rows) + 1:03d}"

    async def create(self, obligation_id: str, spec_summary: str, checklist: list[str],
                     urgency: str, assignee: str) -> str:
        task_id = self._new_id()
        self.rows[task_id] = {
            "id": task_id, "obligation_id": obligation_id, "spec_summary": spec_summary,
            "evidence_checklist": list(checklist), "urgency": urgency, "assignee": assignee,
            "status": "open", "parent_task": None, "created_at": _now(), "updated_at": _now(),
        }
        return task_id

    async def get(self, task_id: str) -> dict | None:
        row = self.rows.get(task_id)
        return dict(row) if row else None

    async def get_by_obligation(self, obligation_id: str) -> dict | None:
        match = None
        for row in self.rows.values():
            if row["obligation_id"] == obligation_id and row["status"] != "deprecated":
                match = row
        return dict(match) if match else None

    async def set_status(self, task_id: str, status: str) -> None:
        self.rows[task_id]["status"] = status
        self.rows[task_id]["updated_at"] = _now()

    async def update_spec(self, task_id: str, spec_summary: str, checklist: list[str]) -> None:
        self.rows[task_id]["spec_summary"] = spec_summary
        self.rows[task_id]["evidence_checklist"] = list(checklist)
        self.rows[task_id]["updated_at"] = _now()

    async def create_delta(self, parent_id: str, spec_summary: str, checklist: list[str]) -> str:
        parent = self.rows[parent_id]
        task_id = self._new_id()
        self.rows[task_id] = {
            "id": task_id, "obligation_id": parent["obligation_id"], "spec_summary": spec_summary,
            "evidence_checklist": list(checklist), "urgency": parent["urgency"],
            "assignee": parent["assignee"], "status": "open", "parent_task": parent_id,
            "created_at": _now(), "updated_at": _now(),
        }
        return task_id


class FakeAuditService:
    def __init__(self):
        self.rows: list[dict] = []

    async def log(self, actor: str, action: str, ref_id: str, detail: dict) -> None:
        self.rows.append({"actor": actor, "action": action, "ref_id": ref_id,
                          "detail": detail, "at": _now()})


circulars = FakeCircularService()
obligations = FakeObligationService()
tasks = FakeTaskService()
audit = FakeAuditService()
