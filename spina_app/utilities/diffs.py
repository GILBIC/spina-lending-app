"""Pure record-difference helpers extracted from SPINA."""

from __future__ import annotations

def _spina_cilog_diff_pairs(old_obj, new_obj):
    if old_obj is None and new_obj is None:
        return []
    if old_obj is None and isinstance(new_obj, dict):
        keys = sorted(new_obj.keys())
        return [(k, None, new_obj.get(k)) for k in keys]
    if new_obj is None and isinstance(old_obj, dict):
        keys = sorted(old_obj.keys())
        return [(k, old_obj.get(k), None) for k in keys]
    if not isinstance(old_obj, dict) or not isinstance(new_obj, dict):
        return [('Value', old_obj, new_obj)] if old_obj != new_obj else []
    skip = {'id'}
    keys = sorted((set(old_obj.keys()) | set(new_obj.keys())) - skip)
    pairs = []
    for k in keys:
        ov = old_obj.get(k)
        nv = new_obj.get(k)
        if ov != nv:
            pairs.append((k, ov, nv))
    return pairs
