"""Complete Client Info Logs controller and installer for SPINA Wave 78."""
from __future__ import annotations

from typing import Any, Callable

from spina_app.repositories.client_info_logs import fetch_client_history_records
from spina_app.services.client_info_logs import transform_client_history_records
from spina_app.tabs.client_info_logs import (
    configure_client_info_logs_dependencies,
    _spina_v24_build_client_info_logs_tab,
    _spina_v24_refresh_client_info_logs,
    _spina_v24_render_client_info_logs,
)

LogCallback = Callable[[str, BaseException | None], Any]
SuppressedLogCallback = Callable[[str, str, BaseException | None], Any]


def _safe_log(
    callback: LogCallback | None,
    context: str,
    exc: BaseException | None = None,
) -> None:
    if not callable(callback):
        return
    try:
        callback(context, exc)
    except Exception:
        pass


def _safe_suppressed_log(
    callback: SuppressedLogCallback | None,
    key: str,
    message: str,
    exc: BaseException | None = None,
) -> None:
    if not callable(callback):
        return
    try:
        callback(key, message, exc)
    except Exception:
        pass


def fetch_client_info_log_rows(
    db: Any,
    *,
    limit: int = 5000,
    log_exc: LogCallback | None = None,
) -> list[dict[str, Any]]:
    """Read and transform Client Info Logs without any Tkinter dependency."""
    try:
        records = fetch_client_history_records(db, limit=limit)
        return transform_client_history_records(records)
    except Exception as exc:
        _safe_log(log_exc, "client_info_logs.fetch_rows", exc)
        return []


def install_client_info_logs_feature(
    app_class: type | None,
    *,
    log_exc: LogCallback | None = None,
    log_suppressed_once: SuppressedLogCallback | None = None,
) -> bool:
    """Install the complete Client Info Logs feature exactly once."""
    if app_class is None:
        return False
    if bool(getattr(app_class, "_spina_client_info_logs_wave78_installed", False)):
        return True

    def feature_log(
        context: str,
        exc: BaseException | None = None,
    ) -> None:
        _safe_log(log_exc, context, exc)

    def fetch_rows(db: Any, limit: int = 5000) -> list[dict[str, Any]]:
        return fetch_client_info_log_rows(
            db,
            limit=limit,
            log_exc=feature_log,
        )

    try:
        missing = configure_client_info_logs_dependencies(
            {
                "_log_exc": feature_log,
                "_spina_cilog_fetch_rows": fetch_rows,
            }
        )
        if missing:
            raise RuntimeError(
                "Client Info Logs dependencies unavailable: " + ", ".join(missing)
            )

        app_class._build_client_info_logs_tab = (
            _spina_v24_build_client_info_logs_tab
        )
        app_class.render_client_info_logs = _spina_v24_render_client_info_logs
        app_class.refresh_client_info_logs = _spina_v24_refresh_client_info_logs
        app_class._client_info_logs_fetch_rows = staticmethod(fetch_rows)

        original_init = app_class.__init__

        def init_with_client_info_logs(self, *args, **kwargs):
            original_init(self, *args, **kwargs)
            try:
                self._build_client_info_logs_tab()
            except Exception as exc:
                feature_log("client_info_logs.init", exc)

        app_class.__init__ = init_with_client_info_logs

        original_refresh_clients = getattr(app_class, "refresh_clients", None)
        if callable(original_refresh_clients):

            def refresh_clients_with_logs(self, *args, **kwargs):
                result = original_refresh_clients(self, *args, **kwargs)
                try:
                    self.refresh_client_info_logs()
                except Exception as exc:
                    feature_log("client_info_logs.refresh_hook", exc)
                return result

            app_class.refresh_clients = refresh_clients_with_logs

        app_class._spina_client_info_logs_wave78_installed = True
        return True
    except Exception as exc:
        _safe_suppressed_log(
            log_suppressed_once,
            "client_info_logs_wave78_install_failed",
            "Wave 78 Client Info Logs installation failed",
            exc,
        )
        feature_log("client_info_logs.wave78.install", exc)
        return False
