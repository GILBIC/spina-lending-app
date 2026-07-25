'Pure PostgreSQL compatibility helpers extracted in Wave 34.'
from __future__ import annotations

_POSTGRES_COMPAT_DEPENDENCIES = {}
_PROTECTED_GLOBALS = {
    "__builtins__", "__cached__", "__doc__", "__file__", "__loader__",
    "__name__", "__package__", "__spec__", "_POSTGRES_COMPAT_DEPENDENCIES",
    "_PROTECTED_GLOBALS", "configure_postgres_compat_dependencies",
    "POSTGRES_COMPAT_SOURCE_SHA256",
}


def configure_postgres_compat_dependencies(namespace):
    _POSTGRES_COMPAT_DEPENDENCIES.clear()
    _POSTGRES_COMPAT_DEPENDENCIES.update(namespace)
    for name, value in namespace.items():
        if name not in _PROTECTED_GLOBALS:
            globals()[name] = value


POSTGRES_COMPAT_SOURCE_SHA256 = {
    "_spina_pg_escape_literal_percents": "e6c3cf7667cefad7b7c301189c5513f6d8b7f6fb232be23a9ee9314aa43a7a11",
    "_spina_pg_guess_collector": "f27b107fc5529bba73e68c249be14d9f03757114d2ff94af47dd3b56555fa5da",
    "_spina_pg_guess_file_type": "4c5ae58cc1c8958be489de35470a4dde256c158fc3f007b364bbffa874b45a04",
    "_spina_pg_guess_report_date": "bcfdf7e9c2366e7d376ee55a8757f78cd3b75c3e867e87f7c3ff76bdef86c291",
    "_spina_pg_normalize_value": "a3d32820748ce7d3b8f8cc40563d75e759b005cdcbff6311a5e8c907efbb4ad0",
    "_spina_pg_replace_qmarks": "444266c36ffc8188f5fe242e25ca37a3d0a09730d76fc25eae07d71030245859",
    "_spina_pg_sha256": "cb67c3f2ff0ca8599ff47ef9cd24f4184061c97c1ddb6418016ea218bb0b2c8f"
}

def _spina_pg_sha256(data: bytes) -> str:
    import hashlib
    return hashlib.sha256(data).hexdigest()

def _spina_pg_guess_file_type(path):
    try:
        rp = _spina_pg_relpath(path).lower()
        name = os.path.basename(str(path or '')).lower()
        ext = os.path.splitext(name)[1].lower()
        if ext == '.pdf':
            if 'closed_collector_routes' in rp or 'closed collector routes' in rp:
                return 'closed_collector_route_pdf'
            if 'collectorroute' in name or 'collector route' in name:
                return 'collector_route_pdf'
            if 'audit' in rp or 'audit' in name:
                return 'audit_pdf'
            if 'renew' in rp or 'renew' in name:
                return 'renewal_pdf'
            return 'client_report_pdf'
        if ext in ('.png', '.jpg', '.jpeg', '.webp', '.bmp', '.gif'):
            if name.startswith('logo'):
                return 'logo_image'
            return 'client_picture_or_image'
        return 'other'
    except Exception:
        return 'other'

def _spina_pg_guess_report_date(path):
    try:
        import re
        from datetime import date as _date
        name = os.path.basename(str(path or ''))
        m = re.search(r'(20\d{2})[-_](\d{2})[-_](\d{2})', name)
        if not m:
            return None
        return _date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
    except Exception:
        return None

def _spina_pg_guess_collector(path):
    try:
        import re
        name = os.path.basename(str(path or ''))
        m = re.search(r'CollectorRoute[_\s-]+(.+?)[_\s-]+20\d{2}[-_]\d{2}[-_]\d{2}', name, re.I)
        if not m:
            return None
        return m.group(1).replace('_', ' ').strip() or None
    except Exception:
        return None

def _spina_pg_normalize_value(v):
    """Convert PostgreSQL-returned values into SQLite-like values."""
    try:
        if isinstance(v, _spina_decimal.Decimal):
            return float(v)
    except Exception:
        pass
    return v

def _spina_pg_replace_qmarks(sql: str) -> str:
    """Replace SQLite ? parameters with psycopg %s outside quoted strings."""
    out = []
    in_single = False
    in_double = False
    i = 0
    while i < len(sql):
        ch = sql[i]
        if ch == "'" and not in_double:
            out.append(ch)
            # SQL escaped single quote: ''
            if in_single and i + 1 < len(sql) and sql[i + 1] == "'":
                i += 1
                out.append(sql[i])
            else:
                in_single = not in_single
        elif ch == '"' and not in_single:
            out.append(ch)
            in_double = not in_double
        elif ch == "?" and not in_single and not in_double:
            out.append("%s")
        else:
            out.append(ch)
        i += 1
    return "".join(out)

def _spina_pg_escape_literal_percents(sql: str) -> str:
    """Escape literal percent signs for psycopg while preserving %s/%b/%t placeholders.

    Old SQLite queries commonly contain LIKE '%ADV%' or LIKE '%[RC:%'.
    Psycopg uses %s-style placeholders, so a literal % in the SQL text must be
    doubled as %%. Without this, ADV/reason queries can fail silently inside the
    app's broad try/except blocks.
    """
    try:
        s = str(sql or "")
    except Exception:
        return sql
    out = []
    i = 0
    while i < len(s):
        ch = s[i]
        if ch == "%":
            nxt = s[i + 1] if i + 1 < len(s) else ""
            # Keep psycopg placeholders and existing escaped percent signs.
            if nxt in ("s", "b", "t", "%"):
                out.append("%")
            else:
                out.append("%%")
        else:
            out.append(ch)
        i += 1
    return "".join(out)
