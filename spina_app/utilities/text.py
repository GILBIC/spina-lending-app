"""Pure text-normalization helpers extracted from SPINA."""

from __future__ import annotations

import re

def _oslp__norm_area_name(s: str) -> str:
    return " ".join(str(s).split()).strip().lower()

def _spina_crc_norm_text(_v):
    try:
        return re.sub(r"\s+", " ", str(_v or "").strip()).upper()
    except Exception:
        return str(_v or "").strip().upper()

def _spina_route_notice_norm_name(value: str) -> str:
    try:
        s = str(value or "").strip().lower()
        s = re.sub(r"\s+", " ", s)
        s = re.sub(r"\s*\([^)]*\)\s*$", "", s).strip()
        return s
    except Exception:
        return str(value or "").strip().lower()

def _spina_cilog_action_label(action, source=''):
    a = str(action or '').strip().upper()
    if a == 'UPDATE':
        src = str(source or '').lower()
        if 'picture' in src:
            return 'PICTURE'
        if 'link' in src:
            return 'LINK'
        if 'area' in src:
            return 'AREA UPDATE'
        return 'EDIT'
    return a or 'CHANGE'
