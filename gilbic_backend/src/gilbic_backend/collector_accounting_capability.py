"""Installed accounting capability, separate from any source's readiness."""


def collector_accounting_capability(conn):
    installed = conn.execute(
        "SELECT to_regprocedure('accounting.post_collector_liability(uuid,text,text,uuid)') IS NOT NULL AS available"
    ).fetchone()["available"]
    return {
        "available": bool(installed),
        "supported_source_families": [
            "settlement",
            "recognition",
            "return_debit",
            "return_confirmation",
            "return_reversal",
        ]
        if installed
        else [],
        "unsupported_source_families": [
            "opening",
            "historical_correction",
            "credit_application",
            "custody_exception",
        ],
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
