import 'dart:typed_data';

import 'package:flutter/material.dart';
import 'package:gilbic_mobile/src/core/auth/user_session.dart';
import 'package:gilbic_mobile/src/core/device/device_identity.dart';
import 'package:gilbic_mobile/src/core/network/spina_api.dart';
import 'package:gilbic_mobile/src/core/renewals/collector_renewal_workflow.dart';
import 'package:gilbic_mobile/src/core/renewals/collector_renewal_workflow_repository.dart';
import 'package:gilbic_mobile/src/theme/spina_theme.dart';
import 'package:image_picker/image_picker.dart';

/// Focused queue for renewal cash already under the Collector's custody.
///
/// The primary queue contains only clients whose exact locked release still
/// needs to be handed over. A just-completed handover may remain temporarily
/// when its required photo is still missing so the field workflow can be
/// finished without sending the Collector through the full renewal list.
class CollectorCashToClientPage extends StatefulWidget {
  const CollectorCashToClientPage({
    required this.session,
    required this.deviceIdentityProvider,
    this.repository,
    this.imagePicker,
    super.key,
  });

  final UserSession session;
  final DeviceIdentityProvider deviceIdentityProvider;
  final CollectorRenewalWorkflowRepository? repository;
  final ImagePicker? imagePicker;

  @override
  State<CollectorCashToClientPage> createState() =>
      _CollectorCashToClientPageState();
}

class _CollectorCashToClientPageState extends State<CollectorCashToClientPage> {
  late final CollectorRenewalWorkflowRepository _repository;
  late final ImagePicker _imagePicker;
  List<CollectorRenewalRequest> _requests = const <CollectorRenewalRequest>[];
  String? _deviceId;
  String? _error;
  bool _loading = true;
  final Set<String> _busy = <String>{};

  @override
  void initState() {
    super.initState();
    _repository =
        widget.repository ?? SpinaCollectorRenewalWorkflowRepository();
    _imagePicker = widget.imagePicker ?? ImagePicker();
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
        _deviceId = identity.installationId;
        _requests = requests.where(_belongsInHandoverQueue).toList(growable: false);
      });
    } on SpinaApiException catch (error) {
      if (mounted) setState(() => _error = error.message);
    } on Object {
      if (mounted) {
        setState(() => _error = 'Client cash handovers could not be loaded.');
      }
    } finally {
      if (mounted) setState(() => _loading = false);
    }
  }

  bool _belongsInHandoverQueue(CollectorRenewalRequest request) {
    return request.canConfirmCashGiven ||
        (request.cashGivenToClientAt != null && request.needsPhoto);
  }

  Future<void> _confirmCashGiven(CollectorRenewalRequest request) async {
    final confirmed = await showDialog<bool>(
          context: context,
          builder: (context) => AlertDialog(
            title: const Text('Confirm cash given to client?'),
            content: Text(
              'Confirm only after you physically hand the exact locked '
              '${_money(request.netReleaseAmount ?? 0)} to ${request.clientName}. '
              'The client must still confirm independently.',
            ),
            actions: [
              TextButton(
                onPressed: () => Navigator.pop(context, false),
                child: const Text('Cancel'),
              ),
              FilledButton(
                onPressed: () => Navigator.pop(context, true),
                child: const Text('Cash Given'),
              ),
            ],
          ),
        ) ??
        false;
    if (!confirmed) return;

    final deviceId = _deviceId;
    if (deviceId == null || _busy.contains(request.requestId)) return;
    setState(() => _busy.add(request.requestId));
    try {
      final updated = await _repository.confirmCashGiven(
        widget.session,
        deviceId: deviceId,
        requestId: request.requestId,
      );
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(
          content: Text(
            'Cash handover recorded. Client confirmation is still required.',
          ),
        ),
      );
      setState(() {
        _requests = [
          for (final item in _requests)
            if (item.requestId != request.requestId)
              item
            else if (_belongsInHandoverQueue(updated))
              updated,
        ];
      });
    } on SpinaApiException catch (error) {
      if (mounted) _message(error.message);
    } on Object {
      if (mounted) _message('The cash handover could not be recorded.');
    } finally {
      if (mounted) setState(() => _busy.remove(request.requestId));
    }
  }

  Future<void> _captureProof(CollectorRenewalRequest request) async {
    final deviceId = _deviceId;
    if (deviceId == null || _busy.contains(request.requestId)) return;
    final source = await showModalBottomSheet<ImageSource>(
      context: context,
      builder: (context) => SafeArea(
        child: Wrap(
          children: [
            ListTile(
              leading: const Icon(Icons.camera_alt_outlined),
              title: const Text('Take handover photo'),
              onTap: () => Navigator.pop(context, ImageSource.camera),
            ),
            ListTile(
              leading: const Icon(Icons.photo_library_outlined),
              title: const Text('Choose from gallery'),
              onTap: () => Navigator.pop(context, ImageSource.gallery),
            ),
          ],
        ),
      ),
    );
    if (source == null) return;

    try {
      final image = await _imagePicker.pickImage(
        source: source,
        imageQuality: 75,
        maxWidth: 1600,
        maxHeight: 1600,
        requestFullMetadata: false,
      );
      if (image == null || !mounted) return;
      final bytes = await image.readAsBytes();
      final draft = RenewalHandoverPhotoDraft.fromBytes(
        filename: image.name,
        bytes: Uint8List.fromList(bytes),
        suggestedContentType: image.mimeType,
      );
      final validation = draft.validate();
      if (validation != null) {
        _message(validation);
        return;
      }

      setState(() => _busy.add(request.requestId));
      await _repository.uploadHandoverPhoto(
        widget.session,
        deviceId: deviceId,
        requestId: request.requestId,
        draft: draft,
      );
      if (!mounted) return;
      _message('Handover proof submitted for Management review.');
      await _load();
    } on SpinaApiException catch (error) {
      if (mounted) _message(error.message);
    } on Object {
      if (mounted) _message('The handover photo could not be saved.');
    } finally {
      if (mounted) setState(() => _busy.remove(request.requestId));
    }
  }

  void _message(String value) {
    ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text(value)));
  }

  @override
  Widget build(BuildContext context) {
    final waitingCount =
        _requests.where((request) => request.canConfirmCashGiven).length;

    return Scaffold(
      appBar: AppBar(
        title: const Text('Give to Client'),
        actions: [
          IconButton(
            tooltip: 'Refresh client handovers',
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
              key: const Key('collector-cash-to-client-summary'),
              padding: const EdgeInsets.all(14),
              decoration: BoxDecoration(
                color: SpinaTheme.brandPinkSoft,
                borderRadius: BorderRadius.circular(16),
              ),
              child: Row(
                children: [
                  const Icon(
                    Icons.handshake_outlined,
                    color: SpinaTheme.brandPinkDark,
                  ),
                  const SizedBox(width: 10),
                  Expanded(
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        const Text(
                          'Client cash handovers',
                          style: TextStyle(fontWeight: FontWeight.w900),
                        ),
                        Text(
                          '$waitingCount ${waitingCount == 1 ? 'client' : 'clients'} waiting for cash handover',
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
                message: 'No client cash handover needs your attention.',
              )
            else
              for (final request in _requests) ...[
                _ClientHandoverCard(
                  request: request,
                  busy: _busy.contains(request.requestId),
                  onCashGiven: () => _confirmCashGiven(request),
                  onProof: () => _captureProof(request),
                ),
                const SizedBox(height: 8),
              ],
          ],
        ),
      ),
    );
  }
}

class _ClientHandoverCard extends StatelessWidget {
  const _ClientHandoverCard({
    required this.request,
    required this.busy,
    required this.onCashGiven,
    required this.onProof,
  });

  final CollectorRenewalRequest request;
  final bool busy;
  final VoidCallback onCashGiven;
  final VoidCallback onProof;

  @override
  Widget build(BuildContext context) {
    final meta = <String>[
      if (request.clientCode.trim().isNotEmpty) request.clientCode.trim(),
      if (request.area.trim().isNotEmpty) request.area.trim(),
    ].join(' • ');

    return Card(
      key: Key('cash-to-client-${request.requestId}'),
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
                        style: Theme.of(context)
                            .textTheme
                            .titleMedium
                            ?.copyWith(fontWeight: FontWeight.w900),
                      ),
                      if (meta.isNotEmpty)
                        Text(meta, style: Theme.of(context).textTheme.bodySmall),
                    ],
                  ),
                ),
                const SizedBox(width: 8),
                Text(
                  _money(request.netReleaseAmount ?? 0),
                  key: Key('cash-to-client-amount-${request.requestId}'),
                  style: Theme.of(context).textTheme.titleMedium?.copyWith(
                        color: SpinaTheme.brandPinkDark,
                        fontWeight: FontWeight.w900,
                      ),
                ),
              ],
            ),
            const SizedBox(height: 6),
            Text(
              '${request.isSevenBySeven ? '7x7' : request.loanTypeName} • ${request.loanNumber}',
              style: Theme.of(context).textTheme.bodySmall,
            ),
            const Divider(height: 20),
            if (request.canConfirmCashGiven) ...[
              const Text(
                'Cash is under your responsibility. Give only the exact locked amount to this client.',
              ),
              const SizedBox(height: 10),
              SizedBox(
                width: double.infinity,
                child: FilledButton.icon(
                  key: Key('cash-to-client-confirm-${request.requestId}'),
                  onPressed: busy ? null : onCashGiven,
                  icon: const Icon(Icons.handshake_outlined),
                  label: const Text('Confirm Cash Given'),
                ),
              ),
            ] else if (request.needsPhoto) ...[
              const Text(
                'Cash handover is recorded. Submit the required handover photo to complete your field evidence.',
              ),
              const SizedBox(height: 10),
              SizedBox(
                width: double.infinity,
                child: OutlinedButton.icon(
                  key: Key('cash-to-client-proof-${request.requestId}'),
                  onPressed: busy ? null : onProof,
                  icon: const Icon(Icons.add_a_photo_outlined),
                  label: Text(
                    request.handoverProofStatus == 'correction_required'
                        ? 'Submit New Handover Photo'
                        : 'Submit Handover Photo',
                  ),
                ),
              ),
            ],
            if (busy) ...[
              const SizedBox(height: 8),
              const LinearProgressIndicator(),
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
        child: Row(
          children: [
            Icon(icon),
            const SizedBox(width: 10),
            Expanded(child: Text(message)),
            if (action != null) action!,
          ],
        ),
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
