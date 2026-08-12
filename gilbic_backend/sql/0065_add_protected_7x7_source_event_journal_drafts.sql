BEGIN;

INSERT INTO core.permissions (code, description)
VALUES (
    'accounting.seven_by_seven.journal.prepare',
    'Create a protected Management-confirmed draft journal for an exact reviewed 7x7 collection source event without posting it'
)
ON CONFLICT (code) DO UPDATE SET description = excluded.description;

INSERT INTO core.role_permissions (role_id, permission_code)
SELECT role.id, permission.code
FROM core.roles role
JOIN core.permissions permission
  ON permission.code = 'accounting.seven_by_seven.journal.prepare'
WHERE role.code = 'management'
ON CONFLICT DO NOTHING;

CREATE TABLE IF NOT EXISTS accounting.seven_by_seven_journal_draft_preparations (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    transaction_id UUID NOT NULL UNIQUE
        REFERENCES lending.collection_transactions(id) ON DELETE RESTRICT,
    loan_id UUID NOT NULL
        REFERENCES lending.loans(id) ON DELETE RESTRICT,
    client_id UUID NOT NULL
        REFERENCES lending.clients(id) ON DELETE RESTRICT,
    journal_entry_id UUID NOT NULL UNIQUE
        REFERENCES accounting.journal_entries(id) ON DELETE RESTRICT,
    source_event_key TEXT NOT NULL UNIQUE,
    source_event_review_token TEXT NOT NULL,
    coordinate_digest TEXT NOT NULL,
    draft_policy_version TEXT NOT NULL,
    posting_date DATE NOT NULL,
    fiscal_period_id UUID NOT NULL
        REFERENCES accounting.fiscal_periods(id) ON DELETE RESTRICT,
    source_cash_amount NUMERIC(18,2) NOT NULL CHECK (source_cash_amount > 0),
    eir_interest_accrual NUMERIC(18,2) NOT NULL CHECK (eir_interest_accrual >= 0),
    accounting_eir_interest_received NUMERIC(18,2) NOT NULL CHECK (accounting_eir_interest_received >= 0),
    accounting_7x7_principal_received NUMERIC(18,2) NOT NULL CHECK (accounting_7x7_principal_received >= 0),
    coordinate_line_count INTEGER NOT NULL CHECK (coordinate_line_count > 0),
    total_debit NUMERIC(18,2) NOT NULL CHECK (total_debit > 0),
    total_credit NUMERIC(18,2) NOT NULL CHECK (total_credit > 0),
    prepared_by_user_id UUID NOT NULL
        REFERENCES core.users(id) ON DELETE RESTRICT,
    prepared_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CHECK (source_event_key = 'collection:' || transaction_id::text),
    CHECK (source_event_review_token ~ '^[0-9a-f]{64}$'),
    CHECK (coordinate_digest ~ '^[0-9a-f]{64}$'),
    CHECK (draft_policy_version = 'seven_by_seven_source_event_journal_draft_v1'),
    CHECK (source_cash_amount = accounting_eir_interest_received + accounting_7x7_principal_received),
    CHECK (total_debit = total_credit)
);

CREATE INDEX IF NOT EXISTS seven_by_seven_journal_draft_preparations_loan_idx
    ON accounting.seven_by_seven_journal_draft_preparations (loan_id, prepared_at DESC);

CREATE OR REPLACE FUNCTION accounting.seven_by_seven_coordinate_digest(p_transaction_id UUID)
RETURNS TEXT
LANGUAGE sql
STABLE
AS $$
    SELECT encode(
        digest(
            string_agg(
                concat_ws(
                    '|',
                    coordinate.line_number::text,
                    coordinate.journal_component,
                    coordinate.account_id::text,
                    coordinate.account_system_key,
                    to_char(coordinate.debit, 'FM999999999999990.00'),
                    to_char(coordinate.credit, 'FM999999999999990.00')
                ),
                '||' ORDER BY coordinate.line_number
            ),
            'sha256'
        ),
        'hex'
    )
    FROM accounting.seven_by_seven_source_event_journal_coordinate_preview coordinate
    WHERE coordinate.transaction_id = p_transaction_id
      AND coordinate.coordinate_preview_ready;
$$;

CREATE OR REPLACE FUNCTION accounting.guard_seven_by_seven_journal_draft_preparation_write()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
    IF TG_OP = 'INSERT'
       AND coalesce(current_setting('accounting.seven_by_seven_journal_prepare_allowed', true), '') = 'on' THEN
        RETURN NEW;
    END IF;

    RAISE EXCEPTION 'Protected 7x7 journal preparation records are immutable and must use the protected preparation function.';
END;
$$;

DROP TRIGGER IF EXISTS accounting_seven_by_seven_journal_draft_preparation_guard
    ON accounting.seven_by_seven_journal_draft_preparations;
CREATE TRIGGER accounting_seven_by_seven_journal_draft_preparation_guard
BEFORE INSERT OR UPDATE OR DELETE
ON accounting.seven_by_seven_journal_draft_preparations
FOR EACH ROW EXECUTE FUNCTION accounting.guard_seven_by_seven_journal_draft_preparation_write();

CREATE OR REPLACE FUNCTION accounting.guard_seven_by_seven_system_journal_entry_change()
RETURNS trigger
LANGUAGE plpgsql
AS $$
DECLARE
    protected_entry BOOLEAN;
BEGIN
    SELECT EXISTS (
        SELECT 1
        FROM accounting.seven_by_seven_journal_draft_preparations prepared
        WHERE prepared.journal_entry_id = OLD.id
    ) INTO protected_entry;

    IF NOT protected_entry THEN
        IF TG_OP = 'DELETE' THEN RETURN OLD; END IF;
        RETURN NEW;
    END IF;

    IF TG_OP = 'DELETE' THEN
        RAISE EXCEPTION 'Protected 7x7 journal drafts cannot be deleted through the General Journal.';
    END IF;

    IF OLD.status = 'draft' AND NEW.status = 'posted' THEN
        IF coalesce(current_setting('accounting.seven_by_seven_journal_post_allowed', true), '') <> 'on' THEN
            RAISE EXCEPTION 'Protected 7x7 journal drafts require the future protected 7x7 posting workflow.';
        END IF;
        RETURN NEW;
    END IF;

    IF NEW IS DISTINCT FROM OLD THEN
        RAISE EXCEPTION 'Protected 7x7 journal drafts are system generated and cannot be edited.';
    END IF;
    RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS accounting_seven_by_seven_system_journal_entry_guard
    ON accounting.journal_entries;
CREATE TRIGGER accounting_seven_by_seven_system_journal_entry_guard
BEFORE UPDATE OR DELETE ON accounting.journal_entries
FOR EACH ROW EXECUTE FUNCTION accounting.guard_seven_by_seven_system_journal_entry_change();

CREATE OR REPLACE FUNCTION accounting.guard_seven_by_seven_system_journal_line_change()
RETURNS trigger
LANGUAGE plpgsql
AS $$
DECLARE
    target_entry_id UUID;
    protected_entry BOOLEAN;
BEGIN
    target_entry_id := CASE WHEN TG_OP = 'DELETE' THEN OLD.journal_entry_id ELSE NEW.journal_entry_id END;

    SELECT EXISTS (
        SELECT 1
        FROM accounting.seven_by_seven_journal_draft_preparations prepared
        WHERE prepared.journal_entry_id = target_entry_id
    ) INTO protected_entry;

    IF protected_entry
       AND coalesce(current_setting('accounting.seven_by_seven_journal_prepare_allowed', true), '') <> 'on' THEN
        RAISE EXCEPTION 'Protected 7x7 journal lines are system generated and immutable.';
    END IF;

    IF TG_OP = 'DELETE' THEN RETURN OLD; END IF;
    RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS accounting_seven_by_seven_system_journal_line_guard
    ON accounting.journal_lines;
CREATE TRIGGER accounting_seven_by_seven_system_journal_line_guard
BEFORE INSERT OR UPDATE OR DELETE ON accounting.journal_lines
FOR EACH ROW EXECUTE FUNCTION accounting.guard_seven_by_seven_system_journal_line_change();

CREATE OR REPLACE FUNCTION accounting.create_seven_by_seven_journal_draft(
    p_transaction_id UUID,
    p_actor_user_id UUID,
    p_expected_review_token TEXT,
    p_expected_coordinate_digest TEXT,
    p_expected_source_event_key TEXT,
    p_expected_posting_date DATE,
    p_expected_fiscal_period_id UUID,
    p_expected_source_cash_amount NUMERIC,
    p_expected_total_debit NUMERIC,
    p_expected_total_credit NUMERIC,
    p_draft_policy_version TEXT
)
RETURNS UUID
LANGUAGE plpgsql
AS $$
DECLARE
    preview_row RECORD;
    existing_preparation accounting.seven_by_seven_journal_draft_preparations%ROWTYPE;
    current_coordinate_digest TEXT;
    current_line_count INTEGER;
    current_total_debit NUMERIC(18,2);
    current_total_credit NUMERIC(18,2);
    current_component_count INTEGER;
    current_invalid_component_count INTEGER;
    journal_id UUID;
    preparation_id UUID;
    normalized_review_token TEXT := lower(btrim(coalesce(p_expected_review_token, '')));
    normalized_coordinate_digest TEXT := lower(btrim(coalesce(p_expected_coordinate_digest, '')));
    normalized_source_key TEXT := btrim(coalesce(p_expected_source_event_key, ''));
    expected_cash NUMERIC(18,2) := round(coalesce(p_expected_source_cash_amount, 0), 2);
    expected_debit NUMERIC(18,2) := round(coalesce(p_expected_total_debit, 0), 2);
    expected_credit NUMERIC(18,2) := round(coalesce(p_expected_total_credit, 0), 2);
    existing_line_count INTEGER;
    existing_total_debit NUMERIC(18,2);
    existing_total_credit NUMERIC(18,2);
    existing_exact_line_count INTEGER;
BEGIN
    IF p_draft_policy_version IS DISTINCT FROM 'seven_by_seven_source_event_journal_draft_v1' THEN
        RAISE EXCEPTION 'Unsupported protected 7x7 journal draft policy version.';
    END IF;
    IF normalized_review_token !~ '^[0-9a-f]{64}$' THEN
        RAISE EXCEPTION 'Protected 7x7 source-event review token is invalid.';
    END IF;
    IF normalized_coordinate_digest !~ '^[0-9a-f]{64}$' THEN
        RAISE EXCEPTION 'Protected 7x7 coordinate digest is invalid.';
    END IF;
    IF normalized_source_key <> 'collection:' || p_transaction_id::text THEN
        RAISE EXCEPTION 'Protected 7x7 source-event identity is invalid.';
    END IF;
    IF expected_cash <= 0
       OR p_expected_source_cash_amount IS DISTINCT FROM expected_cash
       OR expected_debit <= 0
       OR expected_credit <= 0
       OR p_expected_total_debit IS DISTINCT FROM expected_debit
       OR p_expected_total_credit IS DISTINCT FROM expected_credit
       OR expected_debit <> expected_credit THEN
        RAISE EXCEPTION 'Protected 7x7 confirmation requires positive exact two-decimal balanced totals.';
    END IF;

    PERFORM pg_advisory_xact_lock(
        hashtextextended('seven-by-seven-journal-draft:' || p_transaction_id::text, 0)
    );

    LOCK TABLE
        lending.collection_transactions,
        lending.loans,
        lending.loan_types,
        accounting.seven_by_seven_eir_initial_carrying_anchors,
        accounting.seven_by_seven_eir_initial_carrying_anchor_voids,
        accounting.fiscal_periods,
        accounting.accounts,
        accounting.journal_entries,
        accounting.journal_lines,
        accounting.seven_by_seven_journal_draft_preparations
    IN SHARE MODE;

    SELECT *
    INTO preview_row
    FROM accounting.seven_by_seven_source_event_accounting_preview preview
    WHERE preview.transaction_id = p_transaction_id;

    IF preview_row.transaction_id IS NULL THEN
        RAISE EXCEPTION 'Current protected 7x7 source-event preview was not found. Refresh Management review.';
    END IF;
    IF preview_row.accounting_measurement_preview_ready IS DISTINCT FROM true
       OR preview_row.journal_coordinate_preview_ready IS DISTINCT FROM true THEN
        RAISE EXCEPTION 'Current protected 7x7 source event is not coordinate-ready.';
    END IF;
    IF preview_row.operational_allocation_substituted_for_accounting IS DISTINCT FROM false
       OR preview_row.authoritative_current_carrying_amount_ready IS DISTINCT FROM false
       OR preview_row.journal_draft_enabled IS DISTINCT FROM false
       OR preview_row.journal_lines_enabled IS DISTINCT FROM false
       OR preview_row.automatic_source_posting IS DISTINCT FROM false THEN
        RAISE EXCEPTION 'Protected 7x7 source-preview safety flags are inconsistent.';
    END IF;
    IF preview_row.source_event_review_token <> normalized_review_token
       OR preview_row.source_event_key <> normalized_source_key
       OR preview_row.collection_date <> p_expected_posting_date
       OR preview_row.open_fiscal_period_id <> p_expected_fiscal_period_id
       OR preview_row.source_cash_amount <> expected_cash THEN
        RAISE EXCEPTION 'Protected 7x7 source-event evidence changed after Management review. Refresh before preparing the draft.';
    END IF;
    IF preview_row.accounting_eir_interest_received + preview_row.accounting_7x7_principal_received <> expected_cash THEN
        RAISE EXCEPTION 'Protected 7x7 accounting EIR allocation no longer reconciles to source cash.';
    END IF;

    SELECT
        accounting.seven_by_seven_coordinate_digest(p_transaction_id),
        count(*)::integer,
        coalesce(sum(coordinate.debit), 0)::numeric(18,2),
        coalesce(sum(coordinate.credit), 0)::numeric(18,2),
        count(DISTINCT coordinate.journal_component)::integer,
        count(*) FILTER (
            WHERE coordinate.journal_component NOT IN (
                'eir_accrual_debit',
                'eir_accrual_credit',
                'collection_cash_debit',
                'collection_eir_interest_credit',
                'collection_7x7_principal_credit'
            )
            OR coordinate.account_system_key NOT IN (
                'accrued_interest_receivable',
                'interest_income_7x7',
                'cash_collector_custody',
                'loans_receivable_7x7'
            )
            OR coordinate.coordinate_preview_ready IS DISTINCT FROM true
            OR coordinate.journal_lines_enabled IS DISTINCT FROM false
            OR coordinate.automatic_source_posting IS DISTINCT FROM false
        )::integer
    INTO
        current_coordinate_digest,
        current_line_count,
        current_total_debit,
        current_total_credit,
        current_component_count,
        current_invalid_component_count
    FROM accounting.seven_by_seven_source_event_journal_coordinate_preview coordinate
    WHERE coordinate.transaction_id = p_transaction_id;

    IF current_coordinate_digest IS NULL
       OR current_coordinate_digest <> normalized_coordinate_digest
       OR current_line_count <= 0
       OR current_component_count <> current_line_count
       OR current_invalid_component_count <> 0
       OR current_total_debit <> expected_debit
       OR current_total_credit <> expected_credit
       OR current_total_debit <> current_total_credit THEN
        RAISE EXCEPTION 'Protected 7x7 journal coordinates changed or failed exact balance review. Refresh Management review.';
    END IF;

    SELECT *
    INTO existing_preparation
    FROM accounting.seven_by_seven_journal_draft_preparations prepared
    WHERE prepared.transaction_id = p_transaction_id;

    IF existing_preparation.id IS NOT NULL THEN
        IF existing_preparation.source_event_key <> normalized_source_key
           OR existing_preparation.source_event_review_token <> normalized_review_token
           OR existing_preparation.coordinate_digest <> normalized_coordinate_digest
           OR existing_preparation.draft_policy_version <> p_draft_policy_version
           OR existing_preparation.posting_date <> p_expected_posting_date
           OR existing_preparation.fiscal_period_id <> p_expected_fiscal_period_id
           OR existing_preparation.source_cash_amount <> expected_cash
           OR existing_preparation.coordinate_line_count <> current_line_count
           OR existing_preparation.total_debit <> expected_debit
           OR existing_preparation.total_credit <> expected_credit THEN
            RAISE EXCEPTION 'Existing protected 7x7 draft does not match the reviewed confirmation.';
        END IF;

        SELECT
            count(*)::integer,
            coalesce(sum(line.debit), 0)::numeric(18,2),
            coalesce(sum(line.credit), 0)::numeric(18,2),
            count(*) FILTER (
                WHERE EXISTS (
                    SELECT 1
                    FROM accounting.seven_by_seven_source_event_journal_coordinate_preview coordinate
                    WHERE coordinate.transaction_id = p_transaction_id
                      AND coordinate.line_number = line.line_number
                      AND coordinate.account_id = line.account_id
                      AND coordinate.debit = line.debit
                      AND coordinate.credit = line.credit
                )
            )::integer
        INTO existing_line_count, existing_total_debit, existing_total_credit, existing_exact_line_count
        FROM accounting.journal_lines line
        WHERE line.journal_entry_id = existing_preparation.journal_entry_id;

        IF NOT EXISTS (
            SELECT 1
            FROM accounting.journal_entries journal
            WHERE journal.id = existing_preparation.journal_entry_id
              AND journal.status = 'draft'
              AND journal.entry_number IS NULL
              AND journal.source_type = 'seven_by_seven_collection'
              AND journal.source_reference = p_transaction_id::text
              AND journal.source_event_key = normalized_source_key
              AND journal.posting_date = existing_preparation.posting_date
              AND journal.fiscal_period_id = existing_preparation.fiscal_period_id
        )
        OR existing_line_count <> current_line_count
        OR existing_exact_line_count <> current_line_count
        OR existing_total_debit <> expected_debit
        OR existing_total_credit <> expected_credit THEN
            RAISE EXCEPTION 'Existing protected 7x7 journal draft failed immutable integrity review.';
        END IF;

        RETURN existing_preparation.id;
    END IF;

    IF EXISTS (
        SELECT 1
        FROM accounting.journal_entries journal
        WHERE journal.source_event_key = normalized_source_key
    ) THEN
        RAISE EXCEPTION 'Accounting journal history already exists for this protected 7x7 source event.';
    END IF;

    PERFORM set_config('accounting.seven_by_seven_journal_prepare_allowed', 'on', true);

    INSERT INTO accounting.journal_entries (
        fiscal_period_id,
        posting_date,
        description,
        status,
        source_type,
        source_reference,
        source_event_key,
        created_by_user_id
    )
    VALUES (
        preview_row.open_fiscal_period_id,
        preview_row.collection_date,
        '7x7 protected collection source event - ' || preview_row.loan_number,
        'draft',
        'seven_by_seven_collection',
        p_transaction_id::text,
        preview_row.source_event_key,
        p_actor_user_id
    )
    RETURNING id INTO journal_id;

    INSERT INTO accounting.journal_lines (
        journal_entry_id,
        line_number,
        account_id,
        description,
        debit,
        credit,
        client_id,
        loan_id
    )
    SELECT
        journal_id,
        coordinate.line_number,
        coordinate.account_id,
        CASE coordinate.journal_component
            WHEN 'eir_accrual_debit' THEN '7x7 EIR accrual - accrued interest receivable'
            WHEN 'eir_accrual_credit' THEN '7x7 EIR accrual - interest income'
            WHEN 'collection_cash_debit' THEN '7x7 collection - collector custody cash'
            WHEN 'collection_eir_interest_credit' THEN '7x7 collection - settle accrued EIR interest'
            WHEN 'collection_7x7_principal_credit' THEN '7x7 collection - reduce loan principal component'
            ELSE '7x7 protected source event'
        END,
        coordinate.debit,
        coordinate.credit,
        preview_row.client_id,
        preview_row.loan_id
    FROM accounting.seven_by_seven_source_event_journal_coordinate_preview coordinate
    WHERE coordinate.transaction_id = p_transaction_id
      AND coordinate.coordinate_preview_ready
    ORDER BY coordinate.line_number;

    INSERT INTO accounting.seven_by_seven_journal_draft_preparations (
        transaction_id,
        loan_id,
        client_id,
        journal_entry_id,
        source_event_key,
        source_event_review_token,
        coordinate_digest,
        draft_policy_version,
        posting_date,
        fiscal_period_id,
        source_cash_amount,
        eir_interest_accrual,
        accounting_eir_interest_received,
        accounting_7x7_principal_received,
        coordinate_line_count,
        total_debit,
        total_credit,
        prepared_by_user_id
    )
    VALUES (
        p_transaction_id,
        preview_row.loan_id,
        preview_row.client_id,
        journal_id,
        preview_row.source_event_key,
        normalized_review_token,
        normalized_coordinate_digest,
        p_draft_policy_version,
        preview_row.collection_date,
        preview_row.open_fiscal_period_id,
        preview_row.source_cash_amount,
        preview_row.eir_interest_accrual,
        preview_row.accounting_eir_interest_received,
        preview_row.accounting_7x7_principal_received,
        current_line_count,
        current_total_debit,
        current_total_credit,
        p_actor_user_id
    )
    RETURNING id INTO preparation_id;

    PERFORM set_config('accounting.seven_by_seven_journal_prepare_allowed', 'off', true);

    INSERT INTO core.audit_logs (
        actor_user_id,
        action,
        target_type,
        target_id,
        details
    )
    VALUES (
        p_actor_user_id,
        'accounting.seven_by_seven_journal_draft.prepared',
        'seven_by_seven_journal_draft_preparation',
        preparation_id,
        jsonb_build_object(
            'transaction_id', p_transaction_id::text,
            'loan_id', preview_row.loan_id::text,
            'journal_entry_id', journal_id::text,
            'source_event_key', preview_row.source_event_key,
            'source_event_review_token', normalized_review_token,
            'coordinate_digest', normalized_coordinate_digest,
            'posting_date', preview_row.collection_date,
            'source_cash_amount', preview_row.source_cash_amount,
            'eir_interest_accrual', preview_row.eir_interest_accrual,
            'accounting_eir_interest_received', preview_row.accounting_eir_interest_received,
            'accounting_7x7_principal_received', preview_row.accounting_7x7_principal_received,
            'coordinate_line_count', current_line_count,
            'total_debit', current_total_debit,
            'total_credit', current_total_credit,
            'posting_enabled', false,
            'automatic_source_posting', false
        )
    );

    RETURN preparation_id;
END;
$$;

CREATE OR REPLACE VIEW accounting.seven_by_seven_journal_draft_review AS
WITH coordinate_summary AS (
    SELECT
        coordinate.transaction_id,
        accounting.seven_by_seven_coordinate_digest(coordinate.transaction_id) AS coordinate_digest,
        count(*)::integer AS coordinate_line_count,
        coalesce(sum(coordinate.debit), 0)::numeric(18,2) AS total_debit,
        coalesce(sum(coordinate.credit), 0)::numeric(18,2) AS total_credit,
        bool_and(coordinate.coordinate_preview_ready) AS all_coordinates_ready,
        bool_or(coordinate.journal_lines_enabled) AS any_journal_lines_enabled,
        bool_or(coordinate.automatic_source_posting) AS any_automatic_source_posting
    FROM accounting.seven_by_seven_source_event_journal_coordinate_preview coordinate
    GROUP BY coordinate.transaction_id
)
SELECT
    preview.transaction_id,
    preview.loan_id,
    preview.loan_number,
    preview.client_id,
    preview.client_code,
    preview.client_name,
    preview.collection_date AS posting_date,
    preview.open_fiscal_period_id AS fiscal_period_id,
    preview.source_event_key,
    preview.source_event_review_token,
    coordinate_summary.coordinate_digest,
    preview.source_cash_amount,
    preview.eir_interest_accrual,
    preview.accounting_eir_interest_received,
    preview.accounting_7x7_principal_received,
    coordinate_summary.coordinate_line_count,
    coordinate_summary.total_debit,
    coordinate_summary.total_credit,
    'seven_by_seven_source_event_journal_draft_v1'::text AS draft_policy_version,
    (
        preview.accounting_measurement_preview_ready
        AND preview.journal_coordinate_preview_ready
        AND coordinate_summary.all_coordinates_ready
        AND coordinate_summary.coordinate_line_count > 0
        AND coordinate_summary.total_debit > 0
        AND coordinate_summary.total_debit = coordinate_summary.total_credit
        AND NOT coordinate_summary.any_journal_lines_enabled
        AND NOT coordinate_summary.any_automatic_source_posting
        AND NOT preview.operational_allocation_substituted_for_accounting
        AND NOT preview.authoritative_current_carrying_amount_ready
        AND NOT preview.journal_draft_enabled
        AND NOT preview.journal_lines_enabled
        AND NOT preview.automatic_source_posting
    ) AS draft_review_ready,
    false AS posting_enabled,
    false AS automatic_source_posting
FROM accounting.seven_by_seven_source_event_accounting_preview preview
JOIN coordinate_summary ON coordinate_summary.transaction_id = preview.transaction_id;

CREATE OR REPLACE VIEW accounting.seven_by_seven_journal_draft_status AS
WITH current_coordinate AS (
    SELECT
        review.*
    FROM accounting.seven_by_seven_journal_draft_review review
),
line_summary AS (
    SELECT
        prepared.id AS preparation_id,
        count(line.id)::integer AS line_count,
        coalesce(sum(line.debit), 0)::numeric(18,2) AS total_debit,
        coalesce(sum(line.credit), 0)::numeric(18,2) AS total_credit,
        count(line.id) FILTER (
            WHERE EXISTS (
                SELECT 1
                FROM accounting.seven_by_seven_source_event_journal_coordinate_preview coordinate
                WHERE coordinate.transaction_id = prepared.transaction_id
                  AND coordinate.line_number = line.line_number
                  AND coordinate.account_id = line.account_id
                  AND coordinate.debit = line.debit
                  AND coordinate.credit = line.credit
            )
        )::integer AS exact_line_match_count
    FROM accounting.seven_by_seven_journal_draft_preparations prepared
    LEFT JOIN accounting.journal_lines line ON line.journal_entry_id = prepared.journal_entry_id
    GROUP BY prepared.id
)
SELECT
    prepared.id AS preparation_id,
    prepared.transaction_id,
    prepared.loan_id,
    prepared.client_id,
    prepared.journal_entry_id,
    prepared.source_event_key,
    prepared.source_event_review_token,
    prepared.coordinate_digest,
    prepared.draft_policy_version,
    prepared.posting_date,
    prepared.fiscal_period_id,
    period.label AS fiscal_period_label,
    period.status AS fiscal_period_status,
    prepared.source_cash_amount,
    prepared.eir_interest_accrual,
    prepared.accounting_eir_interest_received,
    prepared.accounting_7x7_principal_received,
    prepared.coordinate_line_count,
    prepared.total_debit AS prepared_total_debit,
    prepared.total_credit AS prepared_total_credit,
    prepared.prepared_by_user_id,
    prepared.prepared_at,
    journal.status AS journal_status,
    journal.entry_number,
    line_summary.line_count,
    line_summary.total_debit,
    line_summary.total_credit,
    CASE
        WHEN current_coordinate.transaction_id IS NULL THEN false
        WHEN current_coordinate.draft_review_ready IS DISTINCT FROM true THEN false
        WHEN current_coordinate.source_event_key <> prepared.source_event_key THEN false
        WHEN current_coordinate.source_event_review_token <> prepared.source_event_review_token THEN false
        WHEN current_coordinate.coordinate_digest <> prepared.coordinate_digest THEN false
        WHEN current_coordinate.posting_date <> prepared.posting_date THEN false
        WHEN current_coordinate.fiscal_period_id <> prepared.fiscal_period_id THEN false
        WHEN current_coordinate.source_cash_amount <> prepared.source_cash_amount THEN false
        WHEN current_coordinate.coordinate_line_count <> prepared.coordinate_line_count THEN false
        WHEN current_coordinate.total_debit <> prepared.total_debit
          OR current_coordinate.total_credit <> prepared.total_credit THEN false
        WHEN journal.status <> 'draft' OR journal.entry_number IS NOT NULL THEN false
        WHEN journal.source_type <> 'seven_by_seven_collection' THEN false
        WHEN journal.source_reference <> prepared.transaction_id::text THEN false
        WHEN journal.source_event_key <> prepared.source_event_key THEN false
        WHEN journal.posting_date <> prepared.posting_date
          OR journal.fiscal_period_id <> prepared.fiscal_period_id THEN false
        WHEN period.status <> 'open' THEN false
        WHEN line_summary.line_count <> prepared.coordinate_line_count THEN false
        WHEN line_summary.exact_line_match_count <> prepared.coordinate_line_count THEN false
        WHEN line_summary.total_debit <> prepared.total_debit
          OR line_summary.total_credit <> prepared.total_credit THEN false
        ELSE true
    END AS draft_integrity_ready,
    false AS posting_enabled,
    false AS automatic_source_posting
FROM accounting.seven_by_seven_journal_draft_preparations prepared
JOIN accounting.journal_entries journal ON journal.id = prepared.journal_entry_id
JOIN accounting.fiscal_periods period ON period.id = prepared.fiscal_period_id
JOIN line_summary ON line_summary.preparation_id = prepared.id
LEFT JOIN current_coordinate ON current_coordinate.transaction_id = prepared.transaction_id;

COMMENT ON TABLE accounting.seven_by_seven_journal_draft_preparations IS
    'Immutable Management-confirmed preparation audit for one protected 7x7 collection source-event journal draft. Installation creates no preparations or journals.';
COMMENT ON VIEW accounting.seven_by_seven_journal_draft_review IS
    'Management review boundary for an exact current 0064 source-event token plus exact coordinate digest. Draft creation is explicit; posting and automatic source posting remain disabled.';
COMMENT ON VIEW accounting.seven_by_seven_journal_draft_status IS
    'Fail-closed protected 7x7 draft integrity status. Any source, coordinate, period, account or journal-line drift makes the draft unready for future posting.';

COMMIT;
