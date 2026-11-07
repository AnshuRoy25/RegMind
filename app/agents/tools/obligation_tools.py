﻿"""
Tools for turning a circular into obligations. Used by regmind-parser,
regmind-spec and regmind-router.
"""

from pydantic import BaseModel, Field

from regmind.app.agents.contracts import OBLIGATION_CATEGORIES, URGENCY_TIERS
from regmind.app.agents.gateway import services
from regmind.app.agents.tools.clauses import split_into_clauses


class ObligationInput(BaseModel):
    """Your classification of one clause."""
    section_ref: str = Field(description='Section reference exactly as returned by get_circular_clauses, e.g. "3.1"')
    summary: str = Field(description="One plain-English line saying what the firm must do or avoid")
    actionable: bool = Field(description="True if the firm must do or stop doing something")
    category: str = Field(description="technical, business, prohibitive, governance or informational")
    urgency: str = Field(description="urgent, recurring or conditional. Use urgent for one-time changes with a deadline or immediate effect")


def _as_dict(item) -> dict:
    if isinstance(item, BaseModel):
        return item.model_dump()
    return dict(item)


async def get_circular_clauses(circular_id: int) -> dict:
    """Get a registered circular split into numbered clauses.

    Args:
        circular_id: The id given by regmind-intake, e.g. 1.

    Returns:
        ok, title, kind, clauses: list of {section_ref, text}.
    """
    circular = await services.circulars.get(circular_id)
    if circular is None:
        return {"ok": False, "error": f"No circular with id {circular_id}"}
    clauses = split_into_clauses(circular["raw_text"])
    if not clauses:
        return {"ok": False, "error": "Could not find any numbered clauses in this circular"}
    return {"ok": True, "title": circular["title"], "kind": circular["kind"], "clauses": clauses}


async def save_obligations(circular_id: int, obligations: list[ObligationInput]) -> dict:
    """Save your classification of every clause of a master circular as obligations.

    Call this once per circular, with one entry for every clause returned by
    get_circular_clauses (including informational ones).

    Args:
        circular_id: The circular these clauses belong to.
        obligations: One entry per clause.

    Returns:
        ok, saved: list of {id, section_ref, category, urgency, summary}.
    """
    circular = await services.circulars.get(circular_id)
    if circular is None:
        return {"ok": False, "error": f"No circular with id {circular_id}"}
    existing = await services.obligations.list_by_circular(circular_id)
    if existing:
        return {"ok": False, "error": f"Obligations for circular {circular_id} were already saved ({len(existing)} rows)"}

    clause_text = {}
    for clause in split_into_clauses(circular["raw_text"]):
        clause_text[clause["section_ref"]] = clause["text"]

    items = []
    problems = []
    for raw in obligations:
        item = _as_dict(raw)
        ref = item.get("section_ref", "")
        if ref not in clause_text:
            problems.append(f"unknown section_ref {ref}")
            continue
        if item.get("category") not in OBLIGATION_CATEGORIES:
            problems.append(f"{ref}: category must be one of {list(OBLIGATION_CATEGORIES)}")
            continue
        if item.get("urgency") not in URGENCY_TIERS:
            problems.append(f"{ref}: urgency must be one of {list(URGENCY_TIERS)}")
            continue
        item["raw_text"] = clause_text[ref]
        items.append(item)

    if problems:
        return {"ok": False, "error": "Nothing saved. Fix these and call again: " + "; ".join(problems)}

    ids = await services.obligations.save_many(circular_id, items)
    saved = []
    for obligation_id, item in zip(ids, items):
        saved.append({"id": obligation_id, "section_ref": item["section_ref"], "category": item["category"],
                      "urgency": item["urgency"], "summary": item["summary"]})
    await services.audit.log("regmind-parser", "obligations_saved", str(circular_id), {"count": len(ids)})
    return {"ok": True, "saved": saved}


async def approve_obligations(circular_id: int, approved_by: str) -> dict:
    """Mark all obligations of a circular as approved by the compliance officer.

    Only call this after a person in the room has clearly approved.

    Args:
        circular_id: The circular whose obligations were approved.
        approved_by: Name of the person who approved, as shown in the chat.

    Returns:
        ok, approved_count,
        technical: actionable technical items that go to engineering,
        other_actionable: actionable non-technical items (business, prohibitive, governance)
        that the compliance team owns. Each item is {id, section_ref, category, urgency, summary}.
    """
    approved_ids = await services.obligations.approve_all(circular_id, approved_by)
    rows = await services.obligations.list_by_circular(circular_id)

    technical = []
    other_actionable = []
    for row in rows:
        if not row["actionable"]:
            continue
        item = {"id": row["id"], "section_ref": row["section_ref"], "category": row["category"],
                "urgency": row["urgency"], "summary": row["summary"]}
        if row["category"] == "technical":
            technical.append(item)
        else:
            other_actionable.append(item)

    await services.audit.log("regmind-parser", "obligations_approved", str(circular_id),
                             {"approved_by": approved_by, "count": len(approved_ids),
                              "technical": len(technical), "other_actionable": len(other_actionable)})
    return {"ok": True, "approved_count": len(approved_ids),
            "technical": technical, "other_actionable": other_actionable}


async def list_pending_technical_obligations(circular_id: int) -> dict:
    """List approved technical obligations of a circular that do not have a task yet.

    Args:
        circular_id: The circular to look at.

    Returns:
        ok, obligations: list of {id, section_ref, urgency, summary, raw_text}.
    """
    rows = await services.obligations.list_by_circular(circular_id)
    pending = []
    for row in rows:
        if not (row["approved"] and row["actionable"] and row["category"] == "technical"):
            continue
        if await services.tasks.get_by_obligation(row["id"]) is not None:
            continue
        pending.append({"id": row["id"], "section_ref": row["section_ref"], "urgency": row["urgency"],
                        "summary": row["summary"], "raw_text": row["raw_text"]})
    return {"ok": True, "obligations": pending}


async def find_obligation_by_section(section_ref: str) -> dict:
    """Find the existing approved obligation for a section of an earlier circular.

    Use this when an amendment changes a clause, e.g. "clause 3.1 ... shall be substituted".

    Args:
        section_ref: The section being amended, e.g. "3.1".

    Returns:
        ok, obligation: {id, section_ref, category, summary, raw_text} or found=False.
    """
    row = await services.obligations.find_by_section(section_ref)
    if row is None:
        return {"ok": True, "found": False}
    return {"ok": True, "found": True, "obligation": {
        "id": row["id"], "section_ref": row["section_ref"], "category": row["category"],
        "actionable": row["actionable"], "summary": row["summary"], "raw_text": row["raw_text"]}}


async def add_obligation_from_amendment(circular_id: int, section_ref: str, summary: str,
                                        actionable: bool, category: str, urgency: str) -> dict:
    """Add a brand new obligation introduced by an amendment (not a change to an old clause).

    The amendment was shared by the compliance officer, so it is saved as approved.

    Args:
        circular_id: The amendment circular's id.
        section_ref: Section number the amendment inserts, e.g. "3.3".
        summary: One plain-English line saying what the firm must do.
        actionable: True if the firm must do or stop doing something.
        category: technical, business, prohibitive, governance or informational.
        urgency: urgent, recurring or conditional.

    Returns:
        ok, obligation_id.
    """
    if category not in OBLIGATION_CATEGORIES:
        return {"ok": False, "error": f"category must be one of {list(OBLIGATION_CATEGORIES)}"}
    if urgency not in URGENCY_TIERS:
        return {"ok": False, "error": f"urgency must be one of {list(URGENCY_TIERS)}"}
    circular = await services.circulars.get(circular_id)
    if circular is None:
        return {"ok": False, "error": f"No circular with id {circular_id}"}

    raw_text = summary
    for clause in split_into_clauses(circular["raw_text"]):
        if clause["section_ref"] == section_ref:
            raw_text = clause["text"]
            break

    ids = await services.obligations.save_many(circular_id, [{
        "section_ref": section_ref, "raw_text": raw_text, "summary": summary,
        "actionable": actionable, "category": category, "urgency": urgency}])
    await services.obligations.approve_all(circular_id)
    await services.audit.log("regmind-router", "obligation_added_by_amendment", ids[0],
                             {"circular_id": circular_id, "section_ref": section_ref})
    return {"ok": True, "obligation_id": ids[0]}
