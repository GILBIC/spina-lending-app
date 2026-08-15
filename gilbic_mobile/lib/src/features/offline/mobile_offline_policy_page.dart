import 'package:flutter/material.dart';
import 'package:gilbic_mobile/src/core/auth/user_session.dart';
import 'package:gilbic_mobile/src/core/offline/mobile_offline_policy.dart';

class MobileOfflinePolicyPage extends StatelessWidget {
  const MobileOfflinePolicyPage({required this.session, super.key});

  final UserSession session;

  @override
  Widget build(BuildContext context) {
    final policy = MobileOfflinePolicy.forRole(session.role);
    return Scaffold(
      key: const Key('offline-policy-page'),
      appBar: AppBar(title: const Text('Offline & sync')),
      body: SafeArea(
        child: ListView(
          padding: const EdgeInsets.all(16),
          children: [
            Card(
              child: Padding(
                padding: const EdgeInsets.all(18),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Row(
                      children: [
                        const Icon(Icons.cloud_off_outlined),
                        const SizedBox(width: 10),
                        Expanded(
                          child: Text(
                            '${policy.role.label} offline policy',
                            style: Theme.of(context).textTheme.titleLarge,
                          ),
                        ),
                      ],
                    ),
                    const SizedBox(height: 12),
                    Text(policy.summary),
                  ],
                ),
              ),
            ),
            const SizedBox(height: 10),
            _PolicySection(
              title: 'Available without a live connection',
              icon: Icons.visibility_outlined,
              items: policy.availableOffline,
            ),
            const SizedBox(height: 10),
            _PolicySection(
              title: 'Blocked until you reconnect',
              icon: Icons.lock_outline,
              items: policy.blockedOffline,
            ),
            const SizedBox(height: 10),
            Card(
              key: const Key('offline-write-safety'),
              child: Padding(
                padding: const EdgeInsets.all(18),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      'Write safety',
                      style: Theme.of(context).textTheme.titleMedium,
                    ),
                    const SizedBox(height: 10),
                    const _SafetyRow(
                      label: 'Financial writes while offline',
                      value: 'Blocked',
                    ),
                    const _SafetyRow(
                      label: 'Silent offline write queue',
                      value: 'Not allowed',
                    ),
                    const _SafetyRow(
                      label: 'Automatic financial replay',
                      value: 'Not allowed',
                    ),
                    _SafetyRow(
                      label: 'Persistent offline business data',
                      value: policy.hasPersistentOfflineData
                          ? 'Collector route snapshot only'
                          : 'None',
                    ),
                    _SafetyRow(
                      label: 'Manual idempotent retry',
                      value: policy.explicitIdempotentRetryAvailable
                          ? 'Collector submission only after explicit user retry'
                          : 'No offline write retry workflow',
                    ),
                  ],
                ),
              ),
            ),
            if (policy.explicitIdempotentRetryAvailable) ...[
              const SizedBox(height: 10),
              const Card(
                key: Key('collector-retry-safety'),
                child: Padding(
                  padding: EdgeInsets.all(18),
                  child: Text(
                    'If a Collector explicitly submits while online and the connection fails before the result is known, Gilbic does not replay the write by itself. The Collector must choose Retry same entry; that explicit retry reuses the original idempotency key and device sequence so the server can return the original result instead of creating a duplicate.',
                  ),
                ),
              ),
            ],
            const SizedBox(height: 10),
            Text(
              'FastAPI and PostgreSQL remain authoritative. Local UI state and cached presentation data never replace server authorization, balances, receipts, approvals, custody, or accounting records.',
              style: Theme.of(context).textTheme.bodySmall,
              textAlign: TextAlign.center,
            ),
          ],
        ),
      ),
    );
  }
}

class _PolicySection extends StatelessWidget {
  const _PolicySection({
    required this.title,
    required this.icon,
    required this.items,
  });

  final String title;
  final IconData icon;
  final List<String> items;

  @override
  Widget build(BuildContext context) {
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(18),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              children: [
                Icon(icon, size: 20),
                const SizedBox(width: 8),
                Expanded(
                  child: Text(
                    title,
                    style: Theme.of(context).textTheme.titleMedium,
                  ),
                ),
              ],
            ),
            const SizedBox(height: 8),
            for (final item in items)
              Padding(
                padding: const EdgeInsets.only(top: 6),
                child: Row(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    const Text('• '),
                    Expanded(child: Text(item)),
                  ],
                ),
              ),
          ],
        ),
      ),
    );
  }
}

class _SafetyRow extends StatelessWidget {
  const _SafetyRow({required this.label, required this.value});

  final String label;
  final String value;

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 4),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          SizedBox(
            width: 170,
            child: Text(
              label,
              style: Theme.of(context).textTheme.bodyMedium?.copyWith(
                    fontWeight: FontWeight.w600,
                  ),
            ),
          ),
          Expanded(child: Text(value)),
        ],
      ),
    );
  }
}
