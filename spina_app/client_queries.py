"""Read-only client query methods extracted from the SPINA desktop application.

Wave 31 keeps these functions byte-for-byte equivalent after dedenting and wires
them back onto ``LoanDB`` immediately after the class definition. Application
globals are supplied explicitly so the extracted methods retain the same helper,
compatibility, logging, and PostgreSQL references as before.
"""

from __future__ import annotations

_CLIENT_QUERY_DEPENDENCIES: dict[str, object] = {}
_PROTECTED_GLOBALS = {
    "__builtins__",
    "__cached__",
    "__doc__",
    "__file__",
    "__loader__",
    "__name__",
    "__package__",
    "__spec__",
    "_CLIENT_QUERY_DEPENDENCIES",
    "_PROTECTED_GLOBALS",
    "configure_client_queries_dependencies",
}


def configure_client_queries_dependencies(namespace: dict[str, object]) -> None:
    """Bind application-owned globals required by the extracted LoanDB methods."""
    _CLIENT_QUERY_DEPENDENCIES.clear()
    _CLIENT_QUERY_DEPENDENCIES.update(namespace)
    module_globals = globals()
    for name, value in namespace.items():
        if name not in _PROTECTED_GLOBALS:
            module_globals[name] = value


# Original dedented source SHA-256 values from the guarded Wave 31 base.
CLIENT_QUERY_SOURCE_SHA256 = {
    "find_clients_by_person_uid": "853d18b473c58c7a267139b9f32c9512860bccabb2839a14fa9a80319b8392ea",
    "get_all_clients": "b17c794fb32b23ce1f1bc123ec8c6a12ae14649c57f6b1d1c4d9b8c92a302764",
    "get_client_by_uid": "47fdc53527a5c617c6e38462c31e6f4ff6cafd1e4dd52c9189a897f595a37d52",
    "get_client_history": "8fc2038a3fe26c01399802fe4e91fc35b0263b46b83f14ca4d0f3c27b3f02418",
    "get_client_info": "ee7fe970ef0a989a9cf9b24454caaccee1395ef98d1a37eca4253bf53b7b3798",
    "get_client_link_meta": "ab15065272cd8aeb8ee58cec1a0e878a53a9baceaf5d36a622b38c14378bfe4d",
    "get_client_uid": "2259282ec01dce8bf5efe8b555b8bc69836a8858786ffe0ef9fbf29666733bd1",
    "get_person_uid_for_client_uid": "dc102ae9f96de61a26cb5b161f9430bfd248a0e921d555ae9e67bbbf97b9d14c"
}

def get_all_clients(self, search=None, loan_type=None, search_by='all', include_archived=False):
        """Return client names (optionally filtered by loan_type) with optional search.

        search_by:
          - 'all' / 'both' : match across common client fields (default)
          - 'client'       : match in client name only
          - 'area'         : match in area only
          - 'principal'    : match in principal (as text)
          - 'released'     : match in date_released
          - 'due_date'     : match in due_date
          - 'start_date'   : match in computed start date (date_released + pay_start_offset_days)
          - 'linked'       : show clients that are linked (same person_uid appears in another row)
          - 'unlinked'     : show clients not linked yet (suggested + 7x7-only)
          - 'suggested'    : show clients that have a same-name record in the other loan type but are not linked yet
          - 'blanks'       : show clients with missing key fields (area/released/due/principal)

        Notes:
          - Uses the existing persistent sqlite connection (self.conn).
          - Automatically adapts to older DBs missing some columns.
        """
        import sqlite3

        cur = self.conn.cursor()

        # Normalize loan_type (if provided)
        lt = (loan_type or '').strip()
        if lt:
            lt = self._norm_lt(lt)

        # Introspect available columns for robust queries across versions
        try:
            cols = {r[1] if not isinstance(r, sqlite3.Row) else r["name"] for r in cur.execute("PRAGMA table_info(clients)").fetchall()}
        except Exception:
            cols = set()

        has_loan_type = ("loan_type" in cols)
        has_area = ("area" in cols)
        has_principal = ("principal" in cols)
        has_released = ("date_released" in cols)
        has_due = ("due_date" in cols)
        has_pay_off = ("pay_start_offset_days" in cols)
        has_person = ("person_uid" in cols)
        has_optout = ("link_opt_out" in cols)
        has_archived = ("is_archived" in cols)

        sb = (search_by or 'all').strip().lower()
        term = (search or '').strip()
        # Convenience keywords when search_by is 'all':
        #   - typing 'blanks' shows clients with missing fields
        #   - typing 'linked' shows linked clients
        try:
            _tlow = (term or '').strip().lower()
            if sb in ('all','both') and _tlow in ('blanks','blank','missing','incomplete'):
                sb = 'blanks'
                term = ''
            elif sb in ('all','both') and _tlow in ('linked','link'):
                sb = 'linked'
                term = ''
            elif sb in ('all','both') and _tlow in ('unlinked','not linked','notlinked'):
                sb = 'unlinked'
                term = ''
            elif sb in ('all','both') and _tlow in ('suggested','suggest','suggestion','suggested link','suggestedlink'):
                sb = 'suggested'
                term = ''
        except Exception as __spina_exc:
            _log_suppressed_once('excpass_0139', 'suppressed exception excpass_0139', __spina_exc)
            pass
        like = f"%{term}%"

        # Helper: computed start date expression (SQLite date arithmetic)
        def _start_date_expr():
            # Requires date_released + pay_start_offset_days; if missing, fall back to date_released
            if has_released and has_pay_off:
                # date('YYYY-MM-DD', '+N day')
                return "IFNULL(date(date_released, '+' || IFNULL(pay_start_offset_days,0) || ' day'),'')"
            elif has_released:
                return "IFNULL(date_released,'')"
            else:
                return "''"

        where_pred = None
        where_params = []

        # Special filters that may ignore the search term
        if sb.startswith('blank'):
            preds = []
            if has_area:
                preds.append("IFNULL(area,'') = ''")
            if has_released:
                preds.append("IFNULL(date_released,'') = ''")
            if has_due:
                preds.append("IFNULL(due_date,'') = ''")
            if has_principal:
                preds.append("IFNULL(principal,0) = 0")
            where_pred = "(" + " OR ".join(preds) + ")" if preds else None
            where_params = []
        elif sb.startswith('unl'):
            # Unlinked: clients not linked yet (suggested + 7x7-only).
            # - Suggested: same-name record exists in the other loan type AND person_uid is blank
            # - 7x7-only: loan_type is 7x7 AND there is no Regular record AND person_uid is blank
            if not has_loan_type:
                # Fallback for older DBs: treat "unlinked" as missing person_uid
                if has_person:
                    base_pred = "TRIM(IFNULL(person_uid,'')) = ''"
                    if has_optout:
                        base_pred = f"({base_pred} AND IFNULL(link_opt_out,0)=0)"
                    if term:
                        where_pred = f"({base_pred} AND name LIKE ?)"
                        where_params = [like]
                    else:
                        where_pred = base_pred
                        where_params = []
                else:
                    where_pred = "name LIKE ?" if term else None
                    where_params = [like] if term else []
            else:
                # Suggested link predicate: other loan type exists for same name
                same_name_other = "EXISTS(SELECT 1 FROM clients c2 WHERE c2.name = clients.name AND c2.id <> clients.id AND IFNULL(c2.loan_type,'') <> IFNULL(clients.loan_type,''))"
                # 7x7-only predicate: is 7x7 and no Regular exists
                is_7x7 = "IFNULL(loan_type,'') = '7x7'"
                has_regular = "EXISTS(SELECT 1 FROM clients c2 WHERE c2.name = clients.name AND c2.id <> clients.id AND IFNULL(c2.loan_type,'') = 'Regular')"
                is_7x7_only = f"({is_7x7} AND NOT {has_regular})"
                if has_person:
                    not_linked = "TRIM(IFNULL(person_uid,'')) = ''"
                else:
                    not_linked = "1=1"
                base_pred = f"({not_linked} AND ({same_name_other} OR {is_7x7_only}))"
                if has_optout:
                    base_pred = f"({base_pred} AND IFNULL(link_opt_out,0)=0)"
                if term:
                    where_pred = f"({base_pred} AND name LIKE ?)"
                    where_params = [like]
                else:
                    where_pred = base_pred
                    where_params = []

        elif sb.startswith('link'):
            if not has_person:
                where_pred = None
                where_params = []
            else:
                base = "TRIM(IFNULL(person_uid,'')) <> ''"
                if has_optout:
                    base = f"({base} AND IFNULL(link_opt_out,0)=0)"
                # Require that the person_uid exists in another row (actual link)
                if has_loan_type:
                    link_exists = "EXISTS(SELECT 1 FROM clients c2 WHERE c2.person_uid = clients.person_uid AND c2.id <> clients.id AND IFNULL(c2.loan_type,'') <> IFNULL(clients.loan_type,''))"
                else:
                    link_exists = "EXISTS(SELECT 1 FROM clients c2 WHERE c2.person_uid = clients.person_uid AND c2.id <> clients.id)"
                # If user typed "no/unlinked", invert; else show linked
                t = (term or '').lower()
                if t in ("0","no","n","false","unlinked","not linked"):
                    where_pred = f"NOT ({base} AND {link_exists})"
                    where_params = []
                elif not term or t in ("1","yes","y","true","linked","✓","check"):
                    where_pred = f"({base} AND {link_exists})"
                    where_params = []
                else:
                    # Also allow searching by person_uid text
                    where_pred = f"(({base} AND {link_exists}) AND person_uid LIKE ?)"
                    where_params = [like]

        elif sb.startswith('sug'):
            # Suggested link: same-name record exists in the other loan type, but this row is not linked yet.
            # Mirrors the UI indicator: suggestion only applies when person_uid is blank.
            if has_loan_type:
                same_name_other = "EXISTS(SELECT 1 FROM clients c2 WHERE c2.name = clients.name AND c2.id <> clients.id AND IFNULL(c2.loan_type,'') <> IFNULL(clients.loan_type,''))"
            else:
                same_name_other = "EXISTS(SELECT 1 FROM clients c2 WHERE c2.name = clients.name AND c2.id <> clients.id)"
            if has_person:
                not_linked = "TRIM(IFNULL(person_uid,'')) = ''"
            else:
                not_linked = "1=1"
            base_pred = f"({not_linked} AND {same_name_other})"
            # If a term is provided, allow narrowing by name text
            if term:
                where_pred = f"({base_pred} AND name LIKE ?)"
                where_params = [like]
            else:
                where_pred = base_pred
                where_params = []

        else:
            # Text search across specific columns
            if not term:
                where_pred = None
                where_params = []
            else:
                if sb.startswith('cli') or sb in ("name",):
                    where_pred = "name LIKE ?"
                    where_params = [like]
                elif sb.startswith('are'):
                    if has_area:
                        where_pred = "IFNULL(area,'') LIKE ?"
                        where_params = [like]
                    else:
                        where_pred = "name LIKE ?"
                        where_params = [like]
                elif sb.startswith('pri'):
                    if has_principal:
                        where_pred = "CAST(IFNULL(principal,0) AS TEXT) LIKE ?"
                        where_params = [like]
                    else:
                        where_pred = "name LIKE ?"
                        where_params = [like]
                elif sb.startswith('rel'):
                    if has_released:
                        where_pred = "IFNULL(date_released,'') LIKE ?"
                        where_params = [like]
                    else:
                        where_pred = "name LIKE ?"
                        where_params = [like]
                elif sb.startswith('due'):
                    if has_due:
                        where_pred = "IFNULL(due_date,'') LIKE ?"
                        where_params = [like]
                    else:
                        where_pred = "name LIKE ?"
                        where_params = [like]
                elif sb.startswith('sta'):
                    # start_date
                    where_pred = f"{_start_date_expr()} LIKE ?"
                    where_params = [like]
                else:
                    # all/both
                    preds = ["name LIKE ?"]
                    params = [like]
                    if has_area:
                        preds.append("IFNULL(area,'') LIKE ?"); params.append(like)
                    if has_principal:
                        preds.append("CAST(IFNULL(principal,0) AS TEXT) LIKE ?"); params.append(like)
                    if has_released:
                        preds.append("IFNULL(date_released,'') LIKE ?"); params.append(like)
                    if has_due:
                        preds.append("IFNULL(due_date,'') LIKE ?"); params.append(like)
                    # computed start date (if possible)
                    if has_released:
                        preds.append(f"{_start_date_expr()} LIKE ?"); params.append(like)
                    if has_person:
                        preds.append("IFNULL(person_uid,'') LIKE ?"); params.append(like)
                    where_pred = "(" + " OR ".join(preds) + ")"
                    where_params = params

        # Build final query
        q = "SELECT name FROM clients"
        params = []
        if lt and has_loan_type:
            q += " WHERE loan_type = ?"
            params.append(lt)
            if where_pred:
                q += " AND " + where_pred
                params.extend(where_params)
        else:
            if where_pred:
                q += " WHERE " + where_pred
                params.extend(where_params)

        # Hide archived by default
        if (not include_archived) and has_archived:
            if " WHERE " in q:
                q += " AND COALESCE(is_archived,0)=0"
            else:
                q += " WHERE COALESCE(is_archived,0)=0"

        q += " ORDER BY name COLLATE NOCASE"

        try:
            cur.execute(q, params)
            rows = cur.fetchall()
            return [r["name"] if isinstance(r, sqlite3.Row) else r[0] for r in rows]
        except Exception:
            # Last-resort fallback: name-only
            try:
                if lt and has_loan_type:
                    if (not include_archived) and has_archived:
                        cur.execute("SELECT name FROM clients WHERE loan_type=? AND COALESCE(is_archived,0)=0 ORDER BY name COLLATE NOCASE", (lt,))
                    else:
                        cur.execute("SELECT name FROM clients WHERE loan_type=? ORDER BY name COLLATE NOCASE", (lt,))
                else:
                    if (not include_archived) and has_archived:
                        cur.execute("SELECT name FROM clients WHERE COALESCE(is_archived,0)=0 ORDER BY name COLLATE NOCASE")
                    else:
                        cur.execute("SELECT name FROM clients ORDER BY name COLLATE NOCASE")
                rows = cur.fetchall()
                return [r["name"] if isinstance(r, sqlite3.Row) else r[0] for r in rows]
            except Exception:
                return []

def get_client_info(self, name, loan_type=None, include_archived=False):
        cur = self.conn.cursor()
        lt = self._effective_lt(loan_type)
        q = "SELECT * FROM clients WHERE name = ? AND loan_type = ?"
        params = [name, lt]
        try:
            if not include_archived:
                cols = [r[1] for r in cur.execute("PRAGMA table_info(clients)").fetchall()]
                if "is_archived" in cols:
                    q += " AND COALESCE(is_archived,0)=0"
        except Exception:
            pass
        cur.execute(q, tuple(params))
        r = cur.fetchone()
        return dict(r) if r else None

def get_client_link_meta(self, name, loan_type=None):
        """Return (client_uid, person_uid, link_opt_out) for a client."""
        cur = self.conn.cursor()
        lt = self._effective_lt(loan_type)
        try:
            r = cur.execute(
                "SELECT client_uid, person_uid, link_opt_out FROM clients WHERE name=? AND loan_type=?",
                (name, lt),
            ).fetchone()
            if not r:
                return None
            return {
                "client_uid": r[0],
                "person_uid": r[1] or "",
                "link_opt_out": int(r[2] or 0),
                "loan_type": lt,
                "name": name,
            }
        except Exception:
            return None

def find_clients_by_person_uid(self, person_uid):
        """Return list of client rows linked to this person_uid."""
        pu = (person_uid or '').strip()
        if not pu:
            return []
        cur = self.conn.cursor()
        try:
            rows = cur.execute("SELECT * FROM clients WHERE person_uid=? ORDER BY loan_type, name", (pu,)).fetchall() or []
            return [dict(r) for r in rows]
        except Exception:
            return []

def get_client_uid(self, name, loan_type=None):
        """Return client_uid for (name, loan_type)."""
        cur = self.conn.cursor()
        lt = self._effective_lt(loan_type)
        try:
            r = cur.execute("SELECT client_uid FROM clients WHERE name=? AND loan_type=?", (name, lt)).fetchone()
            if not r:
                return None
            try:
                return (r["client_uid"] if isinstance(r, sqlite3.Row) else r[0]) or None
            except Exception:
                return None
        except Exception:
            return None

def get_client_by_uid(self, client_uid):
        cur = self.conn.cursor()
        uid = (client_uid or '').strip()
        if not uid:
            return None
        try:
            r = cur.execute("SELECT * FROM clients WHERE client_uid=?", (uid,)).fetchone()
            return dict(r) if r else None
        except Exception:
            return None

def get_client_history(self, client_uid=None, name=None, loan_type=None, limit=500):
        """Return audit history rows (most recent first). Prefer client_uid.
        Normalizes key names for UI:
          ts          -> changed_at
          before_json -> old_json
          after_json  -> new_json
        """
        cur = self.conn.cursor()
        lim = int(limit or 500)
        try:
            if client_uid:
                rows = cur.execute(
                    "SELECT * FROM client_history WHERE client_uid=? ORDER BY id DESC LIMIT ?",
                    ((client_uid or '').strip(), lim)
                ).fetchall()
            else:
                # fallback by name (may miss rename chains)
                lt = self._effective_lt(loan_type) if loan_type else None
                if name and lt:
                    rows = cur.execute(
                        """SELECT * FROM client_history
                             WHERE (name_before=? OR name_after=?)
                               AND (loan_type_before=? OR loan_type_after=?)
                             ORDER BY id DESC LIMIT ?""",
                        (name, name, lt, lt, lim)
                    ).fetchall()
                elif name:
                    rows = cur.execute(
                        "SELECT * FROM client_history WHERE (name_before=? OR name_after=?) ORDER BY id DESC LIMIT ?",
                        (name, name, lim)
                    ).fetchall()
                else:
                    rows = []
            out = []
            for r in (rows or []):
                try:
                    d = dict(r)
                except Exception:
                    d = {}
                # normalize
                try:
                    d["ts"] = d.get("changed_at") or d.get("ts") or ""
                    d["before_json"] = d.get("old_json") if d.get("old_json") is not None else d.get("before_json")
                    d["after_json"] = d.get("new_json") if d.get("new_json") is not None else d.get("after_json")
                except Exception as __spina_exc:
                    _log_suppressed_once('excpass_0149', 'suppressed exception excpass_0149', __spina_exc)
                    pass
                out.append(d)
            return out
        except Exception:
            return []

def get_person_uid_for_client_uid(self, client_uid):
        uid = (client_uid or '').strip()
        if not uid:
            return ''
        cur = self.conn.cursor()
        try:
            r = cur.execute("SELECT person_uid FROM clients WHERE client_uid=?", (uid,)).fetchone()
            if not r:
                return ''
            try:
                return (r["person_uid"] if isinstance(r, sqlite3.Row) else r[0]) or ''
            except Exception:
                return r[0] or ''
        except Exception:
            return ''
