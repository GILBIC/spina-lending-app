import 'package:flutter/material.dart';
import 'package:gilbic_mobile/src/core/auth/user_session.dart';
import 'package:gilbic_mobile/src/core/device/device_identity.dart';
import 'package:gilbic_mobile/src/core/network/spina_api.dart';
import 'package:gilbic_mobile/src/core/renewals/collector_renewal_workflow.dart';
import 'package:gilbic_mobile/src/core/renewals/collector_renewal_workflow_repository.dart';
import 'package:gilbic_mobile/src/features/collector/collector_renewal_cash_release_page.dart';
import 'package:gilbic_mobile/src/theme/spina_theme.dart';

/// Focused queue for renewal cash that Management has released but the
/// Collector has not yet physically received.
class CollectorCashToReceivePage extends StatefulWidget {
  const CollectorCashToReceivePage({
    required this.session,
    required this.deviceIdentityProvider,
    this.repository,
    super.key,
  });

  final UserSession session;
  final DeviceIdentityProvider deviceIdentityProvider;
  final CollectorRenewalWorkflowRepository? repository;

  @override
  State<CollectorCashToReceivePage> createState() =>
      _CollectorCashToReceivePageState();
}

class _CollectorCashToReceivePageState extends State<CollectorCashToReceivePage> {
  late final CollectorRenewalWorkflowRepository _repository;
  List<CollectorRenewalRequest> _requests = const <CollectorRenewalRequest>[];
  String? _error;
  bool _loading = true;

  @override
  void initState() {
    super.initState();
    _repository =
        widget.repository ?? SpinaCollectorRenewalWorkflowRepository();
    _load();
  }

  Future<void> _load() async {
    if (!mounted) return;
    setState(() {
      _loading = true;
      _error = null;
    });
    try {
      final identity = await widget.deviceIdentityProvider.load();
      final requests = await _repository.list(
        widget.session,
        deviceId: identity.installationId,
      );
      if (!mounted) return;
      setState(() {
        _requests = requests
            .where((request) => request.canConfirmCashReceived)
            .toList(growable: false);
      });
    } on SpinaApiException catch (error) {
      if (mounted) setState(() => _error = error.message);
    } on Object {
      if (mounted) {
        setState(() => _error = 'Cash releases could not be loaded.');
      }
    } finally {
      if (mounted) setState(() => _loading = false);
    }
  }

  Future<void> _openRelease(CollectorRenewalRequest request) async {
    await Navigator.of(context).push<void>(
      MaterialPageRoute<void>(
        builder: (_) => CollectorRenewalCashReleasePage(
          session: widget.session,
          deviceIdentityProvider: widget.deviceIdentityProvider,
          request: request,
        ),
      ),
    );
    await _load();
  }

  @override
  Widget build(BuildContext context) {
    final total = _requests.fold<double>(
      0,
      (sum, request) => sum + (request.netReleaseAmount ?? 0),
    );

    return Scaffold(
      appBar: AppBar(
        title: const Text('Cash to Receive'),
        actions: [
          IconButton(
            tooltip: 'Refresh cash releases',
            onPressed: _loading ? null : _load,
            icon: const Icon(Icons.refresh_rounded),
          ),
        ],
      ),
      body: RefreshIndicator(
        onRefresh: _load,
        child: ListView(
          physics: const AlwaysScrollableScrollPhysics(),
          padding: const EdgeInsets.all(12),
          children: [
            Container(
              key: const Key('collector-cash-to-receive-summary'),
              padding: const EdgeInsets.all(14),
              decoration: BoxDecoration(
                color: SpinaTheme.brandPinkSoft,
                borderRadius: BorderRadius.circular(16),
              ),
              child: Row(
                children: [
                  const Icon(
                    Icons.payments_outlined,
                    color: SpinaTheme.brandPinkDark,
                  ),
                  const SizedBox(width: 10),
                  Expanded(
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        const Text(
                          'Management releases waiting',
                          style: TextStyle(fontWeight: FontWeight.w900),
                        ),
                        Text(
                          '${_requests.length} ${_requests.length == 1 ? 'client' : 'clients'} • ${_money(total)}',
                        ),
                      ],
                    ),
                  ),
                ],
              ),
            ),
            const SizedBox(height: 10),
            if (_loading && _requests.isEmpty)
              const Padding(
                padding: EdgeInsets.all(36),
                child: Center(child: CircularProgressIndicator()),
              )
            else if (_error != null && _requests.isEmpty)
              _MessageCard(
                icon: Icons.error_outline,
                message: _error!,
                action: TextButton(onPressed: _load, child: const Text('Retry')),
              )
            else if (_requests.isEmpty)
              const _MessageCard(
                icon: Icons.check_circle_outline,
                message: 'No Management cash release is waiting for your receipt.',
              )
            else
              for (final request in _requests) ...[
                Card(
                  key: Key('cash-to-receive-${request.requestId}'),
                  child: Padding(
                    padding: const EdgeInsets.all(14),
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Row(
                          crossAxisAlignment: CrossAxisAlignment.start,
                          children: [
                            Expanded(
                              child: Column(
                                crossAxisAlignment: CrossAxisAlignment.start,
                                children: [
                                  Text(
                                    request.clientName,
                                    style: const TextStyle(
                                      fontWeight: FontWeight.w900,
                                    ),
                                  ),
                                  Text(
                                    _clientMeta(request),
                                    style: Theme.of(context).textTheme.bodySmall,
                                  ),
                                ],
                              ),
                            ),
                            const SizedBox(width: 8),
                            Text(
                              _money(request.netReleaseAmount ?? 0),
                              style: Theme.of(context)
                                  .textTheme
                                  .titleMedium
                                  ?.copyWith(
                                    color: SpinaTheme.brandPinkDark,
                                    fontWeight: FontWeight.w900,
                                  ),
                            ),
                          ],
                        ),
                        const SizedBox(height: 8),
                        Text(
                          '${request.isSevenBySeven ? '7x7' : request.loanTypeName} • ${request.loanNumber}',
                          style: Theme.of(context).textTheme.bodySmall,
                        ),
                        const SizedBox(height: 10),
                        SizedBox(
                          width: double.infinity,
                          child: FilledButton.icon(
                            key: Key(
                              'cash-to-receive-confirm-${request.requestId}',
                            ),
                            onPressed: () => _openRelease(request),
                            icon: const Icon(Icons.check_circle_outline),
                            label: const Text('Confirm Cash Received'),
                          ),
                        ),
                      ],
                    ),
                  ),
                ),
                const SizedBox(height: 8),
              ],
          ],
        ),
      ),
    );
  }
}

class _MessageCard extends StatelessWidget {
  const _MessageCard({
    required this.icon,
    required this.message,
    this.action,
  });

  final IconData icon;
  final String message;
  final Widget? action;

  @override
  Widget build(BuildContext context) {
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(18),
        child: Column(
          children: [
            Icon(icon, color: SpinaTheme.brandPinkDark),
            const SizedBox(height: 8),
            Text(message, textAlign: TextAlign.center),
            if (action != null) ...[
              const SizedBox(height: 6),
              action!,
            ],
          ],
        ),
      ),
    );
  }
}

String _clientMeta(CollectorRenewalRequest request) {
  return <String>[
    if (request.clientCode.trim().isNotEmpty) request.clientCode.trim(),
    if (request.area.trim().isNotEmpty) request.area.trim(),
  ].join(' • ');
}

String _money(double value) {
  final fixed = value.toStringAsFixed(2).split('.');
  return '₱${_groupDigits(fixed.first)}.${fixed.last}';
}

String _groupDigits(String digits) {
  final buffer = StringBuffer();
  for (var index = 0; index < digits.length; index += 1) {
    if (index > 0 && (digits.length - index) % 3 == 0) {
      buffer.write(',');
    }
    buffer.write(digits[index]);
  }
  return buffer.toString();
}
