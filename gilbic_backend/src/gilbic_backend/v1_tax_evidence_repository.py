from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from uuid import UUID

import psycopg
from psycopg.rows import dict_row

from .database import open_connection


class V1TaxEvidenceError(RuntimeError):
    code = "v1_tax_evidence_error"


class V1TaxEvidenceBlocked(V1TaxEvidenceError):
    code = "v1_tax_evidence_blocked"


@dataclass(frozen=True, slots=True)
class V1TaxRuleEvidence:
    id: UUID
    tax_type: str
    rule_key: str
    rule_version: int
    effective_from: date
    effective_to: date | None
    treatment: str
    rate: Decimal
    maturity_max_days: int | None
    legal_source: str
    legal_reference: str
    retained_source_reference: str
    evidence_digest: str
    management_rationale: str
    supersedes_rule_id: UUID | None
    recorded_by_user_id: UUID
    recorded_at: datetime


@dataclass(frozen=True, slots=True)
class V1DstReadiness:
    loan_id: UUID
    client_id: UUID
    disbursement_event_id: UUID
    issue_date: date
    protected_issue_price: Decimal
    protected_term_days: int
    evidence_id: UUID | None
    evidence_version: int | None
    rule_evidence_id: UUID | None
    tax_due: Decimal | None
    calculation_digest: str | None
    tax_status: str
    tax_blocker: str | None
    tax_posting_enabled: bool
    automatic_source_posting: bool


@dataclass(frozen=True, slots=True)
class V1PercentageTaxReadiness:
    transaction_id: UUID
    loan_id: UUID
    client_id: UUID
    collection_date: date
    entry_type: str
    source_cash_amount: Decimal
    is_voided: bool
    evidence_id: UUID | None
    evidence_version: int | None
    rule_evidence_id: UUID | None
    taxable_lending_receipt_amount: Decimal | None
    principal_receipt_amount: Decimal | None
    tax_due: Decimal | None
    allocation_digest: str | None
    tax_status: str
    tax_blocker: str | None
    tax_posting_enabled: bool
    automatic_source_posting: bool


class PostgresV1TaxEvidenceRepository:
    """Management-only repository for Master #296 A6.2 tax evidence/readiness."""

    _RULE_COLUMNS = """
        id, tax_type, rule_key, rule_version, effective_from, effective_to,
        treatment, rate, maturity_max_days, legal_source, legal_reference,
        retained_source_reference, evidence_digest, management_rationale,
        supersedes_rule_id, recorded_by_user_id, recorded_at
    """
    _DST_COLUMNS = """
        loan_id, client_id, disbursement_event_id, issue_date,
        protected_issue_price, protected_term_days, evidence_id,
        evidence_version, rule_evidence_id, tax_due, calculation_digest,
        tax_status, tax_blocker, tax_posting_enabled, automatic_source_posting
    """
    _PERCENTAGE_COLUMNS = """
        transaction_id, loan_id, client_id, collection_date, entry_type,
        source_cash_amount, is_voided, evidence_id, evidence_version,
        rule_evidence_id, taxable_lending_receipt_amount,
        principal_receipt_amount, tax_due, allocation_digest, tax_status,
        tax_blocker, tax_posting_enabled, automatic_source_posting
    """

    def list_rules(
        self, *, limit: int = 100, offset: int = 0
    ) -> tuple[V1TaxRuleEvidence, ...]:
        with open_connection() as connection:
            with connection.cursor(row_factory=dict_row) as cursor:
                cursor.execute(
                    f"""
                    SELECT {self._RULE_COLUMNS}
                    FROM accounting.v1_tax_rule_evidence
                    ORDER BY tax_type, rule_key, rule_version DESC, recorded_at DESC
                    LIMIT %s OFFSET %s
                    """,
                    (limit, offset),
                )
                return tuple(V1TaxRuleEvidence(**dict(row)) for row in cursor.fetchall())

    def list_dst_readiness(
        self, *, status: str = "all", limit: int = 100, offset: int = 0
    ) -> tuple[V1DstReadiness, ...]:
        where = self._readiness_where(status)
        with open_connection() as connection:
            with connection.cursor(row_factory=dict_row) as cursor:
                cursor.execute(
                    f"""
                    SELECT {self._DST_COLUMNS}
                    FROM accounting.v1_tax_dst_readiness
                    WHERE {where}
                    ORDER BY issue_date DESC, loan_id
                    LIMIT %s OFFSET %s
                    """,
                    (limit, offset),
                )
                return tuple(V1DstReadiness(**dict(row)) for row in cursor.fetchall())

    def list_percentage_readiness(
        self, *, status: str = "all", limit: int = 100, offset: int = 0
    ) -> tuple[V1PercentageTaxReadiness, ...]:
        where = self._readiness_where(status)
        with open_connection() as connection:
            with connection.cursor(row_factory=dict_row) as cursor:
                cursor.execute(
                    f"""
                    SELECT {self._PERCENTAGE_COLUMNS}
                    FROM accounting.v1_tax_percentage_readiness
                    WHERE {where}
                    ORDER BY collection_date DESC, transaction_id
                    LIMIT %s OFFSET %s
                    """,
                    (limit, offset),
                )
                return tuple(
                    V1PercentageTaxReadiness(**dict(row)) for row in cursor.fetchall()
                )

    def summary(self) -> dict[str, object]:
        with open_connection() as connection:
            with connection.cursor(row_factory=dict_row) as cursor:
                cursor.execute("SELECT * FROM accounting.v1_tax_readiness_summary")
                row = cursor.fetchone()
                if row is None:
                    raise V1TaxEvidenceError("V1 tax readiness summary is unavailable.")
                return dict(row)

    def record_rule(
        self,
        *,
        actor_user_id: UUID,
        idempotency_key: UUID,
        tax_type: str,
        rule_key: str,
        effective_from: date,
        effective_to: date | None,
        treatment: str,
        rate: Decimal,
        maturity_max_days: int | None,
        legal_source: str,
        legal_reference: str,
        retained_source_reference: str,
        evidence_digest: str,
        management_rationale: str,
        supersedes_rule_id: UUID | None,
    ) -> UUID:
        return self._call_id(
            """
            SELECT accounting.record_v1_tax_rule_evidence(
                %s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s
            ) AS id
            """,
            (
                actor_user_id,
                idempotency_key,
                tax_type,
                rule_key,
                effective_from,
                effective_to,
                treatment,
                rate,
                maturity_max_days,
                legal_source,
                legal_reference,
                retained_source_reference,
                evidence_digest,
                management_rationale,
                supersedes_rule_id,
            ),
        )

    def record_dst(
        self,
        *,
        actor_user_id: UUID,
        idempotency_key: UUID,
        loan_id: UUID,
        disbursement_event_id: UUID,
        rule_evidence_id: UUID,
        expected_issue_price: Decimal,
        expected_term_days: int,
        expected_tax_due: Decimal,
        instrument_reference: str,
        instrument_digest: str,
        calculation_reference: str,
        calculation_digest: str,
        management_rationale: str,
        supersedes_evidence_id: UUID | None,
    ) -> UUID:
        return self._call_id(
            """
            SELECT accounting.record_v1_dst_evidence(
                %s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s
            ) AS id
            """,
            (
                actor_user_id,
                idempotency_key,
                loan_id,
                disbursement_event_id,
                rule_evidence_id,
                expected_issue_price,
                expected_term_days,
                expected_tax_due,
                instrument_reference,
                instrument_digest,
                calculation_reference,
                calculation_digest,
                management_rationale,
                supersedes_evidence_id,
            ),
        )

    def record_percentage(
        self,
        *,
        actor_user_id: UUID,
        idempotency_key: UUID,
        transaction_id: UUID,
        rule_evidence_id: UUID,
        expected_source_cash_amount: Decimal,
        taxable_lending_receipt_amount: Decimal,
        principal_receipt_amount: Decimal,
        expected_tax_due: Decimal,
        allocation_reference: str,
        allocation_digest: str,
        management_rationale: str,
        supersedes_evidence_id: UUID | None,
    ) -> UUID:
        return self._call_id(
            """
            SELECT accounting.record_v1_percentage_tax_evidence(
                %s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s
            ) AS id
            """,
            (
                actor_user_id,
                idempotency_key,
                transaction_id,
                rule_evidence_id,
                expected_source_cash_amount,
                taxable_lending_receipt_amount,
                principal_receipt_amount,
                expected_tax_due,
                allocation_reference,
                allocation_digest,
                management_rationale,
                supersedes_evidence_id,
            ),
        )

    @staticmethod
    def _readiness_where(status: str) -> str:
        clauses = {
            "all": "true",
            "ready": "tax_status = 'evidence_ready'",
            "blocked": "tax_status <> 'evidence_ready'",
        }
        clause = clauses.get(status)
        if clause is None:
            raise ValueError("Unsupported V1 tax readiness filter.")
        return clause

    @staticmethod
    def _call_id(query: str, params: tuple[object, ...]) -> UUID:
        try:
            with open_connection() as connection:
                with connection.cursor(row_factory=dict_row) as cursor:
                    cursor.execute(query, params)
                    row = cursor.fetchone()
                    if row is None or row["id"] is None:
                        raise V1TaxEvidenceBlocked(
                            "Protected V1 tax evidence action returned no immutable identifier."
                        )
                    result = UUID(str(row["id"]))
                connection.commit()
                return result
        except V1TaxEvidenceError:
            raise
        except psycopg.Error as exc:
            message = str(exc).split("CONTEXT:", 1)[0].strip()
            raise V1TaxEvidenceBlocked(message) from exc
