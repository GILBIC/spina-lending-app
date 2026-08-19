from fastapi import FastAPI
from fastapi.responses import JSONResponse

from . import __version__
from .account_api import create_account_router
from .activity_notification_api import create_activity_notification_router
from .auth_api import create_auth_router
from .client_gcash_api import create_client_gcash_router
from .client_loan_api import create_client_loan_router
from .client_payment_api import create_client_payment_router
from .collection_api import create_collection_api_router
from .collection_correction_api import create_collection_correction_router
from .collection_void_api import create_collection_void_router
from .collector_route_api import create_collector_route_router
from .combined_collection_api import create_combined_collection_router
from .config import get_settings
from .contract_collection_activation_api import (
    create_contract_collection_activation_router,
)
from .contract_schedule_registration_api import (
    create_contract_schedule_registration_router,
)
from .cross_period_accounting_sequence_api import (
    create_cross_period_accounting_sequence_router,
)
from .cross_remittance_api import create_cross_remittance_router
from .database import database_ready
from .delegated_area_api import create_delegated_area_router
from .ecl_a5_accounting_api import create_ecl_a5_accounting_router
from .ecl_allowance_posting_api import create_ecl_allowance_posting_router
from .ecl_credit_risk_label_api import create_ecl_credit_risk_label_router
from .ecl_forward_looking_evidence_api import create_ecl_forward_looking_evidence_router
from .ecl_outcome_review_api import create_ecl_outcome_review_router
from .ecl_quantitative_measurement_api import create_ecl_quantitative_measurement_router
from .eir_cash_allocation_api import create_eir_cash_allocation_router
from .eir_period_journal_api import create_eir_period_journal_router
from .financial_accounting_api import create_financial_accounting_router
from .financial_statements_api import create_financial_statements_router
from .general_journal_api import create_general_journal_router
from .greenfield_regular_eir_anchor_api import (
    create_greenfield_regular_eir_anchor_router,
)
from .greenfield_regular_renewal_final_reconciliation_api import (
    create_greenfield_regular_renewal_final_reconciliation_router,
)
from .greenfield_regular_renewal_rollforward_api import (
    create_greenfield_regular_renewal_rollforward_router,
)
from .initial_capital_funding_api import create_initial_capital_funding_router
from .loan_disbursement_cancellation_api import (
    create_loan_disbursement_cancellation_router,
)
from .loan_disbursement_evidence_api import create_loan_disbursement_evidence_router
from .loan_disbursement_journal_draft_api import (
    create_loan_disbursement_journal_draft_router,
)
from .loan_disbursement_journal_posting_api import (
    create_loan_disbursement_journal_posting_router,
)
from .loan_renewal_execution_evidence_api import (
    create_loan_renewal_execution_evidence_router,
)
from .management_api import create_management_router
from .management_loan_api import create_management_loan_router
from .management_operations_api import create_management_operations_router
from .management_no_collection_api import create_management_no_collection_router
from .notification_api import create_notification_router
from .opening_balance_journal_api import create_opening_balance_journal_router
from .opening_balance_workbook_api import create_opening_balance_workbook_router
from .other_area_api import create_other_area_router
from .period_close_api import create_period_close_router
from .posting_ready_evidence_review_api import (
    create_posting_ready_evidence_review_router,
)
from .regular_journal_draft_api import create_regular_journal_draft_router
from .regular_journal_posting_api import create_regular_journal_posting_router
from .remittance_accounting_api import create_remittance_accounting_router
from .remittance_api import create_remittance_router
from .remittance_photo_api import create_remittance_photo_router
from .remittance_transfer_journal_api import create_remittance_transfer_journal_router
from .renewal_api import create_renewal_router
from .renewal_boundary_eir_journal_api import (
    create_renewal_boundary_eir_journal_router,
)
from .renewal_treatment_accounting_target_api import (
    create_renewal_treatment_accounting_target_router,
)
from .renewal_treatment_decision_api import create_renewal_treatment_decision_router
from .renewal_treatment_readiness_api import create_renewal_treatment_readiness_router
from .renewal_workflow_api import create_renewal_workflow_router
from .renewal_workflow_query_api import create_renewal_workflow_query_router
from .seven_by_seven_journal_draft_api import create_seven_by_seven_journal_draft_router
from .seven_by_seven_journal_posting_api import (
    create_seven_by_seven_journal_posting_router,
)
from .source_event_accounting_api import create_source_event_accounting_router
from .support_api import create_support_router
from .v1_tax_additional_amendment_api import create_v1_tax_additional_amendment_router
from .v1_tax_adjustment_api import create_v1_tax_adjustment_router
from .v1_tax_evidence_api import create_v1_tax_evidence_router
from .v1_tax_liability_api import create_v1_tax_liability_router
from .v1_tax_recoverable_credit_api import create_v1_tax_recoverable_credit_router
from .v1_tax_recoverable_refund_api import create_v1_tax_recoverable_refund_router
from .v1_tax_settlement_api import create_v1_tax_settlement_router


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(title=settings.app_name, version=__version__)

    @app.get("/health/live")
    def liveness() -> dict[str, str]:
        return {"status": "ok", "service": "gilbic-backend"}

    @app.get("/health/ready")
    def readiness() -> JSONResponse:
        ready = database_ready(settings)
        return JSONResponse(
            status_code=200 if ready else 503,
            content={
                "status": "ready" if ready else "unavailable",
                "service": "gilbic-backend",
                "database": "ok" if ready else "unavailable",
            },
        )

    @app.get("/api/v1/meta")
    def metadata() -> dict[str, str]:
        return {"service": "gilbic-backend", "version": __version__}

    app.include_router(create_auth_router())
    app.include_router(create_account_router())
    app.include_router(create_management_router())
    app.include_router(create_management_loan_router())
    app.include_router(create_management_operations_router())
    app.include_router(create_management_no_collection_router())
    app.include_router(create_financial_accounting_router())
    app.include_router(create_financial_statements_router())
    app.include_router(create_source_event_accounting_router())
    app.include_router(create_seven_by_seven_journal_draft_router())
    app.include_router(create_seven_by_seven_journal_posting_router())
    app.include_router(create_loan_disbursement_evidence_router())
    app.include_router(create_loan_disbursement_journal_draft_router())
    app.include_router(create_loan_disbursement_journal_posting_router())
    app.include_router(create_loan_disbursement_cancellation_router())
    app.include_router(create_loan_renewal_execution_evidence_router())
    app.include_router(create_greenfield_regular_eir_anchor_router())
    app.include_router(create_greenfield_regular_renewal_rollforward_router())
    app.include_router(create_renewal_boundary_eir_journal_router())
    app.include_router(create_greenfield_regular_renewal_final_reconciliation_router())
    app.include_router(create_renewal_treatment_readiness_router())
    app.include_router(create_renewal_treatment_decision_router())
    app.include_router(create_renewal_treatment_accounting_target_router())
    app.include_router(create_remittance_accounting_router())
    app.include_router(create_remittance_transfer_journal_router())
    app.include_router(create_eir_cash_allocation_router())
    app.include_router(create_eir_period_journal_router())
    app.include_router(create_cross_period_accounting_sequence_router())
    app.include_router(create_posting_ready_evidence_review_router())
    app.include_router(create_regular_journal_draft_router())
    app.include_router(create_regular_journal_posting_router())
    app.include_router(create_contract_schedule_registration_router())
    app.include_router(create_contract_collection_activation_router())
    app.include_router(create_ecl_outcome_review_router())
    app.include_router(create_ecl_credit_risk_label_router())
    app.include_router(create_ecl_forward_looking_evidence_router())
    app.include_router(create_ecl_quantitative_measurement_router())
    app.include_router(create_ecl_allowance_posting_router())
    app.include_router(create_ecl_a5_accounting_router())
    app.include_router(create_initial_capital_funding_router())
    app.include_router(create_v1_tax_evidence_router())
    app.include_router(create_v1_tax_liability_router())
    app.include_router(create_v1_tax_settlement_router())
    app.include_router(create_v1_tax_adjustment_router())
    app.include_router(create_v1_tax_additional_amendment_router())
    app.include_router(create_v1_tax_recoverable_refund_router())
    app.include_router(create_v1_tax_recoverable_credit_router())
    app.include_router(create_period_close_router())
    app.include_router(create_opening_balance_workbook_router())
    app.include_router(create_opening_balance_journal_router())
    app.include_router(create_general_journal_router())
    app.include_router(create_client_loan_router())
    app.include_router(create_client_payment_router())
    app.include_router(create_client_gcash_router())
    app.include_router(create_renewal_router())
    app.include_router(create_renewal_workflow_router())
    app.include_router(create_renewal_workflow_query_router())
    app.include_router(create_support_router())
    app.include_router(create_collector_route_router())
    app.include_router(create_delegated_area_router())
    app.include_router(create_other_area_router())
    app.include_router(create_collection_api_router())
    app.include_router(create_combined_collection_router())
    app.include_router(create_collection_correction_router())
    app.include_router(create_collection_void_router())
    app.include_router(create_remittance_router())
    app.include_router(create_cross_remittance_router())
    app.include_router(create_notification_router())
    app.include_router(create_activity_notification_router())
    app.include_router(create_remittance_photo_router())
    return app


app = create_app()