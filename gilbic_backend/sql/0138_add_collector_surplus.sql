-- Additive collector custody/liability records. No real seeds or broad grants.
begin;
alter table treasury.accounts add column collector_source_watermark bigint not null default 0 check(collector_source_watermark>=0);
insert into core.permissions(code,description) values
 ('treasury.collector_surplus.receive','Receive counted Collector cash'),
 ('treasury.collector_surplus.resolve','Identify Collector excess'),
 ('treasury.collector_surplus.settle','Settle Collector credit'),
 ('treasury.collector_surplus.view','View scoped Collector excess')
on conflict(code) do nothing;
create table if not exists treasury.collector_counts (
 id uuid primary key, version integer not null default 1 check(version>=1),
 account_id uuid not null references treasury.accounts(id),
 ledger_context_id uuid not null references treasury.contexts(id),
 collector_user_id uuid not null references core.users(id),
 unique(id,ledger_context_id,collector_user_id), unique(id,account_id,ledger_context_id,collector_user_id),
 foreign key(account_id,ledger_context_id) references treasury.accounts(id,ledger_context_id),
 payload jsonb not null check(jsonb_typeof(payload)='object'),
 created_at timestamptz not null default now()
);
create index if not exists collector_counts_scope_idx on treasury.collector_counts(account_id,collector_user_id,created_at desc,id desc);
alter table treasury.collector_counts enable row level security;
revoke all on treasury.collector_counts from public;
create table if not exists treasury.collector_settlements (
 id uuid primary key, version integer not null default 1 check(version>=1),
 account_id uuid not null references treasury.accounts(id),
 ledger_context_id uuid not null references treasury.contexts(id),
 collector_user_id uuid not null references core.users(id),
 unique(id,ledger_context_id,collector_user_id), unique(id,account_id,ledger_context_id,collector_user_id),
 foreign key(account_id,ledger_context_id) references treasury.accounts(id,ledger_context_id),
 payload jsonb not null check(jsonb_typeof(payload)='object'),
 created_at timestamptz not null default now()
);
create index if not exists collector_settlements_scope_idx on treasury.collector_settlements(account_id,collector_user_id,created_at desc,id desc);
alter table treasury.collector_settlements enable row level security;
revoke all on treasury.collector_settlements from public;
create table if not exists treasury.collector_cases (
 id uuid primary key, version integer not null default 1 check(version>=1),
 account_id uuid not null references treasury.accounts(id),
 ledger_context_id uuid not null references treasury.contexts(id),
 collector_user_id uuid not null references core.users(id),
 unique(id,ledger_context_id,collector_user_id), unique(id,account_id,ledger_context_id,collector_user_id),
 foreign key(account_id,ledger_context_id) references treasury.accounts(id,ledger_context_id),
 payload jsonb not null check(jsonb_typeof(payload)='object'),
 created_at timestamptz not null default now()
);
create index if not exists collector_cases_scope_idx on treasury.collector_cases(account_id,collector_user_id,created_at desc,id desc);
alter table treasury.collector_cases enable row level security;
revoke all on treasury.collector_cases from public;
create table if not exists treasury.collector_credits (
 id uuid primary key, version integer not null default 1 check(version>=1),
 account_id uuid not null references treasury.accounts(id),
 ledger_context_id uuid not null references treasury.contexts(id),
 collector_user_id uuid not null references core.users(id),
 unique(id,ledger_context_id,collector_user_id), unique(id,account_id,ledger_context_id,collector_user_id),
 foreign key(account_id,ledger_context_id) references treasury.accounts(id,ledger_context_id),
 payload jsonb not null check(jsonb_typeof(payload)='object'),
 created_at timestamptz not null default now()
);
create index if not exists collector_credits_scope_idx on treasury.collector_credits(account_id,collector_user_id,created_at desc,id desc);
alter table treasury.collector_credits enable row level security;
revoke all on treasury.collector_credits from public;
create table if not exists treasury.collector_requests (
 id uuid primary key, version integer not null default 1 check(version>=1),
 account_id uuid not null references treasury.accounts(id),
 ledger_context_id uuid not null references treasury.contexts(id),
 collector_user_id uuid not null references core.users(id),
 unique(id,ledger_context_id,collector_user_id), unique(id,account_id,ledger_context_id,collector_user_id),
 foreign key(account_id,ledger_context_id) references treasury.accounts(id,ledger_context_id),
 payload jsonb not null check(jsonb_typeof(payload)='object'),
 created_at timestamptz not null default now()
);
create index if not exists collector_requests_scope_idx on treasury.collector_requests(account_id,collector_user_id,created_at desc,id desc);
alter table treasury.collector_requests enable row level security;
revoke all on treasury.collector_requests from public;
create table if not exists treasury.collector_actions (
 id uuid primary key, version integer not null default 1 check(version>=1),
 account_id uuid not null references treasury.accounts(id),
 ledger_context_id uuid not null references treasury.contexts(id),
 collector_user_id uuid not null references core.users(id),
 unique(id,ledger_context_id,collector_user_id), unique(id,account_id,ledger_context_id,collector_user_id),
 foreign key(account_id,ledger_context_id) references treasury.accounts(id,ledger_context_id),
 payload jsonb not null check(jsonb_typeof(payload)='object'),
 created_at timestamptz not null default now()
);
create index if not exists collector_actions_scope_idx on treasury.collector_actions(account_id,collector_user_id,created_at desc,id desc);
alter table treasury.collector_actions enable row level security;
revoke all on treasury.collector_actions from public;
create table if not exists treasury.collector_acknowledgments (
 id uuid primary key, version integer not null default 1 check(version>=1),
 account_id uuid not null references treasury.accounts(id),
 ledger_context_id uuid not null references treasury.contexts(id),
 collector_user_id uuid not null references core.users(id),
 unique(id,ledger_context_id,collector_user_id), unique(id,account_id,ledger_context_id,collector_user_id),
 foreign key(account_id,ledger_context_id) references treasury.accounts(id,ledger_context_id),
 payload jsonb not null check(jsonb_typeof(payload)='object'),
 created_at timestamptz not null default now()
);
create index if not exists collector_acknowledgments_scope_idx on treasury.collector_acknowledgments(account_id,collector_user_id,created_at desc,id desc);
alter table treasury.collector_acknowledgments enable row level security;
revoke all on treasury.collector_acknowledgments from public;
create table if not exists treasury.collector_exceptions (
 id uuid primary key, version integer not null default 1 check(version>=1),
 account_id uuid not null references treasury.accounts(id),
 ledger_context_id uuid not null references treasury.contexts(id),
 collector_user_id uuid not null references core.users(id),
 unique(id,ledger_context_id,collector_user_id), unique(id,account_id,ledger_context_id,collector_user_id),
 foreign key(account_id,ledger_context_id) references treasury.accounts(id,ledger_context_id),
 payload jsonb not null check(jsonb_typeof(payload)='object'),
 created_at timestamptz not null default now()
);
create index if not exists collector_exceptions_scope_idx on treasury.collector_exceptions(account_id,collector_user_id,created_at desc,id desc);
alter table treasury.collector_exceptions enable row level security;
revoke all on treasury.collector_exceptions from public;
create table if not exists treasury.collector_openings (
 id uuid primary key, version integer not null default 1 check(version>=1),
 account_id uuid not null references treasury.accounts(id),
 ledger_context_id uuid not null references treasury.contexts(id),
 collector_user_id uuid not null references core.users(id),
 unique(id,ledger_context_id,collector_user_id), unique(id,account_id,ledger_context_id,collector_user_id),
 foreign key(account_id,ledger_context_id) references treasury.accounts(id,ledger_context_id),
 payload jsonb not null check(jsonb_typeof(payload)='object'),
 created_at timestamptz not null default now()
);
create index if not exists collector_openings_scope_idx on treasury.collector_openings(account_id,collector_user_id,created_at desc,id desc);
alter table treasury.collector_openings enable row level security;
revoke all on treasury.collector_openings from public;
create table if not exists treasury.collector_entries (
 id uuid primary key, version integer not null default 1 check(version>=1),
 account_id uuid not null references treasury.accounts(id),
 ledger_context_id uuid not null references treasury.contexts(id),
 collector_user_id uuid not null references core.users(id),
 unique(id,ledger_context_id,collector_user_id), unique(id,account_id,ledger_context_id,collector_user_id),
 foreign key(account_id,ledger_context_id) references treasury.accounts(id,ledger_context_id),
 payload jsonb not null check(jsonb_typeof(payload)='object'),
 created_at timestamptz not null default now()
);
create index if not exists collector_entries_scope_idx on treasury.collector_entries(account_id,collector_user_id,created_at desc,id desc);
alter table treasury.collector_entries enable row level security;
revoke all on treasury.collector_entries from public;
create table if not exists treasury.collector_resolutions (
 id uuid primary key, version integer not null default 1 check(version>=1),
 account_id uuid not null references treasury.accounts(id),
 ledger_context_id uuid not null references treasury.contexts(id),
 collector_user_id uuid not null references core.users(id),
 unique(id,ledger_context_id,collector_user_id), unique(id,account_id,ledger_context_id,collector_user_id),
 foreign key(account_id,ledger_context_id) references treasury.accounts(id,ledger_context_id),
 payload jsonb not null check(jsonb_typeof(payload)='object'),
 created_at timestamptz not null default now()
);
create index if not exists collector_resolutions_scope_idx on treasury.collector_resolutions(account_id,collector_user_id,created_at desc,id desc);
alter table treasury.collector_resolutions enable row level security;
revoke all on treasury.collector_resolutions from public;
alter table treasury.collector_counts add column if not exists remittance_id uuid generated always as ((payload->>'remittance_id')::uuid) stored references lending.collection_remittances(id);
alter table treasury.collector_settlements add column if not exists remittance_id uuid generated always as ((payload->>'remittance_id')::uuid) stored unique references lending.collection_remittances(id);
alter table treasury.collector_settlements add column if not exists count_id uuid generated always as ((payload->>'count_id')::uuid) stored unique references treasury.collector_counts(id);
alter table treasury.collector_settlements add column if not exists event_id uuid generated always as ((payload->>'event_id')::uuid) stored unique references treasury.events(id);
alter table treasury.collector_cases add column if not exists settlement_id uuid generated always as ((payload->>'settlement_id')::uuid) stored unique references treasury.collector_settlements(id);
alter table treasury.collector_credits add column if not exists case_id uuid generated always as ((payload->>'case_id')::uuid) stored references treasury.collector_cases(id);
alter table treasury.collector_requests add column if not exists credit_id uuid generated always as ((payload->>'credit_id')::uuid) stored references treasury.collector_credits(id);
alter table treasury.collector_actions add column if not exists credit_id uuid generated always as ((payload->>'credit_id')::uuid) stored references treasury.collector_credits(id);
alter table treasury.collector_actions add column if not exists exception_id uuid generated always as ((payload->>'exception_id')::uuid) stored references treasury.collector_exceptions(id);
alter table treasury.collector_actions add column if not exists event_id uuid generated always as ((payload->>'event_id')::uuid) stored unique references treasury.events(id);
alter table treasury.collector_acknowledgments add column if not exists action_id uuid generated always as ((payload->>'action_id')::uuid) stored unique references treasury.collector_actions(id);
alter table treasury.collector_exceptions add column if not exists count_id uuid generated always as ((payload->>'count_id')::uuid) stored unique references treasury.collector_counts(id);
alter table treasury.collector_exceptions add column if not exists event_id uuid generated always as ((payload->>'event_id')::uuid) stored unique references treasury.events(id);
alter table treasury.collector_openings add column if not exists opening_id uuid generated always as ((payload->>'opening_id')::uuid) stored references treasury.opening_positions(id);
create unique index if not exists collector_opening_identity on treasury.collector_openings(opening_id,collector_user_id);
alter table treasury.collector_entries add column if not exists credit_id uuid generated always as ((payload->>'credit_id')::uuid) stored references treasury.collector_credits(id);
alter table treasury.collector_resolutions add column if not exists case_id uuid generated always as ((payload->>'case_id')::uuid) stored references treasury.collector_cases(id);
alter table treasury.collector_credits add constraint collector_credit_capacity check(
 (payload->>'recognized_amount')::numeric(18,2)>0 and
 (payload->>'reclassified_amount')::numeric(18,2)>=0 and
 (payload->>'returned_amount')::numeric(18,2)>=0 and
 (payload->>'applied_amount')::numeric(18,2)>=0 and
 (payload->>'reserved_amount')::numeric(18,2)>=0 and
 (payload->>'outstanding_amount')::numeric(18,2)=(payload->>'recognized_amount')::numeric(18,2)-(payload->>'reclassified_amount')::numeric(18,2)-(payload->>'returned_amount')::numeric(18,2)-(payload->>'applied_amount')::numeric(18,2) and
 (payload->>'available_amount')::numeric(18,2)=(payload->>'outstanding_amount')::numeric(18,2)-(payload->>'reserved_amount')::numeric(18,2) and
 (payload->>'available_amount')::numeric(18,2)>=0
);
alter table treasury.collector_cases add constraint collector_case_capacity check(
 (payload->>'received_excess_amount')::numeric(18,2)>0 and
 (payload->>'unidentified_amount')::numeric(18,2)>=0 and
 (payload->>'unidentified_amount')::numeric(18,2)<=(payload->>'received_excess_amount')::numeric(18,2)
);
alter table treasury.collector_counts add constraint collector_count_amount check(
 (payload->>'counted_amount')::numeric(18,2)>=0 and
 (payload->>'physical_cash_required')::numeric(18,2)>=0 and
 (payload->>'difference')::numeric(18,2)=(payload->>'counted_amount')::numeric(18,2)-(payload->>'physical_cash_required')::numeric(18,2)
);
alter table treasury.collector_counts add constraint collector_counts_required check (payload ?& array['remittance_id','recipient_user_id','source_digest','gross_obligation','refund_due_total','physical_cash_required','counted_amount','difference','counted_at','recorded_at','disposition','source_snapshot','evidence_id','recipient_attestation'] and jsonb_typeof(payload->'gross_obligation')='string' and (payload->>'gross_obligation') ~ '^(0|[1-9][0-9]{0,15})\.[0-9]{2}$' and jsonb_typeof(payload->'refund_due_total')='string' and (payload->>'refund_due_total') ~ '^(0|[1-9][0-9]{0,15})\.[0-9]{2}$' and jsonb_typeof(payload->'physical_cash_required')='string' and (payload->>'physical_cash_required') ~ '^(0|[1-9][0-9]{0,15})\.[0-9]{2}$' and jsonb_typeof(payload->'counted_amount')='string' and (payload->>'counted_amount') ~ '^(0|[1-9][0-9]{0,15})\.[0-9]{2}$' and jsonb_typeof(payload->'disposition')='string' and payload->>'disposition' in ('counted_ready','counted_short_rejected'));
alter table treasury.collector_settlements add constraint collector_settlements_required check (payload ?& array['remittance_id','count_id','recipient_user_id','event_id','physical_amount','authorized_credit_amount','gross_obligation','accepted_at'] and jsonb_typeof(payload->'physical_amount')='string' and (payload->>'physical_amount') ~ '^(0|[1-9][0-9]{0,15})\.[0-9]{2}$' and jsonb_typeof(payload->'authorized_credit_amount')='string' and (payload->>'authorized_credit_amount') ~ '^(0|[1-9][0-9]{0,15})\.[0-9]{2}$' and jsonb_typeof(payload->'gross_obligation')='string' and (payload->>'gross_obligation') ~ '^(0|[1-9][0-9]{0,15})\.[0-9]{2}$');
alter table treasury.collector_cases add constraint collector_cases_required check (payload ?& array['settlement_id','opening_id','received_excess_amount','unidentified_amount','source_digest','status','resolutions'] and jsonb_typeof(payload->'received_excess_amount')='string' and (payload->>'received_excess_amount') ~ '^(0|[1-9][0-9]{0,15})\.[0-9]{2}$' and jsonb_typeof(payload->'unidentified_amount')='string' and (payload->>'unidentified_amount') ~ '^(0|[1-9][0-9]{0,15})\.[0-9]{2}$' and jsonb_typeof(payload->'status')='string' and payload->>'status' in ('pending_identification','resolved'));
alter table treasury.collector_credits add constraint collector_credits_required check (payload ?& array['case_id','opening_anchor_id','origin_account_id','recognized_amount','reclassified_amount','returned_amount','applied_amount','reserved_amount','outstanding_amount','available_amount','frozen','status','entries'] and jsonb_typeof(payload->'recognized_amount')='string' and (payload->>'recognized_amount') ~ '^(0|[1-9][0-9]{0,15})\.[0-9]{2}$' and jsonb_typeof(payload->'reclassified_amount')='string' and (payload->>'reclassified_amount') ~ '^(0|[1-9][0-9]{0,15})\.[0-9]{2}$' and jsonb_typeof(payload->'returned_amount')='string' and (payload->>'returned_amount') ~ '^(0|[1-9][0-9]{0,15})\.[0-9]{2}$' and jsonb_typeof(payload->'applied_amount')='string' and (payload->>'applied_amount') ~ '^(0|[1-9][0-9]{0,15})\.[0-9]{2}$' and jsonb_typeof(payload->'reserved_amount')='string' and (payload->>'reserved_amount') ~ '^(0|[1-9][0-9]{0,15})\.[0-9]{2}$' and jsonb_typeof(payload->'outstanding_amount')='string' and (payload->>'outstanding_amount') ~ '^(0|[1-9][0-9]{0,15})\.[0-9]{2}$' and jsonb_typeof(payload->'available_amount')='string' and (payload->>'available_amount') ~ '^(0|[1-9][0-9]{0,15})\.[0-9]{2}$' and jsonb_typeof(payload->'status')='string' and payload->>'status' in ('outstanding','settled','recovery_required'));
alter table treasury.collector_requests add constraint collector_requests_required check (payload ?& array['kind','credit_id','amount','destination','remittance_id','source_digest','status','reason'] and jsonb_typeof(payload->'amount')='string' and (payload->>'amount') ~ '^(0|[1-9][0-9]{0,15})\.[0-9]{2}$' and jsonb_typeof(payload->'kind')='string' and payload->>'kind' in ('return','application') and jsonb_typeof(payload->'status')='string' and payload->>'status' in ('requested','approved'));
alter table treasury.collector_actions add constraint collector_actions_required check (payload ?& array['kind','credit_id','exception_id','collector_request_id','origin_account_id','paying_account_id','amount','destination','status','event_id','event_version','acknowledgment_id','evidence_id','reason'] and jsonb_typeof(payload->'amount')='string' and (payload->>'amount') ~ '^(0|[1-9][0-9]{0,15})\.[0-9]{2}$' and jsonb_typeof(payload->'kind')='string' and payload->>'kind' in ('return','application','exception_return') and jsonb_typeof(payload->'status')='string' and payload->>'status' in ('reserved','debited_confirmation_pending','paid','applied','cancelled','partly_reversed','reversed'));
alter table treasury.collector_acknowledgments add constraint collector_acknowledgments_required check (payload ?& array['action_id','event_id','event_version','reviewed_amount','confirmation','acknowledged_at','recorded_at','reason'] and jsonb_typeof(payload->'reviewed_amount')='string' and (payload->>'reviewed_amount') ~ '^(0|[1-9][0-9]{0,15})\.[0-9]{2}$' and jsonb_typeof(payload->'confirmation')='string' and payload->>'confirmation' in ('received','not_received'));
alter table treasury.collector_exceptions add constraint collector_exceptions_required check (payload ?& array['count_id','remittance_id','holder_user_id','retained_amount','returned_amount','included_amount','reserved_amount','remaining_held_amount','available_amount','status','event_id','source_digest','evidence_id','reason'] and jsonb_typeof(payload->'retained_amount')='string' and (payload->>'retained_amount') ~ '^(0|[1-9][0-9]{0,15})\.[0-9]{2}$' and jsonb_typeof(payload->'returned_amount')='string' and (payload->>'returned_amount') ~ '^(0|[1-9][0-9]{0,15})\.[0-9]{2}$' and jsonb_typeof(payload->'included_amount')='string' and (payload->>'included_amount') ~ '^(0|[1-9][0-9]{0,15})\.[0-9]{2}$' and jsonb_typeof(payload->'reserved_amount')='string' and (payload->>'reserved_amount') ~ '^(0|[1-9][0-9]{0,15})\.[0-9]{2}$' and jsonb_typeof(payload->'remaining_held_amount')='string' and (payload->>'remaining_held_amount') ~ '^(0|[1-9][0-9]{0,15})\.[0-9]{2}$' and jsonb_typeof(payload->'available_amount')='string' and (payload->>'available_amount') ~ '^(0|[1-9][0-9]{0,15})\.[0-9]{2}$' and jsonb_typeof(payload->'status')='string' and payload->>'status' in ('held_disputed','partly_returned','returned','included_in_settlement'));
alter table treasury.collector_openings add constraint collector_openings_required check (payload ?& array['opening_id','opening_version','amount','cutoff','status','evidence_id','reason'] and jsonb_typeof(payload->'amount')='string' and (payload->>'amount') ~ '^(0|[1-9][0-9]{0,15})\.[0-9]{2}$' and jsonb_typeof(payload->'status')='string' and payload->>'status' in ('draft','active'));
alter table treasury.collector_entries add constraint collector_entries_required check (payload ?& array['credit_id','kind','amount','action_id'] and jsonb_typeof(payload->'amount')='string' and (payload->>'amount') ~ '^(0|[1-9][0-9]{0,15})\.[0-9]{2}$' and jsonb_typeof(payload->'kind')='string' and payload->>'kind' in ('recognition','opening','return','return_reversal'));
alter table treasury.collector_resolutions add constraint collector_resolutions_required check (payload ?& array['case_id','kind','credit_id','amount','evidence_id','reason'] and jsonb_typeof(payload->'amount')='string' and (payload->>'amount') ~ '^(0|[1-9][0-9]{0,15})\.[0-9]{2}$' and jsonb_typeof(payload->'kind')='string' and payload->>'kind' in ('collector_credit'));
alter table treasury.collector_counts alter column remittance_id set not null;
alter table treasury.collector_settlements alter column remittance_id set not null;
alter table treasury.collector_settlements alter column count_id set not null;
alter table treasury.collector_credits add column opening_anchor_id uuid generated always as ((payload->>'opening_anchor_id')::uuid) stored unique references treasury.collector_openings(id);
alter table treasury.collector_credits add constraint collector_credit_origin check((payload->>'origin_account_id')::uuid=account_id and ((case_id is null)<>(opening_anchor_id is null)) and jsonb_typeof(payload->'frozen')='boolean');
alter table treasury.collector_cases add constraint collector_case_origin check((settlement_id is null)<>((payload->>'opening_id') is null));
alter table treasury.collector_actions add constraint collector_action_target check((credit_id is null)<>(exception_id is null) and (payload->>'paying_account_id')::uuid=account_id);
alter table treasury.collector_requests alter column credit_id set not null;
alter table treasury.collector_acknowledgments alter column action_id set not null;
alter table treasury.collector_exceptions alter column count_id set not null;
alter table treasury.collector_exceptions alter column event_id set not null;
alter table treasury.collector_openings alter column opening_id set not null;
alter table treasury.collector_exceptions add constraint collector_exception_capacity check(
 (payload->>'retained_amount')::numeric>0 and
 (payload->>'remaining_held_amount')::numeric=(payload->>'retained_amount')::numeric-(payload->>'returned_amount')::numeric-(payload->>'included_amount')::numeric and
 (payload->>'available_amount')::numeric=(payload->>'remaining_held_amount')::numeric-(payload->>'reserved_amount')::numeric and
 (payload->>'available_amount')::numeric>=0);
alter table treasury.collector_settlements add constraint collector_settlements_count_id_scope foreign key(count_id,ledger_context_id,collector_user_id) references treasury.collector_counts(id,ledger_context_id,collector_user_id);
alter table treasury.collector_cases add constraint collector_cases_settlement_id_scope foreign key(settlement_id,ledger_context_id,collector_user_id) references treasury.collector_settlements(id,ledger_context_id,collector_user_id);
alter table treasury.collector_credits add constraint collector_credits_case_id_scope foreign key(case_id,ledger_context_id,collector_user_id) references treasury.collector_cases(id,ledger_context_id,collector_user_id);
alter table treasury.collector_credits add constraint collector_credits_opening_anchor_id_scope foreign key(opening_anchor_id,ledger_context_id,collector_user_id) references treasury.collector_openings(id,ledger_context_id,collector_user_id);
alter table treasury.collector_requests add constraint collector_requests_credit_id_scope foreign key(credit_id,ledger_context_id,collector_user_id) references treasury.collector_credits(id,ledger_context_id,collector_user_id);
alter table treasury.collector_actions add constraint collector_actions_credit_id_scope foreign key(credit_id,ledger_context_id,collector_user_id) references treasury.collector_credits(id,ledger_context_id,collector_user_id);
alter table treasury.collector_actions add constraint collector_actions_exception_id_scope foreign key(exception_id,ledger_context_id,collector_user_id) references treasury.collector_exceptions(id,ledger_context_id,collector_user_id);
alter table treasury.collector_acknowledgments add constraint collector_acknowledgments_action_id_scope foreign key(action_id,ledger_context_id,collector_user_id) references treasury.collector_actions(id,ledger_context_id,collector_user_id);
alter table treasury.collector_exceptions add constraint collector_exceptions_count_id_scope foreign key(count_id,ledger_context_id,collector_user_id) references treasury.collector_counts(id,ledger_context_id,collector_user_id);
alter table treasury.collector_entries add constraint collector_entries_credit_id_scope foreign key(credit_id,ledger_context_id,collector_user_id) references treasury.collector_credits(id,ledger_context_id,collector_user_id);
alter table treasury.collector_resolutions add constraint collector_resolutions_case_id_scope foreign key(case_id,ledger_context_id,collector_user_id) references treasury.collector_cases(id,ledger_context_id,collector_user_id);
alter table treasury.evidence add constraint collector_evidence_identity unique(id,account_id);
alter table treasury.collector_counts add column evidence_id uuid generated always as ((payload->>'evidence_id')::uuid) stored not null references treasury.evidence(id);
alter table treasury.collector_counts add constraint collector_counts_evidence_scope foreign key(evidence_id,account_id) references treasury.evidence(id,account_id);
alter table treasury.collector_actions add column evidence_id uuid generated always as ((payload->>'evidence_id')::uuid) stored not null references treasury.evidence(id);
alter table treasury.collector_actions add constraint collector_actions_evidence_scope foreign key(evidence_id,account_id) references treasury.evidence(id,account_id);
alter table treasury.collector_exceptions add column evidence_id uuid generated always as ((payload->>'evidence_id')::uuid) stored not null references treasury.evidence(id);
alter table treasury.collector_exceptions add constraint collector_exceptions_evidence_scope foreign key(evidence_id,account_id) references treasury.evidence(id,account_id);
alter table treasury.collector_openings add column evidence_id uuid generated always as ((payload->>'evidence_id')::uuid) stored not null references treasury.evidence(id);
alter table treasury.collector_openings add constraint collector_openings_evidence_scope foreign key(evidence_id,account_id) references treasury.evidence(id,account_id);
alter table treasury.collector_resolutions add column evidence_id uuid generated always as ((payload->>'evidence_id')::uuid) stored not null references treasury.evidence(id);
alter table treasury.collector_resolutions add constraint collector_resolutions_evidence_scope foreign key(evidence_id,account_id) references treasury.evidence(id,account_id);
alter table treasury.collector_cases add column opening_anchor_id uuid generated always as ((payload->>'opening_anchor_id')::uuid) stored unique references treasury.collector_openings(id);
alter table treasury.collector_requests add constraint collector_requests_positive check((payload->>'amount')::numeric>0);
alter table treasury.collector_actions add constraint collector_actions_positive check((payload->>'amount')::numeric>0);
alter table treasury.collector_acknowledgments add constraint collector_acknowledgments_positive check((payload->>'reviewed_amount')::numeric>0);
alter table treasury.collector_openings add constraint collector_openings_positive check((payload->>'amount')::numeric>0);
alter table treasury.collector_entries add constraint collector_entries_positive check((payload->>'amount')::numeric>0);
alter table treasury.collector_resolutions add constraint collector_resolutions_positive check((payload->>'amount')::numeric>0);
alter table treasury.collector_counts add constraint collector_count_digest check(jsonb_typeof(payload->'source_digest')='string' and payload->>'source_digest' ~ '^[a-f0-9]{64}$' and jsonb_typeof(payload->'source_snapshot')='object');
alter table treasury.collector_cases add constraint collector_case_digest check(jsonb_typeof(payload->'source_digest')='string' and payload->>'source_digest' ~ '^[a-f0-9]{64}$');
alter table lending.collection_remittances add constraint collector_remittance_actors unique(id,collector_user_id,recipient_user_id);
alter table treasury.collector_counts add column recipient_user_id uuid generated always as ((payload->>'recipient_user_id')::uuid) stored not null references core.users(id);
alter table treasury.collector_counts add constraint collector_count_recipient unique(id,recipient_user_id);
alter table treasury.collector_counts add constraint collector_count_remittance unique(id,remittance_id);
alter table treasury.collector_counts add constraint collector_count_actors foreign key(remittance_id,collector_user_id,recipient_user_id) references lending.collection_remittances(id,collector_user_id,recipient_user_id);
alter table treasury.collector_settlements add column recipient_user_id uuid generated always as ((payload->>'recipient_user_id')::uuid) stored not null references core.users(id);
alter table treasury.collector_settlements add constraint collector_settlement_remittance foreign key(count_id,remittance_id) references treasury.collector_counts(id,remittance_id);
alter table treasury.collector_settlements add constraint collector_settlement_recipient foreign key(count_id,recipient_user_id) references treasury.collector_counts(id,recipient_user_id);
alter table treasury.collector_exceptions add column holder_user_id uuid generated always as ((payload->>'holder_user_id')::uuid) stored not null references core.users(id);
alter table treasury.collector_exceptions add constraint collector_exception_holder foreign key(count_id,holder_user_id) references treasury.collector_counts(id,recipient_user_id);
alter table treasury.collector_settlements add constraint collector_settlements_count_id_account foreign key(count_id,account_id,ledger_context_id,collector_user_id) references treasury.collector_counts(id,account_id,ledger_context_id,collector_user_id);
alter table treasury.collector_cases add constraint collector_cases_settlement_id_account foreign key(settlement_id,account_id,ledger_context_id,collector_user_id) references treasury.collector_settlements(id,account_id,ledger_context_id,collector_user_id);
alter table treasury.collector_cases add constraint collector_cases_opening_anchor_id_account foreign key(opening_anchor_id,account_id,ledger_context_id,collector_user_id) references treasury.collector_openings(id,account_id,ledger_context_id,collector_user_id);
alter table treasury.collector_credits add constraint collector_credits_case_id_account foreign key(case_id,account_id,ledger_context_id,collector_user_id) references treasury.collector_cases(id,account_id,ledger_context_id,collector_user_id);
alter table treasury.collector_credits add constraint collector_credits_opening_anchor_id_account foreign key(opening_anchor_id,account_id,ledger_context_id,collector_user_id) references treasury.collector_openings(id,account_id,ledger_context_id,collector_user_id);
alter table treasury.collector_requests add constraint collector_requests_credit_id_account foreign key(credit_id,account_id,ledger_context_id,collector_user_id) references treasury.collector_credits(id,account_id,ledger_context_id,collector_user_id);
alter table treasury.collector_exceptions add constraint collector_exceptions_count_id_account foreign key(count_id,account_id,ledger_context_id,collector_user_id) references treasury.collector_counts(id,account_id,ledger_context_id,collector_user_id);
alter table treasury.collector_resolutions add constraint collector_resolutions_case_id_account foreign key(case_id,account_id,ledger_context_id,collector_user_id) references treasury.collector_cases(id,account_id,ledger_context_id,collector_user_id);
create or replace function treasury.guard_collector_fact() returns trigger language plpgsql as $$
begin
 if tg_op='DELETE' then raise exception 'Collector facts cannot be deleted'; end if;
 if old.id<>new.id or old.account_id<>new.account_id or old.ledger_context_id<>new.ledger_context_id or old.collector_user_id<>new.collector_user_id or old.created_at<>new.created_at then raise exception 'Collector identity is immutable'; end if;
 if tg_table_name in ('collector_counts','collector_settlements','collector_entries','collector_resolutions','collector_acknowledgments') then raise exception 'Collector fact is append only'; end if;
 if new.version<>old.version+1 then raise exception 'Collector version must advance exactly once'; end if;
 if tg_table_name='collector_cases' and (old.payload - array['unidentified_amount','status','resolutions'])<>(new.payload - array['unidentified_amount','status','resolutions']) then raise exception 'Collector cases facts are immutable'; end if;
 if tg_table_name='collector_requests' and (old.payload - array['status'])<>(new.payload - array['status']) then raise exception 'Collector requests facts are immutable'; end if;
 if tg_table_name='collector_actions' and (old.payload - array['status','event_id','event_version','acknowledgment_id','cancellation_evidence_id','cancellation_reason','reversed_amount'])<>(new.payload - array['status','event_id','event_version','acknowledgment_id','cancellation_evidence_id','cancellation_reason','reversed_amount']) then raise exception 'Collector actions facts are immutable'; end if;
 if tg_table_name='collector_exceptions' and (old.payload - array['returned_amount','included_amount','reserved_amount','remaining_held_amount','available_amount','status'])<>(new.payload - array['returned_amount','included_amount','reserved_amount','remaining_held_amount','available_amount','status']) then raise exception 'Collector exceptions facts are immutable'; end if;
 if tg_table_name='collector_openings' and (old.payload - array['status'])<>(new.payload - array['status']) then raise exception 'Collector openings facts are immutable'; end if;
 if tg_table_name='collector_credits' and (old.payload - array['reclassified_amount','returned_amount','applied_amount','outstanding_amount','reserved_amount','available_amount','frozen','status','entries'])<>(new.payload - array['reclassified_amount','returned_amount','applied_amount','outstanding_amount','reserved_amount','available_amount','frozen','status','entries']) then raise exception 'Recognized Collector credit facts are immutable'; end if;
 return new;
end $$;
create trigger guard_collector_counts before update or delete on treasury.collector_counts for each row execute function treasury.guard_collector_fact();
create trigger guard_collector_settlements before update or delete on treasury.collector_settlements for each row execute function treasury.guard_collector_fact();
create trigger guard_collector_cases before update or delete on treasury.collector_cases for each row execute function treasury.guard_collector_fact();
create trigger guard_collector_credits before update or delete on treasury.collector_credits for each row execute function treasury.guard_collector_fact();
create trigger guard_collector_requests before update or delete on treasury.collector_requests for each row execute function treasury.guard_collector_fact();
create trigger guard_collector_actions before update or delete on treasury.collector_actions for each row execute function treasury.guard_collector_fact();
create trigger guard_collector_acknowledgments before update or delete on treasury.collector_acknowledgments for each row execute function treasury.guard_collector_fact();
create trigger guard_collector_exceptions before update or delete on treasury.collector_exceptions for each row execute function treasury.guard_collector_fact();
create trigger guard_collector_openings before update or delete on treasury.collector_openings for each row execute function treasury.guard_collector_fact();
create trigger guard_collector_entries before update or delete on treasury.collector_entries for each row execute function treasury.guard_collector_fact();
create trigger guard_collector_resolutions before update or delete on treasury.collector_resolutions for each row execute function treasury.guard_collector_fact();
create or replace function treasury.reject_collector_truncate() returns trigger language plpgsql as $$
begin raise exception 'Collector history cannot be truncated'; end $$;
create trigger collector_counts_no_truncate before truncate on treasury.collector_counts for each statement execute function treasury.reject_collector_truncate();
create trigger collector_settlements_no_truncate before truncate on treasury.collector_settlements for each statement execute function treasury.reject_collector_truncate();
create trigger collector_cases_no_truncate before truncate on treasury.collector_cases for each statement execute function treasury.reject_collector_truncate();
create trigger collector_credits_no_truncate before truncate on treasury.collector_credits for each statement execute function treasury.reject_collector_truncate();
create trigger collector_requests_no_truncate before truncate on treasury.collector_requests for each statement execute function treasury.reject_collector_truncate();
create trigger collector_actions_no_truncate before truncate on treasury.collector_actions for each statement execute function treasury.reject_collector_truncate();
create trigger collector_acknowledgments_no_truncate before truncate on treasury.collector_acknowledgments for each statement execute function treasury.reject_collector_truncate();
create trigger collector_exceptions_no_truncate before truncate on treasury.collector_exceptions for each statement execute function treasury.reject_collector_truncate();
create trigger collector_openings_no_truncate before truncate on treasury.collector_openings for each statement execute function treasury.reject_collector_truncate();
create trigger collector_entries_no_truncate before truncate on treasury.collector_entries for each statement execute function treasury.reject_collector_truncate();
create trigger collector_resolutions_no_truncate before truncate on treasury.collector_resolutions for each statement execute function treasury.reject_collector_truncate();
create or replace function treasury.guard_collector_legacy_receive() returns trigger language plpgsql as $$
begin
 if new.status='received' and old.status<>'received' and exists(select 1 from treasury.collector_counts where remittance_id=new.id) and coalesce(current_setting('spina.collector_count_accept',true),'')<>new.id::text then raise exception 'collector_count_required'; end if;
 if new.status='rejected' and old.status<>'rejected' and exists(select 1 from treasury.collector_exceptions where (payload->>'remittance_id')::uuid=new.id and (payload->>'remaining_held_amount')::numeric>0) then raise exception 'retained_cash_dispute_requires_resolution'; end if;
 return new;
end $$;
create trigger guard_collector_legacy_receive before update on lending.collection_remittances for each row execute function treasury.guard_collector_legacy_receive();
create or replace function treasury.guard_collector_rejection() returns trigger language plpgsql as $$
begin
 perform 1 from lending.collection_remittances where id=new.remittance_id for update;
 if exists(select 1 from treasury.collector_exceptions where (payload->>'remittance_id')::uuid=new.remittance_id and (payload->>'remaining_held_amount')::numeric>0) then raise exception 'retained_cash_dispute_requires_resolution'; end if;
 return new;
end $$;
create trigger guard_collector_rejection before insert on lending.collection_remittance_rejections for each row execute function treasury.guard_collector_rejection();
do $$ begin
 if exists(select 1 from pg_roles where rolname='anon') then revoke all on all tables in schema treasury from anon; end if;
 if exists(select 1 from pg_roles where rolname='authenticated') then revoke all on all tables in schema treasury from authenticated; end if;
end $$;
commit;
