# After the Collector Entry Form

Do not enable automatic offline payment synchronization immediately.

The next implementation should add an encrypted outbox with these properties:

1. Store the exact confirmed request payload, idempotency key, device sequence,
   route revision, and creation time.
2. Encrypt the outbox independently from the read-only route snapshot.
3. Never change a queued payload during retry.
4. Require a visible manual retry action before any background worker exists.
5. Stop and require route refresh on stale-route or changed-loan conflicts.
6. Preserve accepted and duplicate responses until the collector acknowledges
   the receipt.
7. Prevent sign-out from silently deleting unresolved collection entries.
8. Keep 7x7 disabled until the dedicated allocator is implemented and tested.
