# Exact source proof composition

Migration 0149 composes protected application accounting from 0146 and retained actual-cutoff assessment from 0148. It changes neither adapter's monetary policy. Earlier migration files 0143 and 0145 remain untouched. The raw legacy inventory is retained under an explicit raw name; its original public name becomes a filtered inventory consumed by both the legacy close assertion and the common period inventory.

## Discharge rules

An exact current 0146 application audit, plus its exact current 0142 receipt cash proof, discharges only that Treasury application and the matching collection row whose reason is `treasury_collection_application_mapping_required`. The proof must belong to the configured book. An original historical posting with a source correction, receipt revision, or changed preceding EIR source remains blocked. No collection allocation, unsupported reversal or another application's source is waived.

The initial Treasury inventory never included raw applications. Add an independent `treasury_application` family with its originating Treasury account scope. Read collection dates from the actual referenced collection transactions, not the source JSON's asserted amounts or a client-provided date. Include a period containing any actual linked collection or void date. When links are missing, malformed, duplicated or incomplete, also use the application's actual `created_at` in Asia/Manila as a conservative fallback. A backdated application's valid collection date remains authoritative even when its recording timestamp is later. Amounts in blocker rows are source evidence amounts and are not additive financial totals.

An exact current 0148 assessment discharges only `eir_period_end` and `ecl_period_end` for that loan and fiscal period. Tax, loan control, Treasury, collection, release, cancellation, remittance and liability rows remain untouched. In particular, missing loan dimensions and a negative balance in any one control account cannot disappear through assessment filtering. Calculated zero ECL needs the existing actual dated quantitative proof; no manufactured journal or manual certification is introduced.

## Snapshot and authority

Only trusted backend callers may execute raw or filtered inventories and proof helpers. Every inventory retains the established six-column signature including nullable internal `account_id`; the existing repository must authorize private Treasury accounts before returning source details. Generic close errors disclose no source identifiers or amounts. Lending-only and assessment rows retain their existing accounting authorization.

Close mutations require READ COMMITTED. Preserve the established legacy source lock prefix, then lock the extra cutoff sources, current application/receipt proof inputs and immutable preparation/posting evidence in fixed order before reading the filtered inventory. Locks are held to transaction end. A writer that commits while a closer waits must be visible in the later volatile check. Existing BEFORE and deferred period/preparation guards keep their authority; no operational source insert is rejected solely because an older period has closed. A late source instead restores the applicable live blockers and keeps historical confirmations intact.

The filtered display may use a repeatable-read reporting snapshot; it does not acquire mutation locks or confer posting authority. Comprehensive source coverage remains false, with the same six source-family categories, because elapsed EIR, historical measurement, additional application families and other unsupported operational states still require adapters.

## Verification plan

The first ten real PostgreSQL cases exercise protected application and dated-assessment fixtures, rather than fabricated audit flags. They cover the absent raw-application inventory, exact application discharge, receipt correction and prior-source change, reversed and broken-link applications, exact assessment discharge, retained stale confirmation, and independent negative/unallocated controls. Parent runs the serialized disposable PostgreSQL window and captures RED before implementation; no production data or external calls are involved.

Add a successful private-assert/period-freeze cycle with legitimate protected tax evidence, idempotent migration replay, private-role revocations and a two-session proof-source race before claiming composition complete. Existing 0143 has 34 passing PostgreSQL cases; 0148 has 33 passing SQL/repository/API/precision checks. Those earlier counts are regression context, not a substitute for 0149 verification.
