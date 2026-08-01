# Gilbic Collector Route API

## Endpoint

```text
GET /api/mobile/v1/collector/routes/today
```

Canonical alias:

```text
GET /api/v1/collector/routes/today
```

Required headers:

```text
Authorization: Bearer <Supabase access token>
X-Device-Id: <Gilbic installation ID>
```

The shared device guard validates the bearer session, active Gilbic account,
active registered installation, and the `route.view` permission before route
data is loaded.

## Server-side route ownership

`lending.collector_area_assignments` is authoritative for the areas assigned to
a collector. The phone cannot supply or expand its own area list. The route
repository joins only active assigned areas to active clients, active loans, and
active loan types.

The route date is calculated using Philippine time (UTC+08:00), not the server's
local timezone.

## Loan collection state

`lending.loan_collection_state` stores the current server-authoritative values
needed by the read-only route:

- remaining balance
- pass count
- last payment date
- advance coverage date
- collector note

The migration initializes missing state rows with the loan principal so newly
created, unpaid loans have a safe initial balance. Before legacy SPINA loans are
made visible in Gilbic, their state rows must be reconciled from the desktop
source of truth. Mobile never recalculates official balances.

The next collection-integration milestone must update this state in the same
PostgreSQL transaction as the accepted payment, ADV, or PASS event.

## Response shape

```json
{
  "success": true,
  "data": {
    "route_date": "2026-08-01",
    "collector_name": "Collector One",
    "areas": ["Cardona"],
    "expected_total": "400.00",
    "entries": [
      {
        "route_entry_id": "loan-uuid",
        "client_id": "client-uuid",
        "loan_id": "loan-uuid",
        "client_name": "Ana Client",
        "area": "Cardona",
        "loan_type": "Regular",
        "daily_amount": "200.00",
        "remaining_balance": "4800.00",
        "pass_count": 1,
        "last_payment_date": "2026-07-31",
        "advance_until": null,
        "status": "Pass",
        "note": "Call before visiting"
      }
    ]
  }
}
```

Currency values are returned as exact decimal strings. Flutter's existing route
parser accepts numeric strings without converting server calculations into
mobile business rules.
