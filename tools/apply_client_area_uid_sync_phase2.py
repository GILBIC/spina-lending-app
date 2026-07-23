from __future__ import annotations

import argparse
from pathlib import Path

APP = Path("OFFICIAL_SPINA_APP_PostgreSQL_TEST_v33_stability_performance_fixed.py")
OPS = Path("spina_app/area_hierarchy_ops.py")

OPS_OLD = '''    node = find_area_node_by_path(conn, path, include_inactive=True)\n    if node is None:\n        return None\n'''
OPS_NEW = '''    path_text = normalize_area_path(path)\n    if not path_text:\n        cur.execute("UPDATE clients SET area_uid='' WHERE client_uid=?", (key,))\n        conn.commit()\n        return None\n    node = find_area_node_by_path(conn, path_text, include_inactive=True)\n    if node is None:\n        return None\n'''

ADD_OLD = '''            self.conn.commit()\n\n            # Ensure renew defaults (safe if columns not present)\n'''
ADD_NEW = '''            self.conn.commit()\n            try:\n                from spina_app.area_hierarchy_ops import sync_client_area_uid_from_path\n                sync_client_area_uid_from_path(self.conn, uid)\n            except Exception as __spina_exc:\n                _log_suppressed_once(\n                    'area_uid_sync_add',\n                    'suppressed client Area UID sync after add',\n                    __spina_exc,\n                )\n                pass\n\n            # Ensure renew defaults (safe if columns not present)\n'''

UPDATE_OLD = '''            except Exception as e:\n                _log_exc("notes:migrate_on_rename", e)\n\n\n            self.conn.commit()\n\n            # Log history\n'''
UPDATE_NEW = '''            except Exception as e:\n                _log_exc("notes:migrate_on_rename", e)\n\n\n            self.conn.commit()\n            try:\n                from spina_app.area_hierarchy_ops import sync_client_area_uid_from_path\n                _area_sync_uid = uid or (\n                    old_row.get("client_uid") if isinstance(old_row, dict) else ""\n                )\n                if _area_sync_uid:\n                    sync_client_area_uid_from_path(self.conn, _area_sync_uid)\n            except Exception as __spina_exc:\n                _log_suppressed_once(\n                    'area_uid_sync_update',\n                    'suppressed client Area UID sync after update',\n                    __spina_exc,\n                )\n                pass\n\n            # Log history\n'''


def _state(text: str, old: str, new: str, label: str) -> str:
    old_count = text.count(old)
    new_count = text.count(new)
    if old_count == 1 and new_count == 0:
        return "source"
    if old_count == 0 and new_count == 1:
        return "patched"
    raise RuntimeError(
        f"Unexpected {label} state: source={old_count}, patched={new_count}"
    )


def inspect() -> str:
    app = APP.read_text(encoding="utf-8")
    ops = OPS.read_text(encoding="utf-8")
    states = {
        _state(ops, OPS_OLD, OPS_NEW, "Area sync helper"),
        _state(app, ADD_OLD, ADD_NEW, "client add sync"),
        _state(app, UPDATE_OLD, UPDATE_NEW, "client update sync"),
    }
    if len(states) != 1:
        raise RuntimeError(f"Mixed client Area UID sync state: {sorted(states)}")
    return next(iter(states))


def apply() -> None:
    if inspect() == "patched":
        return
    app = APP.read_text(encoding="utf-8")
    ops = OPS.read_text(encoding="utf-8")
    ops = ops.replace(OPS_OLD, OPS_NEW, 1)
    app = app.replace(ADD_OLD, ADD_NEW, 1)
    app = app.replace(UPDATE_OLD, UPDATE_NEW, 1)
    compile(ops, str(OPS), "exec")
    compile(app, str(APP), "exec")
    OPS.write_text(ops, encoding="utf-8")
    APP.write_text(app, encoding="utf-8")
    if inspect() != "patched":
        raise RuntimeError("Client Area UID sync patch did not reach patched state")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    state = inspect()
    if args.apply and state == "source":
        apply()
        state = inspect()
        print("Applied immediate client Area UID synchronization")
    else:
        print(f"Client Area UID synchronization state: {state}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
