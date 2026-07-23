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
