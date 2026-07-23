"""Pure record-conversion helpers extracted from SPINA."""

from __future__ import annotations


def _spina_perf_dict_rows(rows):
    out = []
    for r in rows or []:
        try:
            out.append(dict(r))
        except Exception:
            try:
                out.append({k: r[k] for k in r.keys()})
            except Exception:
                pass
    return out
