"""Pure note-entry helpers extracted from SPINA."""

from __future__ import annotations

def _as_note_dict(entry):
    """Normalize a note entry to a dict with '__default__' and YYYY-MM-DD keys."""
    if entry is None:
        return {}
    if isinstance(entry, dict):
        return dict(entry)
    s = str(entry).strip()
    return {"__default__": s} if s else {}


def _append_unique_text(existing: str, addition: str) -> str:
    e = (existing or "").strip()
    a = (addition or "").strip()
    if not a:
        return e
    if not e:
        return a
    # Avoid duplicate appends
    if a in e:
        return e
    return e + "\n" + a
