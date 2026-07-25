"""Read-only linked-client and transaction-history queries for SPINA.

Wave 32 keeps these methods byte-for-byte equivalent after dedenting and wires
them back onto ``LoanDB`` immediately after the class definition. Application
globals are supplied explicitly so the extracted methods retain the same
compatibility, logging, SQLite/PostgreSQL adapter, and helper references.
"""

from __future__ import annotations

_LINKED_CLIENT_QUERY_DEPENDENCIES: dict[str, object] = {}
_PROTECTED_GLOBALS = {
    "__builtins__",
    "__cached__",
    "__doc__",
    "__file__",
    "__loader__",
    "__name__",
    "__package__",
    "__spec__",
    "_LINKED_CLIENT_QUERY_DEPENDENCIES",
    "_PROTECTED_GLOBALS",
    "configure_linked_client_query_dependencies",
}


def configure_linked_client_query_dependencies(namespace: dict[str, object]) -> None:
    """Bind application-owned globals required by the extracted LoanDB methods."""
    _LINKED_CLIENT_QUERY_DEPENDENCIES.clear()
    _LINKED_CLIENT_QUERY_DEPENDENCIES.update(namespace)
    module_globals = globals()
    for name, value in namespace.items():
        if name not in _PROTECTED_GLOBALS:
            module_globals[name] = value


# Original dedented source SHA-256 values from the guarded Wave 32 base.
LINKED_CLIENT_QUERY_SOURCE_SHA256 = {
    "count_clients_in_area": "56dac6dbd2ba92fdc6b1b4d08f8db6c139207e50fe4061f55ba70e9e25d85b2f",
    "get_client_by_person_uid_and_loan_type": "512bb4723957fd90afe16678ee5415f75c3b08ebdd4e87a5743ab61353081f11",
    "get_linked_client_uids": "bbc95ceef6181ec1e0b87aa6514d012e5f1913d114f880626c0a400c148a9f3c",
    "get_transaction_history_for_client_uids": "d2bf907b3da9b8af154e3e08ad878c52d6a195b7673afd29d0bf095613315995",
    "get_transactions_for_client": "2b8757250b6822f00fd37d8221653cbc08b02882c8e0aa2523343408986a713f",
    "get_transactions_for_client_uids": "81f1e6394a4222d2bbaea71172f7b4b2a23632bd82180c36ee80caa26818734f"
}

def get_linked_client_uids(self, client_uid):
        """Return all client_uids linked to the same person_uid (includes self).
        If not linked, returns [client_uid].
        """
        uid = (client_uid or '').strip()
        if not uid:
            return []
        try:
            row = self.get_client_by_uid(uid) or {}
            pu = (row.get("person_uid") or "").strip()
            if not pu:
                return [uid]
            linked = self.find_clients_by_person_uid(pu) or []
            uids = []
            for r in linked:
                try:
                    cu = (r.get("client_uid") or "").strip()
                    if cu:
                        uids.append(cu)
                except Exception as __spina_exc:
                    _log_suppressed_once('excpass_0150', 'suppressed exception excpass_0150', __spina_exc)
                    pass
            if uid not in uids:
                uids.insert(0, uid)
            # de-dup preserving order
            seen = set()
            out = []
            for u in uids:
                if u in seen:
                    continue
                seen.add(u)
                out.append(u)
            return out
        except Exception:
            return [uid]

def get_transaction_history_for_client_uids(self, client_uids, limit=500):
        """Return databank audit rows (most recent first) for a list of client_uids."""
        uids = [ (u or '').strip() for u in (client_uids or []) if (u or '').strip() ]
        if not uids:
            return []
        cur = self.conn.cursor()
        lim = int(limit or 500)
        ph = ",".join(["?"] * len(uids))
        try:
            rows = cur.execute(
                f"SELECT * FROM transaction_history WHERE client_uid IN ({ph}) ORDER BY id DESC LIMIT ?",
                tuple(uids) + (lim,)
            ).fetchall()
        except Exception:
            return []
        out = []
        for r in (rows or []):
            try:
                d = dict(r)
            except Exception:
                d = {}
            try:
                d["ts"] = d.get("changed_at") or d.get("ts") or ""
                d["before_json"] = d.get("old_json") if d.get("old_json") is not None else d.get("before_json")
                d["after_json"] = d.get("new_json") if d.get("new_json") is not None else d.get("after_json")
            except Exception as __spina_exc:
                _log_suppressed_once('excpass_0152', 'suppressed exception excpass_0152', __spina_exc)
                pass
            out.append(d)
        return out

def get_transactions_for_client_uids(self, client_uids, start_date=None, end_date=None, limit=None):
        """Return transactions for a linked person (both Regular + 7x7), using client_uid when available.
        Includes best-effort fallback to legacy rows where client_uid is blank but (name, loan_type) matches.
        """
        uids = [ (u or '').strip() for u in (client_uids or []) if (u or '').strip() ]
        if not uids:
            return []
        cur = self.conn.cursor()
        ph = ",".join(["?"] * len(uids))

        # Build fallback (name, loan_type) list from linked clients
        ors = []
        or_params = []
        try:
            crows = cur.execute(f"SELECT name, loan_type FROM clients WHERE client_uid IN ({ph})", tuple(uids)).fetchall() or []
            for rr in crows:
                try:
                    nm = (rr["name"] if isinstance(rr, sqlite3.Row) else rr[0]) or ""
                    lt = (rr["loan_type"] if isinstance(rr, sqlite3.Row) else rr[1]) or "Regular"
                    nm = nm.strip()
                    lt = lt.strip()
                    if nm:
                        ors.append("(name=? AND IFNULL(loan_type,'Regular')=IFNULL(?,'Regular'))")
                        or_params.extend([nm, lt])
                except Exception as __spina_exc:
                    _log_suppressed_once('excpass_0153', 'suppressed exception excpass_0153', __spina_exc)
                    pass
        except Exception as __spina_exc:
            _log_suppressed_once('excpass_0154', 'suppressed exception excpass_0154', __spina_exc)
            pass

        where = f"(client_uid IN ({ph}))"
        params = list(uids)

        if ors:
            where = f"({where} OR ((client_uid IS NULL OR TRIM(client_uid)='') AND ({' OR '.join(ors)})))"
            params.extend(or_params)

        sql = "SELECT * FROM transactions WHERE " + where
        if start_date:
            sql += " AND date(date) >= date(?)"
            params.append(start_date)
        if end_date:
            sql += " AND date(date) <= date(?)"
            params.append(end_date)
        sql += " ORDER BY date(date) ASC, loan_type ASC, id ASC"
        if limit:
            try:
                lim = int(limit)
                sql += " LIMIT ?"
                params.append(lim)
            except Exception as __spina_exc:
                _log_suppressed_once('excpass_0155', 'suppressed exception excpass_0155', __spina_exc)
                pass

        try:
            rows = cur.execute(sql, params).fetchall()
            return [dict(r) for r in (rows or [])]
        except Exception:
            return []

def count_clients_in_area(self, area_name):
        """Count ACTIVE clients in an area.

        Archived-only areas should not keep showing up as 'in use' in the UI.
        """
        cur = self.conn.cursor()
        nm = (area_name or "").strip()
        if not nm:
            return 0
        try:
            try:
                cols = [str(r[1]) for r in (cur.execute("PRAGMA table_info(clients)").fetchall() or [])]
            except Exception:
                cols = []
            has_arch = ('is_archived' in cols)

            if has_arch:
                row = cur.execute(
                    "SELECT COUNT(*) AS c FROM clients WHERE TRIM(IFNULL(area,'')) = ? AND COALESCE(is_archived,0)=0",
                    (nm,)
                ).fetchone()
            else:
                row = cur.execute("SELECT COUNT(*) AS c FROM clients WHERE TRIM(IFNULL(area,'')) = ?", (nm,)).fetchone()
            return int(row["c"] if isinstance(row, sqlite3.Row) else row[0])
        except Exception:
            return 0

def get_client_by_person_uid_and_loan_type(self, person_uid, loan_type):
        """Return a single client row matching (person_uid, loan_type), or None."""
        pu = (person_uid or "").strip()
        if not pu:
            return None
        lt = self._effective_lt(loan_type)
        cur = self.conn.cursor()
        try:
            r = cur.execute(
                "SELECT * FROM clients WHERE person_uid=? AND loan_type=? ORDER BY name LIMIT 1",
                (pu, lt),
            ).fetchone()
            return dict(r) if r else None
        except Exception:
            return None

def get_transactions_for_client(self, name, start_date=None, end_date=None, loan_type=None):
        cur = self.conn.cursor()
        lt = self._effective_lt(loan_type)
        nm = (name or '').strip()

        # Prefer stable-id lookup so renames do not hide historical rows.
        uid = None
        try:
            uid = self.get_client_uid(nm, loan_type=lt)
        except Exception:
            uid = None

        if uid:
            sql = (
                "SELECT * FROM transactions "
                "WHERE ((client_uid = ?) OR ((client_uid IS NULL OR TRIM(client_uid)='') AND name = ?)) "
                "AND IFNULL(NULLIF(TRIM(loan_type),''),'Regular') = IFNULL(NULLIF(TRIM(?),''),'Regular')"
            )
            params = [uid, nm, lt]
        else:
            sql = (
                "SELECT * FROM transactions "
                "WHERE name = ? "
                "AND IFNULL(NULLIF(TRIM(loan_type),''),'Regular') = IFNULL(NULLIF(TRIM(?),''),'Regular')"
            )
            params = [nm, lt]

        if start_date:
            sql += " AND date(date) >= date(?)"
            params.append(start_date)
        if end_date:
            sql += " AND date(date) <= date(?)"
            params.append(end_date)

        sql += " ORDER BY date(date) ASC, id ASC"
        cur.execute(sql, params)
        return cur.fetchall()
