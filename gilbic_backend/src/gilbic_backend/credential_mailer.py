from __future__ import annotations

import smtplib
from collections.abc import Callable
from dataclasses import dataclass
from email.message import EmailMessage
from email.utils import formataddr
from typing import Any

from .config import Settings, get_settings


@dataclass(frozen=True, slots=True)
class CredentialDeliveryResult:
    sent: bool
    detail: str


def _smtp_client(host: str, port: int, timeout: float) -> smtplib.SMTP:
    return smtplib.SMTP(host=host, port=port, timeout=timeout)


class SmtpCredentialMailer:
    def __init__(
        self,
        settings: Settings | None = None,
        *,
        smtp_factory: Callable[[str, int, float], Any] | None = None,
    ) -> None:
        self._settings = settings or get_settings()
        self._smtp_factory = smtp_factory or _smtp_client

    def send_client_credentials(
        self,
        *,
        email: str,
        full_name: str,
        username: str,
        password: str,
    ) -> CredentialDeliveryResult:
        if not self._settings.credential_smtp_configured:
            return CredentialDeliveryResult(
                sent=False,
                detail="SPINA credential email is not configured.",
            )

        message = EmailMessage()
        message["From"] = formataddr(
            (
                self._settings.credential_email_sender_name.strip(),
                self._settings.credential_email_from_address.strip(),
            )
        )
        message["To"] = email.strip().lower()
        message["Subject"] = "Your SPINA account credentials"
        message.set_content(
            "\n".join(
                (
                    f"Hello {full_name.strip()},",
                    "",
                    "Your SPINA Lending Company account is ready.",
                    f"Website: {self._settings.credential_email_site_label.strip()}",
                    f"Username: {username}",
                    f"Password: {password}",
                    "",
                    "Keep these credentials private. This password remains valid until "
                    "SPINA changes it for your account.",
                    "If you cannot sign in, contact SPINA Lending Company for assistance.",
                )
            )
        )

        try:
            with self._smtp_factory(
                self._settings.credential_smtp_host.strip(),
                self._settings.credential_smtp_port,
                self._settings.credential_smtp_timeout_seconds,
            ) as smtp:
                smtp.starttls()
                smtp.login(
                    self._settings.credential_smtp_username.strip(),
                    self._settings.credential_smtp_password,
                )
                smtp.send_message(message)
        except (OSError, smtplib.SMTPException):
            return CredentialDeliveryResult(
                sent=False,
                detail=(
                    "SPINA could not send the credential email. Provide the displayed "
                    "credentials to the borrower manually."
                ),
            )

        return CredentialDeliveryResult(
            sent=True,
            detail="SPINA account credentials were sent by email.",
        )
