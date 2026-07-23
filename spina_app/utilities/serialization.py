"""Small serialization helpers extracted from SPINA."""

from __future__ import annotations

import json

def _spina_cilog_safe_json(blob):
    try:
        if blob in (None, ''):
            return None
        if isinstance(blob, dict):
            return blob
        return json.loads(blob)
    except Exception:
        return None
