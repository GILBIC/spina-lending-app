"""LoanDB context and read-only area/audit helpers extracted in Wave 33."""
from __future__ import annotations
_LOAN_CONTEXT_DEPENDENCIES={}
_PROTECTED_GLOBALS={"__builtins__","__cached__","__doc__","__file__","__loader__","__name__","__package__","__spec__","_LOAN_CONTEXT_DEPENDENCIES","_PROTECTED_GLOBALS","configure_loan_context_dependencies"}
def configure_loan_context_dependencies(namespace):
    _LOAN_CONTEXT_DEPENDENCIES.clear()
    _LOAN_CONTEXT_DEPENDENCIES.update(namespace)
    for name,value in namespace.items():
        if name not in _PROTECTED_GLOBALS:
            globals()[name]=value

LOAN_CONTEXT_SOURCE_SHA256 = {
    "_effective_lt": "1bc2146699101f4786b2e567c2d9c4798d13eb17a5a383bdad7e5729e9b81bd6",
    "_set_last_error": "95bdf2bcd7562e48bb0d799e062cc4e4edacecb998913f04ef88dc010b8a6112",
    "get_all_areas": "f6f1c6dbfc382a94023c6404ee7d9e2bed0fb6df49f789f3ae7e3bc9483f5754",
    "get_audit_new_loan_rows": "5e10fabbaaf1dc449f14d8d901ffd8eb1dfc4f9fa04fc6b64d42895065068c1f",
    "get_last_error": "01edca045d6ee3cf90d3cf8684f4fc304d9b02d39dba69219461c7eada533a91",
    "set_default_loan_type": "c71854ed8299909dfa3a48a89eeddfef1dbc3ab7881e25e45049ca8f0d3ef9bd"
}

def _set_last_error(self, msg):
        try:
            self._last_error = str(msg or '')
        except Exception:
            self._last_error = ''

def get_last_error(self):
        try:
            return getattr(self, '_last_error', '') or ''
        except Exception:
            return ''

def set_default_loan_type(self, lt):
        """Set the default loan_type context used when caller does not pass loan_type."""
        try:
            self.default_loan_type = self._norm_lt(lt)
        except Exception:
            self.default_loan_type = 'Regular'

def _effective_lt(self, loan_type):
        if loan_type is None:
            return getattr(self, 'default_loan_type', 'Regular')
        return self._norm_lt(loan_type)

def get_audit_new_loan_rows(self, start_date=None, end_date=None, loan_type=None, limit=1000):
        """Return append-only ADD audit rows for new loans."""
        cur = self.conn.cursor()
        lim = max(1, min(int(limit or 1000), 5000))
        lt = self._effective_lt(loan_type) if loan_type else ''
        sql = ["SELECT * FROM client_history WHERE action='ADD'"]
        params = []
        if start_date:
            sql.append("AND date(changed_at) >= date(?)")
            params.append(str(start_date)[:10])
        if end_date:
            sql.append("AND date(changed_at) <= date(?)")
            params.append(str(end_date)[:10])
        if lt:
            sql.append("AND IFNULL(NULLIF(TRIM(loan_type_after),''),'Regular') = IFNULL(NULLIF(TRIM(?),''),'Regular')")
            params.append(lt)
        sql.append("ORDER BY datetime(changed_at) DESC, id DESC LIMIT ?")
        params.append(lim)
        try:
            rows = cur.execute(" ".join(sql), tuple(params)).fetchall()
        except Exception:
            return []

        out = []
        for r in (rows or []):
            try:
                d = dict(r)
            except Exception:
                d = {}
            payload = self._audit_parse_json_payload(d.get('new_json'))
            try:
                date_released = (payload.get('date_released') or '').strip()
            except Exception:
                date_released = ''
            try:
                payment_start_date = (payload.get('payment_start_date') or '').strip()
            except Exception:
                payment_start_date = ''
            if (not payment_start_date) and date_released:
                try:
                    from datetime import datetime, timedelta
                    psod = int(payload.get('pay_start_offset_days') or 0)
                    payment_start_date = (datetime.strptime(date_released[:10], '%Y-%m-%d') + timedelta(days=(1 if psod >= 1 else 0))).strftime('%Y-%m-%d')
                except Exception:
                    payment_start_date = ''
            out.append({
                'ts': d.get('changed_at') or '',
                'client_uid': (d.get('client_uid') or payload.get('client_uid') or '').strip(),
                'person_uid': (payload.get('person_uid') or '').strip() if isinstance(payload, dict) else '',
                'name': (payload.get('name') or d.get('name_after') or '').strip(),
                'loan_type': (payload.get('loan_type') or d.get('loan_type_after') or 'Regular').strip() or 'Regular',
                'date_released': date_released,
                'payment_start_date': payment_start_date,
                'principal': payload.get('principal', 0),
                'area': (payload.get('area') or '').strip(),
                'payment_term': (payload.get('payment_term') or '').strip(),
                'payment_amount': payload.get('payment_amount', 0),
                'source': (d.get('source') or '').strip(),
                'note': (d.get('note') or '').strip(),
                'old_json': d.get('old_json') or '',
                'new_json': d.get('new_json') or '',
            })
        return out

def get_all_areas(self):
        """Return area master list for UI dropdowns.

        Hides areas that are used only by archived clients, but keeps:
        - areas with at least one active client
        - areas with no clients yet (manually-added / still-unused)
        """
        cur = self.conn.cursor()
        try:
            # Robust to older DBs that may not have the archive column yet.
            try:
                cols = [str(r[1]) for r in (cur.execute("PRAGMA table_info(clients)").fetchall() or [])]
            except Exception:
                cols = []
            has_arch = ('is_archived' in cols)

            if has_arch:
                rows = cur.execute(
                    """
                    SELECT a.name
                    FROM areas a
                    LEFT JOIN clients c
                      ON TRIM(IFNULL(c.area,'')) = TRIM(IFNULL(a.name,''))
                    GROUP BY a.name
                    HAVING
                        SUM(CASE WHEN c.id IS NOT NULL AND COALESCE(c.is_archived,0)=0 THEN 1 ELSE 0 END) > 0
                        OR COUNT(c.id) = 0
                    ORDER BY a.name COLLATE NOCASE
                    """
                ).fetchall()
            else:
                rows = cur.execute("SELECT name FROM areas ORDER BY name COLLATE NOCASE").fetchall()

            return [(r["name"] if isinstance(r, sqlite3.Row) else r[0]) for r in (rows or [])]
        except Exception:
            return []
