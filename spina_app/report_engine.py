"""Complete client-statement PDF engine extracted from SPINA Wave 80."""
from __future__ import annotations

import os
import re
from datetime import date, datetime
from typing import Any, Mapping

DATA_DIR = os.getcwd()


def configure_report_engine_dependencies(namespace: Mapping[str, Any]) -> None:
    """Bind desktop helpers and recalculate data-file paths."""
    for name, value in namespace.items():
        if name not in {"configure_report_engine_dependencies", "__name__", "__file__"}:
            globals()[name] = value
    global REPORT_GENERATION_COUNT_FILE, REPORT_GENERATION_LOG_FILE, REPORT_GENERATION_LOG_CSV
    root = str(globals().get("DATA_DIR") or os.getcwd())
    REPORT_GENERATION_COUNT_FILE = os.path.join(root, "report_generation_counts.json")
    REPORT_GENERATION_LOG_FILE = os.path.join(root, "report_generation_logs.jsonl")
    REPORT_GENERATION_LOG_CSV = os.path.join(root, "report_generation_logs.csv")

# ==== BEGIN: SOA ADV/RANGE RENDERING PATCH ====
import re as _re_soapatch
from datetime import date as _date_soapatch, timedelta as _td_soapatch, datetime as _dt_soapatch
if ('_ADV_TAG_RE' not in globals()) or ('_ADV_PLAIN_RE' not in globals()):
    _ADV_TAG_RE = _re_soapatch.compile(r"\[ADV:(\d{4}-\d{2}-\d{2})\.\.(\d{4}-\d{2}-\d{2})\]")
    _ADV_PLAIN_RE = _re_soapatch.compile(
        r"\badv(ance)?\b[^0-9]*(\d{4}-\d{2}-\d{2})\s*(?:to|-|–|—|\.\.)\s*(\d{4}-\d{2}-\d{2})",
        _re_soapatch.IGNORECASE,
    )


def _parse_adv_range_any(desc: str):
    if not desc:
        return None
    m = _ADV_TAG_RE.search(str(desc))
    if m:
        try:
            return (_dt_soapatch.fromisoformat(m.group(1)).date(),
                    _dt_soapatch.fromisoformat(m.group(2)).date())
        except Exception:
            return None
    m = _ADV_PLAIN_RE.search(str(desc))
    if m:
        try:
            return (_dt_soapatch.fromisoformat(m.group(2)).date(),
                    _dt_soapatch.fromisoformat(m.group(3)).date())
        except Exception:
            return None
    return None

def _daterange_inclusive(d0: _date_soapatch, d1: _date_soapatch):
    d = d0
    while d <= d1:
        yield d
        d = d + _td_soapatch(days=1)



# ==== BEGIN: REASON COLOR TOKEN HELPERS (Encoder Reason -> PDF Color) ====
_REASON_COLOR_NAME_MAP = {
    "red": "#d32f2f",
    "orange": "#f57c00",
    "yellow": "#fbc02d",
    "green": "#388e3c",
    "blue": "#1976d2",
    "purple": "#7b1fa2",
    "pink": "#d81b60",
    "gray": "#455a64",
    "grey": "#455a64",
    "black": "#000000",
}

_REASON_COLOR_TOKEN_RE = re.compile(r"\[\s*RC\s*:\s*([^\]]+)\]", re.IGNORECASE)

def _parse_reason_color_token(desc: str):
    """Extract a [RC:...] token (hex or a color-name) from the description.

    Returns: (color_hex or "", desc_without_token)
    """
    if not desc:
        return ("", "")
    s = str(desc)
    m = _REASON_COLOR_TOKEN_RE.search(s)
    if not m:
        return ("", s)
    raw = (m.group(1) or "").strip()
    s2 = (s[:m.start()] + s[m.end():]).strip()
    if not raw:
        return ("", s2)
    # Normalize color
    r = raw.strip()
    rl = r.lower()
    if rl in _REASON_COLOR_NAME_MAP:
        return (_REASON_COLOR_NAME_MAP[rl], s2)
    if rl.startswith("#") and len(rl) == 7 and all(ch in "0123456789abcdef" for ch in rl[1:]):
        return (rl, s2)
    # Unknown token content -> ignore color, keep cleaned text
    return ("", s2)


def _parse_reason_color_token_meta(desc: str):
    """Extract [RC:...] token plus optional window meta from the description.

    Supported token payloads (inside the brackets):
      - '#RRGGBB'
      - 'red' / 'green' / etc
      - '#RRGGBB;D:3'                 -> days=3 (inclusive, starting from the reason's date)
      - '#RRGGBB;UNTIL:YYYY-MM-DD'    -> until (inclusive)
      - 'red;D:3' / 'red;UNTIL:...'   -> also supported

    Returns: (color_hex or "", meta_dict, desc_without_token)

    meta_dict = {'days': int|None, 'until': datetime.date|None}
    """
    if not desc:
        return ("", {"days": None, "until": None}, "")
    s = str(desc)
    m = _REASON_COLOR_TOKEN_RE.search(s)
    if not m:
        return ("", {"days": None, "until": None}, s)

    raw = (m.group(1) or "").strip()
    s2 = (s[:m.start()] + s[m.end():]).strip()

    meta = {"days": None, "until": None}
    if not raw:
        return ("", meta, s2)

    # Split payload by ';' so we can support '#hex;D:n' / '#hex;UNTIL:...'
    parts = [p.strip() for p in raw.split(";") if p.strip()]
    color_part = parts[0] if parts else ""
    directives = parts[1:] if len(parts) > 1 else []

    # Normalize color
    color_hex = ""
    cp = (color_part or "").strip()
    cpl = cp.lower()
    if cpl in _REASON_COLOR_NAME_MAP:
        color_hex = _REASON_COLOR_NAME_MAP[cpl]
    elif cpl.startswith("#") and len(cpl) == 7 and all(ch in "0123456789abcdef" for ch in cpl[1:]):
        color_hex = cpl

    # Parse directives
    try:
        from datetime import date as _d
    except Exception:
        _d = None

    for d in directives:
        dl = (d or "").strip()
        if not dl:
            continue

        m_d = re.match(r"^D\s*:\s*(\d+)$", dl, flags=re.IGNORECASE)
        if m_d:
            try:
                n = int(m_d.group(1))
                if n and n > 0:
                    meta["days"] = n
            except Exception as __spina_exc:
                _log_suppressed_once('excpass_0588', 'suppressed exception excpass_0588', __spina_exc)
                pass
            continue

        m_u = re.match(r"^UNTIL\s*:\s*(\d{4}-\d{2}-\d{2})$", dl, flags=re.IGNORECASE)
        if m_u and _d is not None:
            try:
                meta["until"] = _d.fromisoformat(m_u.group(1))
            except Exception as __spina_exc:
                _log_suppressed_once('excpass_0589', 'suppressed exception excpass_0589', __spina_exc)
                pass
            continue

    return (color_hex, meta, s2)

_ADV_STRIP_RE = re.compile(r"\[\s*ADV\s*:[^\]]*\]", re.IGNORECASE)

def _strip_adv_tags(desc: str) -> str:
    """Remove [ADV:...] tags from a description string."""
    if not desc:
        return ""
    s = str(desc)
    s = _ADV_STRIP_RE.sub("", s)
    # cleanup double spaces
    s = re.sub(r"\s{2,}", " ", s).strip()
    return s

def _extract_reason_and_color_from_desc(desc: str):
    """Return (reason_text, color_hex) from a transaction description.

    - Removes [ADV:...] tags
    - Extracts and removes [RC:...] token (optional ';D:n' / ';UNTIL:YYYY-MM-DD')
    - Returns trimmed reason text (may be empty)
    """
    if not desc:
        return ("", "")
    color_hex, _meta, s = _parse_reason_color_token_meta(str(desc))
    s = _strip_adv_tags(s)
    s = (s or "").strip()
    return (s, color_hex)

def _extract_reason_color_meta_from_desc(desc: str):
    """Return (reason_text, color_hex, meta) from a transaction description.

    meta = {'days': int|None, 'until': date|None}
    """
    if not desc:
        return ("", "", {"days": None, "until": None})
    color_hex, meta, s = _parse_reason_color_token_meta(str(desc))
    s = _strip_adv_tags(s)
    s = (s or "").strip()
    return (s, color_hex, meta)

def _hex_to_rgb01(hex_color: str):
    """'#RRGGBB' -> (r,g,b) floats 0..1"""
    try:
        hx = (hex_color or "").strip()
        if hx.startswith("#") and len(hx) == 7:
            r = int(hx[1:3], 16) / 255.0
            g = int(hx[3:5], 16) / 255.0
            b = int(hx[5:7], 16) / 255.0
            return (r, g, b)
    except Exception as __spina_exc:
        _log_suppressed_once('excpass_0590', 'suppressed exception excpass_0590', __spina_exc)
        pass
    return (0.0, 0.0, 0.0)



def _get_reason_color_for_client_date(db, client_name: str, day_iso: str, primary_loan_type=None):
    """Return the active reason color for this client on this day (Collector Route only).

    Behavior:
      - If the reason token has no window (no D/UNTIL), color applies ONLY on the reason's date.
      - If token has D:n, color applies for n days starting from the reason's date.
      - If token has UNTIL:YYYY-MM-DD, color applies from reason's date up to UNTIL (inclusive).

    Returns '#RRGGBB' or ''.
    """
    try:
        if not db or not getattr(db, "conn", None):
            return ""
        day_iso = str(day_iso or "").strip()[:10]
        if not day_iso:
            return ""
        cname = _normalize_client_name_for_lookup(client_name)
        if not cname:
            return ""
        try:
            from datetime import date as _d, timedelta as _td
            target = _d.fromisoformat(day_iso)
        except Exception:
            return ""

        # Prefer current mode, but also check the other loan type in case the reason was stored there.
        try:
            lt_primary = db._effective_lt(primary_loan_type)
        except Exception:
            lt_primary = (primary_loan_type or "Regular")
        lt_primary = (lt_primary or "Regular")
        lt_other = "7x7" if (str(lt_primary).lower().replace(" ", "") != "7x7") else "Regular"

        for lt in [lt_primary, lt_other]:
            try:
                cur = db.conn.cursor()
                cuid = None
                try:
                    if hasattr(db, 'get_client_uid'):
                        cuid = db.get_client_uid(cname, loan_type=lt)
                except Exception:
                    cuid = None
                if cuid:
                    cur.execute(
                        """SELECT date, description
                           FROM transactions
                           WHERE (((client_uid=?)) OR ((client_uid IS NULL OR TRIM(client_uid)='') AND name=? COLLATE NOCASE))
                             AND date<=?
                             AND IFNULL(NULLIF(TRIM(loan_type),''),'Regular') = IFNULL(NULLIF(TRIM(?),''),'Regular')
                             AND description IS NOT NULL AND TRIM(description)<>''
                           ORDER BY date DESC, rowid DESC
                           LIMIT 80""",
                        (cuid, cname, day_iso, lt),
                    )
                else:
                    cur.execute(
                        """SELECT date, description
                           FROM transactions
                           WHERE name=? COLLATE NOCASE AND date<=? AND loan_type=?
                             AND description IS NOT NULL AND TRIM(description)<>''
                           ORDER BY date DESC, rowid DESC
                           LIMIT 80""",
                        (cname, day_iso, lt),
                    )
                rows = cur.fetchall() or []
            except Exception:
                rows = []

            for rr in rows:
                try:
                    rdate = rr["date"] if isinstance(rr, dict) else rr[0]
                except Exception:
                    rdate = None
                try:
                    dsc = rr["description"] if isinstance(rr, dict) else rr[1]
                except Exception:
                    dsc = ""

                if not rdate:
                    continue
                try:
                    start = _d.fromisoformat(str(rdate)[:10])
                except Exception:
                    continue

                reason_txt, color_hex, meta = _extract_reason_color_meta_from_desc(dsc)
                if not reason_txt:
                    continue

                # Determine end date for the highlight window
                end = start
                try:
                    until = meta.get("until")
                    days = meta.get("days")
                except Exception:
                    until, days = None, None

                if until:
                    try:
                        end = until
                    except Exception:
                        end = start
                elif days and int(days) > 1:
                    try:
                        end = start + _td(days=int(days) - 1)
                    except Exception:
                        end = start

                if start <= target <= end:
                    return (color_hex or "#d32f2f")  # default red if no token color

        return ""
    except Exception:
        return ""
# ==== END: REASON COLOR TOKEN HELPERS ====


def _collect_day_flags_for_month(txns, month_start: _date_soapatch, month_end: _date_soapatch):
    """
    txns: iterable of dicts/rows having keys: 'date'|'d', 'payment'|'amt', 'description'|'desc'
    Returns dict: day(date)-> {'adv':bool, 'adv_paid_on':set(str), 'reason':str or None, 'paid':float}

    Reporting rules:
      - ADV is marked ONLY on the COVERED days (NOT on the payment date).
      - Covered days also store the payment date(s) that funded the ADV coverage (adv_paid_on).
    """
    def _gv(r, klist, default=None):
        for k in klist:
            try:
                if isinstance(r, dict):
                    if k in r:
                        return r[k]
                else:
                    v = r[k]
                    return v
            except Exception:
                continue
        return default

    def _row_date(r):
        dt_s = _gv(r, ['date', 'd'], None)
        if isinstance(dt_s, str):
            try:
                return _dt_soapatch.strptime(dt_s[:10], "%Y-%m-%d").date()
            except Exception:
                return None
        try:
            return dt_s if isinstance(dt_s, _date_soapatch) else _date_soapatch(dt_s.year, dt_s.month, dt_s.day)
        except Exception:
            return None

    def _adv_ranges_from_desc(desc: str):
        """Return list of (start_date, end_date) as date objects."""
        if not desc:
            return []
        ranges = []
        # Prefer the global multi-range parser if available
        try:
            if 'parse_advance_ranges' in globals():
                for a, b in (parse_advance_ranges(str(desc)) or []):
                    try:
                        da = _dt_soapatch.fromisoformat(a).date()
                        db = _dt_soapatch.fromisoformat(b).date()
                        if da <= db:
                            ranges.append((da, db))
                        else:
                            ranges.append((db, da))
                    except Exception:
                        continue
        except Exception as __spina_exc:
            _log_suppressed_once('excpass_0592', 'suppressed exception excpass_0592', __spina_exc)
            pass

        # Fallback to single-range / plain-text parser used by older patches
        if not ranges:
            try:
                rng = _parse_adv_range_any(str(desc))
                if rng:
                    ranges.append(rng)
            except Exception as __spina_exc:
                _log_suppressed_once('excpass_0593', 'suppressed exception excpass_0593', __spina_exc)
                pass
        return ranges

    flags = {}

    # 1) Mark ADV ranges (exclude payment day, store paid-on date)
    for r in txns:
        desc = (_gv(r, ['description', 'desc'], "") or "").strip()
        adv_ranges = _adv_ranges_from_desc(desc)
        if not adv_ranges:
            continue

        paid_on = _row_date(r)  # the payment date that created the ADV tag
        for s, e in adv_ranges:
            s2 = max(s, month_start)
            e2 = min(e, month_end)
            if s2 <= e2:
                for d in _daterange_inclusive(s2, e2):
                    # Do NOT show ADV on the payment date
                    if paid_on and d == paid_on:
                        continue
                    flags.setdefault(d, {})
                    flags[d]['adv'] = True
                    if paid_on:
                        flags[d].setdefault('adv_paid_on', set()).add(paid_on.isoformat())


    # 2) Mark payments + reasons (reasons can coexist with payments)
    for r in txns:
        d = _row_date(r)
        if d is None or not (month_start <= d <= month_end):
            continue

        amt = 0.0
        try:
            amt = float(_gv(r, ['payment', 'amt'], 0) or 0)
        except Exception:
            amt = 0.0

        desc = (_gv(r, ['description', 'desc'], "") or "").strip()
        has_adv = bool(_adv_ranges_from_desc(desc))

        # Extract reason text + optional color token, stripping ADV tags.
        reason_txt = ""
        reason_color = ""
        try:
            if "_extract_reason_and_color_from_desc" in globals():
                reason_txt, reason_color = _extract_reason_and_color_from_desc(desc)
            else:
                reason_txt = (desc or "").strip()
                if has_adv:
                    reason_txt = ""
        except Exception:
            reason_txt = (desc or "").strip()
            if has_adv:
                reason_txt = ""

        if amt > 0:
            flags.setdefault(d, {})
            # Data Bank semantics: one effective payment per day.
            # If duplicates exist for the same date, the latest non-zero payment wins.
            prev_paid = float(flags[d].get('paid', 0.0) or 0.0)
            if amt > 0:
                flags[d]['paid'] = amt
            else:
                # Only set zero if nothing exists yet.
                if abs(prev_paid) < 1e-9:
                    flags[d]['paid'] = 0.0

        # Keep reason even if there is a payment on that day.
        if reason_txt:
            flags.setdefault(d, {})
            prev = str(flags[d].get('reason') or '').strip()
            if not prev:
                flags[d]['reason'] = reason_txt
            elif reason_txt not in prev:
                flags[d]['reason'] = prev + " | " + reason_txt
            if reason_color and not str(flags[d].get('reason_color') or '').strip():
                flags[d]['reason_color'] = reason_color

    return flags





# --- BEGIN: Official report generation counter ---
REPORT_GENERATION_COUNT_FILE = os.path.join(DATA_DIR, "report_generation_counts.json")
REPORT_GENERATION_LOG_FILE = os.path.join(DATA_DIR, "report_generation_logs.jsonl")
REPORT_GENERATION_LOG_CSV = os.path.join(DATA_DIR, "report_generation_logs.csv")

def _spina_record_report_generation(client_name: str, loan_type: str | None = None, out_path: str = "", start_date: str = "", end_date: str = "") -> dict:
    """Increment and return the daily Generate Report counter.

    Stored in:
      - data/report_generation_counts.json (summary counts)
      - data/report_generation_logs.csv (Excel-friendly full log)
      - data/report_generation_logs.jsonl (append-only full log)

    Counts:
      - total: all reports generated today
      - per client+loan type: how many times that exact report was generated today
    """
    try:
        today = datetime.now().strftime("%Y-%m-%d")
        now_s = datetime.now().strftime("%Y-%m-%d %I:%M %p")
    except Exception:
        today = str(date.today())
        now_s = today

    try:
        lt = _normalize_loan_type_value(loan_type)
    except Exception:
        lt = str(loan_type or "Regular").strip() or "Regular"

    try:
        nm = str(client_name or "").strip() or "Unknown"
    except Exception:
        nm = "Unknown"

    key = f"{lt}::{nm}".lower()
    out = {
        "date": today,
        "generated_at": now_s,
        "start_date": str(start_date or "")[:10],
        "end_date": str(end_date or "")[:10],
        "daily_total": 1,
        "client_daily_count": 1,
    }

    try:
        data = _read_json_file(REPORT_GENERATION_COUNT_FILE)
        if not isinstance(data, dict):
            data = {}

        day_rec = data.get(today)
        if not isinstance(day_rec, dict):
            day_rec = {}

        try:
            day_total = int(day_rec.get("total") or 0) + 1
        except Exception:
            day_total = 1
        day_rec["total"] = day_total

        clients = day_rec.get("clients")
        if not isinstance(clients, dict):
            clients = {}

        client_rec = clients.get(key)
        if isinstance(client_rec, dict):
            try:
                client_count = int(client_rec.get("count") or 0) + 1
            except Exception:
                client_count = 1
        else:
            try:
                client_count = int(client_rec or 0) + 1
            except Exception:
                client_count = 1
            client_rec = {}

        client_rec.update({
            "count": client_count,
            "name": nm,
            "loan_type": lt,
            "last_generated_at": now_s,
            "last_file": str(out_path or ""),
        })
        clients[key] = client_rec

        day_rec["clients"] = clients
        day_rec["last_generated_at"] = now_s
        data[today] = day_rec

        try:
            if len(data) > 370:
                keep = sorted(data.keys())[-370:]
                data = {k: data[k] for k in keep if k in data}
        except Exception:
            pass

        _write_json_atomic(REPORT_GENERATION_COUNT_FILE, data)
        out.update({
            "daily_total": day_total,
            "client_daily_count": client_count,
        })

        # Full append-only Generate Report log (global, not just per-client).
        try:
            log_rec = {
                "generated_at": now_s,
                "generated_date": today,
                "client_name": nm,
                "loan_type": lt,
                "start_date": str(start_date or "")[:10],
                "end_date": str(end_date or "")[:10],
                "daily_total": day_total,
                "client_daily_count": client_count,
                "pdf_path": str(out_path or ""),
            }

            # JSONL: safer append-only machine-readable log.
            try:
                import json as _json_log
                os.makedirs(os.path.dirname(REPORT_GENERATION_LOG_FILE), exist_ok=True)
                with open(REPORT_GENERATION_LOG_FILE, "a", encoding="utf-8") as _jf:
                    _jf.write(_json_log.dumps(log_rec, ensure_ascii=False) + "\n")
            except Exception as __spina_log_exc:
                _log_suppressed_once('excpass_report_generation_jsonl_log', 'suppressed exception report generation jsonl log', __spina_log_exc)

            # CSV: easier to open in Excel.
            try:
                import csv as _csv_log
                os.makedirs(os.path.dirname(REPORT_GENERATION_LOG_CSV), exist_ok=True)
                _exists = os.path.exists(REPORT_GENERATION_LOG_CSV) and os.path.getsize(REPORT_GENERATION_LOG_CSV) > 0
                with open(REPORT_GENERATION_LOG_CSV, "a", newline="", encoding="utf-8-sig") as _cf:
                    _fields = ["generated_at", "generated_date", "client_name", "loan_type", "start_date", "end_date", "daily_total", "client_daily_count", "pdf_path"]
                    _w = _csv_log.DictWriter(_cf, fieldnames=_fields)
                    if not _exists:
                        _w.writeheader()
                    _w.writerow({k: log_rec.get(k, "") for k in _fields})
            except Exception as __spina_csv_exc:
                _log_suppressed_once('excpass_report_generation_csv_log', 'suppressed exception report generation csv log', __spina_csv_exc)
        except Exception as __spina_full_log_exc:
            _log_suppressed_once('excpass_report_generation_full_log', 'suppressed exception report generation full log', __spina_full_log_exc)
    except Exception as __spina_exc:
        try:
            _log_suppressed_once('excpass_report_generation_counter', 'suppressed exception report generation counter', __spina_exc)
        except Exception:
            pass

    return out
# --- END: Official report generation counter ---


def generate_client_pdf(db, client_name, start_date, end_date, out_path, note_text="", loan_type=None, page_size_name="A4", **_kw):
    """
    Override: Client SOA PDF that expands ADV ranges to daily 'Adv' markers in the Payment column,
    and prints other reasons as text in Payment. Never prints long notes in the Date column.
    Layout: 3 columns per page, 11 rows per column.
    """
    try:
        from reportlab.lib.pagesizes import A4 as _A4_soapatch, letter as _LETTER_soapatch, legal as _LEGAL_soapatch
        from reportlab.lib.units import inch as _inch_soapatch
        from reportlab.pdfgen import canvas as _cv_soapatch
    except Exception as _e:
        raise RuntimeError("reportlab not installed") from _e

    # normalize loan type context (Regular vs 7x7)
    try:
        loan_type = db._effective_lt(loan_type)
    except Exception:
        loan_type = loan_type or 'Regular'

    def _display_loan_type_label(_lt) -> str:
        s = (str(_lt or '')).strip()
        sl = s.lower()
        if '7x7' in sl or 'emer' in sl:
            return '7x7 (Emer)'
        if sl in ('regular', 'reg'):
            return 'Regular'
        return s or 'Regular'

    # Pull transactions in range
    rows = db.get_transactions_for_client(client_name, start_date, end_date, loan_type=loan_type)
    info = db.get_client_info(client_name, loan_type=loan_type) or {}

    # linked-type flags for header checkboxes / 'Also has' line
    try:
        has_reg = bool(db.get_client_info(client_name, loan_type='Regular'))
    except Exception:
        has_reg = False
    try:
        has_x7 = bool(db.get_client_info(client_name, loan_type='7x7'))
    except Exception:
        has_x7 = False


    # Renew info (how many renewals and last released cash)
    renew_count = 0
    last_released_cash = None
    last_release_date = None
    try:
        _uid = (info.get('client_uid') or '').strip()
        if _uid:
            renew_count, last_released_cash, last_release_date = db.get_renewal_stats(_uid, loan_type=loan_type)
    except Exception as __spina_exc:
        _log_suppressed_once('excpass_0594', 'suppressed exception excpass_0594', __spina_exc)
        pass
    # Keep the report period exactly as requested by the caller.
    # Do not apply any extra 7x7-only start bump here; the client's
    # Start of Payment is handled separately by _cycle_start below.

    def _gv(r,k,default=None):
        try:
            return r[k]
        except Exception:
            try:
                return dict(r).get(k, default)
            except Exception:
                return default

    total_paid_all = _sum_paid_per_day(rows)
    principal    = float(info.get('principal') or 0)
    interest     = float(info.get('interest_amount') or 0)
    # total_to_pay should normally be principal + interest (Regular) or principal (7x7).
    # Some legacy DB upgrades may have total_to_pay == principal even when interest_amount exists.
    try:
        total_to_pay = float(info.get('total_to_pay') or 0)
    except Exception:
        total_to_pay = 0.0
    computed_total = round(principal + interest, 2)
    if total_to_pay <= 0 or (interest > 0 and abs(total_to_pay - principal) < 0.01):
        total_to_pay = computed_total


    # --- Cycle totals (used for Balance / Renew cash) ---
    # Use "Start of Payment" if available (manual), otherwise Released + offset.
    _cycle_start = ""
    try:
        _ps = (str(info.get('payment_start_date') or '')[:10]).strip()
        if _ps:
            _dt_soapatch.strptime(_ps, "%Y-%m-%d")
            _cycle_start = _ps

        # Safety: after RENEW, payment_start_date can be stale (old cycle) or equal to date_released.
        # If it is <= date_released, treat it as unset so we fall back to Released + offset.
        if _cycle_start:
            _dr0 = (str(info.get('date_released') or '')[:10]).strip()
            if _dr0:
                try:
                    _dt_soapatch.strptime(_dr0, "%Y-%m-%d")
                    try:
                        _off_chk = int(info.get('pay_start_offset_days') or 0)
                    except Exception:
                        _off_chk = 0
                    _off_chk = 1 if _off_chk >= 1 else 0
                    if _cycle_start < _dr0 or (_off_chk == 1 and _cycle_start == _dr0):
                        _cycle_start = ""
                except Exception as __spina_exc:
                    _log_suppressed_once('excpass_0597', 'suppressed exception excpass_0597', __spina_exc)
                    pass
    except Exception:
        _cycle_start = ""
    if not _cycle_start:
        _cycle_start = (str(info.get('date_released') or '')[:10]).strip()
        try:
            _dt_soapatch.strptime(_cycle_start, "%Y-%m-%d")
        except Exception:
            _cycle_start = start_date
        # offset: 0 = same-day start, 1 = next-day start (optional)
        if _cycle_start:
            try:
                _off = int(info.get('pay_start_offset_days') or 0)
            except Exception:
                _off = 0
            _off = 1 if _off >= 1 else 0

            try:
                _cycle_start = (_dt_soapatch.strptime(_cycle_start, "%Y-%m-%d").date() + _td_soapatch(days=_off)).strftime("%Y-%m-%d")
            except Exception as __spina_exc:
                _log_suppressed_once('excpass_0598', 'suppressed exception excpass_0598', __spina_exc)
                pass
    try:
        cycle_rows = db.get_transactions_for_client(client_name, _cycle_start, end_date, loan_type=loan_type) or []
    except Exception:
        cycle_rows = []
    total_paid_cycle = float(_sum_paid_per_day(cycle_rows) or 0.0)

    # --- 7x7 split (interest per 1000 per day) ---
    _lt_s = str(loan_type or '').lower().replace('×', 'x')
    is_7x7 = ('7x7' in _lt_s) or ('emer' in _lt_s)
    _official_report_count = _spina_record_report_generation(client_name, loan_type=loan_type, out_path=out_path, start_date=start_date, end_date=end_date)


    def _per_day_effective_payments(_rows):
        """Return ordered list of (date, effective_payment) using the same rule as totals:
        last non-zero wins; 0 does not overwrite a prior non-zero; ignore ADV-only marker rows."""
        if not _rows:
            return []
        per = {}
        for r in _rows:
            ds = str(_gv(r, 'date', '') or '')[:10].strip()
            if not ds:
                continue
            try:
                pay = float(_gv(r, 'payment', 0) or 0.0)
            except Exception:
                pay = 0.0
            desc = str(_gv(r, 'description', '') or '')
            if abs(pay) < 1e-9:
                dl = desc.lower()
                if 'adv' in dl and ('[' in dl or 'range' in dl or ':' in dl):
                    continue
            if ds not in per:
                per[ds] = pay
            else:
                if abs(pay) > 1e-9:
                    per[ds] = pay
        out = []
        for ds, pay in per.items():
            try:
                d = _dt_soapatch.strptime(ds, "%Y-%m-%d").date()
            except Exception:
                continue
            out.append((d, float(pay or 0.0)))
        out.sort(key=lambda x: x[0])
        return out

    _x7_daily_interest = 0.0
    _x7_interest_part_period = 0.0
    _x7_principal_part_period = 0.0
    _x7_interest_paid_cycle = 0.0
    _x7_principal_paid_cycle = 0.0
    _x7_balance_principal = round(max(0.0, principal), 2)
    _x7_due_label = (str(info.get('due_date') or '')[:10]).strip()
    _x7_first_pay_amount = 0.0
    _x7_first_pay_date = None

    # NEW: gap-aware first-payment split + interest arrears carry
    _x7_first_split_interest = 0.0
    _x7_first_split_principal = 0.0
    _x7_first_split_gap_days = 1
    _x7_interest_arrears_end = 0.0

    if is_7x7 and principal > 0:
        # Daily interest is fixed from the recorded loan principal for the whole cycle.
        # Paying principal lowers the balance but does not lower this daily-interest basis.
        def _x7_daily_interest_for_principal(_loan_principal):
            return float(_wave74_x7_daily_interest(_loan_principal))

        _x7_daily_interest = round(_x7_daily_interest_for_principal(principal), 2)
        # Parse report window dates (safe)
        try:
            _r_start_dt = _dt_soapatch.strptime(str(start_date)[:10], "%Y-%m-%d").date()
        except Exception:
            _r_start_dt = None
        try:
            _r_end_dt = _dt_soapatch.strptime(str(end_date)[:10], "%Y-%m-%d").date()
        except Exception:
            _r_end_dt = None

        # Determine cycle start date (Start of Payment)
        try:
            _cycle_start_dt = _dt_soapatch.strptime(str(_cycle_start)[:10], "%Y-%m-%d").date()
        except Exception:
            _cycle_start_dt = None

        _cycle_days = _per_day_effective_payments(cycle_rows)

        def _x7_split_with_gaps(pay_days, start_dt):
            """7x7 rule:
            - Interest accrues DAILY: (daily_interest * gap_days)
            - Payment pays INTEREST FIRST, then PRINCIPAL
            - If payment < interest due, unpaid interest carries forward (arrears)
            """
            rem = float(principal)
            arrears = 0.0
            prev_dt = (start_dt - _td_soapatch(days=1)) if start_dt else None
            splits = []
            last_dt = None
            finish_dt = None

            for d, amt in (pay_days or []):
                try:
                    amt = float(amt or 0.0)
                except Exception:
                    amt = 0.0
                if amt <= 0:
                    continue

                last_dt = d

                # gap days since previous payment date; for first payment, include the start day
                gap = 1
                if prev_dt is not None:
                    try:
                        gap = (d - prev_dt).days
                    except Exception:
                        gap = 1
                if gap <= 0:
                    gap = 1

                _di = float(_x7_daily_interest_for_principal(principal))

                interest_due = (_di * float(gap)) + float(arrears)
                interest_paid = min(float(amt), float(interest_due))
                principal_pay_raw = max(0.0, float(amt) - float(interest_paid))

                apply_p = min(principal_pay_raw, rem) if rem > 0 else 0.0
                rem -= apply_p

                arrears = float(interest_due) - float(interest_paid)

                splits.append((d, float(amt), float(interest_paid), float(apply_p), int(gap), float(arrears), float(rem)))

                prev_dt = d

                if rem <= 0:
                    rem = 0.0
                    finish_dt = d
                    break

            return splits, rem, arrears, last_dt, finish_dt

        _cycle_splits, _rem, _arrears, _last_dt, _finish_dt = _x7_split_with_gaps(_cycle_days, _cycle_start_dt)

        _x7_interest_arrears_end = round(max(0.0, float(_arrears or 0.0)), 2)
        _x7_balance_principal = round(max(0.0, float(_rem or 0.0)), 2)

        # Sum cycle totals + period totals (period totals are filtered from the cycle allocation)
        for _d, _amt, _ip, _pp, _gap, _arr, _remv in (_cycle_splits or []):
            _x7_interest_paid_cycle += float(_ip or 0.0)
            _x7_principal_paid_cycle += float(_pp or 0.0)

            if _r_start_dt and _r_end_dt and (_r_start_dt <= _d <= _r_end_dt):
                _x7_interest_part_period += float(_ip or 0.0)
                _x7_principal_part_period += float(_pp or 0.0)


        # Keep the statement balance based on the FULL current loan cycle, not only
        # the visible report window.  The old code recalculated balance from
        # _x7_principal_part_period, so a PDF generated from a manual/partial
        # date range could show a wrong 7x7 balance and wrong renew basis.
        # _x7_balance_principal is already computed above from _cycle_splits
        # using _cycle_start -> end_date, so leave it unchanged here.

        # Keep daily interest display fixed to the recorded loan principal.
        try:
            _x7_daily_interest = round(_x7_daily_interest_for_principal(principal), 2)
        except Exception as __spina_exc:
            _log_suppressed_once('excpass_0600', 'suppressed exception excpass_0600', __spina_exc)
            pass

        # remember the first payment for the example line in the PDF (gap-aware)
        try:
            if _cycle_splits:
                _x7_first_pay_date = _cycle_splits[0][0]
                _x7_first_pay_amount = float(_cycle_splits[0][1] or 0.0)
                _x7_first_split_interest = float(_cycle_splits[0][2] or 0.0)
                _x7_first_split_principal = float(_cycle_splits[0][3] or 0.0)
                _x7_first_split_gap_days = int(_cycle_splits[0][4] or 1)
        except Exception as __spina_exc:
            _log_suppressed_once('excpass_0601', 'suppressed exception excpass_0601', __spina_exc)
            pass

        # Due date: exact if finished; otherwise estimate using avg gap + avg pay
        if _finish_dt:
            _x7_due_label = _finish_dt.strftime("%Y-%m-%d")
        else:
            try:
                import math as _math7
                _pay_tuples = [(d, a) for (d, a) in (_cycle_days or []) if a > 0]
                if _pay_tuples and _last_dt and _x7_balance_principal > 0:
                    _tail = _pay_tuples[-7:] if len(_pay_tuples) > 7 else _pay_tuples
                    _avg_pay = sum(a for (d, a) in _tail) / len(_tail)

                    _dates = [d for (d, a) in _tail]
                    _avg_gap = 1.0
                    if len(_dates) >= 2:
                        _gaps = []
                        for i in range(1, len(_dates)):
                            try:
                                g = (_dates[i] - _dates[i-1]).days
                            except Exception:
                                g = 0
                            if g > 0:
                                _gaps.append(g)
                        if _gaps:
                            _avg_gap = sum(_gaps) / len(_gaps)

                    _avg_gap = max(1.0, float(_avg_gap))
                    _interest_per_payment = float(_x7_daily_interest) * _avg_gap
                    _surplus = float(_avg_pay) - _interest_per_payment

                    # include unpaid interest arrears because it eats the next surplus first
                    _need_amt = float(_x7_balance_principal) + float(_x7_interest_arrears_end or 0.0)

                    if _surplus > 0:
                        _need = int(_math7.ceil(_need_amt / _surplus))
                        _est_days = int(_math7.ceil(_avg_gap * _need))
                        _est = _last_dt + _td_soapatch(days=_est_days)
                        _x7_due_label = f"Est. {_est.strftime('%Y-%m-%d')}"
            except Exception as __spina_exc:
                _log_suppressed_once('excpass_0602', 'suppressed exception excpass_0602', __spina_exc)
                pass

    try:
        if is_7x7 and principal > 0:
            _hdr_interest_amt = round(max(0.0, float(_x7_interest_paid_cycle or 0.0)), 2)
            _hdr_balance_amt = round(max(0.0, float(_x7_balance_principal or 0.0)), 2)
        else:
            _hdr_interest_amt = round(max(0.0, float(interest or 0.0)), 2)
            _hdr_balance_amt = round(max(0.0, float(total_to_pay or 0.0) - float(total_paid_cycle or 0.0)), 2)
    except Exception:
        _hdr_interest_amt = round(max(0.0, float(interest or 0.0)), 2)
        _hdr_balance_amt = round(max(0.0, float(total_to_pay or 0.0) - float(total_paid_cycle or 0.0)), 2)

    # Normalize entries and group by month
    norm = []
    for r in rows:
        try:
            dt = _dt_soapatch.strptime(str(_gv(r,'date','') or '')[:10], "%Y-%m-%d").date()
        except Exception:
            continue
        amt = float(_gv(r,'payment',0) or 0)
        dsc = (_gv(r,'description','') or '').strip()
        norm.append((dt, amt, dsc))
    norm.sort(key=lambda x: x[0])

    # Resolve page size for Report (A4/Letter/Folio/Legal)
    _ps = _A4_soapatch
    try:
        _lbl = (page_size_name or 'A4').strip()
    except Exception:
        _lbl = 'A4'
    _u = str(_lbl).upper()
    if _u.startswith('LETTER'):
        _ps = _LETTER_soapatch
    elif _u.startswith('LEGAL'):
        _ps = _LEGAL_soapatch
    elif _u.startswith('FOLIO') or '8.5 X 13' in _u or '8 X 13' in _u or 'LONG' in _u:
        # PH long bond (8.5 x 13)
        _ps = (8.5*_inch_soapatch, 13*_inch_soapatch)
    c = _cv_soapatch.Canvas(out_path, pagesize=_ps)
    width, height = _ps
    margin = 28
    inner_w = width - 2*margin
    y = height - margin

    # Title
    base_font = globals().get("_PDF_FONT_BASE","Helvetica")
    bold_font = globals().get("_PDF_FONT_BOLD","Helvetica-Bold")
    def _safe(s):
        try:
            s = str(s)
        except Exception:
            s = ""
        # Avoid broken glyphs/question marks in ReportLab Helvetica.
        # Collector Route uses narrow boxes, so keep separators simple ASCII.
        try:
            s = (s.replace("\u2022", "-")
                   .replace("\u2219", "-")
                   .replace("\u00b7", "-")
                   .replace("\u2013", "-")
                   .replace("\u2014", "-")
                   .replace("\u2010", "-"))
        except Exception:
            pass
        try:
            s.encode("latin-1")
            return s
        except Exception:
            try:
                return s.encode("latin-1","replace").decode("latin-1")
            except Exception:
                return str(s)

    # Logo
    logo = globals().get("LOGO_FILENAME","logo.png")
    if isinstance(logo, str):
        import os as _os
        if _os.path.exists(logo):
            try:
                c.drawImage(logo, margin+4, y-58, width=96, height=46, preserveAspectRatio=True, mask='auto')
            except Exception as __spina_exc:
                _log_suppressed_once('excpass_0603', 'suppressed exception excpass_0603', __spina_exc)
                pass

    c.setFont(bold_font, 12); c.setFillColorRGB(0,0,0)
    c.drawString(margin+112, y-16, _safe("SPINA"))
    c.setFont(base_font, 9); c.setFillColorRGB(0,0,0)
    c.drawString(margin+112, y-31, _safe(f"Client Statement of Account ({_display_loan_type_label(loan_type)})"))
    c.setStrokeColorRGB(0,0,0); c.setLineWidth(1.4)
    c.line(margin, y-42, width-margin, y-42)
    y -= 56
    c.setFillColorRGB(0,0,0)

    # Period / client info header (clean aligned grid)
    try:
        s_disp = _dt_soapatch.strptime(start_date, "%Y-%m-%d").strftime("%B %d, %Y")
        e_disp = _dt_soapatch.strptime(end_date, "%Y-%m-%d").strftime("%B %d, %Y")
    except Exception:
        s_disp, e_disp = start_date, end_date

    try:
        area_raw = str(info.get('area', '') or '')
    except Exception:
        area_raw = ''
    try:
        from datetime import datetime as _dt
        _sd = _dt.strptime(start_date, "%Y-%m-%d").date()
        _ed = _dt.strptime(end_date, "%Y-%m-%d").date()
        days_count = (_ed - _sd).days + 1
    except Exception:
        days_count = None

    try:
        contact_raw = str(info.get('contact_number', '') or info.get('contact', '') or info.get('contact_no', '') or '').strip()
    except Exception:
        contact_raw = ''

    try:
        _term_hdr = str(info.get('payment_term') or 'Daily').strip() or 'Daily'
    except Exception:
        _term_hdr = 'Daily'
    try:
        _mode_hdr = str(info.get('payment_mode') or 'Cash').strip() or 'Cash'
    except Exception:
        _mode_hdr = 'Cash'
    try:
        _day_due_hdr, _due_today_hdr = _spina__client_due_meta(info, as_of=end_date)
    except Exception:
        _day_due_hdr, _due_today_hdr = ('', False)
    def _hdr_php(_v):
        try:
            return f"PHP {float(_v):,.2f}"
        except Exception:
            return "PHP 0.00"
    try:
        _pay_amt_hdr = _hdr_php(info.get('payment_amount') or 0)
    except Exception:
        _pay_amt_hdr = _hdr_php(0)
    try:
        # Use the normalized cycle start so the PDF matches the client-side
        # Start of Payment computation even when a stale payment_start_date exists.
        _start_hdr = _cycle_start or ''
    except Exception:
        _start_hdr = _cycle_start or ''
    try:
        _due_date_hdr = (str(info.get('due_date') or '')[:10]).strip()
    except Exception:
        _due_date_hdr = ''

    try:
        _client_picture_rel = str(info.get('client_picture') or '').strip()
    except Exception:
        _client_picture_rel = ''
    if not _client_picture_rel:
        try:
            _client_picture_rel = str(db.get_client_picture(client_name, loan_type=loan_type, include_archived=True) or '').strip()
        except Exception:
            _client_picture_rel = ''
    try:
        _client_picture_abs = _spina__resolve_app_path(_client_picture_rel) if _client_picture_rel else ''
    except Exception:
        _client_picture_abs = ''
    try:
        _has_client_picture = bool(_client_picture_abs and os.path.exists(_client_picture_abs))
    except Exception:
        _has_client_picture = False

    info_top = y
    box_top = info_top + 6
    box_h = 116
    c.setLineWidth(0.8)
    c.roundRect(margin, box_top - box_h, inner_w, box_h, 6, stroke=1, fill=0)

    label_size = 9
    value_size = 9
    row_gap = 12
    col_gap = 14
    left_x = margin + 10
    _pic_gap = 12 if _has_client_picture else 0
    _pic_w = 82 if _has_client_picture else 0
    text_inner_w = inner_w - 20 - _pic_gap - _pic_w
    col_w = (text_inner_w - col_gap) / 2.0
    right_x = left_x + col_w + col_gap

    def _draw_kv(x, y0, label, value, max_w):
        label = str(label or '').strip()
        value = str(value or '-').strip() or '-'
        lab = f"{label} "
        c.setFont(bold_font, label_size)
        c.drawString(x, y0, _safe(lab))
        lab_w = stringWidth(lab, bold_font, label_size)
        val_w = max(40, max_w - lab_w)
        lines = _wrap_to_width(value, base_font, value_size, val_w) or ['-']
        c.setFont(base_font, value_size)
        c.drawString(x + lab_w, y0, _safe(lines[0]))
        yy = y0
        for extra in lines[1:]:
            yy -= (value_size + 2)
            c.drawString(x + lab_w, yy, _safe(extra))
        return len(lines)

    def _draw_pair(y0, left_label, left_val, right_label='', right_val=''):
        ll = _draw_kv(left_x, y0, left_label, left_val, col_w)
        rr = 1
        if str(right_label).strip() or str(right_val).strip():
            rr = _draw_kv(right_x, y0, right_label, right_val, col_w)
        return y0 - max(ll, rr) * row_gap

    if _has_client_picture:
        try:
            from reportlab.lib.utils import ImageReader as _ImageReader_soapatch
            _pic_box_x = margin + inner_w - 10 - _pic_w
            _pic_box_y = box_top - box_h + 10
            _pic_box_h = box_h - 20
            c.setLineWidth(0.6)
            c.roundRect(_pic_box_x, _pic_box_y, _pic_w, _pic_box_h, 4, stroke=1, fill=0)
            _img_reader = _ImageReader_soapatch(_client_picture_abs)
            _img_w, _img_h = _img_reader.getSize()
            _fit_w = max(1.0, float(_pic_w - 6))
            _fit_h = max(1.0, float(_pic_box_h - 6))
            if _img_w and _img_h:
                _scale = min(_fit_w / float(_img_w), _fit_h / float(_img_h))
                _draw_w = max(1.0, float(_img_w) * _scale)
                _draw_h = max(1.0, float(_img_h) * _scale)
            else:
                _draw_w, _draw_h = _fit_w, _fit_h
            _draw_x = _pic_box_x + ((_pic_w - _draw_w) / 2.0)
            _draw_y = _pic_box_y + ((_pic_box_h - _draw_h) / 2.0)
            c.drawImage(_img_reader, _draw_x, _draw_y, width=_draw_w, height=_draw_h, mask='auto')
        except Exception as __spina_exc:
            _log_suppressed_once('excpass_client_picture_pdf_001', 'suppressed exception excpass_client_picture_pdf_001', __spina_exc)
            pass

    info_y = info_top - 12
    info_y = _draw_pair(info_y, 'Client:', client_name, 'Period:', f'{s_disp} to {e_disp}')
    info_y = _draw_pair(info_y, 'Area:', area_raw or '-', 'Days:', str(days_count) if days_count is not None else '-')
    info_y = _draw_pair(info_y, 'Loan Type:', _display_loan_type_label(loan_type), 'Contact:', contact_raw or '-')
    info_y = _draw_pair(info_y, 'Payment Term:', _term_hdr, 'Payment Amount:', _pay_amt_hdr)
    info_y = _draw_pair(info_y, 'Principal:', _hdr_php(principal), 'Interest:', _hdr_php(_hdr_interest_amt))
    info_y = _draw_pair(info_y, 'Balance:', _hdr_php(_hdr_balance_amt), 'Mode:', _mode_hdr)
    info_y = _draw_pair(info_y, 'Day Due:', _day_due_hdr or '-', 'Start of Payment:', _start_hdr or '-')
    info_y = _draw_pair(info_y, 'Due Date:', _due_date_hdr or '-', '', '')
    _also_parts = []
    if has_reg:
        _also_parts.append('Regular [X]')
    else:
        _also_parts.append('Regular [ ]')
    if has_x7:
        _also_parts.append('7x7 [X]')
    else:
        _also_parts.append('7x7 [ ]')
    info_y = _draw_pair(info_y, 'Also has:', '   '.join(_also_parts), '', '')

    y = box_top - box_h - 8

    # restore default header font size
    try:
        c.setFont(base_font, 10)
    except Exception as __spina_exc:
        _log_suppressed_once('excpass_0611', 'suppressed exception excpass_0611', __spina_exc)
        pass

    # "Also has" footer disabled (replaced by header checkboxes)
    also_txt = ""

    def _draw_also_footer():
        """Draw small footer note (subtle) on the current page."""
        if not also_txt:
            return
        try:
            c.saveState()
            try:
                c.setFillColorRGB(0.35, 0.35, 0.35)
            except Exception as __spina_exc:
                _log_suppressed_once('excpass_0612', 'suppressed exception excpass_0612', __spina_exc)
                pass
            try:
                c.setFont(base_font, 6)
            except Exception:
                c.setFont(base_font, 6)
            c.drawRightString(width - margin, 12, _safe(also_txt))
            c.restoreState()
        except Exception:
            try:
                c.restoreState()
            except Exception as __spina_exc:
                _log_suppressed_once('excpass_0613', 'suppressed exception excpass_0613', __spina_exc)
                pass

    y -= 10; c.line(margin, y, width-margin, y)


    # Notes are drawn later near the bottom, after Total Payment.


    # When Renew (compact top line)
    y -= 8
    def _php(x):
        try:
            return f"PHP {float(x):,.2f}"
        except Exception:
            return "PHP 0.00"

    try:
        if is_7x7 and principal > 0:
            # Match the Renew dialog: compute from the TRUE current-cycle
            # Start of Payment up to the PDF end date, not just the visible
            # report period. This fixes wrong renew/cash-out amounts when the
            # report start date was typed manually or when payment starts next day.
            try:
                _wr_start_dt = _dt_soapatch.strptime(str(_cycle_start or start_date)[:10], "%Y-%m-%d").date()
            except Exception:
                _wr_start_dt = None
            try:
                _wr_end_dt = _dt_soapatch.strptime(str(end_date)[:10], "%Y-%m-%d").date()
            except Exception:
                _wr_end_dt = None

            _wr_days = 0
            if _wr_start_dt and _wr_end_dt:
                try:
                    _wr_days = max(0, int((_wr_end_dt - _wr_start_dt).days) + 1)
                except Exception:
                    _wr_days = 0
            if _wr_days <= 0:
                try:
                    _wr_days = max(0, len(_per_day_effective_payments(cycle_rows) or []))
                except Exception:
                    _wr_days = 0

            try:
                _wr_di = round(max(0.0, float(_x7_daily_interest_for_principal(principal))), 2)
            except Exception:
                _wr_di = round(max(0.0, float(_x7_daily_interest or 0.0)), 2)

            try:
                _wr_total = round(max(0.0, float(total_paid_cycle or 0.0)), 2)
            except Exception:
                _wr_total = round(max(0.0, float(total_paid_all or 0.0)), 2)

            _wr_interest_due = round(max(0.0, float(_wr_days) * float(_wr_di)), 2)
            _wr_interest_paid = round(min(float(_wr_total), float(_wr_interest_due)), 2)
            _wr_cash_out = round(max(0.0, float(_wr_total) - float(_wr_interest_due)), 2)
            try:
                _wr_cash_out = round(min(float(principal or 0.0), float(_wr_cash_out)), 2)
            except Exception:
                pass

            try:
                _wr_start_label = _wr_start_dt.strftime("%Y-%m-%d") if _wr_start_dt else str(_cycle_start or start_date)[:10]
            except Exception:
                _wr_start_label = str(_cycle_start or start_date)[:10]
            try:
                _wr_end_label = _wr_end_dt.strftime("%Y-%m-%d") if _wr_end_dt else str(end_date)[:10]
            except Exception:
                _wr_end_label = str(end_date)[:10]

            _wr_text = (
                f"{_php(_wr_cash_out)} = Total Payment {_php(_wr_total)} "
                f"Less Interest Due {_php(_wr_interest_due)} "
                f"({_wr_days} day(s) x {_php(_wr_di)}; cycle {_wr_start_label} to {_wr_end_label})"
            )
        else:
            # Regular renew/cash-out computation.
            # Business rule for fixed-interest Regular loans:
            #   1) Payments first cover the fixed interest for the current cycle.
            #   2) Only the excess after fixed interest is treated as principal paid / releasable cash.
            #   3) Do not release more than the current principal.
            # This avoids the confusing old display "Principal - Balance" and makes the PDF
            # match the actual Regular loan cycle computation.
            _wr_total = round(max(0.0, float(total_paid_cycle or 0.0)), 2)
            _wr_ttp = round(max(0.0, float(total_to_pay or 0.0)), 2)
            _wr_balance = round(max(0.0, float(_wr_ttp) - float(_wr_total)), 2)

            try:
                _wr_fixed_interest = round(max(0.0, float(interest or 0.0)), 2)
            except Exception:
                _wr_fixed_interest = 0.0
            try:
                # Legacy safety: if interest_amount is blank but total_to_pay contains interest, derive it.
                if _wr_fixed_interest <= 0 and _wr_ttp > float(principal or 0.0):
                    _wr_fixed_interest = round(max(0.0, _wr_ttp - float(principal or 0.0)), 2)
            except Exception:
                pass

            _wr_principal_paid = round(max(0.0, float(_wr_total) - float(_wr_fixed_interest)), 2)
            try:
                _wr_cash_out = round(min(float(principal or 0.0), float(_wr_principal_paid)), 2)
            except Exception:
                _wr_cash_out = round(max(0.0, float(_wr_principal_paid or 0.0)), 2)

            _wr_text = (
                f"{_php(_wr_cash_out)} = Total Payment {_php(_wr_total)} - Fixed Interest {_php(_wr_fixed_interest)} "
                f"(Balance {_php(_wr_balance)} / Total {_php(_wr_ttp)})"
            )
    except Exception:
        _wr_text = '-'

    c.saveState()
    try:
        c.setFillColorRGB(0.75, 0.0, 0.0)
    except Exception:
        pass
    c.setFont(bold_font, 9)
    c.drawString(margin, y, _safe('When Renew:'))
    c.setFont(base_font, 9)
    _wr_lines = _wrap_to_width(_wr_text, base_font, 9, max(80, inner_w - 78)) or ['-']
    _wr_y = y
    for _i, _ln in enumerate(_wr_lines):
        c.drawString(margin + 72, _wr_y, _safe(_ln))
        _wr_y -= 10
    c.restoreState()
    y = _wr_y - 1
    c.line(margin, y, width-margin, y)
    y -= 8

    # History layout (three month columns with tighter, cleaner wrapping)
    HISTORY_COLS = 3
    HISTORY_COL_GAP = 14
    history_col_w = (inner_w - HISTORY_COL_GAP * (HISTORY_COLS - 1)) / float(HISTORY_COLS)
    history_x = [margin + i * (history_col_w + HISTORY_COL_GAP) for i in range(HISTORY_COLS)]
    date_font_size = 8.5
    pay_font_size = 8.5
    date_w = max(34, stringWidth('Sep 30', base_font, date_font_size) + 6)
    pay_w = max(56, history_col_w - date_w - 8)
    line_h = 9
    row_pad = 3

    page_no = 1
    def _page_no_draw():
        nonlocal page_no
        c.setFont(base_font, 9)
        c.drawRightString(width - margin, margin - 10, f"Page {page_no}")
        page_no += 1

    def _draw_official_report_footer():
        """Draw a small, subtle official-version label and daily Generate Report counter at the bottom.

        This footer is intentionally NOT styled like the big notes section. It is only a quiet
        authenticity/count marker near the bottom of the page.
        """
        try:
            _cnt = _official_report_count if isinstance(_official_report_count, dict) else {}
            _gen_date = str(_cnt.get('date') or date.today().strftime('%Y-%m-%d'))
            _gen_at = str(_cnt.get('generated_at') or datetime.now().strftime('%Y-%m-%d %I:%M %p'))
            try:
                _daily_total = int(_cnt.get('daily_total') or 1)
            except Exception:
                _daily_total = 1
            try:
                _client_count = int(_cnt.get('client_daily_count') or 1)
            except Exception:
                _client_count = 1

            c.saveState()
            try:
                c.setFillColorRGB(0.35, 0.35, 0.35)  # subtle gray, not attention-grabbing
                c.setStrokeColorRGB(0.70, 0.70, 0.70)
                c.setLineWidth(0.35)
            except Exception:
                pass

            # Thin separator only; no colored box/background.
            _footer_y = margin + 18
            try:
                c.line(margin, _footer_y + 10, margin + inner_w, _footer_y + 10)
            except Exception:
                pass

            c.setFont(base_font, 6.8)
            _line = (
                f"Official SPINA Generated Report • Generated today: {_daily_total} overall "
                f"• This client/report today: {_client_count} • {_gen_date} • {_gen_at}"
            )
            _lines = _wrap_to_width(_line, base_font, 6.8, max(80, inner_w - 10)) or [_line]
            _yy = _footer_y
            for _ln in _lines[:2]:
                c.drawCentredString(margin + (inner_w / 2.0), _yy, _safe(_ln))
                _yy -= 7
            c.restoreState()
        except Exception as __spina_exc:
            try:
                c.restoreState()
            except Exception:
                pass
            _log_suppressed_once('excpass_official_report_footer', 'suppressed exception official report footer', __spina_exc)

    # Group by month/year
    from itertools import groupby as _groupby
    norm.sort(key=lambda x: (x[0].year, x[0].month, x[0].day))

    try:
        _sd_bound = _dt_soapatch.strptime(start_date, "%Y-%m-%d").date()
        _ed_bound = _dt_soapatch.strptime(end_date,   "%Y-%m-%d").date()
        if _ed_bound < _sd_bound:
            _sd_bound, _ed_bound = _ed_bound, _sd_bound
    except Exception:
        _sd_bound, _ed_bound = None, None

    if _sd_bound and _ed_bound:
        try:
            _yy, _mm = _sd_bound.year, _sd_bound.month
            while (_yy, _mm) <= (_ed_bound.year, _ed_bound.month):
                if not any((d.year == _yy and d.month == _mm) for (d, _a, _s) in norm):
                    norm.append((_date_soapatch(_yy, _mm, 1), 0.0, ""))
                _mm += 1
                if _mm >= 13:
                    _mm = 1
                    _yy += 1
            norm.sort(key=lambda x: (x[0].year, x[0].month, x[0].day))
        except Exception as __spina_exc:
            _log_suppressed_once('excpass_0616', 'suppressed exception excpass_0616', __spina_exc)
            pass

    def _payment_text_from_flag(f):
        pieces = []
        if f.get('adv'):
            _po = []
            try:
                _raw = f.get('adv_paid_on', None)
                if isinstance(_raw, (set, list, tuple)):
                    _po = [str(x).strip() for x in _raw if str(x).strip()]
                elif _raw:
                    _po = [str(_raw).strip()]
            except Exception:
                _po = []
            _short = []
            for _d in sorted(set([x for x in _po if x])):
                try:
                    _short.append(_dt_soapatch.strptime(str(_d)[:10], '%Y-%m-%d').strftime('%b %d'))
                except Exception:
                    _short.append(str(_d)[:10])
            if len(_short) > 2:
                adv_txt = 'Adv(' + ', '.join(_short[:2]) + ', +%d)' % (len(_short) - 2)
            elif _short:
                adv_txt = 'Adv(' + ', '.join(_short) + ')'
            else:
                adv_txt = 'Adv'
            pieces.append(adv_txt)
        if f.get('paid'):
            try:
                pieces.append(f"PHP {float(f['paid']):,.2f}")
            except Exception:
                pieces.append(str(f.get('paid')))
        if f.get('reason'):
            pieces.append(str(f.get('reason')))
        return ' - '.join([p for p in pieces if str(p).strip()])

    def _build_month_entries(yr, mo, items):
        month_start = _date_soapatch(yr, mo, 1)
        if mo == 12:
            month_end = _date_soapatch(yr+1, 1, 1) - _td_soapatch(days=1)
        else:
            month_end = _date_soapatch(yr, mo+1, 1) - _td_soapatch(days=1)
        flags = _collect_day_flags_for_month(
            [{'date': d.strftime('%Y-%m-%d'), 'payment': a, 'description': s} for (d,a,s) in items],
            month_start, month_end
        )
        try:
            s_bound = max(month_start, _sd_bound) if _sd_bound else month_start
            e_bound = min(month_end,  _ed_bound) if _ed_bound else month_end
        except Exception:
            s_bound, e_bound = month_start, month_end
        if s_bound > e_bound:
            return []
        entries = []
        for d in _daterange_inclusive(s_bound, e_bound):
            f = flags.get(d, {})
            payment_text = _payment_text_from_flag(f)
            wrap = _wrap_to_width(payment_text, base_font, pay_font_size, max(52, pay_w)) if payment_text else ['']
            wrap = wrap or ['']
            row_h = max(12, len(wrap) * line_h + row_pad)
            entries.append((d.strftime('%b %d'), wrap, row_h))
        return entries

    def _draw_month_block(month_text, entries):
        nonlocal y
        if not entries:
            return
        import math as _math
        split_at = int(_math.ceil(len(entries) / float(max(1, HISTORY_COLS))))
        cols = [entries[i * split_at:(i + 1) * split_at] for i in range(HISTORY_COLS)]
        col_heights = []
        for col in cols:
            h = 18
            for _d, _lines, _rh in col:
                h += _rh
            col_heights.append(h)
        block_h = 18 + max(col_heights or [0]) + 8
        if y - block_h < margin + 82:
            _page_no_draw(); c.showPage(); y = height - margin
            c.setFillColorRGB(0,0,0)
        c.setFont(bold_font, 11)
        c.drawString(margin, y, _safe(month_text))
        c.setLineWidth(0.6)
        c.line(margin, y - 4, margin + inner_w, y - 4)
        y_top = y - 16
        bottom_candidates = []
        for idx, col in enumerate(cols):
            if idx >= len(history_x):
                break
            if not col:
                bottom_candidates.append(y_top - 16)
                continue
            x = history_x[idx]
            c.setFont(bold_font, 8.5)
            c.drawString(x, y_top, _safe('Date'))
            c.drawString(x + date_w + 4, y_top, _safe('Payment'))
            c.setLineWidth(0.4)
            c.line(x, y_top - 4, x + history_col_w, y_top - 4)
            row_y = y_top - 14
            for dlabel, wrapped, rh in col:
                c.setFont(base_font, date_font_size)
                c.drawString(x, row_y, _safe(dlabel))
                text_y = row_y
                c.setFont(base_font, pay_font_size)
                for ln in wrapped:
                    c.drawString(x + date_w + 4, text_y, _safe(ln))
                    text_y -= line_h
                row_y -= rh
            bottom_candidates.append(row_y)
        y = (min(bottom_candidates) if bottom_candidates else y_top) - 2
        c.setLineWidth(0.4)
        c.line(margin, y, margin + inner_w, y)
        y -= 6

    for (yr, mo), grp in _groupby(norm, key=lambda x: (x[0].year, x[0].month)):
        items = list(grp)
        month_text = _dt_soapatch(yr, mo, 1).strftime('%B %Y')
        _entries = _build_month_entries(yr, mo, items)
        _draw_month_block(month_text, _entries)

    if is_7x7 and principal > 0:
        y -= 4

        def _x7_units_ceil(_bal):
            try:
                b = float(_bal or 0.0)
            except Exception:
                b = 0.0
            if b <= 0:
                return 0
            try:
                return int((b + 999.999999) // 1000)
            except Exception:
                return 0

        _start_units = _x7_units_ceil(principal)
        if _start_units < 1:
            _start_units = 1
        _end_units = _x7_units_ceil(_x7_balance_principal)
        _min_units = max(1, _end_units) if _end_units > 0 else 1
        if _min_units > _start_units:
            _min_units = _start_units

        _units_list = list(range(_start_units, _min_units - 1, -1))
        _MAX_ROWS = 12
        if len(_units_list) > _MAX_ROWS:
            _top = _units_list[:6]
            _bottom = _units_list[-5:]
            _units_list = _top + [-1] + _bottom

        _ip_by_u = {u: 0.0 for u in _units_list if isinstance(u, int) and u > 0}
        _last_bal_by_u = {u: None for u in _units_list if isinstance(u, int) and u > 0}

        for _d, _amt, _ip, _pp, _gap, _arr, _remv in (_cycle_splits or []):
            if _r_start_dt and _r_end_dt:
                try:
                    if not (_r_start_dt <= _d <= _r_end_dt):
                        continue
                except Exception as __spina_exc:
                    _log_suppressed_once('excpass_0618_readd', 'suppressed exception excpass_0618_readd', __spina_exc)
                    pass

            try:
                _rem_before = float(_remv or 0.0) + float(_pp or 0.0)
            except Exception:
                try:
                    _rem_before = float(_remv or 0.0)
                except Exception:
                    _rem_before = 0.0

            _u = _x7_units_ceil(_rem_before)
            if _u in _ip_by_u:
                _ip_by_u[_u] += float(_ip or 0.0)
                try:
                    _last_bal_by_u[_u] = float(_remv or 0.0)
                except Exception:
                    _last_bal_by_u[_u] = _remv

        # 7x7 compact summary only (table removed by request)
        try:
            _summary_h = 28
            if y - _summary_h < margin + 45:
                _page_no_draw(); c.showPage(); y = height - margin
                c.setFillColorRGB(0,0,0)
        except Exception as __spina_exc:
            _log_suppressed_once('excpass_0619_readd', 'suppressed exception excpass_0619_readd', __spina_exc)
            pass

        y -= 8
        c.setFont(bold_font, 9)
        c.drawString(margin, y, _safe('7x7 Daily Interest:'))
        c.drawRightString(margin + inner_w, y, _safe(_php(_x7_daily_interest)))
        y -= 12

    # Bottom total + notes on last page
    y -= 6
    if y < 86:
        _page_no_draw(); c.showPage(); y = height - margin
        c.setFillColorRGB(0,0,0)
    c.setLineWidth(0.6)
    c.line(margin, y, margin + inner_w, y)
    y -= 8
    c.setFont(bold_font, 10)
    c.drawString(margin, y, _safe("Total Payment:"))
    c.drawRightString(margin + inner_w, y, _safe(_php(total_paid_all)))
    y -= 6

    def _estimate_note_block_h(_note, _max_w, _font, _size=9, _leading=11, _label='Note:'):
        try:
            _label_w = stringWidth(_label, _font, _size)
            _gap = 6
            _x_text = _label_w + _gap
            _date_col_w = stringWidth('0000-00-00', _font, _size) + 6
            _text_col_w = max(60, _max_w - _x_text - _date_col_w)
            _count = 0
            for _raw in (str(_note or '').splitlines() or []):
                _raw = str(_raw or '').strip()
                if not _raw:
                    continue
                if ':' in _raw and _raw[:10].count('-') == 2:
                    _, _rest = _raw.split(':', 1)
                    _rest = _rest.strip()
                else:
                    _rest = _raw
                _wrapped = _wrap_to_width(_rest, _font, _size, _text_col_w) or ['']
                _count += max(1, len(_wrapped))
            if _count <= 0:
                _count = 1
            return 22 + (_count * _leading) + 8
        except Exception:
            return 54

    if note_text:
        try:
            # Bigger, more visible report notes block.
            # Keep it near the bottom after Total Payment, but make it stand out for collectors/clients.
            _note_body_size = 15
            _note_leading = 20
            _note_label = 'PLEASE READ:'
            _note_box_h = _estimate_note_block_h(note_text, inner_w - 28, bold_font, _note_body_size, _note_leading, _note_label) + 64
            if y - _note_box_h < margin + 92:
                _page_no_draw(); c.showPage(); y = height - margin
                c.setFillColorRGB(0,0,0)
            _note_top = y

            c.saveState()
            # Light warning background + thicker red border so notes are easy to notice.
            try:
                c.setFillColorRGB(1.0, 0.995, 0.82)
                c.rect(margin, _note_top - _note_box_h, inner_w, _note_box_h, stroke=0, fill=1)
                c.setStrokeColorRGB(0.75, 0.0, 0.0)
                c.setLineWidth(2.4)
            except Exception:
                c.setLineWidth(2.0)
            c.rect(margin, _note_top - _note_box_h, inner_w, _note_box_h, stroke=1, fill=0)

            try:
                c.setFillColorRGB(0.75, 0.0, 0.0)
            except Exception:
                pass
            c.setFont(bold_font, 18)
            c.drawCentredString(margin + (inner_w / 2), _note_top - 22, _safe('VERY IMPORTANT NOTES'))
            c.setLineWidth(0.8)
            c.line(margin + 10, _note_top - 32, margin + inner_w - 10, _note_top - 32)

            try:
                c.setFillColorRGB(0.0, 0.0, 0.0)
            except Exception:
                pass
            _note_y = _note_top - 54
            _note_y = draw_notes_aligned(
                c,
                x_label=margin + 14,
                y=_note_y,
                max_w=inner_w - 28,
                note_text=note_text,
                font=bold_font,
                size=_note_body_size,
                leading=_note_leading,
                label=_note_label
            )
            c.restoreState()
            y = _note_top - _note_box_h - 10
        except Exception as __spina_exc:
            _log_suppressed_once('excpass_0614b', 'suppressed exception excpass_0614b', __spina_exc)
            pass

    # Reserve bottom space for signature + subtle official-version footer.
    if y < margin + 82:
        _page_no_draw(); c.showPage(); y = height - margin
        c.setFillColorRGB(0,0,0)

    # --- Signatures / official footer / finalize PDF (both Regular and 7x7) ---
    c.setFont(base_font, 10)
    c.drawString(margin, y, _safe("Prepared by: ___________________________"))
    c.drawString(margin + inner_w/2 + 20, y, _safe("Checked by: ___________________________"))
    try:
        _draw_official_report_footer()
    except Exception as __spina_exc:
        _log_suppressed_once('excpass_official_report_footer_call', 'suppressed exception official report footer call', __spina_exc)
        pass
    _page_no_draw()
    try:
        _draw_also_footer()
    except Exception as __spina_exc:
        _log_suppressed_once('excpass_0622', 'suppressed exception excpass_0622', __spina_exc)
        pass
    c.save()

# Replace original generator with patched one
# ==== END: SOA ADV/RANGE RENDERING PATCH ====
