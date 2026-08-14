BEGIN;

-- Master #296 A6.2, slice 1: immutable evidence/readiness only.
-- This migration deliberately creates no tax journal, liability or payment.
-- Tax posting remains disabled until a later A6.2 slice proves the protected
-- General Journal path from exact evidence. Automatic source posting remains off.

INSERT INTO core.permissions (code, description)
VALUES
    ('accounting.tax.rule_evidence.record', 'Record immutable Management-approved V1 tax rule evidence'),
    ('accounting.tax.dst_evidence.record', 'Record immutable DST evidence for one exact protected loan debt-instrument issue'),
    ('accounting.tax.percentage_evidence.record', 'Record immutable percentage/gross-receipts tax allocation evidence for one exact protected cash transaction')
ON CONFLICT (code) DO UPDATE SET description = excluded.description;

INSERT INTO core.role_permissions (role_id, permission_code)
SELECT role.id, permission.code
FROM core.roles role
JOIN core.permissions permission
  ON permission.code IN (
      'accounting.tax.rule_evidence.record',
      'accounting.tax.dst_evidence.record',
      'accounting.tax.percentage_evidence.record'
  )
WHERE role.code = 'management'
ON CONFLICT DO NOTHING;

CREATE TABLE IF NOT EXISTS accounting.v1_tax_rule_evidence (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    idempotency_key UUID NOT NULL UNIQUE,
    tax_type TEXT NOT NULL CHECK (
        tax_type IN ('documentary_stamp_tax', 'percentage_tax_lending')
    ),
    rule_key TEXT NOT NULL CHECK (btrim(rule_key) <> ''),
    rule_version INTEGER NOT NULL CHECK (rule_version > 0),
    effective_from DATE NOT NULL,
    effective_to DATE,
    treatment TEXT NOT NULL CHECK (treatment IN ('taxable', 'exempt')),
    rate NUMERIC(14,10) NOT NULL CHECK (rate >= 0 AND rate <= 1),
    maturity_max_days INTEGER CHECK (maturity_max_days IS NULL OR maturity_max_days > 0),
    legal_source TEXT NOT NULL CHECK (btrim(legal_source) <> ''),
    legal_reference TEXT NOT NULL CHECK (btrim(legal_reference) <> ''),
    retained_source_reference TEXT NOT NULL CHECK (btrim(retained_source_reference) <> ''),
    evidence_digest TEXT NOT NULL CHECK (evidence_digest ~ '^[0-9a-f]{64}$'),
    management_rationale TEXT NOT NULL CHECK (length(btrim(management_rationale)) >= 20),
    supersedes_rule_id UUID REFERENCES accounting.v1_tax_rule_evidence(id) ON DELETE RESTRICT,
    recorded_by_user_id UUID NOT NULL REFERENCES core.users(id) ON DELETE RESTRICT,
    recorded_at TIMESTAMPTZ NOT NULL DEFAULT clock_timestamp(),
    CHECK (effective_to IS NULL OR effective_to >= effective_from),
    CHECK (
        (treatment = 'taxable' AND rate > 0)
        OR (treatment = 'exempt' AND rate = 0)
    ),
    CHECK (supersedes_rule_id IS NULL OR supersedes_rule_id <> id),
    UNIQUE (tax_type, rule_key, rule_version)
);

CREATE INDEX IF NOT EXISTS v1_tax_rule_evidence_effective_idx
    ON accounting.v1_tax_rule_evidence(tax_type, rule_key, effective_from, rule_version DESC);

CREATE TABLE IF NOT EXISTS accounting.v1_dst_evidence (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    idempotency_key UUID NOT NULL UNIQUE,
    loan_id UUID NOT NULL REFERENCES lending.loans(id) ON DELETE RESTRICT,
    client_id UUID NOT NULL REFERENCES lending.clients(id) ON DELETE RESTRICT,
    disbursement_event_id UUID NOT NULL
        REFERENCES lending.loan_disbursement_events(id) ON DELETE RESTRICT,
    rule_evidence_id UUID NOT NULL
        REFERENCES accounting.v1_tax_rule_evidence(id) ON DELETE RESTRICT,
    evidence_version INTEGER NOT NULL CHECK (evidence_version > 0),
    supersedes_evidence_id UUID REFERENCES accounting.v1_dst_evidence(id) ON DELETE RESTRICT,
    issue_date DATE NOT NULL,
    issue_price NUMERIC(18,2) NOT NULL CHECK (issue_price > 0),
    term_days INTEGER NOT NULL CHECK (term_days > 0),
    applied_rate NUMERIC(14,10) NOT NULL CHECK (applied_rate >= 0 AND applied_rate <= 1),
    proration_numerator INTEGER NOT NULL CHECK (proration_numerator > 0 AND proration_numerator <= 365),
    proration_denominator INTEGER NOT NULL CHECK (proration_denominator = 365),
    tax_due NUMERIC(18,2) NOT NULL CHECK (tax_due >= 0),
    instrument_reference TEXT NOT NULL CHECK (btrim(instrument_reference) <> ''),
    instrument_digest TEXT NOT NULL CHECK (instrument_digest ~ '^[0-9a-f]{64}$'),
    calculation_reference TEXT NOT NULL CHECK (btrim(calculation_reference) <> ''),
    calculation_digest TEXT NOT NULL CHECK (calculation_digest ~ '^[0-9a-f]{64}$'),
    management_rationale TEXT NOT NULL CHECK (length(btrim(management_rationale)) >= 20),
    recorded_by_user_id UUID NOT NULL REFERENCES core.users(id) ON DELETE RESTRICT,
    recorded_at TIMESTAMPTZ NOT NULL DEFAULT clock_timestamp(),
    CHECK (supersedes_evidence_id IS NULL OR supersedes_evidence_id <> id),
    UNIQUE (loan_id, evidence_version)
);

CREATE INDEX IF NOT EXISTS v1_dst_evidence_loan_idx
    ON accounting.v1_dst_evidence(loan_id, evidence_version DESC);

CREATE TABLE IF NOT EXISTS accounting.v1_percentage_tax_evidence (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    idempotency_key UUID NOT NULL UNIQUE,
    transaction_id UUID NOT NULL
        REFERENCES lending.collection_transactions(id) ON DELETE RESTRICT,
    loan_id UUID NOT NULL REFERENCES lending.loans(id) ON DELETE RESTRICT,
    client_id UUID NOT NULL REFERENCES lending.clients(id) ON DELETE RESTRICT,
    rule_evidence_id UUID NOT NULL
        REFERENCES accounting.v1_tax_rule_evidence(id) ON DELETE RESTRICT,
    evidence_version INTEGER NOT NULL CHECK (evidence_version > 0),
    supersedes_evidence_id UUID
        REFERENCES accounting.v1_percentage_tax_evidence(id) ON DELETE RESTRICT,
    collection_date DATE NOT NULL,
    source_cash_amount NUMERIC(18,2) NOT NULL CHECK (source_cash_amount > 0),
    taxable_lending_receipt_amount NUMERIC(18,2) NOT NULL
        CHECK (taxable_lending_receipt_amount >= 0),
    principal_receipt_amount NUMERIC(18,2) NOT NULL CHECK (principal_receipt_amount >= 0),
    applied_rate NUMERIC(14,10) NOT NULL CHECK (applied_rate >= 0 AND applied_rate <= 1),
    tax_due NUMERIC(18,2) NOT NULL CHECK (tax_due >= 0),
    allocation_reference TEXT NOT NULL CHECK (btrim(allocation_reference) <> ''),
    allocation_digest TEXT NOT NULL CHECK (allocation_digest ~ '^[0-9a-f]{64}$'),
    management_rationale TEXT NOT NULL CHECK (length(btrim(management_rationale)) >= 20),
    recorded_by_user_id UUID NOT NULL REFERENCES core.users(id) ON DELETE RESTRICT,
    recorded_at TIMESTAMPTZ NOT NULL DEFAULT clock_timestamp(),
    CHECK (source_cash_amount = taxable_lending_receipt_amount + principal_receipt_amount),
    CHECK (supersedes_evidence_id IS NULL OR supersedes_evidence_id <> id),
    UNIQUE (transaction_id, evidence_version)
);

CREATE INDEX IF NOT EXISTS v1_percentage_tax_evidence_transaction_idx
    ON accounting.v1_percentage_tax_evidence(transaction_id, evidence_version DESC);

CREATE OR REPLACE FUNCTION accounting.guard_v1_tax_evidence_write()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
    IF TG_OP = 'INSERT'
       AND coalesce(current_setting('accounting.v1_tax_evidence_insert_allowed', true), '') = 'on' THEN
        RETURN NEW;
    END IF;
    RAISE EXCEPTION 'V1 tax evidence is immutable and must use the protected Management evidence functions.';
END;
$$;

DROP TRIGGER IF EXISTS accounting_v1_tax_rule_evidence_guard
    ON accounting.v1_tax_rule_evidence;
CREATE TRIGGER accounting_v1_tax_rule_evidence_guard
BEFORE INSERT OR UPDATE OR DELETE ON accounting.v1_tax_rule_evidence
FOR EACH ROW EXECUTE FUNCTION accounting.guard_v1_tax_evidence_write();

DROP TRIGGER IF EXISTS accounting_v1_dst_evidence_guard
    ON accounting.v1_dst_evidence;
CREATE TRIGGER accounting_v1_dst_evidence_guard
BEFORE INSERT OR UPDATE OR DELETE ON accounting.v1_dst_evidence
FOR EACH ROW EXECUTE FUNCTION accounting.guard_v1_tax_evidence_write();

DROP TRIGGER IF EXISTS accounting_v1_percentage_tax_evidence_guard
    ON accounting.v1_percentage_tax_evidence;
CREATE TRIGGER accounting_v1_percentage_tax_evidence_guard
BEFORE INSERT OR UPDATE OR DELETE ON accounting.v1_percentage_tax_evidence
FOR EACH ROW EXECUTE FUNCTION accounting.guard_v1_tax_evidence_write();

CREATE OR REPLACE FUNCTION accounting.require_v1_tax_management_actor(
    p_actor_user_id UUID,
    p_permission TEXT
)
RETURNS VOID
LANGUAGE plpgsql
STABLE
AS $$
BEGIN
    IF p_actor_user_id IS NULL OR NOT EXISTS (
        SELECT 1
        FROM core.users actor
        JOIN core.user_roles user_role ON user_role.user_id = actor.id
        JOIN core.role_permissions role_permission ON role_permission.role_id = user_role.role_id
        WHERE actor.id = p_actor_user_id
          AND actor.status = 'active'
          AND role_permission.permission_code = p_permission
    ) THEN
        RAISE EXCEPTION 'An active Management actor with % permission is required.', p_permission;
    END IF;
END;
$$;

CREATE OR REPLACE FUNCTION accounting.record_v1_tax_rule_evidence(
    p_actor_user_id UUID,
    p_idempotency_key UUID,
    p_tax_type TEXT,
    p_rule_key TEXT,
    p_effective_from DATE,
    p_effective_to DATE,
    p_treatment TEXT,
    p_rate NUMERIC,
    p_maturity_max_days INTEGER,
    p_legal_source TEXT,
    p_legal_reference TEXT,
    p_retained_source_reference TEXT,
    p_evidence_digest TEXT,
    p_management_rationale TEXT,
    p_supersedes_rule_id UUID DEFAULT NULL
)
RETURNS UUID
LANGUAGE plpgsql
AS $$
DECLARE
    existing accounting.v1_tax_rule_evidence%ROWTYPE;
    prior accounting.v1_tax_rule_evidence%ROWTYPE;
    normalized_tax_type TEXT := btrim(coalesce(p_tax_type, ''));
    normalized_rule_key TEXT := btrim(coalesce(p_rule_key, ''));
    normalized_treatment TEXT := btrim(coalesce(p_treatment, ''));
    normalized_legal_source TEXT := btrim(coalesce(p_legal_source, ''));
    normalized_legal_reference TEXT := btrim(coalesce(p_legal_reference, ''));
    normalized_retained_reference TEXT := btrim(coalesce(p_retained_source_reference, ''));
    normalized_digest TEXT := lower(btrim(coalesce(p_evidence_digest, '')));
    normalized_rationale TEXT := btrim(coalesce(p_management_rationale, ''));
    normalized_rate NUMERIC(14,10) := round(coalesce(p_rate, -1), 10);
    next_version INTEGER;
    result_id UUID;
BEGIN
    PERFORM accounting.require_v1_tax_management_actor(
        p_actor_user_id,
        'accounting.tax.rule_evidence.record'
    );
    IF p_idempotency_key IS NULL THEN
        RAISE EXCEPTION 'Tax rule evidence requires an exact idempotency key.';
    END IF;
    IF normalized_tax_type NOT IN ('documentary_stamp_tax', 'percentage_tax_lending') THEN
        RAISE EXCEPTION 'Unsupported V1 tax type.';
    END IF;
    IF normalized_rule_key = '' OR p_effective_from IS NULL
       OR (p_effective_to IS NOT NULL AND p_effective_to < p_effective_from) THEN
        RAISE EXCEPTION 'Tax rule evidence requires a valid rule key and effective date range.';
    END IF;
    IF normalized_treatment NOT IN ('taxable', 'exempt') THEN
        RAISE EXCEPTION 'Tax rule evidence must explicitly state taxable or exempt treatment.';
    END IF;
    IF p_rate IS DISTINCT FROM normalized_rate OR normalized_rate < 0 OR normalized_rate > 1
       OR (normalized_treatment = 'taxable' AND normalized_rate <= 0)
       OR (normalized_treatment = 'exempt' AND normalized_rate <> 0) THEN
        RAISE EXCEPTION 'Tax rule evidence rate is invalid for the approved treatment.';
    END IF;
    IF p_maturity_max_days IS NOT NULL AND p_maturity_max_days <= 0 THEN
        RAISE EXCEPTION 'Tax rule maturity boundary must be positive when supplied.';
    END IF;
    IF normalized_legal_source = '' OR normalized_legal_reference = ''
       OR normalized_retained_reference = '' OR length(normalized_rationale) < 20
       OR normalized_digest !~ '^[0-9a-f]{64}$' THEN
        RAISE EXCEPTION 'Tax rule evidence requires retained legal source/reference, SHA-256 digest and substantive Management rationale.';
    END IF;

    SELECT * INTO existing
    FROM accounting.v1_tax_rule_evidence item
    WHERE item.idempotency_key = p_idempotency_key;
    IF existing.id IS NOT NULL THEN
        IF existing.tax_type <> normalized_tax_type
           OR existing.rule_key <> normalized_rule_key
           OR existing.effective_from <> p_effective_from
           OR existing.effective_to IS DISTINCT FROM p_effective_to
           OR existing.treatment <> normalized_treatment
           OR existing.rate <> normalized_rate
           OR existing.maturity_max_days IS DISTINCT FROM p_maturity_max_days
           OR existing.legal_source <> normalized_legal_source
           OR existing.legal_reference <> normalized_legal_reference
           OR existing.retained_source_reference <> normalized_retained_reference
           OR existing.evidence_digest <> normalized_digest
           OR existing.management_rationale <> normalized_rationale
           OR existing.supersedes_rule_id IS DISTINCT FROM p_supersedes_rule_id
           OR existing.recorded_by_user_id <> p_actor_user_id THEN
            RAISE EXCEPTION 'Existing tax rule evidence does not match the immutable retry identity.';
        END IF;
        RETURN existing.id;
    END IF;

    IF p_supersedes_rule_id IS NULL THEN
        IF EXISTS (
            SELECT 1 FROM accounting.v1_tax_rule_evidence item
            WHERE item.tax_type = normalized_tax_type AND item.rule_key = normalized_rule_key
        ) THEN
            RAISE EXCEPTION 'A later tax rule version must explicitly supersede the current immutable rule evidence.';
        END IF;
        next_version := 1;
    ELSE
        SELECT * INTO prior
        FROM accounting.v1_tax_rule_evidence item
        WHERE item.id = p_supersedes_rule_id
        FOR SHARE;
        IF prior.id IS NULL OR prior.tax_type <> normalized_tax_type OR prior.rule_key <> normalized_rule_key THEN
            RAISE EXCEPTION 'Superseded tax rule evidence must be the exact same tax type and rule key.';
        END IF;
        IF EXISTS (
            SELECT 1 FROM accounting.v1_tax_rule_evidence later
            WHERE later.supersedes_rule_id = prior.id
        ) THEN
            RAISE EXCEPTION 'The selected tax rule evidence was already superseded.';
        END IF;
        IF p_effective_from < prior.effective_from THEN
            RAISE EXCEPTION 'A superseding tax rule cannot become effective before the prior rule version.';
        END IF;
        next_version := prior.rule_version + 1;
    END IF;

    PERFORM set_config('accounting.v1_tax_evidence_insert_allowed', 'on', true);
    INSERT INTO accounting.v1_tax_rule_evidence (
        idempotency_key, tax_type, rule_key, rule_version, effective_from, effective_to,
        treatment, rate, maturity_max_days, legal_source, legal_reference,
        retained_source_reference, evidence_digest, management_rationale,
        supersedes_rule_id, recorded_by_user_id
    ) VALUES (
        p_idempotency_key, normalized_tax_type, normalized_rule_key, next_version,
        p_effective_from, p_effective_to, normalized_treatment, normalized_rate,
        p_maturity_max_days, normalized_legal_source, normalized_legal_reference,
        normalized_retained_reference, normalized_digest, normalized_rationale,
        p_supersedes_rule_id, p_actor_user_id
    ) RETURNING id INTO result_id;
    PERFORM set_config('accounting.v1_tax_evidence_insert_allowed', 'off', true);

    INSERT INTO core.audit_logs(actor_user_id, action, target_type, target_id, details)
    VALUES (
        p_actor_user_id,
        'accounting.tax.rule_evidence.recorded',
        'v1_tax_rule_evidence',
        result_id,
        jsonb_build_object(
            'tax_type', normalized_tax_type,
            'rule_key', normalized_rule_key,
            'rule_version', next_version,
            'effective_from', p_effective_from,
            'effective_to', p_effective_to,
            'treatment', normalized_treatment,
            'rate', normalized_rate,
            'evidence_digest', normalized_digest,
            'tax_posting_enabled', false,
            'automatic_source_posting', false
        )
    );
    RETURN result_id;
END;
$$;

CREATE OR REPLACE FUNCTION accounting.record_v1_dst_evidence(
    p_actor_user_id UUID,
    p_idempotency_key UUID,
    p_loan_id UUID,
    p_disbursement_event_id UUID,
    p_rule_evidence_id UUID,
    p_expected_issue_price NUMERIC,
    p_expected_term_days INTEGER,
    p_expected_tax_due NUMERIC,
    p_instrument_reference TEXT,
    p_instrument_digest TEXT,
    p_calculation_reference TEXT,
    p_calculation_digest TEXT,
    p_management_rationale TEXT,
    p_supersedes_evidence_id UUID DEFAULT NULL
)
RETURNS UUID
LANGUAGE plpgsql
AS $$
DECLARE
    existing accounting.v1_dst_evidence%ROWTYPE;
    prior accounting.v1_dst_evidence%ROWTYPE;
    loan_row lending.loans%ROWTYPE;
    event_row lending.loan_disbursement_events%ROWTYPE;
    rule_row accounting.v1_tax_rule_evidence%ROWTYPE;
    issue_price NUMERIC(18,2) := round(coalesce(p_expected_issue_price, -1), 2);
    tax_due NUMERIC(18,2) := round(coalesce(p_expected_tax_due, -1), 2);
    actual_term_days INTEGER;
    proration_days INTEGER;
    expected_due NUMERIC(18,2);
    normalized_instrument_reference TEXT := btrim(coalesce(p_instrument_reference, ''));
    normalized_instrument_digest TEXT := lower(btrim(coalesce(p_instrument_digest, '')));
    normalized_calculation_reference TEXT := btrim(coalesce(p_calculation_reference, ''));
    normalized_calculation_digest TEXT := lower(btrim(coalesce(p_calculation_digest, '')));
    normalized_rationale TEXT := btrim(coalesce(p_management_rationale, ''));
    next_version INTEGER;
    result_id UUID;
BEGIN
    PERFORM accounting.require_v1_tax_management_actor(
        p_actor_user_id,
        'accounting.tax.dst_evidence.record'
    );
    IF p_idempotency_key IS NULL OR p_loan_id IS NULL OR p_disbursement_event_id IS NULL
       OR p_rule_evidence_id IS NULL THEN
        RAISE EXCEPTION 'DST evidence requires exact source, rule and idempotency identifiers.';
    END IF;
    IF p_expected_issue_price IS DISTINCT FROM issue_price OR issue_price <= 0
       OR p_expected_tax_due IS DISTINCT FROM tax_due OR tax_due < 0
       OR p_expected_term_days IS NULL OR p_expected_term_days <= 0 THEN
        RAISE EXCEPTION 'DST evidence requires exact positive issue price/term and non-negative currency-cent tax due.';
    END IF;
    IF normalized_instrument_reference = '' OR normalized_calculation_reference = ''
       OR normalized_instrument_digest !~ '^[0-9a-f]{64}$'
       OR normalized_calculation_digest !~ '^[0-9a-f]{64}$'
       OR length(normalized_rationale) < 20 THEN
        RAISE EXCEPTION 'DST evidence requires retained instrument/calculation references, SHA-256 digests and substantive Management rationale.';
    END IF;

    SELECT * INTO existing
    FROM accounting.v1_dst_evidence item
    WHERE item.idempotency_key = p_idempotency_key;
    IF existing.id IS NOT NULL THEN
        IF existing.loan_id <> p_loan_id
           OR existing.disbursement_event_id <> p_disbursement_event_id
           OR existing.rule_evidence_id <> p_rule_evidence_id
           OR existing.issue_price <> issue_price
           OR existing.term_days <> p_expected_term_days
           OR existing.tax_due <> tax_due
           OR existing.instrument_reference <> normalized_instrument_reference
           OR existing.instrument_digest <> normalized_instrument_digest
           OR existing.calculation_reference <> normalized_calculation_reference
           OR existing.calculation_digest <> normalized_calculation_digest
           OR existing.management_rationale <> normalized_rationale
           OR existing.supersedes_evidence_id IS DISTINCT FROM p_supersedes_evidence_id
           OR existing.recorded_by_user_id <> p_actor_user_id THEN
            RAISE EXCEPTION 'Existing DST evidence does not match the immutable retry identity.';
        END IF;
        RETURN existing.id;
    END IF;

    PERFORM pg_advisory_xact_lock(hashtextextended('v1-tax-dst:' || p_loan_id::text, 0));

    SELECT * INTO loan_row FROM lending.loans loan WHERE loan.id = p_loan_id FOR SHARE;
    IF loan_row.id IS NULL THEN RAISE EXCEPTION 'DST source loan was not found.'; END IF;

    SELECT * INTO event_row
    FROM lending.loan_disbursement_events event
    WHERE event.id = p_disbursement_event_id
    FOR SHARE;
    IF event_row.id IS NULL OR event_row.loan_id <> loan_row.id
       OR event_row.client_id <> loan_row.client_id OR event_row.is_voided
       OR event_row.business_date <> loan_row.date_released
       OR event_row.principal_snapshot <> loan_row.principal THEN
        RAISE EXCEPTION 'DST evidence requires the exact active authoritative disbursement event matching the protected loan.';
    END IF;

    actual_term_days := loan_row.due_date - loan_row.date_released;
    IF actual_term_days <= 0 OR p_expected_term_days <> actual_term_days
       OR issue_price <> event_row.principal_snapshot THEN
        RAISE EXCEPTION 'DST issue price or term changed from the protected loan/disbursement coordinates.';
    END IF;

    SELECT * INTO rule_row
    FROM accounting.v1_tax_rule_evidence rule
    WHERE rule.id = p_rule_evidence_id
    FOR SHARE;
    IF rule_row.id IS NULL OR rule_row.tax_type <> 'documentary_stamp_tax'
       OR event_row.business_date < rule_row.effective_from
       OR (rule_row.effective_to IS NOT NULL AND event_row.business_date > rule_row.effective_to)
       OR (rule_row.maturity_max_days IS NOT NULL AND actual_term_days > rule_row.maturity_max_days) THEN
        RAISE EXCEPTION 'DST evidence requires the exact approved rule applicable to the issue date and term.';
    END IF;
    IF EXISTS (
        SELECT 1 FROM accounting.v1_tax_rule_evidence later
        WHERE later.tax_type = rule_row.tax_type
          AND later.rule_key = rule_row.rule_key
          AND later.rule_version > rule_row.rule_version
          AND later.effective_from <= event_row.business_date
          AND (later.effective_to IS NULL OR event_row.business_date <= later.effective_to)
    ) THEN
        RAISE EXCEPTION 'Selected DST rule evidence is superseded for this issue date.';
    END IF;

    proration_days := CASE WHEN actual_term_days < 365 THEN actual_term_days ELSE 365 END;
    expected_due := CASE
        WHEN rule_row.treatment = 'exempt' THEN 0::numeric(18,2)
        ELSE round(issue_price * rule_row.rate * proration_days::numeric / 365::numeric, 2)
    END;
    IF tax_due <> expected_due THEN
        RAISE EXCEPTION 'DST tax due does not reconcile to the exact approved rule, issue price and term-day proration.';
    END IF;

    IF p_supersedes_evidence_id IS NULL THEN
        IF EXISTS (SELECT 1 FROM accounting.v1_dst_evidence item WHERE item.loan_id = p_loan_id) THEN
            RAISE EXCEPTION 'A corrected DST evidence version must explicitly supersede the current immutable evidence.';
        END IF;
        next_version := 1;
    ELSE
        SELECT * INTO prior
        FROM accounting.v1_dst_evidence item
        WHERE item.id = p_supersedes_evidence_id
        FOR SHARE;
        IF prior.id IS NULL OR prior.loan_id <> p_loan_id THEN
            RAISE EXCEPTION 'Superseded DST evidence must belong to the exact same loan.';
        END IF;
        IF EXISTS (SELECT 1 FROM accounting.v1_dst_evidence later WHERE later.supersedes_evidence_id = prior.id) THEN
            RAISE EXCEPTION 'The selected DST evidence was already superseded.';
        END IF;
        next_version := prior.evidence_version + 1;
    END IF;

    PERFORM set_config('accounting.v1_tax_evidence_insert_allowed', 'on', true);
    INSERT INTO accounting.v1_dst_evidence (
        idempotency_key, loan_id, client_id, disbursement_event_id, rule_evidence_id,
        evidence_version, supersedes_evidence_id, issue_date, issue_price, term_days,
        applied_rate, proration_numerator, proration_denominator, tax_due,
        instrument_reference, instrument_digest, calculation_reference,
        calculation_digest, management_rationale, recorded_by_user_id
    ) VALUES (
        p_idempotency_key, loan_row.id, loan_row.client_id, event_row.id, rule_row.id,
        next_version, p_supersedes_evidence_id, event_row.business_date, issue_price,
        actual_term_days, rule_row.rate, proration_days, 365, tax_due,
        normalized_instrument_reference, normalized_instrument_digest,
        normalized_calculation_reference, normalized_calculation_digest,
        normalized_rationale, p_actor_user_id
    ) RETURNING id INTO result_id;
    PERFORM set_config('accounting.v1_tax_evidence_insert_allowed', 'off', true);

    INSERT INTO core.audit_logs(actor_user_id, action, target_type, target_id, details)
    VALUES (
        p_actor_user_id,
        'accounting.tax.dst_evidence.recorded',
        'v1_dst_evidence',
        result_id,
        jsonb_build_object(
            'loan_id', loan_row.id,
            'disbursement_event_id', event_row.id,
            'rule_evidence_id', rule_row.id,
            'evidence_version', next_version,
            'issue_date', event_row.business_date,
            'issue_price', issue_price,
            'term_days', actual_term_days,
            'tax_due', tax_due,
            'tax_posting_enabled', false,
            'automatic_source_posting', false
        )
    );
    RETURN result_id;
END;
$$;

CREATE OR REPLACE FUNCTION accounting.record_v1_percentage_tax_evidence(
    p_actor_user_id UUID,
    p_idempotency_key UUID,
    p_transaction_id UUID,
    p_rule_evidence_id UUID,
    p_expected_source_cash_amount NUMERIC,
    p_taxable_lending_receipt_amount NUMERIC,
    p_principal_receipt_amount NUMERIC,
    p_expected_tax_due NUMERIC,
    p_allocation_reference TEXT,
    p_allocation_digest TEXT,
    p_management_rationale TEXT,
    p_supersedes_evidence_id UUID DEFAULT NULL
)
RETURNS UUID
LANGUAGE plpgsql
AS $$
DECLARE
    existing accounting.v1_percentage_tax_evidence%ROWTYPE;
    prior accounting.v1_percentage_tax_evidence%ROWTYPE;
    transaction_row lending.collection_transactions%ROWTYPE;
    rule_row accounting.v1_tax_rule_evidence%ROWTYPE;
    source_cash NUMERIC(18,2) := round(coalesce(p_expected_source_cash_amount, -1), 2);
    taxable_receipt NUMERIC(18,2) := round(coalesce(p_taxable_lending_receipt_amount, -1), 2);
    principal_receipt NUMERIC(18,2) := round(coalesce(p_principal_receipt_amount, -1), 2);
    tax_due NUMERIC(18,2) := round(coalesce(p_expected_tax_due, -1), 2);
    expected_due NUMERIC(18,2);
    normalized_reference TEXT := btrim(coalesce(p_allocation_reference, ''));
    normalized_digest TEXT := lower(btrim(coalesce(p_allocation_digest, '')));
    normalized_rationale TEXT := btrim(coalesce(p_management_rationale, ''));
    next_version INTEGER;
    result_id UUID;
BEGIN
    PERFORM accounting.require_v1_tax_management_actor(
        p_actor_user_id,
        'accounting.tax.percentage_evidence.record'
    );
    IF p_idempotency_key IS NULL OR p_transaction_id IS NULL OR p_rule_evidence_id IS NULL THEN
        RAISE EXCEPTION 'Percentage-tax evidence requires exact source, rule and idempotency identifiers.';
    END IF;
    IF p_expected_source_cash_amount IS DISTINCT FROM source_cash OR source_cash <= 0
       OR p_taxable_lending_receipt_amount IS DISTINCT FROM taxable_receipt OR taxable_receipt < 0
       OR p_principal_receipt_amount IS DISTINCT FROM principal_receipt OR principal_receipt < 0
       OR p_expected_tax_due IS DISTINCT FROM tax_due OR tax_due < 0
       OR source_cash <> taxable_receipt + principal_receipt THEN
        RAISE EXCEPTION 'Percentage-tax allocation must exactly reconcile taxable receipt plus principal to source cash using currency-cent amounts.';
    END IF;
    IF normalized_reference = '' OR normalized_digest !~ '^[0-9a-f]{64}$'
       OR length(normalized_rationale) < 20 THEN
        RAISE EXCEPTION 'Percentage-tax evidence requires retained allocation reference, SHA-256 digest and substantive Management rationale.';
    END IF;

    SELECT * INTO existing
    FROM accounting.v1_percentage_tax_evidence item
    WHERE item.idempotency_key = p_idempotency_key;
    IF existing.id IS NOT NULL THEN
        IF existing.transaction_id <> p_transaction_id
           OR existing.rule_evidence_id <> p_rule_evidence_id
           OR existing.source_cash_amount <> source_cash
           OR existing.taxable_lending_receipt_amount <> taxable_receipt
           OR existing.principal_receipt_amount <> principal_receipt
           OR existing.tax_due <> tax_due
           OR existing.allocation_reference <> normalized_reference
           OR existing.allocation_digest <> normalized_digest
           OR existing.management_rationale <> normalized_rationale
           OR existing.supersedes_evidence_id IS DISTINCT FROM p_supersedes_evidence_id
           OR existing.recorded_by_user_id <> p_actor_user_id THEN
            RAISE EXCEPTION 'Existing percentage-tax evidence does not match the immutable retry identity.';
        END IF;
        RETURN existing.id;
    END IF;

    PERFORM pg_advisory_xact_lock(hashtextextended('v1-tax-percentage:' || p_transaction_id::text, 0));

    SELECT * INTO transaction_row
    FROM lending.collection_transactions transaction
    WHERE transaction.id = p_transaction_id
    FOR SHARE;
    IF transaction_row.id IS NULL OR transaction_row.is_voided
       OR transaction_row.entry_type NOT IN ('payment', 'advance')
       OR transaction_row.amount <= 0 OR transaction_row.amount <> source_cash THEN
        RAISE EXCEPTION 'Percentage-tax evidence requires the exact non-voided positive protected payment/advance transaction.';
    END IF;
    IF NOT EXISTS (
        SELECT 1 FROM accounting.regular_journal_posting_entries posted
        WHERE posted.transaction_id = transaction_row.id
        UNION ALL
        SELECT 1 FROM accounting.seven_by_seven_journal_postings posted
        WHERE posted.transaction_id = transaction_row.id
    ) THEN
        RAISE EXCEPTION 'Percentage-tax evidence requires the source cash transaction to have completed its protected lending accounting posting first.';
    END IF;

    SELECT * INTO rule_row
    FROM accounting.v1_tax_rule_evidence rule
    WHERE rule.id = p_rule_evidence_id
    FOR SHARE;
    IF rule_row.id IS NULL OR rule_row.tax_type <> 'percentage_tax_lending'
       OR transaction_row.collection_date < rule_row.effective_from
       OR (rule_row.effective_to IS NOT NULL AND transaction_row.collection_date > rule_row.effective_to) THEN
        RAISE EXCEPTION 'Percentage-tax evidence requires the exact approved rule applicable to the collection date.';
    END IF;
    IF rule_row.maturity_max_days IS NOT NULL AND EXISTS (
        SELECT 1 FROM lending.loans loan
        WHERE loan.id = transaction_row.loan_id
          AND (loan.due_date - loan.date_released) > rule_row.maturity_max_days
    ) THEN
        RAISE EXCEPTION 'Selected percentage-tax rule maturity boundary does not cover the source loan.';
    END IF;
    IF EXISTS (
        SELECT 1 FROM accounting.v1_tax_rule_evidence later
        WHERE later.tax_type = rule_row.tax_type
          AND later.rule_key = rule_row.rule_key
          AND later.rule_version > rule_row.rule_version
          AND later.effective_from <= transaction_row.collection_date
          AND (later.effective_to IS NULL OR transaction_row.collection_date <= later.effective_to)
    ) THEN
        RAISE EXCEPTION 'Selected percentage-tax rule evidence is superseded for this collection date.';
    END IF;

    expected_due := CASE
        WHEN rule_row.treatment = 'exempt' THEN 0::numeric(18,2)
        ELSE round(taxable_receipt * rule_row.rate, 2)
    END;
    IF tax_due <> expected_due THEN
        RAISE EXCEPTION 'Percentage-tax due does not reconcile to the exact approved rule and retained taxable lending-receipt allocation.';
    END IF;

    IF p_supersedes_evidence_id IS NULL THEN
        IF EXISTS (
            SELECT 1 FROM accounting.v1_percentage_tax_evidence item
            WHERE item.transaction_id = p_transaction_id
        ) THEN
            RAISE EXCEPTION 'A corrected percentage-tax evidence version must explicitly supersede the current immutable evidence.';
        END IF;
        next_version := 1;
    ELSE
        SELECT * INTO prior
        FROM accounting.v1_percentage_tax_evidence item
        WHERE item.id = p_supersedes_evidence_id
        FOR SHARE;
        IF prior.id IS NULL OR prior.transaction_id <> p_transaction_id THEN
            RAISE EXCEPTION 'Superseded percentage-tax evidence must belong to the exact same source transaction.';
        END IF;
        IF EXISTS (
            SELECT 1 FROM accounting.v1_percentage_tax_evidence later
            WHERE later.supersedes_evidence_id = prior.id
        ) THEN
            RAISE EXCEPTION 'The selected percentage-tax evidence was already superseded.';
        END IF;
        next_version := prior.evidence_version + 1;
    END IF;

    PERFORM set_config('accounting.v1_tax_evidence_insert_allowed', 'on', true);
    INSERT INTO accounting.v1_percentage_tax_evidence (
        idempotency_key, transaction_id, loan_id, client_id, rule_evidence_id,
        evidence_version, supersedes_evidence_id, collection_date, source_cash_amount,
        taxable_lending_receipt_amount, principal_receipt_amount, applied_rate, tax_due,
        allocation_reference, allocation_digest, management_rationale, recorded_by_user_id
    ) VALUES (
        p_idempotency_key, transaction_row.id, transaction_row.loan_id, transaction_row.client_id,
        rule_row.id, next_version, p_supersedes_evidence_id, transaction_row.collection_date,
        source_cash, taxable_receipt, principal_receipt, rule_row.rate, tax_due,
        normalized_reference, normalized_digest, normalized_rationale, p_actor_user_id
    ) RETURNING id INTO result_id;
    PERFORM set_config('accounting.v1_tax_evidence_insert_allowed', 'off', true);

    INSERT INTO core.audit_logs(actor_user_id, action, target_type, target_id, details)
    VALUES (
        p_actor_user_id,
        'accounting.tax.percentage_evidence.recorded',
        'v1_percentage_tax_evidence',
        result_id,
        jsonb_build_object(
            'transaction_id', transaction_row.id,
            'loan_id', transaction_row.loan_id,
            'rule_evidence_id', rule_row.id,
            'evidence_version', next_version,
            'collection_date', transaction_row.collection_date,
            'source_cash_amount', source_cash,
            'taxable_lending_receipt_amount', taxable_receipt,
            'principal_receipt_amount', principal_receipt,
            'tax_due', tax_due,
            'tax_posting_enabled', false,
            'automatic_source_posting', false
        )
    );
    RETURN result_id;
END;
$$;

CREATE OR REPLACE VIEW accounting.v1_tax_dst_readiness AS
WITH latest AS (
    SELECT DISTINCT ON (evidence.loan_id)
        evidence.*
    FROM accounting.v1_dst_evidence evidence
    ORDER BY evidence.loan_id, evidence.evidence_version DESC, evidence.recorded_at DESC
)
SELECT
    event.loan_id,
    event.client_id,
    event.id AS disbursement_event_id,
    event.business_date AS issue_date,
    event.principal_snapshot AS protected_issue_price,
    (loan.due_date - loan.date_released)::integer AS protected_term_days,
    latest.id AS evidence_id,
    latest.evidence_version,
    latest.rule_evidence_id,
    latest.tax_due,
    latest.calculation_digest,
    CASE
        WHEN event.is_voided THEN 'blocked_source_voided'
        WHEN latest.id IS NULL THEN 'evidence_required'
        WHEN latest.disbursement_event_id <> event.id
          OR latest.issue_date <> event.business_date
          OR latest.issue_price <> event.principal_snapshot
          OR latest.term_days <> (loan.due_date - loan.date_released)::integer
            THEN 'blocked_source_changed'
        WHEN rule.id IS NULL
          OR latest.issue_date < rule.effective_from
          OR (rule.effective_to IS NOT NULL AND latest.issue_date > rule.effective_to)
            THEN 'blocked_rule_not_applicable'
        WHEN EXISTS (
            SELECT 1 FROM accounting.v1_tax_rule_evidence later
            WHERE later.tax_type = rule.tax_type
              AND later.rule_key = rule.rule_key
              AND later.rule_version > rule.rule_version
              AND later.effective_from <= latest.issue_date
              AND (later.effective_to IS NULL OR latest.issue_date <= later.effective_to)
        ) THEN 'blocked_rule_superseded'
        ELSE 'evidence_ready'
    END AS tax_status,
    CASE
        WHEN event.is_voided THEN 'Authoritative disbursement evidence is voided; prior DST evidence cannot remain current.'
        WHEN latest.id IS NULL THEN 'Retained debt-instrument and DST calculation evidence is required.'
        WHEN latest.disbursement_event_id <> event.id
          OR latest.issue_date <> event.business_date
          OR latest.issue_price <> event.principal_snapshot
          OR latest.term_days <> (loan.due_date - loan.date_released)::integer
            THEN 'Protected loan/disbursement coordinates changed from the retained DST evidence.'
        WHEN rule.id IS NULL
          OR latest.issue_date < rule.effective_from
          OR (rule.effective_to IS NOT NULL AND latest.issue_date > rule.effective_to)
            THEN 'Approved DST rule evidence is missing or not effective for the issue date.'
        WHEN EXISTS (
            SELECT 1 FROM accounting.v1_tax_rule_evidence later
            WHERE later.tax_type = rule.tax_type
              AND later.rule_key = rule.rule_key
              AND later.rule_version > rule.rule_version
              AND later.effective_from <= latest.issue_date
              AND (later.effective_to IS NULL OR latest.issue_date <= later.effective_to)
        ) THEN 'A later approved DST rule version is effective for the issue date.'
        ELSE NULL
    END AS tax_blocker,
    false AS tax_posting_enabled,
    false AS automatic_source_posting
FROM lending.loan_disbursement_events event
JOIN lending.loans loan ON loan.id = event.loan_id
LEFT JOIN latest ON latest.loan_id = event.loan_id
LEFT JOIN accounting.v1_tax_rule_evidence rule ON rule.id = latest.rule_evidence_id;

CREATE OR REPLACE VIEW accounting.v1_tax_percentage_readiness AS
WITH protected_transactions AS (
    SELECT transaction_id FROM accounting.regular_journal_posting_entries
    UNION
    SELECT transaction_id FROM accounting.seven_by_seven_journal_postings
), latest AS (
    SELECT DISTINCT ON (evidence.transaction_id)
        evidence.*
    FROM accounting.v1_percentage_tax_evidence evidence
    ORDER BY evidence.transaction_id, evidence.evidence_version DESC, evidence.recorded_at DESC
)
SELECT
    transaction.id AS transaction_id,
    transaction.loan_id,
    transaction.client_id,
    transaction.collection_date,
    transaction.entry_type,
    transaction.amount AS source_cash_amount,
    transaction.is_voided,
    latest.id AS evidence_id,
    latest.evidence_version,
    latest.rule_evidence_id,
    latest.taxable_lending_receipt_amount,
    latest.principal_receipt_amount,
    latest.tax_due,
    latest.allocation_digest,
    CASE
        WHEN transaction.is_voided THEN 'blocked_source_voided'
        WHEN latest.id IS NULL THEN 'allocation_evidence_required'
        WHEN latest.loan_id <> transaction.loan_id
          OR latest.client_id <> transaction.client_id
          OR latest.collection_date <> transaction.collection_date
          OR latest.source_cash_amount <> transaction.amount
            THEN 'blocked_source_changed'
        WHEN latest.taxable_lending_receipt_amount + latest.principal_receipt_amount <> transaction.amount
            THEN 'blocked_allocation_unreconciled'
        WHEN rule.id IS NULL
          OR transaction.collection_date < rule.effective_from
          OR (rule.effective_to IS NOT NULL AND transaction.collection_date > rule.effective_to)
            THEN 'blocked_rule_not_applicable'
        WHEN EXISTS (
            SELECT 1 FROM accounting.v1_tax_rule_evidence later
            WHERE later.tax_type = rule.tax_type
              AND later.rule_key = rule.rule_key
              AND later.rule_version > rule.rule_version
              AND later.effective_from <= transaction.collection_date
              AND (later.effective_to IS NULL OR transaction.collection_date <= later.effective_to)
        ) THEN 'blocked_rule_superseded'
        ELSE 'evidence_ready'
    END AS tax_status,
    CASE
        WHEN transaction.is_voided THEN 'Protected collection source is voided; prior tax allocation cannot remain current.'
        WHEN latest.id IS NULL THEN 'Retained contractual/statutory tax allocation evidence is required; PFRS/EIR interest is not substituted.'
        WHEN latest.loan_id <> transaction.loan_id
          OR latest.client_id <> transaction.client_id
          OR latest.collection_date <> transaction.collection_date
          OR latest.source_cash_amount <> transaction.amount
            THEN 'Protected collection coordinates changed from the retained tax allocation.'
        WHEN latest.taxable_lending_receipt_amount + latest.principal_receipt_amount <> transaction.amount
            THEN 'Taxable lending receipt plus principal does not reconcile to protected source cash.'
        WHEN rule.id IS NULL
          OR transaction.collection_date < rule.effective_from
          OR (rule.effective_to IS NOT NULL AND transaction.collection_date > rule.effective_to)
            THEN 'Approved percentage-tax rule evidence is missing or not effective for the collection date.'
        WHEN EXISTS (
            SELECT 1 FROM accounting.v1_tax_rule_evidence later
            WHERE later.tax_type = rule.tax_type
              AND later.rule_key = rule.rule_key
              AND later.rule_version > rule.rule_version
              AND later.effective_from <= transaction.collection_date
              AND (later.effective_to IS NULL OR transaction.collection_date <= later.effective_to)
        ) THEN 'A later approved percentage-tax rule version is effective for the collection date.'
        ELSE NULL
    END AS tax_blocker,
    false AS tax_posting_enabled,
    false AS automatic_source_posting
FROM protected_transactions protected
JOIN lending.collection_transactions transaction ON transaction.id = protected.transaction_id
LEFT JOIN latest ON latest.transaction_id = transaction.id
LEFT JOIN accounting.v1_tax_rule_evidence rule ON rule.id = latest.rule_evidence_id
WHERE transaction.entry_type IN ('payment', 'advance') AND transaction.amount > 0;

CREATE OR REPLACE VIEW accounting.v1_tax_readiness_summary AS
SELECT
    (SELECT count(*)::bigint FROM accounting.v1_tax_rule_evidence) AS rule_evidence_count,
    (SELECT count(*)::bigint FROM accounting.v1_tax_dst_readiness) AS dst_source_count,
    (SELECT count(*)::bigint FROM accounting.v1_tax_dst_readiness WHERE tax_status = 'evidence_ready') AS dst_ready_count,
    (SELECT count(*)::bigint FROM accounting.v1_tax_dst_readiness WHERE tax_status <> 'evidence_ready') AS dst_blocked_count,
    (SELECT coalesce(sum(tax_due), 0)::numeric(18,2) FROM accounting.v1_tax_dst_readiness WHERE tax_status = 'evidence_ready') AS dst_evidence_tax_total,
    (SELECT count(*)::bigint FROM accounting.v1_tax_percentage_readiness) AS percentage_source_count,
    (SELECT count(*)::bigint FROM accounting.v1_tax_percentage_readiness WHERE tax_status = 'evidence_ready') AS percentage_ready_count,
    (SELECT count(*)::bigint FROM accounting.v1_tax_percentage_readiness WHERE tax_status <> 'evidence_ready') AS percentage_blocked_count,
    (SELECT coalesce(sum(taxable_lending_receipt_amount), 0)::numeric(18,2) FROM accounting.v1_tax_percentage_readiness WHERE tax_status = 'evidence_ready') AS percentage_taxable_receipt_total,
    (SELECT coalesce(sum(tax_due), 0)::numeric(18,2) FROM accounting.v1_tax_percentage_readiness WHERE tax_status = 'evidence_ready') AS percentage_evidence_tax_total,
    true AS evidence_backed_tax_readiness_enabled,
    false AS tax_posting_enabled,
    false AS automatic_source_posting;

COMMENT ON TABLE accounting.v1_tax_rule_evidence IS
'Immutable Management-approved legal/BIR/tax-classification rule evidence. A later version explicitly supersedes prior evidence; no rule row posts accounting automatically.';
COMMENT ON TABLE accounting.v1_dst_evidence IS
'Immutable per-loan DST evidence tied to the exact active authoritative disbursement event, protected issue price/term, approved rule and retained instrument/calculation digests.';
COMMENT ON TABLE accounting.v1_percentage_tax_evidence IS
'Immutable per-transaction tax allocation evidence. Taxable lending receipt and principal must exactly reconcile to protected cash; no PFRS/EIR field is substituted as the tax base.';
COMMENT ON VIEW accounting.v1_tax_readiness_summary IS
'A6.2 slice-1 evidence/readiness summary. Tax posting remains disabled and automatic_source_posting=false.';

COMMIT;