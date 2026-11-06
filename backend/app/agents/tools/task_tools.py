"""
Tools for engineering tasks. Used by regmind-spec, regmind-router and regmind-auditor.

All status changes go through _move(), which enforces the task state machine
in plain Python. The LLM decides WHAT happened; this file decides what that
means for the task.
"""

from regmind.backend.app.agents.gateway import services

# status -> statuses it may move to
ALLOWED_MOVES = {
    "open": {"ongoing", "deprecated"},
    "ongoing": {"done", "paused", "deprecated"},
    "paused": {"ongoing", "deprecated"},
    "done": {"complete", "ongoing", "deprecated"},
    "complete": {"deprecated"},
    "deprecated": set(),
}


async def _move(task: dict, new_status: str, actor: str, detail: dict | None = None) -> dict | None:
    """Change status if allowed. Returns an error dict, or None on success."""
    current = task["status"]
    if new_status not in ALLOWED_MOVES[current]:
        return {"ok": False, "error": f"{task['id']} is '{current}' and cannot move to '{new_status}'"}
    await services.tasks.set_status(task["id"], new_status)
    log_detail = {"from": current, "to": new_status}
    if detail:
        log_detail.update(detail)
    await services.audit.log(actor, "task_status_changed", task["id"], log_detail)
    return None


def _public(task: dict) -> dict:
    return {
        "id": task["id"], "obligation_id": task["obligation_id"], "status": task["status"],
        "urgency": task["urgency"], "assignee": task["assignee"], "spec_summary": task["spec_summary"],
        "evidence_checklist": task["evidence_checklist"], "parent_task": task["parent_task"],
    }


# ---------- regmind-spec ----------

async def create_engineering_task(obligation_id: str, spec_summary: str, evidence_checklist: list[str],
                                  assignee: str) -> dict:
    """Create an engineering task for one approved technical obligation.

    Args:
        obligation_id: e.g. "OBL-003".
        spec_summary: 2-4 plain sentences telling an engineer exactly what to build or change. No legal language.
        evidence_checklist: 2-5 concrete, checkable items that prove the work is done, e.g. "config sets log retention to 730 days".
        assignee: Chat name of the engineer who owns it.

    Returns:
        ok, task: {id, status, urgency, assignee, spec_summary, evidence_checklist}.
    """
    obligation = await services.obligations.get(obligation_id)
    if obligation is None:
        return {"ok": False, "error": f"No obligation {obligation_id}"}
    if not obligation["approved"]:
        return {"ok": False, "error": f"{obligation_id} is not approved yet"}
    if obligation["category"] != "technical" or not obligation["actionable"]:
        return {"ok": False, "error": f"{obligation_id} is not an actionable technical obligation"}
    if await services.tasks.get_by_obligation(obligation_id) is not None:
        return {"ok": False, "error": f"{obligation_id} already has a live task"}
    if len(evidence_checklist) < 1:
        return {"ok": False, "error": "evidence_checklist needs at least one item"}

    task_id = await services.tasks.create(obligation_id, spec_summary, evidence_checklist,
                                          obligation["urgency"] or "urgent", assignee)
    await services.audit.log("regmind-spec", "task_created", task_id,
                             {"obligation_id": obligation_id, "assignee": assignee})
    task = await services.tasks.get(task_id)
    return {"ok": True, "task": _public(task)}


async def start_task(task_id: str, engineer: str) -> dict:
    """Mark a task as being worked on. Use when an engineer says they are starting or resuming a task.

    Works for open tasks (start) and paused tasks (resume with the updated spec).

    Args:
        task_id: e.g. "TSK-001".
        engineer: Chat name of the engineer who said it.

    Returns:
        ok, task.
    """
    task = await services.tasks.get(task_id)
    if task is None:
        return {"ok": False, "error": f"No task {task_id}"}
    error = await _move(task, "ongoing", "regmind-spec", {"by": engineer})
    if error:
        return error
    return {"ok": True, "resumed": task["status"] == "paused", "task": _public(await services.tasks.get(task_id))}


async def get_task(task_id: str) -> dict:
    """Get one task with its current status, spec and evidence checklist.

    Args:
        task_id: e.g. "TSK-001".
    """
    task = await services.tasks.get(task_id)
    if task is None:
        return {"ok": False, "error": f"No task {task_id}"}
    return {"ok": True, "task": _public(task)}


# ---------- regmind-router ----------

async def get_task_for_obligation(obligation_id: str) -> dict:
    """Get the live task (if any) for an obligation, including its current status and spec.

    Args:
        obligation_id: e.g. "OBL-003".
    """
    task = await services.tasks.get_by_obligation(obligation_id)
    if task is None:
        return {"ok": True, "found": False}
    return {"ok": True, "found": True, "task": _public(task)}


async def apply_amendment(obligation_id: str, change_type: str, new_spec_summary: str,
                          new_evidence_checklist: list[str], amendment_circular_id: int) -> dict:
    """Apply an amendment to the task of an existing obligation. The right action is chosen
    automatically from the task's current status.

    open -> spec rewritten in place
    ongoing -> spec rewritten and task paused, engineer must be told
    done or complete -> a new delta task is created for the change
    change_type "remove" -> task deprecated

    Args:
        obligation_id: The obligation being amended, from find_obligation_by_section.
        change_type: "modify" if the rule changed, "remove" if it was withdrawn or deleted.
        new_spec_summary: The full updated spec for an engineer (for "remove", a one-line reason).
        new_evidence_checklist: The full updated checklist (for "remove", pass an empty list).
        amendment_circular_id: The amendment circular's id, for the audit trail.

    Returns:
        ok, action, task_id, new_task_id (for delta), assignee, notify (True if a person must be told).
    """
    if change_type not in ("modify", "remove"):
        return {"ok": False, "error": 'change_type must be "modify" or "remove"'}
    task = await services.tasks.get_by_obligation(obligation_id)
    if task is None:
        return {"ok": True, "action": "no_task", "note": "This obligation has no task, nothing to change."}

    status = task["status"]
    audit_detail = {"amendment_circular_id": amendment_circular_id, "change_type": change_type, "old_status": status}
    result = {"ok": True, "task_id": task["id"], "assignee": task["assignee"], "new_task_id": None}

    if change_type == "remove":
        error = await _move(task, "deprecated", "regmind-router", audit_detail)
        if error:
            return error
        result.update(action="deprecated", notify=status in ("ongoing", "paused"))

    elif status == "open":
        await services.tasks.update_spec(task["id"], new_spec_summary, new_evidence_checklist)
        result.update(action="spec_rewritten", notify=False)

    elif status in ("ongoing", "paused"):
        await services.tasks.update_spec(task["id"], new_spec_summary, new_evidence_checklist)
        if status == "ongoing":
            error = await _move(task, "paused", "regmind-router", audit_detail)
            if error:
                return error
        result.update(action="paused_with_new_spec", notify=True)

    elif status in ("done", "complete"):
        new_id = await services.tasks.create_delta(task["id"], new_spec_summary, new_evidence_checklist)
        result.update(action="delta_task_created", new_task_id=new_id, notify=True)

    else:
        return {"ok": False, "error": f"Task {task['id']} is '{status}', nothing can be applied"}

    await services.audit.log("regmind-router", "amendment_applied", task["id"],
                             {**audit_detail, "action": result["action"], "new_task_id": result["new_task_id"]})
    return result


# ---------- regmind-auditor ----------

async def mark_task_done(task_id: str, pr_number: int, engineer: str) -> dict:
    """Record that an engineer says a task is done and has a pull request ready for review.

    Args:
        task_id: e.g. "TSK-001".
        pr_number: The pull request number the engineer gave, e.g. 4.
        engineer: Chat name of the engineer.

    Returns:
        ok, task (with its evidence checklist to verify against).
    """
    task = await services.tasks.get(task_id)
    if task is None:
        return {"ok": False, "error": f"No task {task_id}"}
    if task["status"] == "paused":
        return {"ok": False, "error": f"{task_id} is paused because the rule was amended. "
                                      "The engineer must resume it and build to the updated spec first."}
    if task["status"] != "done":
        error = await _move(task, "done", "regmind-auditor", {"by": engineer, "pr_number": pr_number})
        if error:
            return error
    return {"ok": True, "task": _public(await services.tasks.get(task_id))}


async def record_verification(task_id: str, passed: bool, missing_items: list[str], notes: str) -> dict:
    """Record the result of checking a task's evidence.

    passed=True moves the task to complete. passed=False sends it back to ongoing.

    Args:
        task_id: e.g. "TSK-001".
        passed: True only if every evidence checklist item is clearly met.
        missing_items: Checklist items not met (empty list if passed).
        notes: One or two lines on what you checked.

    Returns:
        ok, status.
    """
    task = await services.tasks.get(task_id)
    if task is None:
        return {"ok": False, "error": f"No task {task_id}"}
    if task["status"] != "done":
        return {"ok": False, "error": f"{task_id} must be 'done' before it can be verified (it is '{task['status']}')"}
    if passed and missing_items:
        return {"ok": False, "error": "passed=True but missing_items is not empty"}

    new_status = "complete" if passed else "ongoing"
    error = await _move(task, new_status, "regmind-auditor",
                        {"passed": passed, "missing_items": missing_items, "notes": notes})
    if error:
        return error
    return {"ok": True, "task_id": task_id, "status": new_status}
