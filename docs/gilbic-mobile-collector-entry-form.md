# Gilbic Collector Entry Form

## Purpose

Enable the first collector-facing mobile write flow only after the FastAPI and
PostgreSQL collection boundary became atomic, idempotent, device-aware, and
server-authoritative.

## Supported online entries

- Payment
- ADV with coverage start and end dates
- PASS

The collector confirms each entry before it is sent. A successful or duplicate
response displays the official receipt number and balance returned by FastAPI.
The route is refreshed after the collector finishes the successful entry.

## Safety gates

The entry button remains disabled when:

- the route is an encrypted offline copy
- the account lacks `collection.create`
- the loan is 7x7
- FastAPI marks the loan unavailable for mobile collection
- the route revision or loan identity is missing

Unsupported clients remain visible on the route with a plain-language reason.

## Retry behavior

The UI creates the draft only after local validation and confirmation. The draft
contains one UUID idempotency key and one persistent device sequence. If the
request has an uncertain network result, **Retry same entry** sends the exact
same draft again. Editing the entry discards the uncertain draft so the next
submission receives a new transaction identity.

The app never retries automatically and does not save collection drafts into an
offline outbox in this milestone.

## 7x7 boundary

Payment, ADV, and PASS are all blocked for 7x7 loans in the mobile UI. FastAPI
also rejects unsupported allocation modes. Mobile 7x7 collection must not be
enabled until its dedicated allocator is implemented, reconciled against SPINA,
and covered by allocation and balance tests.

## Validation

The Flutter suite covers:

- persistent device-sequence increments
- uncertain network retry using the same idempotency key and sequence
- duplicate success receipt and official balance display
- direct 7x7 form blocking
- offline route collection blocking
- ready online route collection enabling
- absence of an automatic retry or pending offline outbox
