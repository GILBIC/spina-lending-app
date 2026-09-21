# Web collection and remittance review

Employee remittance notifications open a fresh, recipient-scoped itemized review. The screen shows each payment, receipt, collection date, covered dates and any Refund Due cash outflows. Acceptance requires separate acknowledgments for reviewing the list and physically receiving and counting the cash. The existing receipt API remains the authority for transferring custody.

Collector payment and remittance submissions share one in-flight guard. Disconnecting locks both controls immediately; reconnecting requires Refresh to reload authoritative state. A lost response can mean the request was already saved. Refresh and inspect the receipt, balance and remittance history before another attempt. The portal does not queue offline payments or automatically replay an uncertain request.

Acceptance errors with an uncertain result require Refresh. Closing a review clears both acknowledgments. Workspace replacement and logout dispose handlers and prevent late responses from repopulating the old workspace. The service-worker shell advances to v11 and includes both new modules.

This change does not modify APIs, schema, loan calculations, cash-custody rules or General Ledger posting. Local synthetic workflow evidence is separate from physical cash confirmation, hosted identity verification and device acceptance.
