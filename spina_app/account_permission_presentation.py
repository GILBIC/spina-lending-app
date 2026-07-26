"""Account permission summary presentation extracted in Wave 47."""
from __future__ import annotations

ACCOUNT_PERMISSION_TARGET = '_spina_v32_account_permission_text'
ACCOUNT_PERMISSION_SOURCE_LINES = 11
ACCOUNT_PERMISSION_SOURCE_SHA256 = 'd5505320cff939e064d9e85d4e8fc26ec4abe7d5b4f08852cf31d0b703abc6e4'
ACCOUNT_PERMISSION_SIGNATURE = 'role'


def _spina_v32_account_permission_text(role):
    r = str(role or "").strip()
    if r == "Admin":
        return "Full app access"
    if r == "Encoder":
        return "Encoding, reports, and route access"
    if r == "Viewer":
        return "Reports access"
    if r == "System":
        return "Audit, controls, and system tools"
    return "Custom account access"
