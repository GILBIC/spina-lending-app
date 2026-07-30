#!/usr/bin/env python3
"""Focused runtime regression for the Wave 83 accounts boundary."""
from __future__ import annotations

import copy

from spina_app.features.accounts import install_accounts_feature
from spina_app.services.accounts import (
    account_choices,
    default_account_name,
    normalize_access_profile,
    selected_label_for_user,
)


class StatusVar:
    def __init__(self):
        self.value = ""

    def set(self, value):
        self.value = str(value)


class DummyApp:
    source_database = {
        "version": 1,
        "users": {
            "admin": {"role": "Admin", "salt": "a", "hash": "h"},
            "second": {
                "role": "Viewer",
                "display_name": "Owner Account",
                "salt": "b",
                "hash": "h",
            },
            "legacy": {"role": "Unknown", "salt": "c", "hash": "h"},
        },
    }

    def __init__(self):
        self.saved_databases = []
        self.saved_users = []
        self.saved_roles = []
        self.header_refreshes = 0
        self.navigation_refreshes = 0
        self.permission_refreshes = 0
        self.user_name = "admin"
        self.user_role = "Admin"
        self.status_var = StatusVar()

    def _load_users_db(self):
        return copy.deepcopy(self.source_database)

    def _save_users_db(self, database):
        self.saved_databases.append(copy.deepcopy(database))
        return True

    def _save_last_user(self, username):
        self.saved_users.append(username)

    def _save_user_role(self, role):
        self.saved_roles.append(role)

    def _rebuild_side_nav(self):
        self.navigation_refreshes += 1

    def apply_role_access(self):
        self.permission_refreshes += 1


def prompt_login(self, default_user="admin"):
    return "second", "Viewer"


def refresh_header(self):
    self.header_refreshes += 1


def build_header(self, *args, **kwargs):
    return args, kwargs


def main() -> None:
    assert normalize_access_profile("Admin") == "Admin"
    assert normalize_access_profile("bad") == "Viewer"
    assert normalize_access_profile("bad", default="Admin") == "Admin"
    assert default_account_name("admin") == "Owner Account"
    assert default_account_name("custom") == "custom"

    choices, label_to_user = account_choices(DummyApp.source_database["users"])
    assert choices == ["Owner Account", "legacy", "Owner Account 2"]
    assert label_to_user["Owner Account"] == "admin"
    assert label_to_user["Owner Account 2"] == "second"
    assert selected_label_for_user("second", choices, label_to_user) == "Owner Account 2"

    assert install_accounts_feature(
        DummyApp,
        namespace={"_log_exc": lambda *_args, **_kwargs: None},
        prompt_login=prompt_login,
        refresh_header=refresh_header,
        build_header=build_header,
    )
    assert DummyApp._spina_accounts_wave83_installed is True
    assert DummyApp._load_users_db.__module__ == "spina_app.features.accounts"
    assert DummyApp.switch_account.__module__ == "spina_app.features.accounts"

    app = DummyApp()
    database = app._load_users_db()
    users = database["users"]
    assert users["admin"]["display_name"] == "Owner Account"
    assert users["admin"]["access_profile"] == "Admin"
    assert users["admin"]["permission_summary"] == "Full app access"
    assert users["legacy"]["role"] == "Viewer"
    assert users["legacy"]["access_profile"] == "Viewer"
    assert len(app.saved_databases) == 1

    app.switch_account()
    assert app.user_name == "second"
    assert app.user_role == "Viewer"
    assert app.saved_users == ["second"]
    assert app.saved_roles == ["Viewer"]
    assert app.header_refreshes == 1
    assert app.navigation_refreshes == 1
    assert app.permission_refreshes == 1
    assert app.status_var.value == "Switched account: Owner Account → Owner Account"

    first_loader = DummyApp._load_users_db
    first_switch = DummyApp.switch_account
    assert install_accounts_feature(
        DummyApp,
        namespace={"_log_exc": lambda *_args, **_kwargs: None},
        prompt_login=prompt_login,
        refresh_header=refresh_header,
        build_header=build_header,
    )
    assert DummyApp._load_users_db is first_loader
    assert DummyApp.switch_account is first_switch

    print("Wave 83 accounts feature regression passed.")


if __name__ == "__main__":
    main()
