"""One private read snapshot for dated Collector controls and current capacity."""

from datetime import timezone
from uuid import UUID

from .accounting_book_repository import book_identity_payload, read_book_identity
from .treasury_authorization import TreasuryDenied, TreasuryUnavailable, require_actor

DENIED = "Current Management accounting and private history access to every contributing Treasury account is required."

# All dated source rows and all current capacity rows contribute to authorization,
# independently of LIMIT/OFFSET. Numeric values remain exact decimal strings.
SNAPSHOT = """
WITH clock AS MATERIALIZED (SELECT clock_timestamp() observed_at),
cutoff AS (SELECT coalesce(%s::date,(observed_at AT TIME ZONE 'Asia/Manila')::date) AS cutoff_date FROM clock),
raw AS MATERIALIZED (
 SELECT m.*,accounting.collector_source_exact(m.source_type,m.source_id,c.cutoff_date) exact_posted
 FROM accounting.collector_control_movements() m CROSS JOIN cutoff c WHERE m.effective_date<=c.cutoff_date
), status AS MATERIALIZED (
 SELECT p.* FROM accounting.collector_liability_posting_status p CROSS JOIN cutoff c WHERE p.posting_date<=c.cutoff_date
), wallets AS (
 SELECT account_id id FROM raw
 UNION SELECT account_id FROM treasury.collector_cases
 UNION SELECT account_id FROM treasury.collector_credits
 UNION SELECT account_id FROM treasury.collector_actions WHERE payload->>'kind' IN('return','application')
 UNION SELECT (payload->>'origin_account_id')::uuid FROM treasury.collector_actions WHERE payload->>'kind' IN('return','application')
 UNION SELECT (payload->>'paying_account_id')::uuid FROM treasury.collector_actions WHERE payload->>'kind' IN('return','application')
 UNION SELECT event.account_id FROM treasury.collector_actions action
 JOIN treasury.events event ON event.id=action.event_id WHERE action.payload->>'kind'='return'
 UNION SELECT event.account_id FROM treasury.collector_cases item
 JOIN treasury.collector_settlements settlement ON settlement.id=item.settlement_id
 JOIN treasury.events event ON event.id=settlement.event_id
 UNION SELECT event.account_id FROM treasury.collector_entries entry
 JOIN treasury.events event ON event.id=(entry.payload->>'incoming_event_id')::uuid
 WHERE entry.payload->>'kind'='return_reversal'
 UNION SELECT ack.account_id FROM treasury.collector_entries entry
 JOIN treasury.collector_actions action ON action.id=(entry.payload->>'action_id')::uuid
 JOIN treasury.collector_acknowledgments ack ON ack.id=(action.payload->>'acknowledgment_id')::uuid
 WHERE entry.payload->>'kind'='return'
 UNION SELECT opening.account_id FROM treasury.collector_openings opening
 WHERE EXISTS(SELECT 1 FROM treasury.collector_cases item WHERE item.opening_anchor_id=opening.id)
    OR EXISTS(SELECT 1 FROM treasury.collector_credits credit WHERE credit.opening_anchor_id=opening.id)
 UNION SELECT event.account_id FROM status JOIN treasury.events event ON event.id=status.event_id
 UNION SELECT jsonb_array_elements_text(p.snapshot->'account_ids')::uuid
 FROM accounting.collector_liability_preparations p JOIN status s ON s.preparation_id=p.id
), controls AS (
 SELECT r.*,CASE WHEN r.account_code='1060' THEN 'debit' ELSE 'credit' END normal_balance,
 CASE WHEN r.account_code='1060' THEN 1 ELSE -1 END direction
 FROM cutoff c CROSS JOIN LATERAL accounting.collector_control_reconciliation(c.cutoff_date) r
)
SELECT (SELECT cutoff_date FROM cutoff) as_of,(SELECT observed_at FROM clock) observed_at,
 coalesce((SELECT jsonb_agg(id ORDER BY id) FROM wallets WHERE id IS NOT NULL),'[]'::jsonb) wallets,
 coalesce((SELECT jsonb_agg(jsonb_build_object(
  'account_code',account_code,'normal_balance',normal_balance,
  'source_balance',source_balance::numeric(18,2)::text,'ledger_balance',ledger_balance::numeric(18,2)::text,
  'difference',difference::numeric(18,2)::text,'source_amount',(direction*source_balance)::numeric(18,2)::text,
  'ledger_amount',(direction*ledger_balance)::numeric(18,2)::text,'unregistered_line_count',unregistered_line_count
 ) ORDER BY account_code) FROM controls),'[]'::jsonb) controls,
 coalesce((SELECT jsonb_agg(jsonb_build_object(
  'account_code',account_code,'effective_date',effective_date,'signed_amount',signed_amount::numeric(18,2)::text,
  'source_type',source_type,'source_id',source_id,'exact_posted',exact_posted
 ) ORDER BY effective_date,source_type,source_id,account_code)
 FROM (SELECT * FROM raw ORDER BY effective_date,source_type,source_id,account_code LIMIT %s OFFSET %s) page),'[]'::jsonb) movements,
 (SELECT count(*) FROM raw) movement_count,
 (SELECT count(*) FROM raw WHERE NOT exact_posted) unproven_movement_count,
 (SELECT count(*) FROM status WHERE NOT exact_posted OR correction_pending) correction_count,
 (SELECT coalesce(sum((payload->>'unidentified_amount')::numeric),0)::numeric(18,2)::text FROM treasury.collector_cases) unidentified_amount,
 (SELECT coalesce(sum((payload->>'outstanding_amount')::numeric),0)::numeric(18,2)::text FROM treasury.collector_credits) outstanding_amount,
 (SELECT coalesce(sum((payload->>'reserved_amount')::numeric),0)::numeric(18,2)::text FROM treasury.collector_credits) reserved_amount,
 (SELECT coalesce(sum((payload->>'available_amount')::numeric),0)::numeric(18,2)::text FROM treasury.collector_credits) available_amount,
 (SELECT count(*) FROM treasury.collector_credits WHERE
  payload->>'outstanding_amount' IS NULL OR payload->>'reserved_amount' IS NULL OR payload->>'available_amount' IS NULL OR
  (payload->>'outstanding_amount')::numeric<0 OR (payload->>'reserved_amount')::numeric<0 OR
  (payload->>'available_amount')::numeric<0 OR
  (payload->>'available_amount')::numeric<>(payload->>'outstanding_amount')::numeric-(payload->>'reserved_amount')::numeric) invalid_capacity_count
"""


def load_collector_control_schedule(conn, actor, *, as_of=None, limit=100, offset=0):
    if not 1 <= limit <= 500 or offset < 0:
        raise TreasuryUnavailable("A valid schedule page is required.")
    require_actor(conn, actor)
    permitted = conn.execute(
        """SELECT u.id FROM core.users u JOIN core.user_roles ur ON ur.user_id=u.id
        JOIN core.roles r ON r.id=ur.role_id JOIN core.role_permissions rp ON rp.role_id=r.id
        WHERE u.id=%s AND u.status='active' AND r.code='management' AND rp.permission_code='accounting.view'
        FOR SHARE OF u,ur,r,rp""",
        (actor.user_id,),
    ).fetchone()
    if permitted is None:
        raise TreasuryDenied(DENIED)
    with conn.cursor() as cursor:
        book = book_identity_payload(read_book_identity(cursor))
    if book["status"] != "configured":
        raise TreasuryUnavailable(
            "Configure the accounting book before reviewing Collector controls."
        )
    snapshot = conn.execute(SNAPSHOT, (as_of, limit, offset)).fetchone()
    # Do not use the mutation guard: history includes inactive wallets and this
    # read requires accounting.view, not permission to post monetary journals.
    for raw_id in snapshot["wallets"]:
        account_id = UUID(raw_id)
        for permission in ("treasury.view", "treasury.collector_surplus.view"):
            grant = conn.execute(
                """SELECT a.id FROM treasury.accounts a JOIN treasury.account_access g ON g.account_id=a.id
                WHERE a.id=%s AND g.user_id=%s AND g.enabled AND g.private_history AND %s=ANY(g.permissions)
                FOR SHARE OF a,g""",
                (account_id, actor.user_id, permission),
            ).fetchone()
            live = conn.execute(
                """SELECT rp.permission_code FROM core.user_roles ur JOIN core.role_permissions rp ON rp.role_id=ur.role_id
                WHERE ur.user_id=%s AND rp.permission_code=%s FOR SHARE OF ur,rp""",
                (actor.user_id, permission),
            ).fetchone()
            if grant is None or live is None:
                raise TreasuryDenied(DENIED)
    if snapshot["invalid_capacity_count"]:
        raise TreasuryUnavailable(
            "Current Collector capacity evidence is inconsistent."
        )
    controls = snapshot["controls"]
    if len(controls) != 3:
        raise TreasuryUnavailable("Collector control evidence is incomplete.")
    return {
        "book": book,
        "as_of": snapshot["as_of"].isoformat(),
        "business_timezone": "Asia/Manila",
        "balance_basis": "debit_minus_credit",
        "controls": controls,
        "movements": snapshot["movements"],
        "movement_count": snapshot["movement_count"],
        "unproven_movement_count": snapshot["unproven_movement_count"],
        "correction_count": snapshot["correction_count"],
        "limit": limit,
        "offset": offset,
        "current_capacity": {
            "observed_at": snapshot["observed_at"].astimezone(timezone.utc).isoformat(),
            **{
                key: snapshot[key]
                for key in (
                    "unidentified_amount",
                    "outstanding_amount",
                    "reserved_amount",
                    "available_amount",
                )
            },
        },
        "controls_reconciled": all(
            row["difference"] == "0.00" and row["unregistered_line_count"] == 0
            for row in controls
        )
        and snapshot["unproven_movement_count"] == 0
        and snapshot["correction_count"] == 0,
        "comprehensive_source_coverage": False,
    }
