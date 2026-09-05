from __future__ import annotations

from email.message import EmailMessage

from gilbic_backend.config import Settings


class FakeSmtp:
    def __init__(self, host: str, port: int, timeout: float) -> None:
        self.host = host
        self.port = port
        self.timeout = timeout
        self.started_tls = False
        self.login_args: tuple[str, str] | None = None
        self.message: EmailMessage | None = None

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        return None

    def starttls(self) -> None:
        self.started_tls = True

    def login(self, username: str, password: str) -> None:
        self.login_args = (username, password)

    def send_message(self, message: EmailMessage) -> None:
        self.message = message


def _settings(**overrides) -> Settings:
    values = {
        "credential_email_sender_name": "SPINA Lending Company",
        "credential_email_from_address": "spinalendingcompany@gmail.com",
        "credential_email_site_label": "spina.com.ph",
        "credential_smtp_host": "smtp.gmail.com",
        "credential_smtp_port": 587,
        "credential_smtp_username": "spinalendingcompany@gmail.com",
        "credential_smtp_password": "gmail-app-password",
        "credential_smtp_timeout_seconds": 10.0,
    }
    values.update(overrides)
    return Settings(**values)


def test_unconfigured_mailer_returns_controlled_not_sent_result() -> None:
    from gilbic_backend.credential_mailer import SmtpCredentialMailer

    called = False

    def factory(host: str, port: int, timeout: float):
        nonlocal called
        called = True
        return FakeSmtp(host, port, timeout)

    mailer = SmtpCredentialMailer(
        settings=_settings(credential_smtp_password=""),
        smtp_factory=factory,
    )

    result = mailer.send_client_credentials(
        email="client@example.com",
        full_name="Maria Santos",
        username="spina.c.001",
        password="Generated@Pass9",
    )

    assert result.sent is False
    assert "not configured" in result.detail.lower()
    assert called is False


def test_mailer_sends_branded_username_and_password_without_financial_data() -> None:
    from gilbic_backend.credential_mailer import SmtpCredentialMailer

    smtp = FakeSmtp("", 0, 0)

    def factory(host: str, port: int, timeout: float):
        smtp.host = host
        smtp.port = port
        smtp.timeout = timeout
        return smtp

    mailer = SmtpCredentialMailer(settings=_settings(), smtp_factory=factory)
    result = mailer.send_client_credentials(
        email="client@example.com",
        full_name="Maria Santos",
        username="spina.c.001",
        password="Generated@Pass9",
    )

    assert result.sent is True
    assert smtp.host == "smtp.gmail.com"
    assert smtp.port == 587
    assert smtp.started_tls is True
    assert smtp.login_args == (
        "spinalendingcompany@gmail.com",
        "gmail-app-password",
    )
    assert smtp.message is not None
    assert smtp.message["To"] == "client@example.com"
    assert "SPINA Lending Company" in str(smtp.message["From"])
    assert "SPINA" in str(smtp.message["Subject"])
    body = smtp.message.get_body(preferencelist=("plain",)).get_content()
    assert "Maria Santos" in body
    assert "spina.c.001" in body
    assert "Generated@Pass9" in body
    assert "spina.com.ph" in body
    assert "loan balance" not in body.lower()
    assert "payment history" not in body.lower()


def test_mailer_failure_does_not_echo_password_or_smtp_secret() -> None:
    from gilbic_backend.credential_mailer import SmtpCredentialMailer

    class BrokenSmtp(FakeSmtp):
        def send_message(self, message: EmailMessage) -> None:
            raise OSError("mail server failed with gmail-app-password")

    mailer = SmtpCredentialMailer(
        settings=_settings(),
        smtp_factory=lambda host, port, timeout: BrokenSmtp(host, port, timeout),
    )
    result = mailer.send_client_credentials(
        email="client@example.com",
        full_name="Maria Santos",
        username="spina.c.001",
        password="Generated@Pass9",
    )

    assert result.sent is False
    assert "Generated@Pass9" not in result.detail
    assert "gmail-app-password" not in result.detail
