"""Installed accounting capability, separate from any source's readiness."""


def collector_accounting_capability(conn):
    capability = conn.execute(
        "SELECT to_regprocedure('accounting.post_collector_liability(uuid,text,text,uuid)') IS NOT NULL AS available, "
        "to_regprocedure('treasury.collector_credit_application_ready()') IS NOT NULL AS application_supported"
    ).fetchone()
    installed = capability["available"]
    applications = bool(installed and capability.get("application_supported"))
    return {
        "available": bool(installed),
        "supported_source_families": [
            "settlement",
            "recognition",
            "return_debit",
            "return_confirmation",
            "return_reversal",
        ]
        + (["credit_application"] if applications else [])
        if installed
        else [],
        "unsupported_source_families": [
            "opening",
            "historical_correction",
            "custody_exception",
        ]
        + ([] if applications else ["credit_application"]),
        "review_required": True,
        "automatic_posting": False,
        "comprehensive_source_coverage": False,
        "review_path": "/management/financial-accounting/collector",
        "message": (
            "Accepted counts, credit recognition and actual return steps have explicit accounting reviews. "
            "A configured book, reviewed cash mapping and current source evidence are required. "
            "Operational actions do not post journals."
            if installed
            else "Collector accounting review is unavailable until its protected adapter is installed."
        ),
    }
