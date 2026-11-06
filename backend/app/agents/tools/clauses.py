"""
Deterministic clause splitting for SEBI circulars.

Splitting is done in plain Python, not by the LLM, so the same circular always
produces the same clauses and section references. The LLM only classifies them.
"""

import re

# "3.1 Stock brokers shall ..." or "3. Log Retention"
_CLAUSE_START = re.compile(r"^\s*(\d+(?:\.\d+)*)\.?\s+(\S.*)$")

HEADING_MAX_WORDS = 6


def split_into_clauses(text: str) -> list[dict]:
    """Return [{"section_ref": "3.1", "text": "..."}] in document order.

    Lines that do not start a new numbered clause are joined onto the previous
    clause. Short numbered lines that have sub-clauses (like "3. Log Retention"
    followed by "3.1 ...") are treated as headings and dropped.
    """
    clauses: list[dict] = []
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        match = _CLAUSE_START.match(line)
        if match:
            clauses.append({"section_ref": match.group(1), "text": match.group(2).strip()})
        elif clauses:
            clauses[-1]["text"] += " " + line

    refs = set()
    for clause in clauses:
        refs.add(clause["section_ref"])

    result = []
    for clause in clauses:
        has_children = False
        for ref in refs:
            if ref.startswith(clause["section_ref"] + "."):
                has_children = True
                break
        is_short = len(clause["text"].split()) <= HEADING_MAX_WORDS
        if has_children and is_short:
            continue  # it's a heading like "3. Log Retention"
        result.append(clause)
    return result
