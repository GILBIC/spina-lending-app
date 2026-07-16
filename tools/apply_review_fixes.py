#!/usr/bin/env python3
from __future__ import annotations

import ast
import textwrap
from pathlib import Path

SOURCE = Path("OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py")


def find_function(tree: ast.AST, name: str, *, parent_class: str | None = None):
    if parent_class:
        for node in tree.body:
            if isinstance(node, ast.ClassDef) and node.name == parent_class:
                matches = [
                    child
                    for child in ast.walk(node)
                    if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef))
                    and child.name == name
                ]
                if matches:
                    return matches[0]
        raise RuntimeError(f"missing {parent_class}.{name}")
    matches = [
        node
        for node in ast.walk(tree)
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        and node.name == name
    ]
    if not matches:
        raise RuntimeError(f"missing function {name}")
    return matches[0]


def indent_block(text: str, spaces: int) -> str:
    text = textwrap.dedent(text).strip("\n")
    pad = " " * spaces
    return "\n".join((pad + line if line else "") for line in text.splitlines()) + "\n"


def main() -> int:
    source = SOURCE.read_text(encoding="utf-8")
    tree = ast.parse(source, filename=str(SOURCE))
    lines = source.splitlines(keepends=True)
    replacements: list[tuple[int, int, str]] = []

    call_node = find_function(tree, "_call_work_fn")
    call_replacement = indent_block(
        '''
        def _call_work_fn():
            """Call work_fn once, optionally passing cancel_event when supported.

            Signature inspection errors fall back to a no-argument call. Exceptions
            raised by the task itself are deliberately allowed to propagate to the
            worker so a database write or import is never executed a second time.
            """
            import inspect as _inspect
            try:
                sig = _inspect.signature(work_fn)
            except Exception:
                sig = None

            if sig:
                params = list(sig.parameters.values())
                has_varkw = any(p.kind == p.VAR_KEYWORD for p in params)
                if has_varkw or ("cancel_event" in sig.parameters):
                    return work_fn(cancel_event=cancel_event)
                pos = [
                    p for p in params
                    if p.kind in (p.POSITIONAL_ONLY, p.POSITIONAL_OR_KEYWORD)
                ]
                if len(pos) == 1 and not any(p.kind == p.VAR_POSITIONAL for p in params):
                    return work_fn(cancel_event)
            return work_fn()
        ''',
        call_node.col_offset,
    )
    replacements.append((call_node.lineno - 1, call_node.end_lineno, call_replacement))

    set_password = find_function(tree, "_set_user_password", parent_class="App")
    old_set_password = "".join(lines[set_password.lineno - 1 : set_password.end_lineno])
    password_save = "            self._save_users_db(db)\n            return True\n"
    if password_save not in old_set_password:
        raise RuntimeError("password save call changed")
    replacements.append(
        (
            set_password.lineno - 1,
            set_password.end_lineno,
            old_set_password.replace(
                password_save,
                "            if not self._save_users_db(db):\n"
                "                return False\n"
                "            return True\n",
                1,
            ),
        )
    )

    save_users = find_function(tree, "_save_users_db", parent_class="App")
    save_replacement = indent_block(
        '''
        def _save_users_db(self, data: dict) -> bool:
            """Atomically save accounts and maintain a last-known-good backup."""
            import json
            import os
            import shutil

            p = self._users_db_path()
            tmp = p + '.tmp'
            backup = p + '.bak'
            try:
                os.makedirs(os.path.dirname(p), exist_ok=True)
            except Exception as e:
                _log_exc('save_users_db:makedirs', e)
                _alert_user(
                    'Save Error',
                    'Failed to prepare the account storage folder.\\n'
                    'See log: data/spina_app.log',
                    kind='warning',
                )
                return False

            try:
                with open(tmp, 'w', encoding='utf-8') as f:
                    json.dump(data, f, ensure_ascii=False, indent=2)
                    f.flush()
                    try:
                        os.fsync(f.fileno())
                    except Exception:
                        pass

                os.replace(tmp, p)
                try:
                    shutil.copy2(p, backup)
                except Exception as e:
                    _log_suppressed_once(
                        'users_backup_write',
                        'account backup could not be refreshed',
                        e,
                    )

                try:
                    if os.name != 'nt':
                        os.chmod(p, 0o600)
                        if os.path.exists(backup):
                            os.chmod(backup, 0o600)
                except Exception as e:
                    _log_suppressed_once(
                        'users_chmod', 'account permission update failed', e
                    )
                return True
            except Exception as e:
                try:
                    if os.path.exists(tmp):
                        os.remove(tmp)
                except Exception:
                    pass
                _log_exc('save_users_db:write', e)
                _alert_user(
                    'Save Error',
                    'Failed to save user accounts (data/users.json).\\n\\n'
                    'Check permissions/disk space.\\nSee log: data/spina_app.log',
                    kind='warning',
                )
                return False
        ''',
        save_users.col_offset,
    )
    replacements.append((save_users.lineno - 1, save_users.end_lineno, save_replacement))

    load_users = find_function(tree, "_load_users_db", parent_class="App")
    old_load_users = "".join(lines[load_users.lineno - 1 : load_users.end_lineno])
    marker = "        users = data.get('users')\n"
    if marker not in old_load_users:
        raise RuntimeError("users load marker changed")
    suffix = old_load_users[old_load_users.index(marker) :]
    old_final_save = (
        "        if changed or (not os.path.exists(p)):\n"
        "            self._save_users_db(data)\n"
        "        return data\n"
    )
    new_final_save = (
        "        if changed or missing_primary:\n"
        "            if not self._save_users_db(data):\n"
        "                data['_save_error'] = True\n"
        "        return data\n"
    )
    if old_final_save not in suffix:
        raise RuntimeError("users load final save block changed")
    suffix = suffix.replace(old_final_save, new_final_save, 1)
    load_prefix = indent_block(
        '''
        def _load_users_db(self) -> dict:
            """Load account data without silently overwriting an unreadable file.

            Missing files create the default first-run accounts. Corrupt or unreadable
            files are recovered from users.json.bak when possible. If both copies are
            unreadable, login fails safely and the original files are left untouched.
            """
            import json
            import os
            import shutil

            p = self._users_db_path()
            backup = p + '.bak'
            data = {}
            missing_primary = False
            recovered_from_backup = False

            try:
                with open(p, 'r', encoding='utf-8') as f:
                    data = json.load(f) or {}
                if not isinstance(data, dict):
                    raise ValueError('users.json root must be an object')
            except FileNotFoundError:
                missing_primary = True
                data = {}
            except Exception as primary_error:
                _log_exc('load_users_db:primary', primary_error)
                try:
                    with open(backup, 'r', encoding='utf-8') as f:
                        data = json.load(f) or {}
                    if not isinstance(data, dict):
                        raise ValueError('users.json.bak root must be an object')
                    recovered_from_backup = True
                except Exception as backup_error:
                    _log_exc('load_users_db:backup', backup_error)
                    if not getattr(self, '_users_load_error_alerted', False):
                        self._users_load_error_alerted = True
                        _alert_user(
                            'Account File Error',
                            'SPINA could not read data/users.json or its backup.\\n\\n'
                            'The files were not overwritten. Restore users.json from a '
                            'known-good backup, then restart SPINA.\\n\\n'
                            'See log: data/spina_app.log',
                            kind='error',
                        )
                    return {'version': 1, 'users': {}, '_load_error': True}

            if recovered_from_backup:
                try:
                    restore_tmp = p + '.recovery.tmp'
                    shutil.copy2(backup, restore_tmp)
                    os.replace(restore_tmp, p)
                except Exception as e:
                    _log_suppressed_once(
                        'users_backup_restore',
                        'account file backup loaded but primary restore failed',
                        e,
                    )
                if not getattr(self, '_users_backup_recovery_alerted', False):
                    self._users_backup_recovery_alerted = True
                    _alert_user(
                        'Account File Recovered',
                        'SPINA recovered the account file from data/users.json.bak.',
                        kind='warning',
                    )
        ''',
        load_users.col_offset,
    )
    replacements.append(
        (load_users.lineno - 1, load_users.end_lineno, load_prefix + suffix)
    )

    performance = find_function(tree, "_spina_perf_ensure_indexes")
    old_performance = "".join(lines[performance.lineno - 1 : performance.end_lineno])
    old_header = '''def _spina_perf_ensure_indexes(db):
    """Create helpful indexes for large datasets. Safe/idempotent."""
    try:
        conn = getattr(db, "conn", None)
        if conn is None:
            return
'''
    new_header = '''_SPINA_PERF_INDEXES_READY = False


def _spina_perf_ensure_indexes(db):
    """Create performance indexes once per application process."""
    global _SPINA_PERF_INDEXES_READY
    if _SPINA_PERF_INDEXES_READY:
        return True
    try:
        conn = getattr(db, "conn", None)
        if conn is None:
            return False
'''
    if old_header not in old_performance:
        raise RuntimeError("performance index header changed")
    new_performance = old_performance.replace(old_header, new_header, 1)
    old_pragma = '''        try:
            cur.execute("PRAGMA optimize")
        except Exception:
            pass
    except Exception as e:
'''
    new_pragma = '''        try:
            cur.execute("PRAGMA optimize")
        except Exception:
            pass
        _SPINA_PERF_INDEXES_READY = True
        return True
    except Exception as e:
'''
    if old_pragma not in new_performance:
        raise RuntimeError("performance index footer changed")
    new_performance = new_performance.replace(old_pragma, new_pragma, 1)
    old_exception_footer = '''    except Exception as e:
        try:
            _log_suppressed_once("perf_indexes_outer", "performance index setup failed", e)
        except Exception:
            pass
'''
    new_exception_footer = old_exception_footer + "        return False\n"
    if old_exception_footer not in new_performance:
        raise RuntimeError("performance index exception footer changed")
    new_performance = new_performance.replace(
        old_exception_footer, new_exception_footer, 1
    )
    replacements.append(
        (performance.lineno - 1, performance.end_lineno, new_performance)
    )

    eager = '''try:
    if "App" in globals():
        try:
            _spina_perf_ensure_indexes(LoanDB(DB_FILE))
        except Exception:
            pass
        setattr(App, "refresh_clients", _spina_perf_refresh_clients)
        setattr(App, "refresh_data_grid", _spina_perf_refresh_data_grid)
'''
    eager_replacement = '''try:
    if "App" in globals():
        # Index setup runs on the first real refresh using App's existing DB
        # connection, avoiding a second startup connection and schema pass.
        setattr(App, "refresh_clients", _spina_perf_refresh_clients)
        setattr(App, "refresh_data_grid", _spina_perf_refresh_data_grid)
'''
    if eager not in source:
        raise RuntimeError("performance binding block changed")

    for start, end, replacement in sorted(replacements, reverse=True):
        lines[start:end] = [replacement]
    updated = "".join(lines).replace(eager, eager_replacement, 1)
    ast.parse(updated, filename=str(SOURCE))
    SOURCE.write_text(updated, encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
