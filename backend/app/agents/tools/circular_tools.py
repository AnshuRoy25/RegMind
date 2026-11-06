"""
Tools for reading and registering SEBI circulars. Used by regmind-intake.

Design rule: the LLM never copies the full circular text through tool arguments.
It reads a preview, makes a decision, and the tool re-reads the file itself.
"""

from pathlib import Path

import pymupdf

from regmind.backend.app.agents.contracts import CIRCULAR_KINDS
from regmind.backend.app.agents.gateway import services

PREVIEW_CHARS = 8000


def _extract_text(file_path: str) -> str:
    path = Path(file_path)
    if path.suffix.lower() == ".pdf":
        pages = []
        with pymupdf.open(path) as doc:
            for page in doc:
                pages.append(page.get_text())
        return "\n".join(pages).strip()
    return path.read_text(encoding="utf-8").strip()


async def read_circular(file_path: str) -> dict:
    """Read a SEBI circular (PDF or text file) and return a preview of its text.

    Use this first, to decide whether the circular applies to the firm and
    whether it is a master circular or an amendment.

    Args:
        file_path: Path to the circular file shared in the chat.

    Returns:
        ok, total_chars, preview (first part of the text), truncated flag.
    """
    path = Path(file_path)
    if not path.exists():
        return {"ok": False, "error": f"File not found: {file_path}"}
    try:
        text = _extract_text(file_path)
    except Exception as exc:  # corrupt or unreadable file
        return {"ok": False, "error": f"Could not read file: {exc}"}
    if not text:
        return {"ok": False, "error": "No text found. The PDF may be a scan."}

    return {
        "ok": True,
        "total_chars": len(text),
        "preview": text[:PREVIEW_CHARS],
        "truncated": len(text) > PREVIEW_CHARS,
    }


async def register_circular(file_path: str, title: str, kind: str, applies: bool, reason: str) -> dict:
    """Save the circular with your decision about it.

    Call this once, after read_circular, for every circular, including ones
    that do not apply (so the audit trail shows they were reviewed).

    Args:
        file_path: Same path you passed to read_circular.
        title: Short title of the circular, taken from its subject line.
        kind: "master" for a master circular or a new full circular, "amendment" if it changes an earlier one.
        applies: True if it applies to this firm, False if not.
        reason: One sentence explaining the applies and kind decision.

    Returns:
        ok, circular_id, kind, applies.
    """
    if kind not in CIRCULAR_KINDS:
        return {"ok": False, "error": f"kind must be one of {list(CIRCULAR_KINDS)}"}
    try:
        text = _extract_text(file_path)
    except Exception as exc:
        return {"ok": False, "error": f"Could not read file: {exc}"}

    circular_id = await services.circulars.save(title=title, kind=kind, applies=applies, raw_text=text)
    await services.audit.log(
        actor="regmind-intake",
        action="circular_registered",
        ref_id=str(circular_id),
        detail={"title": title, "kind": kind, "applies": applies, "reason": reason},
    )
    return {"ok": True, "circular_id": circular_id, "kind": kind, "applies": applies}
