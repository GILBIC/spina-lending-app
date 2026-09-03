import 'package:flutter/material.dart';
import 'package:gilbic_mobile/src/core/auth/user_session.dart';
import 'package:gilbic_mobile/src/core/device/device_identity.dart';
import 'package:gilbic_mobile/src/core/network/spina_api.dart';
import 'package:gilbic_mobile/src/core/renewals/collector_renewal_workflow.dart';
import 'package:gilbic_mobile/src/core/renewals/collector_renewal_workflow_repository.dart';
import 'package:gilbic_mobile/src/theme/spina_theme.dart';

/// Focused destination for a Collector cash-release alert.
///
/// This page intentionally exposes only the exact Management release that needs
/// physical receipt confirmation. The full renewal workflow remains available
/// from Renewal Requests.
class CollectorRenewalCashReleasePage extends StatefulWidget {
  const CollectorRenewalCashReleasePage({
    required this.session,
    required this.deviceIdentityProvider,
    required this.request,
    this.repository,
    super.key,
  });

  final UserSession session;
  final DeviceIdentityProvider deviceIdentityProvider;
  final CollectorRenewalRequest request;
  final CollectorRenewalWorkflowRepository? repository;

  @override
  State<CollectorRenewalCashReleasePage> createState() =>
      _CollectorRenewalCashReleasePageState();
}

class _CollectorRenewalCashReleasePageState
    extends State<CollectorRenewalCashReleasePage> {
  late final CollectorRenewalWorkflowRepository _repository;
  bool _busy = false;

  @override
  void initState() {
    super.initState();
    _repository =
        widget.repository ?? SpinaCollectorRenewalWorkflowRepository();
  }

  Future<void> _confirmReceived() async {
    if (_busy || !widget.request.canConfirmCashReceived) return;
    final confirmed = await showDialog<bool>(
          context: context,
          builder: (context) => AlertDialog(
            title: const Text('Confirm cash received?'),
            content: Text(
              'Confirm only after you physically receive ${_money(widget.request.netReleaseAmount ?? 0)} from Management for ${widget.request.clientName}.',
            ),
            actions: [
              TextButton(
                onPressed: () => Navigator.pop(context, false),
                child: const Text('Cancel'),
              ),
              FilledButton(
                key: const Key('cash-release-confirm-received-dialog'),
                onPressed: () => Navigator.pop(context, true),
                child: const Text('Confirm Received'),
              ),
            ],
          ),
        ) ??
        false;
    if (!confirmed || !mounted) return;

    setState(() => _busy = true);
    try {
      final identity = await widget.deviceIdentityProvider.load();
      await _repository.confirmCashReceived(
        widget.session,
        deviceId: identity.installationId,
        requestId: widget.request.requestId,
      );
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('Cash custody transferred to you.')),
      );
      Navigator.of(context).pop(true);
    } on SpinaApiException catch (error) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text(error.message)),
        );
      }
    } on Object {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(content: Text('Cash receipt could not be confirmed.')),
        );
      }
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    final request = widget.request;
    return Scaffold(
      appBar: AppBar(title: const Text('Cash Release')),
      body: ListView(
        padding: const EdgeInsets.all(16),
        children: [
          Card(
            color: SpinaTheme.brandPinkSoft,
            child: Padding(
              padding: const EdgeInsets.all(16),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  const Text(
                    'Management released cash',
                    style: TextStyle(fontWeight: FontWeight.w900),
                  ),
                  const SizedBox(height: 6),
                  Text(
                    _money(request.netReleaseAmount ?? 0),
                    key: const Key('cash-release-amount'),
                    style: Theme.of(context).textTheme.headlineSmall?.copyWith(
                          color: SpinaTheme.brandPinkDark,
                          fontWeight: FontWeight.w900,
                        ),
                  ),
                  const SizedBox(height: 12),
                  Text(
                    request.clientName,
                    style: Theme.of(context)
                        .textTheme
                        .titleMedium
                        ?.copyWith(fontWeight: FontWeight.w900),
                  ),
                  Text('${request.clientCode} • ${request.area}'),
                  Text('${request.loanTypeName} • ${request.loanNumber}'),
                ],
              ),
            ),
          ),
          const SizedBox(height: 12),
          const Text(
            'Confirm only when the physical cash is already in your possession. This confirmation transfers cash custody from Management to you.',
          ),
          const SizedBox(height: 18),
          FilledButton.icon(
            key: const Key('cash-release-confirm-received'),
            onPressed:
                request.canConfirmCashReceived && !_busy ? _confirmReceived : null,
            icon: _busy
                ? const SizedBox(
                    width: 18,
                    height: 18,
                    child: CircularProgressIndicator(strokeWidth: 2),
                  )
                : const Icon(Icons.payments_outlined),
            label: const Text('Confirm Cash Received'),
          ),
        ],
      ),
    );
  }
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
