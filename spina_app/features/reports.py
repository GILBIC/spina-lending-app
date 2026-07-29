"""Complete Reports feature installer for SPINA Wave 80."""
from __future__ import annotations

from typing import Any, Mapping

from spina_app import client_statement_generation as _generation
from spina_app import report_controller as _controller
from spina_app import report_engine as _engine
from spina_app.reports_tab_presentation import (
    configure_reports_tab_dependencies,
    _build_reports_tab,
)


def _safe_log(callback, context: str, exc: BaseException | None = None) -> None:
    if not callable(callback):
        return
    try:
        callback(context, exc)
    except Exception:
        pass


def install_reports_feature(
    app_class: type | None,
    *,
    namespace: Mapping[str, Any],
    log_exc=None,
    log_suppressed_once=None,
) -> bool:
    """Install all active Reports methods exactly once."""
    if app_class is None:
        return False
    if bool(getattr(app_class, "_spina_reports_wave80_installed", False)):
        return True
    try:
        dependencies = dict(namespace)
        _engine.configure_report_engine_dependencies(dependencies)
        dependencies.update(
            {
                "generate_client_pdf": _engine.generate_client_pdf,
                "REPORT_GENERATION_COUNT_FILE": _engine.REPORT_GENERATION_COUNT_FILE,
                "REPORT_GENERATION_LOG_FILE": _engine.REPORT_GENERATION_LOG_FILE,
                "REPORT_GENERATION_LOG_CSV": _engine.REPORT_GENERATION_LOG_CSV,
                "_spina_record_report_generation": _engine._spina_record_report_generation,
            }
        )
        missing_controller = _controller.configure_report_controller_dependencies(dependencies)
        configure_reports_tab_dependencies(dependencies)
        _generation.configure_client_statement_generation_dependencies(dependencies)
        if missing_controller:
            raise RuntimeError(
                "Reports controller dependencies unavailable: "
                + ", ".join(missing_controller)
            )

        app_class._build_reports_tab = _build_reports_tab
        app_class.generate_pdf_selected = _generation.generate_pdf_selected
        for name, value in _controller.REPORT_CONTROLLER_METHODS.items():
            setattr(app_class, name, value)

        # Preserve compatibility for callers that still resolve report helpers from
        # the desktop entry module while keeping their implementation modular.
        try:
            namespace["generate_client_pdf"] = _engine.generate_client_pdf
            namespace["REPORT_GENERATION_COUNT_FILE"] = _engine.REPORT_GENERATION_COUNT_FILE
            namespace["REPORT_GENERATION_LOG_FILE"] = _engine.REPORT_GENERATION_LOG_FILE
            namespace["REPORT_GENERATION_LOG_CSV"] = _engine.REPORT_GENERATION_LOG_CSV
            namespace["_spina_record_report_generation"] = _engine._spina_record_report_generation
        except Exception:
            pass

        app_class._spina_reports_wave80_installed = True
        return True
    except Exception as exc:
        try:
            if callable(log_suppressed_once):
                log_suppressed_once(
                    "reports_wave80_install_failed",
                    "Wave 80 Reports installation failed",
                    exc,
                )
        except Exception:
            pass
        _safe_log(log_exc, "reports.wave80.install", exc)
        return False
