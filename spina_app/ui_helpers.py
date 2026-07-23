"""Small UI drawing and card-label helpers extracted from SPINA."""

from __future__ import annotations


def _spina_v20_round_rect(cv, x1, y1, x2, y2, r=10, **kw):
    try:
        pts = [
            x1+r, y1, x2-r, y1, x2, y1, x2, y1+r,
            x2, y2-r, x2, y2, x2-r, y2, x1+r, y2,
            x1, y2, x1, y2-r, x1, y1+r, x1, y1
        ]
        return cv.create_polygon(pts, smooth=True, **kw)
    except Exception:
        return cv.create_rectangle(x1, y1, x2, y2, **kw)


def _spina_v24_cilog_round_rect(cv, x1, y1, x2, y2, r=10, **kw):
    try:
        pts = [
            x1+r, y1, x2-r, y1, x2, y1, x2, y1+r,
            x2, y2-r, x2, y2, x2-r, y2, x1+r, y2,
            x1+r, y2, x1, y2, x1, y2-r, x1, y1+r, x1, y1
        ]
        return cv.create_polygon(pts, smooth=True, **kw)
    except Exception:
        return cv.create_rectangle(x1, y1, x2, y2, **kw)


def _spina_v18_draw_round_rect(cv, x1, y1, x2, y2, r=14, **kwargs):
    """Canvas rounded rectangle fallback using polygon smoothing."""
    try:
        points = [
            x1+r, y1, x2-r, y1, x2, y1, x2, y1+r,
            x2, y2-r, x2, y2, x2-r, y2, x1+r, y2,
            x1, y2, x1, y2-r, x1, y1+r, x1, y1
        ]
        return cv.create_polygon(points, smooth=True, **kwargs)
    except Exception:
        return cv.create_rectangle(x1, y1, x2, y2, **kwargs)


def _spina_v17_set_card(self, key, value, subtitle=None):
    try:
        val_lbl, sub_lbl = (getattr(self, "_dash_cards", {}) or {}).get(key, (None, None))
        if val_lbl is not None:
            val_lbl.configure(text=str(value))
        if subtitle is not None and sub_lbl is not None:
            sub_lbl.configure(text=str(subtitle))
    except Exception:
        pass


def _spina_v24_cilog_set_card(self, key, value, subtitle=None):
    try:
        val_lbl, sub_lbl = (getattr(self, "_cilog_cards", {}) or {}).get(key, (None, None))
        if val_lbl is not None:
            val_lbl.configure(text=str(value))
        if subtitle is not None and sub_lbl is not None:
            sub_lbl.configure(text=str(subtitle))
    except Exception:
        pass


def _spina_v21_cash_set_card(self, key, value, subtitle=None):
    try:
        v_lbl, s_lbl = (getattr(self, "_cashctl_cards", {}) or {}).get(key, (None, None))
        if v_lbl is not None:
            v_lbl.configure(text=str(value))
        if subtitle is not None and s_lbl is not None:
            s_lbl.configure(text=str(subtitle))
    except Exception:
        pass
