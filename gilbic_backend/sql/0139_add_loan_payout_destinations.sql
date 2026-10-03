-- Private reviewed loan funding; preparation is never a money movement.
begin;
create table treasury.loan_payouts (
 id uuid primary key,
 account_id uuid not null,
 ledger_context_id uuid not null,
 source_kind text not null check(source_kind in ('first_loan','renewal')),
 source_id uuid not null,
 loan_id uuid not null references lending.loans(id),
 renewal_request_id uuid references lending.client_renewal_requests(id),
 client_id uuid not null references lending.clients(id),
 collector_user_id uuid references core.users(id),
 destination text not null check(destination in ('collector','borrower')),
 recipient_reference text not null check(btrim(recipient_reference)<>''),
 amount numeric(18,2) not null check(amount>0),
 source_digest text not null check(source_digest ~ '^[a-f0-9]{64}$'),
 source_snapshot jsonb not null check(jsonb_typeof(source_snapshot)='object'),
 version integer not null default 1 check(version>=1),
 status text not null default 'prepared'
   check(status in ('prepared','debited','recipient_confirmed','completed','cancelled')),
 event_id uuid unique references treasury.events(id),
 payload jsonb not null default '{}' check(jsonb_typeof(payload)='object'),
 prepared_by uuid not null references core.users(id),
 prepared_device_id uuid not null references core.devices(id),
 created_at timestamptz not null default now(),
 foreign key(account_id,ledger_context_id) references treasury.accounts(id,ledger_context_id),
 check((source_kind='first_loan' and source_id=loan_id and renewal_request_id is null)
    or (source_kind='renewal' and source_id=renewal_request_id and renewal_request_id is not null)),
 check(destination<>'collector' or collector_user_id is not null),
 check((status in ('prepared','cancelled') and event_id is null)
    or (status in ('debited','recipient_confirmed','completed') and event_id is not null))
);
create unique index loan_payout_one_live_source on treasury.loan_payouts(source_kind,source_id)
 where status<>'cancelled';
create index loan_payout_account_scope on treasury.loan_payouts(account_id,created_at desc,id desc);
alter table treasury.loan_payouts enable row level security;
revoke all on treasury.loan_payouts from public;
do $$ declare role_name text; begin
 foreach role_name in array array['anon','authenticated'] loop
   if exists(select 1 from pg_roles where rolname=role_name) then
     execute format('revoke all on treasury.loan_payouts from %I',role_name);
   end if;
 end loop;
end $$;

create function treasury.guard_loan_payout_identity() returns trigger
language plpgsql set search_path=pg_catalog as $$
begin
 if tg_op<>'UPDATE' then
   raise exception 'Loan payout history cannot be deleted or truncated' using errcode='23514';
 end if;
 if (new.id,new.account_id,new.ledger_context_id,new.source_kind,new.source_id,new.loan_id,
     new.renewal_request_id,new.client_id,new.collector_user_id,new.destination,
     new.recipient_reference,new.amount,new.source_digest,new.source_snapshot,
     new.prepared_by,new.prepared_device_id,new.created_at)
    is distinct from
    (old.id,old.account_id,old.ledger_context_id,old.source_kind,old.source_id,old.loan_id,
     old.renewal_request_id,old.client_id,old.collector_user_id,old.destination,
     old.recipient_reference,old.amount,old.source_digest,old.source_snapshot,
     old.prepared_by,old.prepared_device_id,old.created_at)
    or (old.event_id is not null and new.event_id is distinct from old.event_id)
    or new.version<>old.version+1 or old.status in ('completed','cancelled') then
   raise exception 'Reviewed payout identity and completed history are immutable' using errcode='23514';
 end if;
 if not ((old.status='prepared' and new.status in ('debited','cancelled'))
   or (old.status='debited' and new.status in ('debited','recipient_confirmed'))
   or (old.status='recipient_confirmed' and new.status in ('recipient_confirmed','completed'))) then
   raise exception 'Loan payout stages must follow verified debit and recipient receipt' using errcode='23514';
 end if;
 return new;
end $$;
create trigger loan_payout_identity before update or delete on treasury.loan_payouts
 for each row execute function treasury.guard_loan_payout_identity();
create trigger loan_payout_no_truncate before truncate on treasury.loan_payouts
 for each statement execute function treasury.guard_loan_payout_identity();
revoke all on function treasury.guard_loan_payout_identity() from public;
-- Truthful borrower receipt and funding route, preserving every legacy cash row.
alter table lending.office_review_evidence drop constraint office_review_evidence_purpose_check;
alter table lending.office_review_evidence add constraint office_review_evidence_purpose_check
 check(purpose in ('cif_review','application_review','borrower_contract_signed',
 'borrower_cash_received','privacy_acknowledgment','borrower_payout_received'));
alter table lending.first_loan_releases
 alter column cash_evidence_reference drop not null,
 alter column cash_amount drop not null,
 add column funding_payout_id uuid unique references treasury.loan_payouts(id),
 add column receipt_method text not null default 'cash' check(receipt_method in ('cash','gcash','bank')),
 add column received_amount numeric(18,2),
 add column borrower_receipt_reference text,
 add constraint first_loan_receipt_shape check(
  (funding_payout_id is null and cash_amount is not null and cash_evidence_reference is not null
   and receipt_method='cash' and received_amount is null and borrower_receipt_reference is null)
  or (funding_payout_id is not null and cash_amount is null and cash_evidence_reference is null
   and received_amount is not null and received_amount>0
   and borrower_receipt_reference is not null and btrim(borrower_receipt_reference)<>''));

create function lending.guard_first_loan_payout_release() returns trigger
language plpgsql set search_path=pg_catalog as $$
declare payout treasury.loan_payouts%rowtype;
begin
 select * into payout from treasury.loan_payouts
 where source_kind='first_loan' and source_id=new.loan_id and status<>'cancelled';
 if found then
  if new.funding_payout_id is distinct from payout.id or payout.status<>'recipient_confirmed'
   or new.received_amount is distinct from payout.amount then
   raise exception 'Complete the exact funded loan payout and borrower receipt' using errcode='23514';
  end if;
 elsif new.funding_payout_id is not null then
  raise exception 'The protected payout is unavailable' using errcode='23514';
 end if;
 return new;
end $$;
create trigger first_loan_payout_release before insert on lending.first_loan_releases
 for each row execute function lending.guard_first_loan_payout_release();

-- The existing bank/GCash category is a funding description, not a legal wallet mapping.
create function accounting.guard_loan_payout_journal() returns trigger
language plpgsql set search_path=pg_catalog as $$
begin
 if exists(select 1 from treasury.loan_payouts p
   join lending.loan_disbursement_events d on d.loan_id=p.loan_id
   left join lending.loan_renewal_execution_events r on r.disbursement_event_id=d.id
   where p.status<>'cancelled' and (new.source_event_key='loan_disbursement:'||d.id::text
    or new.source_event_key='loan_renewal_execution:'||r.id::text)) then
  raise exception 'Loan payout requires a reviewed wallet and legal-context journal mapping';
 end if;
 return new;
end $$;
create trigger loan_payout_journal_guard before insert or update on accounting.journal_entries
 for each row execute function accounting.guard_loan_payout_journal();
revoke all on function lending.guard_first_loan_payout_release(), accounting.guard_loan_payout_journal() from public;

-- A renewal payout cannot race or masquerade as the pre-existing cash workflow.
create function lending.guard_renewal_payout_cash() returns trigger
language plpgsql set search_path=pg_catalog as $$
begin
 if exists(select 1 from treasury.loan_payouts where source_kind='renewal' and source_id=new.id and status<>'cancelled')
 and (new.cash_released_to_collector_at is not null or new.collector_cash_received_at is not null
      or new.cash_given_to_client_at is not null or new.client_cash_confirmed_at is not null) then
  raise exception 'Use the protected payout receipt; cash custody fields cannot describe wallet funding' using errcode='23514';
 end if;
 return new;
end $$;
create trigger renewal_payout_cash before update on lending.client_renewal_requests
 for each row execute function lending.guard_renewal_payout_cash();
create function lending.guard_renewal_payout_activation() returns trigger
language plpgsql set search_path=pg_catalog as $$
begin
 if exists(select 1 from lending.client_renewal_requests r join treasury.loan_payouts p
  on p.source_kind='renewal' and p.source_id=r.id where r.id=new.id and r.activation_status='active'
  and p.status not in ('completed','cancelled')) then
  raise exception 'Renewal activation requires completed protected payout and independent borrower receipt' using errcode='23514';
 end if;
 return new;
end $$;
create constraint trigger renewal_payout_activation after update on lending.client_renewal_requests
 deferrable initially deferred for each row execute function lending.guard_renewal_payout_activation();
create unique index loan_payout_one_live_loan on treasury.loan_payouts(loan_id) where status<>'cancelled';
revoke all on function lending.guard_renewal_payout_cash(), lending.guard_renewal_payout_activation() from public;

-- Retain protected source facts while the actual funding is unresolved or consumed.
create function lending.guard_payout_source_void() returns trigger
language plpgsql set search_path=pg_catalog as $$
begin
 if new.is_voided and not old.is_voided and exists(
  select 1 from treasury.loan_payouts p where p.status<>'cancelled'
  and (case when tg_table_name='loan_disbursement_events' then p.loan_id::text=to_jsonb(new)->>'loan_id'
       else p.source_snapshot->'source'->>'execution_id'=new.id::text end)) then
   raise exception 'Reconcile the retained loan payout before voiding its protected source' using errcode='23514';
 end if;
 return new;
end $$;
create trigger payout_source_void before update on lending.loan_disbursement_events
 for each row execute function lending.guard_payout_source_void();
create trigger payout_source_void before update on lending.loan_renewal_execution_events
 for each row execute function lending.guard_payout_source_void();
revoke all on function lending.guard_payout_source_void() from public;

commit;
