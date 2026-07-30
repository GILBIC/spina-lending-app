"""Final account-based runtime ownership consolidated in Wave 83."""
from __future__ import annotations

from collections.abc import Mapping

from spina_app.account_permission_presentation import (
    _spina_v32_account_permission_text,
)
from spina_app.services.accounts import (
    account_choices,
    default_account_name,
    normalize_access_profile,
    selected_label_for_user,
)

_ACCOUNT_DEPENDENCIES: dict[str, object] = {}
_REQUIRED_METHODS = (
    "_load_users_db",
    "_prompt_login",
    "_prompt_user_role",
    "_refresh_user_header",
    "switch_account",
    "_build_header",
)


def _dependency(name: str, default=None):
    return _ACCOUNT_DEPENDENCIES.get(name, default)


def _log(context: str, exc: Exception) -> None:
    callback = _dependency("_log_exc")
    if callable(callback):
        try:
            callback(context, exc)
            return
        except TypeError:
            try:
                callback(context)
                return
            except Exception:
                pass
        except Exception:
            pass


def account_display_name(self, username):
    """Resolve the human-readable account name without exposing internal roles."""
    key = str(username or "").strip()
    try:
        database = self._load_users_db()
        record = ((database.get("users") or {}).get(key) or {})
        display = str(
            record.get("display_name")
            or record.get("account_name")
            or record.get("label")
            or ""
        ).strip()
        if display:
            return display
    except Exception:
        pass
    return default_account_name(key)


def account_role(self, username):
    """Resolve the internal access profile for one account."""
    key = str(username or "").strip()
    try:
        database = self._load_users_db()
        record = ((database.get("users") or {}).get(key) or {})
        return normalize_access_profile(
            record.get("access_profile") or record.get("role"),
            default="Viewer",
        )
    except Exception:
        return "Viewer"


def account_choices_for_app(self, users=None):
    if not isinstance(users, Mapping):
        try:
            users = (self._load_users_db().get("users") or {})
        except Exception:
            users = {}
    return account_choices(users)


def selected_label_for_user_for_app(self, username, choices, label_to_user):
    return selected_label_for_user(username, choices, label_to_user)


def load_users_account_based(self):
    """Add account display metadata while preserving existing credentials."""
    cls = type(self)
    original = getattr(cls, "_spina_accounts_wave83_original_load_users_db", None)
    if not callable(original):
        original = getattr(cls, "_spina_v32_orig_load_users_db", None)

    try:
        database = original(self) if callable(original) else {"users": {}}
    except Exception as exc:
        _log("accounts_wave83_load_original", exc)
        return {"users": {}}

    if not isinstance(database, dict):
        database = {}
    users = database.get("users")
    if not isinstance(users, dict):
        users = {}
        database["users"] = users

    changed = False
    for username, raw_record in list(users.items()):
        if not isinstance(raw_record, dict):
            continue
        record = raw_record
        role = normalize_access_profile(
            record.get("access_profile") or record.get("role"),
            default="Viewer",
        )
        if record.get("role") != role:
            record["role"] = role
            changed = True
        if str(record.get("access_profile") or "").strip() != role:
            record["access_profile"] = role
            changed = True

        if not str(record.get("display_name") or "").strip():
            record["display_name"] = default_account_name(username)
            changed = True

        summary = _spina_v32_account_permission_text(role)
        if str(record.get("permission_summary") or "").strip() != summary:
            record["permission_summary"] = summary
            changed = True
        users[username] = record

    database["users"] = users
    if changed:
        saver = getattr(self, "_save_users_db", None)
        if callable(saver):
            try:
                saver(database)
            except Exception as exc:
                _log("accounts_wave83_save_metadata", exc)
    return database


def prompt_user_role(self, default: str = "Admin") -> str:
    """Compatibility fallback that never restores the obsolete role picker."""
    return normalize_access_profile(default, default="Admin")


def switch_account(self):
    """Switch the active account and fully refresh account-dependent UI state."""
    old_user = str(getattr(self, "user_name", "") or "")
    old_display = account_display_name(self, old_user) if old_user else ""

    try:
        username, role = self._prompt_login(
            default_user=(getattr(self, "user_name", "") or "admin")
        )
    except Exception as exc:
        _log("switch_account_login", exc)
        messagebox = _dependency("messagebox")
        if messagebox is not None:
            try:
                messagebox.showerror(
                    "Switch Account",
                    "Failed to open the account sign-in window. See log for details.",
                )
            except Exception:
                pass
        return

    if not username or not role:
        return

    self.user_name = username
    self.user_role = normalize_access_profile(role, default="Viewer")

    for method_name, value in (
        ("_save_last_user", self.user_name),
        ("_save_user_role", self.user_role),
    ):
        method = getattr(self, method_name, None)
        if callable(method):
            try:
                method(value)
            except Exception as exc:
                _log(f"accounts_wave83_{method_name}", exc)

    for method_name in ("_refresh_user_header", "_rebuild_side_nav"):
        method = getattr(self, method_name, None)
        if callable(method):
            try:
                method()
            except Exception as exc:
                _log(f"accounts_wave83_{method_name}", exc)

    try:
        self.apply_role_access()
    except Exception as exc:
        _log("switch_account_apply_role_access", exc)
        messagebox = _dependency("messagebox")
        if messagebox is not None:
            try:
                messagebox.showwarning(
                    "Switch Account",
                    "The account was switched, but the UI permissions could not be "
                    "fully refreshed. Please restart the app if something looks wrong.",
                )
            except Exception:
                pass

    try:
        new_display = account_display_name(self, self.user_name)
        self.status_var.set(
            f"Switched account: {old_display or old_user} → {new_display}"
        )
    except Exception:
        pass


def _configure_login_presentation(namespace: dict[str, object], prompt_login) -> None:
    try:
        from spina_app.login_dialog_presentation import (
            configure_login_dialog_dependencies,
        )

        dependencies = dict(namespace)
        dependencies.update(
            {
                "_spina_v32_account_default_name": default_account_name,
                "_spina_v32_account_display_name": account_display_name,
                "_spina_v32_account_role": account_role,
                "_spina_v32_account_choices": account_choices_for_app,
                "_spina_v32_selected_label_for_user": (
                    selected_label_for_user_for_app
                ),
                "_spina_v32_account_permission_text": (
                    _spina_v32_account_permission_text
                ),
            }
        )
        configure_login_dialog_dependencies(dependencies)
    except Exception as exc:
        _log("accounts_wave83_configure_login", exc)


def install_accounts_feature(
    app_class,
    *,
    namespace=None,
    prompt_login=None,
    refresh_header=None,
    build_header=None,
) -> bool:
    """Install one idempotent account-based runtime boundary on ``App``."""
    if app_class is None:
        return False

    dependencies = dict(namespace or {})
    _ACCOUNT_DEPENDENCIES.clear()
    _ACCOUNT_DEPENDENCIES.update(dependencies)

    if prompt_login is None:
        from spina_app.login_dialog_presentation import _spina_v32_prompt_login

        prompt_login = _spina_v32_prompt_login

    original_loader = getattr(
        app_class, "_spina_accounts_wave83_original_load_users_db", None
    )
    if not callable(original_loader):
        original_loader = getattr(app_class, "_spina_v32_orig_load_users_db", None)
    if not callable(original_loader):
        original_loader = getattr(app_class, "_load_users_db", None)
    if callable(original_loader):
        app_class._spina_accounts_wave83_original_load_users_db = original_loader
        if not hasattr(app_class, "_spina_v32_orig_load_users_db"):
            app_class._spina_v32_orig_load_users_db = original_loader

    _configure_login_presentation(dependencies, prompt_login)

    app_class._account_display_name = account_display_name
    app_class._account_role = account_role
    app_class._account_choices = account_choices_for_app
    app_class._selected_account_label = selected_label_for_user_for_app
    app_class._load_users_db = load_users_account_based
    app_class._prompt_login = prompt_login
    app_class._prompt_user_role = prompt_user_role
    app_class.switch_account = switch_account
    if callable(refresh_header):
        app_class._refresh_user_header = refresh_header
    if callable(build_header):
        app_class._build_header = build_header

    app_class._spina_accounts_wave83_installed = True
    return all(callable(getattr(app_class, name, None)) for name in _REQUIRED_METHODS)
