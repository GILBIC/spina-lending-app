"""Active account header presentation extracted in Wave 46."""
from __future__ import annotations

_ACCOUNT_HEADER_DEPENDENCIES = {}
_PROTECTED_GLOBALS = {
    "__builtins__", "__cached__", "__doc__", "__file__", "__loader__",
    "__name__", "__package__", "__spec__",
    "_ACCOUNT_HEADER_DEPENDENCIES", "_PROTECTED_GLOBALS",
    "configure_account_header_dependencies",
    "ACCOUNT_HEADER_TARGETS", "ACCOUNT_HEADER_SOURCE_LINES",
    "ACCOUNT_HEADER_SOURCE_SHA256", "ACCOUNT_HEADER_SIGNATURES",
    "ACCOUNT_HEADER_NESTED_CALLBACKS", "ACCOUNT_HEADER_CALLS",
}


def configure_account_header_dependencies(namespace):
    _ACCOUNT_HEADER_DEPENDENCIES.clear()
    _ACCOUNT_HEADER_DEPENDENCIES.update(namespace)
    for name, value in namespace.items():
        if name not in _PROTECTED_GLOBALS:
            globals()[name] = value


ACCOUNT_HEADER_TARGETS = ['_spina_v32_refresh_user_header', '_spina_v32_build_header']
ACCOUNT_HEADER_SOURCE_LINES = {'_spina_v32_refresh_user_header': 14, '_spina_v32_build_header': 12}
ACCOUNT_HEADER_SOURCE_SHA256 = {'_spina_v32_refresh_user_header': '01feaa575f128e605ab8bb143c208503cad6868103591d9fe72b108045c88f5a', '_spina_v32_build_header': 'ff46e61d0f56a1432ca0d4e4e5257936ff3ba150a84d5b43b254e98424368bac'}
ACCOUNT_HEADER_SIGNATURES = {'_spina_v32_refresh_user_header': "self", '_spina_v32_build_header': "self, *args, **kwargs"}
ACCOUNT_HEADER_NESTED_CALLBACKS = {'_spina_v32_refresh_user_header': [], '_spina_v32_build_header': []}
ACCOUNT_HEADER_CALLS = {'_spina_v32_refresh_user_header': ['_log_suppressed_once', '_spina_v32_account_display_name', 'getattr', 'self._refresh_header_theme', 'self.user_role_label.config'], '_spina_v32_build_header': ['_spina_v32_orig_build_header', 'getattr', 'self._refresh_user_header', 'self.switch_account_btn.configure']}

def _spina_v32_refresh_user_header(self):
    try:
        if getattr(self, "user_role_label", None) is not None:
            display = _spina_v32_account_display_name(self, getattr(self, "user_name", ""))
            self.user_role_label.config(text=f"Account: {display}")
    except Exception as __spina_exc:
        try:
            _log_suppressed_once("v32_refresh_user_header", "v32 refresh user header failed", __spina_exc)
        except Exception:
            pass
    try:
        self._refresh_header_theme()
    except Exception:
        pass

def _spina_v32_build_header(self, *args, **kwargs):
    res = _spina_v32_orig_build_header(self, *args, **kwargs)
    try:
        self._refresh_user_header()
    except Exception:
        pass
    try:
        if getattr(self, "switch_account_btn", None) is not None:
            self.switch_account_btn.configure(text="Account")
    except Exception:
        pass
    return res
