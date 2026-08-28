# Protected 7x7 Extra Principal Bridge Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build an atomic, intent-aware 7x7 Extra Principal receipt, posting, Refund Due, reversal, and replay bridge on the existing protected SPINA financial systems.

**Architecture:** Extend the current 7x7 collection bridge inside its existing PostgreSQL transaction and persist forward operational effects through migration 0106. Add forward-only migration 0108 for immutable Refund Due lifecycle, reversal requests, reconstruction evidence, and controlled operational replay; reuse the existing Management collection void and protected 7x7 accounting reversal.

**Tech Stack:** Python 3.11+, FastAPI, Pydantic, psycopg 3, PostgreSQL PL/pgSQL, pytest, Flutter contract regressions where wire compatibility changes.

**Spec:** `docs/superpowers/specs/2026-08-28-7x7-extra-principal-bridge-design.md`

## Global Constraints

- Start from commit `6be0b0861a49aebaf5551162cbe66ea84d06b7dd` on `codex/7x7-extra-principal-bridge`.
- Only `extra_as_principal_reduction` activates the bridge; legacy `voluntary_extra` remains rejected.
- Preserve the original receipt, source event, signed contract, signed schedule, adjustments, journals, voids, reversals, and audit evidence.
- Use `Decimal` and repository money quantization; never use binary floating point.
- Keep receipt, posting, schedule change, Refund Due, audit, reconciliation, and idempotency result in one transaction.
- Keep `automatic_source_posting=false`; do not invent accounting accounts or recognition rules.
- Do not implement the all-future-rows-touched daily-amount rule.
- Do not deploy, restart protected services, apply migrations to protected/live databases, merge, mark PR #370 Ready, or enable auto-merge.
- Use test-first red/green cycles and commit each independently testable task.

---

### Task 1: Exact collection result replay metadata

**Files:**
- Modify: `spina_backend_mobile/src/spina_mobile_collections/contracts.py`
- Modify: `spina_backend_mobile/src/spina_mobile_collections/postgres.py`
- Test: `spina_backend_mobile/tests/test_postgres_executor.py`
- Test: `spina_backend_mobile/tests/test_postgres_integration.py`

**Interfaces:**
- Consumes: existing `PostedCollection`, `CollectionOutcome`, and `mobile.gilbic_collection_idempotency.result_payload`.
- Produces: `PostedCollection.result_metadata: dict[str, Any]` and duplicate responses reconstructed from the stored immutable result payload.

- [ ] **Step 1: Write failing executor tests for exact metadata replay**

```python
def test_exact_retry_replays_extra_principal_result_metadata():
    posted = PostedCollection(
        server_transaction_id=str(TRANSACTION_ID),
        receipt_number="OR-20260828-00000001",
        official_balance=Decimal("7000.00"),
        accepted_at=ACCEPTED_AT,
        route_revision="route-v8",
        result_metadata={
            "extra_principal_adjustment_id": str(ADJUSTMENT_ID),
            "principal_reduction": "1000.00",
            "refund_due": "200.00",
        },
    )
    first = executor.execute(
        actor=actor,
        command=command,
        canonical_payload=payload,
        request_hash=request_hash,
    )
    duplicate = executor.execute(
        actor=actor,
        command=command,
        canonical_payload=payload,
        request_hash=request_hash,
    )
    assert first.response_payload()["result"] == posted.result_metadata
    assert duplicate.response_payload()["result"] == posted.result_metadata
```

- [ ] **Step 2: Run the focused tests and confirm they fail**

Run: `python -m pytest spina_backend_mobile/tests/test_postgres_executor.py -q`

Expected: failure because `PostedCollection` has no `result_metadata` and duplicate lookup ignores `result_payload`.

- [ ] **Step 3: Extend the response contract without breaking existing clients**

```python
@dataclass(frozen=True, slots=True)
class PostedCollection:
    server_transaction_id: str
    receipt_number: str
    official_balance: Decimal
    accepted_at: datetime
    route_revision: str | None = None
    message: str = "Payment saved."
    result_metadata: dict[str, Any] = field(default_factory=dict)

    def response_payload(self, *, idempotency_key: UUID, duplicate: bool) -> dict[str, Any]:
        payload = {  # retain every existing key and value
            "status": CollectionStatus.DUPLICATE.value if duplicate else CollectionStatus.ACCEPTED.value,
            "duplicate": duplicate,
            "client_transaction_id": str(idempotency_key),
            "transaction_id": self.server_transaction_id,
            "receipt_number": self.receipt_number,
            "official_balance": _money_text(self.official_balance),
            "accepted_at": _utc_isoformat(self.accepted_at),
            "route_revision": self.route_revision,
            "message": "Already recorded. No duplicate payment was created." if duplicate else self.message,
        }
        if self.result_metadata:
            payload["result"] = self.result_metadata
        return payload
```

Select `result_payload` in `_find_existing`, validate its protected identity fields against the row columns, and load its optional `result` object into `PostedCollection.result_metadata`.

- [ ] **Step 4: Run executor and PostgreSQL integration tests**

Run: `python -m pytest spina_backend_mobile/tests/test_postgres_executor.py spina_backend_mobile/tests/test_postgres_integration.py -q`

Expected: all tests pass and legacy responses omit `result` when metadata is empty.

- [ ] **Step 5: Commit the result contract change**

```bash
git add spina_backend_mobile/src/spina_mobile_collections/contracts.py spina_backend_mobile/src/spina_mobile_collections/postgres.py spina_backend_mobile/tests/test_postgres_executor.py spina_backend_mobile/tests/test_postgres_integration.py
git commit -m "feat(collections): replay exact protected result metadata"
```

### Task 2: Pure 7x7 Extra Principal eligibility and replay planner

**Files:**
- Create: `gilbic_backend/src/gilbic_backend/seven_by_seven_extra_principal_replay.py`
- Modify: `gilbic_backend/src/gilbic_backend/seven_by_seven_extra_principal.py`
- Test: `gilbic_backend/tests/test_seven_by_seven_extra_principal_replay.py`
- Test: `gilbic_backend/tests/test_seven_by_seven_extra_principal.py`

**Interfaces:**
- Consumes: `FutureInstallmentPrincipalState`, `SevenBySevenExtraPrincipalPlan`, and `plan_seven_by_seven_extra_principal_tail`.
- Produces: `ActiveExtraPrincipalEvent`, `ExtraPrincipalReplayResult`, `require_extra_principal_interest_clear`, and `replay_extra_principal_history`.

- [ ] **Step 1: Write failing eligibility and replay tests**

```python
def test_interest_must_be_clear_before_extra_principal():
    with pytest.raises(SevenBySevenExtraPrincipalReplayError) as raised:
        require_extra_principal_interest_clear(
            past_due_interest=Decimal("10.00"),
            today_interest=Decimal("0.00"),
        )
    assert raised.value.code == "seven_by_seven_extra_principal_interest_outstanding"


def test_replay_omits_reversed_event_and_matches_prior_state():
    result = replay_extra_principal_history(
        signed_installments=SIGNED_ROWS,
        active_events=(FIRST_ADJUSTMENT,),
    )
    assert result.operational_rows == FIRST_ADJUSTMENT_EXPECTED_ROWS
    assert result.source_history_digest == EXPECTED_SHA256
```

- [ ] **Step 2: Run the new test file and confirm missing symbols fail**

Run: `python -m pytest gilbic_backend/tests/test_seven_by_seven_extra_principal_replay.py -q`

Expected: import failure for the new replay module.

- [ ] **Step 3: Implement deterministic pure replay**

```python
@dataclass(frozen=True, slots=True)
class ActiveExtraPrincipalEvent:
    adjustment_id: UUID
    transaction_id: UUID
    principal_reduction: Decimal
    resulting_operational_version: int


@dataclass(frozen=True, slots=True)
class ExtraPrincipalReplayResult:
    operational_rows: tuple[ExtraPrincipalInstallmentProjection, ...]
    active_adjustment_ids: tuple[UUID, ...]
    future_principal: Decimal
    removed_future_interest: Decimal
    refund_due: Decimal
    source_history_digest: str
    operational_state_digest: str


def require_extra_principal_interest_clear(*, past_due_interest: Decimal, today_interest: Decimal) -> None:
    if money(past_due_interest) != ZERO or money(today_interest) != ZERO:
        raise SevenBySevenExtraPrincipalReplayError(
            "Past Due Interest and Today Interest must be fully paid before Extra Principal.",
            code="seven_by_seven_extra_principal_interest_outstanding",
        )


def replay_extra_principal_history(
    *,
    signed_installments: Iterable[FutureInstallmentPrincipalState],
    active_events: Iterable[ActiveExtraPrincipalEvent],
) -> ExtraPrincipalReplayResult:
    # Sort signed rows and events deterministically, invoke the existing planner
    # once per event, feed each projection into the next event, and hash canonical
    # JSON containing UUID/date/Decimal values rendered as strings.
```

The implementation must reject duplicate event identities, non-monotonic versions, unexplained row drift, reductions exceeding replayed future principal, and nondeterministic order.

- [ ] **Step 4: Run planner and replay tests**

Run: `python -m pytest gilbic_backend/tests/test_seven_by_seven_extra_principal.py gilbic_backend/tests/test_seven_by_seven_extra_principal_replay.py -q`

Expected: all tests pass, including full-tail removal, one boundary row, retained Advance, Refund Due, and deterministic digests.

- [ ] **Step 5: Commit the replay engine**

```bash
git add gilbic_backend/src/gilbic_backend/seven_by_seven_extra_principal.py gilbic_backend/src/gilbic_backend/seven_by_seven_extra_principal_replay.py gilbic_backend/tests/test_seven_by_seven_extra_principal.py gilbic_backend/tests/test_seven_by_seven_extra_principal_replay.py
git commit -m "feat(7x7): add deterministic extra principal replay"
```

### Task 3: Migration 0108 immutable evidence and guards

**Files:**
- Create: `gilbic_backend/sql/0108_add_7x7_extra_principal_bridge.sql`
- Create: `gilbic_backend/tests/test_seven_by_seven_extra_principal_bridge_migration.py`
- Modify: `gilbic_backend/tests/test_disposable_validation_migration_boundaries.py`

**Interfaces:**
- Consumes: migration 0106 tables/views and collection void/accounting reversal trigger order from migrations 0044, 0067, and 0068.
- Produces: the five immutable evidence tables and derived status/active-Advance views defined by the spec.

- [ ] **Step 1: Write migration contract tests**

```python
def test_0108_is_forward_only_and_does_not_rewrite_0106():
    sql = MIGRATION.read_text(encoding="utf-8")
    assert "seven_by_seven_extra_principal_reversal_requests" in sql
    assert "seven_by_seven_extra_principal_reversal_items" in sql
    assert "loan_unused_advance_refund_due_approvals" in sql
    assert "loan_unused_advance_refund_due_releases" in sql
    assert "loan_unused_advance_refund_due_release_items" in sql
    assert "DROP TABLE" not in sql.upper()
    assert "UPDATE lending.seven_by_seven_extra_principal_adjustments" not in sql


def test_0108_installs_reconstruction_before_accounting_reversal():
    sql = MIGRATION.read_text(encoding="utf-8")
    assert "accounting_01a_extra_principal_operational_reversal" in sql
    assert "accounting_01b_extra_principal_operational_reversal_guard" in sql
```

- [ ] **Step 2: Run migration contract tests and confirm failure**

Run: `python -m pytest gilbic_backend/tests/test_seven_by_seven_extra_principal_bridge_migration.py -q`

Expected: failure because migration 0108 does not exist.

- [ ] **Step 3: Add schema, checks, indexes, guards, and views**

Implement the exact tables from the spec with:

```sql
CREATE TABLE lending.seven_by_seven_extra_principal_reversal_requests (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    idempotency_key UUID NOT NULL UNIQUE,
    canonical_request_hash TEXT NOT NULL,
    transaction_id UUID NOT NULL REFERENCES lending.collection_transactions(id) ON DELETE RESTRICT,
    adjustment_id UUID NOT NULL REFERENCES lending.seven_by_seven_extra_principal_adjustments(id) ON DELETE RESTRICT,
    requested_by_user_id UUID NOT NULL REFERENCES core.users(id) ON DELETE RESTRICT,
    reason TEXT NOT NULL CHECK (btrim(reason) <> ''),
    outcome TEXT NOT NULL CHECK (outcome IN ('completed', 'blocked_refund_released')),
    collection_void_id UUID UNIQUE REFERENCES lending.collection_transaction_voids(id) ON DELETE RESTRICT,
    released_refund_amount NUMERIC(18,2) NOT NULL DEFAULT 0 CHECK (released_refund_amount >= 0),
    result_payload JSONB NOT NULL,
    requested_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CHECK ((outcome = 'completed') = (collection_void_id IS NOT NULL))
);

CREATE TABLE lending.seven_by_seven_extra_principal_reversals (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    reversal_request_id UUID NOT NULL UNIQUE REFERENCES lending.seven_by_seven_extra_principal_reversal_requests(id) ON DELETE RESTRICT,
    adjustment_id UUID NOT NULL UNIQUE REFERENCES lending.seven_by_seven_extra_principal_adjustments(id) ON DELETE RESTRICT,
    transaction_id UUID NOT NULL UNIQUE REFERENCES lending.collection_transactions(id) ON DELETE RESTRICT,
    collection_void_id UUID NOT NULL UNIQUE REFERENCES lending.collection_transaction_voids(id) ON DELETE RESTRICT,
    loan_id UUID NOT NULL REFERENCES lending.loans(id) ON DELETE RESTRICT,
    schedule_id UUID NOT NULL REFERENCES lending.loan_contract_schedules(id) ON DELETE RESTRICT,
    expected_operational_version INTEGER NOT NULL CHECK (expected_operational_version >= 0),
    resulting_operational_version INTEGER NOT NULL CHECK (resulting_operational_version = expected_operational_version + 1),
    original_operational_principal NUMERIC(18,2) NOT NULL CHECK (original_operational_principal >= 0),
    reconstructed_operational_principal NUMERIC(18,2) NOT NULL CHECK (reconstructed_operational_principal >= 0),
    restored_active_advance NUMERIC(18,2) NOT NULL CHECK (restored_active_advance >= 0),
    cancelled_refund_due NUMERIC(18,2) NOT NULL CHECK (cancelled_refund_due >= 0),
    source_history_digest TEXT NOT NULL CHECK (source_history_digest ~ '^[0-9a-f]{64}$'),
    operational_state_digest TEXT NOT NULL CHECK (operational_state_digest ~ '^[0-9a-f]{64}$'),
    reversed_by_user_id UUID NOT NULL REFERENCES core.users(id) ON DELETE RESTRICT,
    reason TEXT NOT NULL CHECK (btrim(reason) <> ''),
    reversed_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE lending.seven_by_seven_extra_principal_reversal_items (
    reversal_id UUID NOT NULL REFERENCES lending.seven_by_seven_extra_principal_reversals(id) ON DELETE RESTRICT,
    installment_id BIGINT NOT NULL REFERENCES lending.loan_contract_installments(id) ON DELETE RESTRICT,
    installment_number INTEGER NOT NULL CHECK (installment_number > 0),
    signed_amount NUMERIC(18,2) NOT NULL CHECK (signed_amount > 0),
    signed_principal NUMERIC(18,2) NOT NULL CHECK (signed_principal > 0),
    signed_interest NUMERIC(18,2) NOT NULL CHECK (signed_interest >= 0),
    prior_operational_amount NUMERIC(18,2) NOT NULL CHECK (prior_operational_amount >= 0),
    reconstructed_operational_amount NUMERIC(18,2) NOT NULL CHECK (reconstructed_operational_amount >= 0),
    prior_removed BOOLEAN NOT NULL,
    reconstructed_removed BOOLEAN NOT NULL,
    prior_active_advance NUMERIC(18,2) NOT NULL CHECK (prior_active_advance >= 0),
    reconstructed_active_advance NUMERIC(18,2) NOT NULL CHECK (reconstructed_active_advance >= 0),
    prior_active_refund_due NUMERIC(18,2) NOT NULL CHECK (prior_active_refund_due >= 0),
    reconstructed_active_refund_due NUMERIC(18,2) NOT NULL CHECK (reconstructed_active_refund_due >= 0),
    last_active_adjustment_id UUID REFERENCES lending.seven_by_seven_extra_principal_adjustments(id) ON DELETE RESTRICT,
    PRIMARY KEY (reversal_id, installment_id)
);

CREATE TABLE lending.loan_unused_advance_refund_due_approvals (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    idempotency_key UUID NOT NULL UNIQUE,
    canonical_request_hash TEXT NOT NULL,
    adjustment_id UUID NOT NULL REFERENCES lending.seven_by_seven_extra_principal_adjustments(id) ON DELETE RESTRICT,
    loan_id UUID NOT NULL REFERENCES lending.loans(id) ON DELETE RESTRICT,
    client_id UUID NOT NULL REFERENCES lending.clients(id) ON DELETE RESTRICT,
    approved_amount NUMERIC(18,2) NOT NULL CHECK (approved_amount > 0),
    approved_by_user_id UUID NOT NULL REFERENCES core.users(id) ON DELETE RESTRICT,
    reason TEXT NOT NULL CHECK (btrim(reason) <> ''),
    authority_reference TEXT NOT NULL CHECK (btrim(authority_reference) <> ''),
    approved_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE lending.loan_unused_advance_refund_due_releases (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    idempotency_key UUID NOT NULL UNIQUE,
    canonical_request_hash TEXT NOT NULL,
    approval_id UUID NOT NULL REFERENCES lending.loan_unused_advance_refund_due_approvals(id) ON DELETE RESTRICT,
    loan_id UUID NOT NULL REFERENCES lending.loans(id) ON DELETE RESTRICT,
    client_id UUID NOT NULL REFERENCES lending.clients(id) ON DELETE RESTRICT,
    released_amount NUMERIC(18,2) NOT NULL CHECK (released_amount > 0),
    released_by_user_id UUID NOT NULL REFERENCES core.users(id) ON DELETE RESTRICT,
    released_at TIMESTAMPTZ NOT NULL,
    evidence_reference TEXT NOT NULL CHECK (btrim(evidence_reference) <> ''),
    evidence_digest TEXT NOT NULL CHECK (evidence_digest ~ '^[0-9a-f]{64}$'),
    result_payload JSONB NOT NULL
);

CREATE TABLE lending.loan_unused_advance_refund_due_release_items (
    release_id UUID NOT NULL REFERENCES lending.loan_unused_advance_refund_due_releases(id) ON DELETE RESTRICT,
    adjustment_id UUID NOT NULL,
    installment_id BIGINT NOT NULL,
    amount_released NUMERIC(18,2) NOT NULL CHECK (amount_released > 0),
    PRIMARY KEY (release_id, adjustment_id, installment_id),
    FOREIGN KEY (adjustment_id, installment_id)
        REFERENCES lending.loan_unused_advance_refund_dues(adjustment_id, installment_id)
        ON DELETE RESTRICT
);
```

Use `NUMERIC(18,2)`, `ON DELETE RESTRICT`, unique source identities, exact aggregate checks in protected functions, and immutable `BEFORE INSERT OR UPDATE OR DELETE` guards that allow inserts only under transaction-local `set_config` sessions. Recreate `lending.loan_installment_active_advance` so only non-reversed classifications remain inactive Advance. Add `lending.loan_unused_advance_refund_due_status` and `lending.seven_by_seven_extra_principal_reversal_status` views.

- [ ] **Step 4: Run migration contract and boundary tests**

Run: `python -m pytest gilbic_backend/tests/test_seven_by_seven_extra_principal_bridge_migration.py gilbic_backend/tests/test_disposable_validation_migration_boundaries.py -q`

Expected: all tests pass and migration ordering ends at 0108.

- [ ] **Step 5: Commit migration structure**

```bash
git add gilbic_backend/sql/0108_add_7x7_extra_principal_bridge.sql gilbic_backend/tests/test_seven_by_seven_extra_principal_bridge_migration.py gilbic_backend/tests/test_disposable_validation_migration_boundaries.py
git commit -m "feat(db): add protected extra principal reversal evidence"
```

### Task 4: Atomic forward Extra Principal posting bridge

**Files:**
- Create: `gilbic_backend/src/gilbic_backend/seven_by_seven_extra_principal_posting.py`
- Modify: `gilbic_backend/src/gilbic_backend/seven_by_seven_collection_posting.py`
- Modify: `gilbic_backend/src/gilbic_backend/voluntary_extra_collection_posting.py`
- Test: `gilbic_backend/tests/test_seven_by_seven_extra_principal_posting.py`
- Test: `gilbic_backend/tests/test_seven_by_seven_mobile_collection_postgres.py`

**Interfaces:**
- Consumes: Task 2 replay types, existing official 7x7 posting cursor/locks, 0106 persistence, and `PaymentAllocationIntent.EXTRA_AS_PRINCIPAL_REDUCTION`.
- Produces: `post_seven_by_seven_extra_principal` returning `SevenBySevenExtraPrincipalPostingResult` and official response metadata.

- [ ] **Step 1: Write failing intent, interest, and persistence tests**

```python
def test_modern_intent_posts_zero_interest_and_exact_principal(postgres_fixture):
    outcome = submit_collection(
        payment_allocation_intent="extra_as_principal_reduction",
        amount="1000.00",
    )
    assert outcome.status.value == "accepted"
    assert outcome.posted.result_metadata["principal_reduction"] == "1000.00"
    persisted = load_extra_principal_state(outcome.posted.server_transaction_id)
    assert persisted.interest_contribution == Decimal("0.00")
    assert persisted.principal_contribution == Decimal("1000.00")


@pytest.mark.parametrize("intent", ["scheduled", "voluntary_extra"])
def test_non_modern_intent_cannot_activate_extra_principal(intent, postgres_fixture):
    outcome = submit_extra_shaped_collection(payment_allocation_intent=intent)
    assert outcome.code == "seven_by_seven_extra_principal_intent_required"
```

- [ ] **Step 2: Run focused posting tests and confirm failure**

Run: `python -m pytest gilbic_backend/tests/test_seven_by_seven_extra_principal_posting.py -q`

Expected: failure because no posting helper routes 7x7 Extra Principal.

- [ ] **Step 3: Implement the posting helper and narrow branch**

```python
@dataclass(frozen=True, slots=True)
class SevenBySevenExtraPrincipalPostingResult:
    adjustment_id: UUID
    principal_reduction: Decimal
    resulting_future_principal: Decimal
    removed_future_interest: Decimal
    retained_advance: Decimal
    refund_due: Decimal
    resulting_operational_version: int
    operational_state_digest: str


def post_seven_by_seven_extra_principal(
    cursor: Any,
    *,
    transaction_id: UUID,
    loan_id: UUID,
    actor_user_id: UUID,
    collection_date: date,
    receipt_amount: Decimal,
    payment_allocation_intent: PaymentAllocationIntent,
    expected_route_revision: str,
) -> SevenBySevenExtraPrincipalPostingResult:
    if payment_allocation_intent is not PaymentAllocationIntent.EXTRA_AS_PRINCIPAL_REDUCTION:
        raise ExtraPrincipalPostingRejected(
            "Choose Principal Reduction explicitly before saving 7x7 Extra Principal.",
            code="seven_by_seven_extra_principal_intent_required",
        )
    locked = lock_extra_principal_authoritative_state(
        cursor,
        loan_id=loan_id,
        collection_date=collection_date,
        expected_route_revision=expected_route_revision,
    )
    replayed = replay_locked_extra_principal_history(locked)
    require_extra_principal_interest_clear(
        past_due_interest=replayed.past_due_interest,
        today_interest=replayed.today_interest,
    )
    plan = plan_seven_by_seven_extra_principal_tail(
        future_installments=replayed.future_installments,
        principal_reduction=receipt_amount,
    )
    stored = store_extra_principal_plan(
        cursor,
        transaction_id=transaction_id,
        actor_user_id=actor_user_id,
        locked=locked,
        plan=plan,
    )
    reconcile_persisted_extra_principal(
        cursor,
        transaction_id=transaction_id,
        adjustment_id=stored.adjustment_id,
    )
    return stored
```

The body must load/lock the active registered signed schedule, operational state and rows, active Advance, and prior adjustments; prove current replay; prove both interest buckets are zero; run the existing planner; write 0106 rows/overlays/version; and reload/reconcile exact results. In `seven_by_seven_collection_posting.py`, branch only the modern intent and include it in receipt `details` before inserting the 0106 adjustment. In `voluntary_extra_collection_posting.py`, leave the legacy intent parseable but rejected for principal reduction.

- [ ] **Step 4: Run focused and existing 7x7 PostgreSQL tests**

Run: `python -m pytest gilbic_backend/tests/test_seven_by_seven_extra_principal_posting.py gilbic_backend/tests/test_seven_by_seven_mobile_collection_postgres.py gilbic_backend/tests/test_seven_by_seven_extra_principal_persistence_postgres.py -q`

Expected: all tests pass with one receipt, one adjustment, no duplicate financial rows, and unchanged signed schedule rows.

- [ ] **Step 5: Commit forward posting**

```bash
git add gilbic_backend/src/gilbic_backend/seven_by_seven_extra_principal_posting.py gilbic_backend/src/gilbic_backend/seven_by_seven_collection_posting.py gilbic_backend/src/gilbic_backend/voluntary_extra_collection_posting.py gilbic_backend/tests/test_seven_by_seven_extra_principal_posting.py gilbic_backend/tests/test_seven_by_seven_mobile_collection_postgres.py
git commit -m "feat(7x7): post protected extra principal receipts"
```

### Task 5: Forward reconciliation and accounting readiness

**Files:**
- Create: `gilbic_backend/src/gilbic_backend/seven_by_seven_extra_principal_reconciliation.py`
- Modify: `gilbic_backend/src/gilbic_backend/seven_by_seven_extra_principal_posting.py`
- Modify: `gilbic_backend/sql/0108_add_7x7_extra_principal_bridge.sql`
- Test: `gilbic_backend/tests/test_seven_by_seven_extra_principal_reconciliation.py`
- Test: `gilbic_backend/tests/test_seven_by_seven_extra_principal_bridge_postgres.py`

**Interfaces:**
- Consumes: official receipt, 7x7 contributions, 0106 adjustment/items, operational rows, active Advance, Refund Due, audit logs, and existing 7x7 accounting readiness/posting status.
- Produces: `ExtraPrincipalReconciliation` and `reconcile_persisted_extra_principal`.

- [ ] **Step 1: Write failing persisted mismatch/rollback tests**

```python
@pytest.mark.parametrize(
    "fault",
    ["receipt", "audit", "refund_due", "accounting_readiness", "operational_row"],
)
def test_any_forward_mismatch_rolls_back_every_fragment(postgres_fixture, fault):
    inject_fault(fault)
    outcome = submit_extra_principal()
    assert outcome.code == "seven_by_seven_extra_principal_reconciliation_failed"
    assert load_financial_fragments(IDEMPOTENCY_KEY).is_empty
```

- [ ] **Step 2: Run reconciliation tests and confirm failure**

Run: `python -m pytest gilbic_backend/tests/test_seven_by_seven_extra_principal_reconciliation.py -q`

Expected: import or assertion failures because the exact reconciliation component is absent.

- [ ] **Step 3: Implement exact read-back reconciliation**

```python
@dataclass(frozen=True, slots=True)
class ExtraPrincipalReconciliation:
    cash_received: Decimal
    receipt_total: Decimal
    interest_contribution: Decimal
    principal_contribution: Decimal
    adjustment_principal: Decimal
    future_principal: Decimal
    retained_advance: Decimal
    refund_due: Decimal
    operational_version: int
    accounting_status: str
    audit_present: bool


def reconcile_persisted_extra_principal(
    cursor: Any,
    *,
    transaction_id: UUID,
    adjustment_id: UUID,
) -> ExtraPrincipalReconciliation:
    # Load every coordinate independently, compare exact Decimal totals and IDs,
    # and raise the stable reconciliation error on any mismatch.
```

Add a read-only 0108 readiness/status view that exposes `automatic_source_posting=false` and blocks explicit posting if the existing protected source coordinates cannot be reconciled. Do not create a journal or new account.

- [ ] **Step 4: Run reconciliation and protected accounting regressions**

Run: `python -m pytest gilbic_backend/tests/test_seven_by_seven_extra_principal_reconciliation.py gilbic_backend/tests/test_seven_by_seven_extra_principal_bridge_postgres.py gilbic_backend/tests/test_7x7_source_event_accounting_preview_postgres.py gilbic_backend/tests/test_7x7_protected_journal_posting_postgres.py -q`

Expected: all pass; failures injected after any write leave no fragment.

- [ ] **Step 5: Commit reconciliation**

```bash
git add gilbic_backend/src/gilbic_backend/seven_by_seven_extra_principal_reconciliation.py gilbic_backend/src/gilbic_backend/seven_by_seven_extra_principal_posting.py gilbic_backend/sql/0108_add_7x7_extra_principal_bridge.sql gilbic_backend/tests/test_seven_by_seven_extra_principal_reconciliation.py gilbic_backend/tests/test_seven_by_seven_extra_principal_bridge_postgres.py
git commit -m "feat(7x7): reconcile extra principal financial evidence"
```

### Task 6: Refund Due approval and physical-release evidence

**Files:**
- Create: `gilbic_backend/src/gilbic_backend/refund_due_repository.py`
- Create: `gilbic_backend/src/gilbic_backend/refund_due_api.py`
- Modify: `gilbic_backend/src/gilbic_backend/main.py`
- Modify: `gilbic_backend/src/gilbic_backend/collector_cash_accountability_api.py`
- Modify: `gilbic_backend/src/gilbic_backend/remittance_repository.py`
- Modify: `gilbic_backend/src/gilbic_backend/cross_remittance_repository.py`
- Test: `gilbic_backend/tests/test_refund_due_api.py`
- Test: `gilbic_backend/tests/test_refund_due_postgres.py`
- Test: `gilbic_backend/tests/test_remittance_api.py`
- Test: `gilbic_backend/tests/test_cross_remittance_api.py`

**Interfaces:**
- Consumes: 0108 Refund Due tables/views, account authentication, permanent client assignment, and current receipt/remittance custody evidence.
- Produces: `PostgresRefundDueRepository.approve`, `.release`, and protected Management/Collector endpoints.

- [ ] **Step 1: Write failing approval/release/idempotency tests**

```python
def test_approval_does_not_reduce_collector_cash(client, seeded_refund_due):
    before = collector_cash(client)
    approval = approve_refund_due(client, amount="200.00", key=APPROVAL_KEY)
    assert collector_cash(client) == before
    assert approval["approved_amount"] == "200.00"


def test_physical_release_reduces_cash_once_and_never_nets_loan(client, seeded_refund_due):
    approval = approve_refund_due(client, amount="200.00", key=APPROVAL_KEY)
    first = release_refund_due(client, approval["id"], amount="200.00", key=RELEASE_KEY)
    duplicate = release_refund_due(client, approval["id"], amount="200.00", key=RELEASE_KEY)
    assert duplicate == first
    assert collector_cash(client).total_cash_held == Decimal("200.00")
    assert loan_balance(client) == ORIGINAL_LOAN_BALANCE
```

- [ ] **Step 2: Run focused tests and confirm missing routes fail**

Run: `python -m pytest gilbic_backend/tests/test_refund_due_api.py gilbic_backend/tests/test_refund_due_postgres.py -q`

Expected: 404/import failures because repository and routes do not exist.

- [ ] **Step 3: Implement protected terminal evidence operations**

```python
class PostgresRefundDueRepository:
    def approve(
        self,
        *,
        idempotency_key: UUID,
        actor_user_id: UUID,
        adjustment_id: UUID,
        approved_amount: Decimal,
        reason: str,
        authority_reference: str,
    ) -> RefundDueApprovalRecord:
        request = RefundDueApprovalRequest.canonical(
            idempotency_key=idempotency_key,
            actor_user_id=actor_user_id,
            adjustment_id=adjustment_id,
            approved_amount=approved_amount,
            reason=reason,
            authority_reference=authority_reference,
        )
        return self._approve_in_transaction(request)

    def release(
        self,
        *,
        idempotency_key: UUID,
        actor_user_id: UUID,
        approval_id: UUID,
        released_amount: Decimal,
        released_at: datetime,
        evidence_reference: str,
        evidence_digest: str,
    ) -> RefundDueReleaseRecord:
        request = RefundDueReleaseRequest.canonical(
            idempotency_key=idempotency_key,
            actor_user_id=actor_user_id,
            approval_id=approval_id,
            released_amount=released_amount,
            released_at=released_at,
            evidence_reference=evidence_reference,
            evidence_digest=evidence_digest,
        )
        return self._release_in_transaction(request)
```

Both methods take advisory locks, compare canonical hashes for retries, lock active status rows, use protected SQL insert functions, allocate releases oldest-first to original due rows, and reload the terminal result. The API requires Management permission for approval and assigned-Collector permission for release. Add separate immutable release lines to existing cash-accountability/remittance calculations; never change receipt `amount` or original remittance snapshots.

- [ ] **Step 4: Run refund and remittance regressions**

Run: `python -m pytest gilbic_backend/tests/test_refund_due_api.py gilbic_backend/tests/test_refund_due_postgres.py gilbic_backend/tests/test_remittance_api.py gilbic_backend/tests/test_cross_remittance_api.py -q`

Expected: all pass; approval has no cash effect, release has one exact cash effect, and Refund Due never changes a loan allocation.

- [ ] **Step 5: Commit Refund Due lifecycle**

```bash
git add gilbic_backend/src/gilbic_backend/refund_due_repository.py gilbic_backend/src/gilbic_backend/refund_due_api.py gilbic_backend/src/gilbic_backend/main.py gilbic_backend/src/gilbic_backend/collector_cash_accountability_api.py gilbic_backend/src/gilbic_backend/remittance_repository.py gilbic_backend/src/gilbic_backend/cross_remittance_repository.py gilbic_backend/tests/test_refund_due_api.py gilbic_backend/tests/test_refund_due_postgres.py gilbic_backend/tests/test_remittance_api.py gilbic_backend/tests/test_cross_remittance_api.py
git commit -m "feat(refunds): protect advance refund due release evidence"
```

### Task 7: Idempotent Management reversal request boundary

**Files:**
- Create: `gilbic_backend/src/gilbic_backend/seven_by_seven_extra_principal_reversal.py`
- Modify: `gilbic_backend/src/gilbic_backend/collection_void_api.py`
- Modify: `gilbic_backend/src/gilbic_backend/collection_void_repository.py`
- Test: `gilbic_backend/tests/test_collection_void_api.py`
- Create: `gilbic_backend/tests/test_seven_by_seven_extra_principal_reversal_requests_postgres.py`

**Interfaces:**
- Consumes: existing collection void, 0108 request table/status views, Refund Due releases, and canonical SHA-256 helper.
- Produces: `ExtraPrincipalReversalRequestResult` and an idempotent extra-principal-aware branch in `void_unremitted`.

- [ ] **Step 1: Write failing exact/conflicting/blocked retry tests**

```python
def test_released_refund_creates_durable_blocked_reversal_request(client, seeded_released_refund):
    first = void_collection(client, TRANSACTION_ID, REVERSAL_KEY, "wrong receipt")
    second = void_collection(client, TRANSACTION_ID, REVERSAL_KEY, "wrong receipt")
    assert first.status_code == second.status_code == 409
    assert first.json() == second.json()
    assert reversal_request(REVERSAL_KEY).outcome == "blocked_refund_released"
    assert collection_transaction(TRANSACTION_ID).is_voided is False


def test_changed_reversal_retry_conflicts(client, seeded_extra_principal):
    void_collection(client, TRANSACTION_ID, REVERSAL_KEY, "wrong receipt")
    changed = void_collection(client, TRANSACTION_ID, REVERSAL_KEY, "different reason")
    assert changed.json()["detail"]["code"] == "seven_by_seven_extra_principal_reversal_idempotency_mismatch"
```

- [ ] **Step 2: Run request-boundary tests and confirm failure**

Run: `python -m pytest gilbic_backend/tests/test_collection_void_api.py gilbic_backend/tests/test_seven_by_seven_extra_principal_reversal_requests_postgres.py -q`

Expected: body rejects/ignores `idempotency_key` and no terminal request evidence exists.

- [ ] **Step 3: Implement terminal request handling**

```python
class CollectionVoidBody(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    reason: str = Field(min_length=3, max_length=500)
    idempotency_key: UUID | None = None


@dataclass(frozen=True, slots=True)
class ExtraPrincipalReversalRequestResult:
    request_id: UUID
    outcome: Literal["completed", "blocked_refund_released"]
    result_payload: dict[str, object]
    collection_void: CollectionVoidRecord | None
```

Refactor the existing repository so its SQL body can use an already-open connection. For Extra Principal, require an idempotency key, serialize on it and the transaction, return stored exact results, persist blocked results without raising inside the transaction, or complete the existing void under the same transaction. Non-Extra-Principal behavior stays wire compatible.

- [ ] **Step 4: Run void API and PostgreSQL request tests**

Run: `python -m pytest gilbic_backend/tests/test_collection_void_api.py gilbic_backend/tests/test_seven_by_seven_extra_principal_reversal_requests_postgres.py -q`

Expected: exact retries match, changed retries conflict, blocked attempts persist, and normal legacy void tests remain green.

- [ ] **Step 5: Commit reversal request boundary**

```bash
git add gilbic_backend/src/gilbic_backend/seven_by_seven_extra_principal_reversal.py gilbic_backend/src/gilbic_backend/collection_void_api.py gilbic_backend/src/gilbic_backend/collection_void_repository.py gilbic_backend/tests/test_collection_void_api.py gilbic_backend/tests/test_seven_by_seven_extra_principal_reversal_requests_postgres.py
git commit -m "feat(7x7): add idempotent extra principal void requests"
```

### Task 8: Controlled operational reconstruction and reversal evidence

**Files:**
- Modify: `gilbic_backend/sql/0108_add_7x7_extra_principal_bridge.sql`
- Modify: `gilbic_backend/src/gilbic_backend/seven_by_seven_extra_principal_reversal.py`
- Modify: `gilbic_backend/src/gilbic_backend/seven_by_seven_extra_principal_replay.py`
- Create: `gilbic_backend/tests/test_seven_by_seven_extra_principal_reversal_postgres.py`
- Modify: `gilbic_backend/tests/test_7x7_controlled_collection_reversal_postgres.py`

**Interfaces:**
- Consumes: completed reversal request, collection void snapshot, pure replay result, 0106 rows, and 0067 accounting reversal.
- Produces: controlled reconstruction SQL function/trigger, immutable reversal evidence, and read-only replay verification.

- [ ] **Step 1: Write failing successful reversal and replay tests**

```python
def test_successful_reversal_reconstructs_schedule_and_preserves_originals(postgres_fixture):
    original = post_extra_principal(amount="1000.00")
    voided = void_extra_principal(original.transaction_id, key=REVERSAL_KEY)
    assert voided.is_voided is True
    assert signed_schedule_rows() == ORIGINAL_SIGNED_ROWS
    assert operational_rows() == BEFORE_EXTRA_OPERATIONAL_ROWS
    assert extra_adjustment(original.adjustment_id).still_exists
    assert extra_reversal(original.adjustment_id).collection_void_id == voided.void_id


def test_read_only_replay_matches_persisted_reversal_state(postgres_fixture):
    reverse_latest_extra_principal()
    replay = replay_from_database(LOAN_ID)
    assert replay.operational_state_digest == reversal_record().operational_state_digest
    assert replay.operational_rows == load_operational_rows()
```

- [ ] **Step 2: Run reversal tests and confirm operational state is not restored**

Run: `python -m pytest gilbic_backend/tests/test_seven_by_seven_extra_principal_reversal_postgres.py -q`

Expected: void either fails the 0106 validator or leaves the shortened operational overlay.

- [ ] **Step 3: Implement controlled reconstruction trigger and final guard**

```sql
CREATE FUNCTION lending.reverse_seven_by_seven_extra_principal_for_void(
    p_transaction_id uuid,
    p_collection_void_id uuid,
    p_actor_user_id uuid,
    p_reason text
) RETURNS uuid LANGUAGE plpgsql AS $$
-- Lock schedule/operational/refund/reversal rows; reject release evidence;
-- prove current state by replay; insert reversal header/items; enable the
-- transaction-local reconstruction guard; upsert every operational amount;
-- increment version; disable the guard; prove exact totals/digests; return ID.
$$;
```

Install `accounting_01a_extra_principal_operational_reversal` before the 0067 accounting trigger and `accounting_01b_extra_principal_operational_reversal_guard` immediately after it. The final guard requires exact immutable reversal evidence whenever an Extra Principal source is voided. The Python verifier independently reconstructs and compares the persisted state.

- [ ] **Step 4: Run operational and accounting reversal tests**

Run: `python -m pytest gilbic_backend/tests/test_seven_by_seven_extra_principal_reversal_postgres.py gilbic_backend/tests/test_7x7_controlled_collection_reversal_postgres.py -q`

Expected: unposted sources reconstruct without journals; posted sources additionally create one exact 0067 debit/credit-swapped reversal; originals remain unchanged.

- [ ] **Step 5: Commit operational reversal**

```bash
git add gilbic_backend/sql/0108_add_7x7_extra_principal_bridge.sql gilbic_backend/src/gilbic_backend/seven_by_seven_extra_principal_reversal.py gilbic_backend/src/gilbic_backend/seven_by_seven_extra_principal_replay.py gilbic_backend/tests/test_seven_by_seven_extra_principal_reversal_postgres.py gilbic_backend/tests/test_7x7_controlled_collection_reversal_postgres.py
git commit -m "feat(7x7): reconstruct operational state on extra principal void"
```

### Task 9: Concurrency, stale-state, rollback, and regression matrix

**Files:**
- Create: `gilbic_backend/tests/test_seven_by_seven_extra_principal_concurrency_postgres.py`
- Modify: `gilbic_backend/tests/test_seven_by_seven_extra_principal_bridge_postgres.py`
- Modify: `gilbic_backend/tests/test_seven_by_seven_mobile_collection_postgres.py`
- Modify: `gilbic_backend/tests/test_regular_collection_reversal_postgres.py`

**Interfaces:**
- Consumes: complete forward/reversal bridge.
- Produces: persisted-state proof for all work-order test scenarios and simultaneous requests.

- [ ] **Step 1: Add real two-connection concurrency tests**

```python
def test_concurrent_identical_requests_create_one_receipt_and_adjustment(postgres_fixture):
    results = submit_in_parallel(COMMAND, COMMAND)
    assert sorted(result.status.value for result in results) == ["accepted", "duplicate"]
    assert count_receipts(IDEMPOTENCY_KEY) == 1
    assert count_adjustments_for_receipt(IDEMPOTENCY_KEY) == 1


def test_concurrent_post_and_reversal_serialize_without_partial_state(postgres_fixture):
    posting, reversal = race_post_and_void()
    assert exactly_one_terminal_order_is_observed(posting, reversal)
    assert persisted_state_reconciles()
```

- [ ] **Step 2: Run concurrency tests and confirm any missing lock failures**

Run: `python -m pytest gilbic_backend/tests/test_seven_by_seven_extra_principal_concurrency_postgres.py -q`

Expected: tests expose missing advisory/row locks until the bridge uses the required common ordering.

- [ ] **Step 3: Complete the 36-case persisted-state matrix**

Add named tests for both interest buckets, zero-interest allocation, tail removal, boundary reduction, signed immutability, retained Advance, Refund Due separation, exact/conflicting retries, stale route/loan/schedule/Advance, plan mismatch, receipt/accounting/audit/refund/reconciliation rollback, reversal/retry/replay, release block, immutability, duplicate prevention, 7x7 regression, Regular regression, and disposable bootstrap. Use transaction-local fault triggers for rollback cases and independent SQL reads after failure.

- [ ] **Step 4: Run the focused matrix and regressions**

Run: `python -m pytest gilbic_backend/tests/test_seven_by_seven_extra_principal_* gilbic_backend/tests/test_seven_by_seven_mobile_collection_postgres.py gilbic_backend/tests/test_regular_collection_reversal_postgres.py -q`

Expected: at least 36 named bridge scenarios pass with no persisted fragment after any rejected transaction.

- [ ] **Step 5: Commit the concurrency and regression matrix**

```bash
git add gilbic_backend/tests/test_seven_by_seven_extra_principal_concurrency_postgres.py gilbic_backend/tests/test_seven_by_seven_extra_principal_bridge_postgres.py gilbic_backend/tests/test_seven_by_seven_mobile_collection_postgres.py gilbic_backend/tests/test_regular_collection_reversal_postgres.py
git commit -m "test(7x7): prove extra principal atomicity and concurrency"
```

### Task 10: Disposable PostgreSQL, full validation, and Draft PR

**Files:**
- Modify only if validation discovers a scoped defect: files already listed in Tasks 1-9.
- Record evidence in Draft PR body; do not add generated logs to Git.

**Interfaces:**
- Consumes: final branch implementation and repository CI scripts.
- Produces: exact test counts, clean committed head, pushed branch, Draft PR to `mobile/ca4-collector-ui`, and five same-head CI conclusions.

- [ ] **Step 1: Run syntax and focused unit validation**

Run the repository-supported Python compile command, then:

```bash
python -m pytest gilbic_backend/tests/test_seven_by_seven_extra_principal.py gilbic_backend/tests/test_seven_by_seven_extra_principal_replay.py gilbic_backend/tests/test_seven_by_seven_extra_principal_posting.py -q
```

Expected: zero failures/errors.

- [ ] **Step 2: Run migration/bootstrap and real disposable PostgreSQL validation**

Run the repository's existing disposable PostgreSQL bootstrap command through migration 0108, followed by all `test_seven_by_seven_extra_principal_*_postgres.py` tests.

Expected: clean bootstrap from migration 0001 through 0108 and clean 0107-to-0108 upgrade, with zero failures/errors.

- [ ] **Step 3: Run accounting, concurrency, 7x7, and Regular regressions**

```bash
python -m pytest gilbic_backend/tests/test_7x7_source_event_accounting_preview_postgres.py gilbic_backend/tests/test_7x7_protected_journal_posting_postgres.py gilbic_backend/tests/test_7x7_controlled_collection_reversal_postgres.py gilbic_backend/tests/test_seven_by_seven_extra_principal_concurrency_postgres.py gilbic_backend/tests/test_seven_by_seven_mobile_collection_postgres.py gilbic_backend/tests/test_regular_collection_reversal_postgres.py -q
```

Expected: zero failures/errors and exact reconciliation evidence.

- [ ] **Step 4: Run repository backend suite and static controls**

Use the exact commands from the five GitHub workflow files for backend tests, lint, formatting, type checking, migration validation, security/compliance, reliability, and financial controls.

Expected: all local commands succeed; record exact passed/failed/skipped/errored counts.

- [ ] **Step 5: Verify diff and commit any final scoped correction**

```bash
git status --short --branch
git diff --check
git diff 6be0b0861a49aebaf5551162cbe66ea84d06b7dd...HEAD --stat
```

Expected: no uncommitted changes, no whitespace errors, and only bridge-related files.

- [ ] **Step 6: Push and create the Draft PR**

Push `codex/7x7-extra-principal-bridge`, create a Draft PR with base `mobile/ca4-collector-ui`, and reference Draft PR #370 and Master Issue #296. Do not mark Ready or merge.

- [ ] **Step 7: Wait for the five permanent CI lanes on one exact head**

Record run IDs and conclusions for Core Validation, Financial & Database Validation, Code Quality, Security & Compliance, and Reliability & Performance. A pending, cancelled, skipped, or unavailable lane is not green.

- [ ] **Step 8: Deliver the exact evidence report and continue Master #296**

Report starting/final SHA, commits, Draft PR, changed files, reused primitives, migration, tests/counts, PostgreSQL/accounting/idempotency evidence, CI run IDs, remaining risks, and confirmation of no merge/deployment/protected actions. Then select the next unchecked Master #296 dependency whose prerequisites are satisfied.
