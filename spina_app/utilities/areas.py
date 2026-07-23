"""Area-name parsing and display helpers extracted from SPINA."""

from __future__ import annotations


def split_area_main_sub(area: str):
    """Split a single Area string into (main_area, sub_area).

    Backwards compatible:
      - If no separator is found, main_area = original, sub_area = ""
      - Supports separators like: 'Main - Sub', 'Main / Sub', 'Main | Sub', 'Main: Sub'
    """
    try:
        a = str(area or "").strip()
    except Exception:
        a = ""
    if not a:
        return ("", "")

    # Prefer separators with spaces first (less chance of false split)
    seps = [" | ", " / ", " - ", " > ", " : ", " — ", " – "]
    for sep in seps:
        if sep in a:
            left, right = a.split(sep, 1)
            left = (left or "").strip()
            right = (right or "").strip()
            if left and right:
                return (left, right)

    # Fallback single-char separators (use only if it looks like two parts)
    for sep in ["|", "/", ">", ":"]:
        if sep in a:
            left, right = a.split(sep, 1)
            left = (left or "").strip()
            right = (right or "").strip()
            if left and right:
                return (left, right)

    return (a, "")


def join_area_main_sub(main_area: str, sub_area: str = "") -> str:
    """Join main/sub into a single Area string using a consistent separator.

    - If sub_area is blank -> returns main_area
    - Else -> 'Main - Sub'
    """
    try:
        ma = str(main_area or "").strip()
    except Exception:
        ma = ""
    try:
        su = str(sub_area or "").strip()
    except Exception:
        su = ""
    if not ma:
        return su
    if not su:
        return ma
    return f"{ma} - {su}"


def _spina_crc_split_area(_area):
    try:
        if 'split_area_main_sub' in globals():
            return split_area_main_sub(_area)
    except Exception:
        pass
    a = str(_area or "").strip()
    for sep in [" | ", " / ", " - ", " > ", " : ", " — ", " – ", "|", "/", ">", ":"]:
        if sep in a:
            left, right = a.split(sep, 1)
            if left.strip() and right.strip():
                return left.strip(), right.strip()
    return a, ""
