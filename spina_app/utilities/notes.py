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


def _merge_note_dict(dst: dict, src: dict) -> dict:
    """Merge src into dst without losing data; if conflicts, append text uniquely."""
    out = _as_note_dict(dst)
    inc = _as_note_dict(src)
    for k, v in inc.items():
        vv = (str(v) if v is not None else "").strip()
        if not vv:
            continue
        if k not in out or not str(out.get(k) or "").strip():
            out[k] = vv
        else:
            out[k] = _append_unique_text(str(out.get(k) or ""), vv)
    return out
