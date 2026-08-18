import 'package:flutter/material.dart';
import 'package:gilbic_mobile/src/core/auth/user_session.dart';
import 'package:gilbic_mobile/src/core/collector/delegated_area_access.dart';
import 'package:gilbic_mobile/src/core/collector/delegated_area_repository.dart';
import 'package:gilbic_mobile/src/core/device/device_identity.dart';
import 'package:gilbic_mobile/src/core/network/spina_api.dart';
import 'package:gilbic_mobile/src/core/time/spina_business_time.dart';

class DelegatedAreaAccessPage extends StatefulWidget {
  const DelegatedAreaAccessPage({
    required this.session,
    required this.deviceIdentityProvider,
    this.repository,
    super.key,
  });

  final UserSession session;
  final DeviceIdentityProvider deviceIdentityProvider;
  final DelegatedAreaRepository? repository;

  @override
  State<DelegatedAreaAccessPage> createState() =>
      _DelegatedAreaAccessPageState();
}

class _DelegatedAreaAccessPageState extends State<DelegatedAreaAccessPage> {
  late final DelegatedAreaRepository _repository;

  List<DelegatedAreaScope> _availableScopes = const <DelegatedAreaScope>[];
  List<DelegatedAreaRequest> _incoming = const <DelegatedAreaRequest>[];
  List<DelegatedAreaRequest> _outgoing = const <DelegatedAreaRequest>[];
  List<DelegatedAreaGrant> _grants = const <DelegatedAreaGrant>[];
  final Set<String> _busyIds = <String>{};
  bool _loading = true;
  String? _errorMessage;

  bool get _canRequest => widget.session.hasPermission('delegated_area.request');
  bool get _canGrant => widget.session.hasPermission('delegated_area.grant');
  bool get _canView => widget.session.hasPermission('delegated_area.view');

  @override
  void initState() {
    super.initState();
    _repository = widget.repository ??
        SpinaDelegatedAreaRepository(
          deviceIdentityProvider: widget.deviceIdentityProvider,
        );
    _reload();
  }

  Future<void> _reload() async {
    setState(() {
      _loading = true;
      _errorMessage = null;
    });
    try {
      final available = _canRequest
          ? await _repository.availableScopes(widget.session)
          : const <DelegatedAreaScope>[];
      final outgoing = _canView
          ? await _repository.outgoingRequests(widget.session)
          : const <DelegatedAreaRequest>[];
      final incoming = _canGrant
          ? await _repository.incomingRequests(widget.session)
          : const <DelegatedAreaRequest>[];
      final grants = _canView
          ? await _repository.activeGrants(widget.session)
          : const <DelegatedAreaGrant>[];
      if (!mounted) {
        return;
      }
      setState(() {
        _availableScopes = available;
        _outgoing = outgoing;
        _incoming = incoming;
        _grants = grants;
      });
    } on SpinaApiException catch (error) {
      if (mounted) {
        setState(() => _errorMessage = error.message);
      }
    } on Object {
      if (mounted) {
        setState(() {
          _errorMessage = 'Temporary area access could not be loaded.';
        });
      }
    } finally {
      if (mounted) {
        setState(() => _loading = false);
      }
    }
  }

  Future<void> _requestAccess() async {
    if (!_canRequest || _availableScopes.isEmpty) {
      return;
    }
    final owners = <String, _OwnerOption>{};
    for (final scope in _availableScopes) {
      final option = owners.putIfAbsent(
        scope.ownerUserId,
        () => _OwnerOption(
          userId: scope.ownerUserId,
          name: scope.ownerName,
          areas: <String>[],
        ),
      );
      if (!option.areas.contains(scope.areaPath)) {
        option.areas.add(scope.areaPath);
      }
    }
    final orderedOwners = owners.values.toList(growable: false)
      ..sort((left, right) => left.name.toLowerCase().compareTo(right.name.toLowerCase()));
    if (!mounted || orderedOwners.isEmpty) {
      return;
    }

    var reasonText = '';
    var selectedOwnerId = orderedOwners.first.userId;
    final draft = await showDialog<_AccessRequestDraft>(
      context: context,
      builder: (context) => StatefulBuilder(
        builder: (context, setDialogState) => AlertDialog(
          title: const Text('Request temporary area access'),
          content: SingleChildScrollView(
            child: Column(
              mainAxisSize: MainAxisSize.min,
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                const Text(
                  'Each assigned Collector decides only for their own areas. '
                  'Access requested here lasts 24 hours if approved.',
                ),
                const SizedBox(height: 16),
                DropdownButtonFormField<String>(
                  key: const Key('delegated-owner-select'),
                  initialValue: selectedOwnerId,
                  decoration: const InputDecoration(labelText: 'Assigned collector'),
                  items: orderedOwners
                      .map(
                        (owner) => DropdownMenuItem<String>(
                          value: owner.userId,
                          child: Text(owner.name),
                        ),
                      )
                      .toList(growable: false),
                  onChanged: (value) {
                    if (value != null) {
                      setDialogState(() => selectedOwnerId = value);
                    }
                  },
                ),
                const SizedBox(height: 8),
                Text(
                  _areasForOwner(orderedOwners, selectedOwnerId),
                  style: Theme.of(context).textTheme.bodySmall,
                ),
                const SizedBox(height: 12),
                TextField(
                  key: const Key('delegated-request-reason'),
                  onChanged: (value) => reasonText = value,
                  maxLength: 500,
                  decoration: const InputDecoration(
                    labelText: 'Reason',
                    hintText: 'Example: Help cover today’s collection route',
                  ),
                ),
              ],
            ),
          ),
          actions: [
            TextButton(
              onPressed: () => Navigator.of(context).pop(),
              child: const Text('Cancel'),
            ),
            OutlinedButton(
              key: const Key('request-all-delegated-areas'),
              onPressed: () {
                final reason = reasonText.trim();
                if (reason.isEmpty) {
                  return;
                }
                Navigator.of(context).pop(
                  _AccessRequestDraft(
                    ownerUserId: selectedOwnerId,
                    reason: reason,
                    allOwners: true,
                  ),
                );
              },
              child: const Text('Request All Areas'),
            ),
            FilledButton(
              key: const Key('request-owner-delegated-areas'),
              onPressed: () {
                final reason = reasonText.trim();
                if (reason.isEmpty) {
                  return;
                }
                Navigator.of(context).pop(
                  _AccessRequestDraft(
                    ownerUserId: selectedOwnerId,
                    reason: reason,
                    allOwners: false,
                  ),
                );
              },
              child: const Text('Request This Collector'),
            ),
          ],
        ),
      ),
    );
    if (draft == null || !mounted) {
      return;
    }

    final expiresAt = DateTime.now().toUtc().add(const Duration(hours: 24));
    final targetOwners = draft.allOwners
        ? orderedOwners
        : orderedOwners
            .where((owner) => owner.userId == draft.ownerUserId)
            .toList(growable: false);
    var sent = 0;
    final failures = <String>[];
    for (final owner in targetOwners) {
      try {
        await _repository.createRequest(
          widget.session,
          ownerUserId: owner.userId,
          scopes: const <DelegatedAreaScope>[],
          allOwnerAreas: true,
          reason: draft.reason,
          expiresAt: expiresAt,
        );
        sent += 1;
      } on SpinaApiException catch (error) {
        failures.add('${owner.name}: ${error.message}');
      }
    }
    if (!mounted) {
      return;
    }
    if (sent > 0) {
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(
          content: Text(
            failures.isEmpty
                ? 'Sent $sent temporary access request${sent == 1 ? '' : 's'}.'
                : 'Sent $sent request${sent == 1 ? '' : 's'}; '
                    '${failures.length} could not be sent.',
          ),
        ),
      );
      await _reload();
    } else if (failures.isNotEmpty) {
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text(failures.first)),
      );
    }
  }

  String _areasForOwner(List<_OwnerOption> owners, String ownerUserId) {
    final owner = owners.firstWhere((item) => item.userId == ownerUserId);
    return owner.areas.join(' • ');
  }

  Future<void> _approve(DelegatedAreaRequest request) async {
    final confirmed = await _confirm(
      title: 'Allow temporary access?',
      message: '${request.requesterName} will be able to view and collect only '
          'inside the requested scope until ${formatSpinaBusinessDateTime(request.requestedExpiresAt)}.',
      confirmLabel: 'Allow Access',
    );
    if (confirmed != true) {
      return;
    }
    await _mutate(request.requestId, () async {
      await _repository.approveRequest(widget.session, request.requestId);
    });
  }

  Future<void> _decline(DelegatedAreaRequest request) async {
    final confirmed = await _confirm(
      title: 'Decline request?',
      message: 'This declines access to your area only. It does not affect requests sent to other collectors.',
      confirmLabel: 'Decline',
    );
    if (confirmed != true) {
      return;
    }
    await _mutate(request.requestId, () async {
      await _repository.declineRequest(widget.session, request.requestId);
    });
  }

  Future<void> _cancel(DelegatedAreaRequest request) async {
    final confirmed = await _confirm(
      title: 'Cancel request?',
      message: 'The assigned collector will no longer be able to approve this request.',
      confirmLabel: 'Cancel Request',
    );
    if (confirmed != true) {
      return;
    }
    await _mutate(request.requestId, () async {
      await _repository.cancelRequest(widget.session, request.requestId);
    });
  }

  Future<void> _revoke(DelegatedAreaGrant grant) async {
    var revokeReason = '';
    final reason = await showDialog<String>(
      context: context,
      builder: (context) => AlertDialog(
        title: const Text('Revoke temporary access?'),
        content: TextField(
          key: const Key('delegated-revoke-reason'),
          onChanged: (value) => revokeReason = value,
          maxLength: 500,
          decoration: const InputDecoration(
            labelText: 'Reason',
            hintText: 'Reason for revoking access',
          ),
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.of(context).pop(),
            child: const Text('Keep Access'),
          ),
          FilledButton(
            key: const Key('confirm-delegated-revoke'),
            onPressed: () {
              final value = revokeReason.trim();
              if (value.isNotEmpty) {
                Navigator.of(context).pop(value);
              }
            },
            child: const Text('Revoke'),
          ),
        ],
      ),
    );
    if (reason == null || !mounted) {
      return;
    }
    await _mutate(grant.grantId, () async {
      await _repository.revokeGrant(
        widget.session,
        grant.grantId,
        reason: reason,
      );
    });
  }

  Future<bool?> _confirm({
    required String title,
    required String message,
    required String confirmLabel,
  }) {
    return showDialog<bool>(
      context: context,
      builder: (context) => AlertDialog(
        title: Text(title),
        content: Text(message),
        actions: [
          TextButton(
            onPressed: () => Navigator.of(context).pop(false),
            child: const Text('Back'),
          ),
          FilledButton(
            onPressed: () => Navigator.of(context).pop(true),
            child: Text(confirmLabel),
          ),
        ],
      ),
    );
  }

  Future<void> _mutate(String id, Future<void> Function() action) async {
    setState(() => _busyIds.add(id));
    try {
      await action();
      if (mounted) {
        await _reload();
      }
    } on SpinaApiException catch (error) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text(error.message)),
        );
      }
    } finally {
      if (mounted) {
        setState(() => _busyIds.remove(id));
      }
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('Temporary Area Access'),
        actions: [
          IconButton(
            tooltip: 'Refresh',
            onPressed: _loading ? null : _reload,
            icon: const Icon(Icons.refresh),
          ),
        ],
      ),
      floatingActionButton: _canRequest && _availableScopes.isNotEmpty
          ? FloatingActionButton.extended(
              key: const Key('request-delegated-access'),
              onPressed: _requestAccess,
              icon: const Icon(Icons.add_location_alt_outlined),
              label: const Text('Request Access'),
            )
          : null,
      body: SafeArea(
        child: _loading
            ? const Center(child: CircularProgressIndicator())
            : RefreshIndicator(
                onRefresh: _reload,
                child: ListView(
                  padding: const EdgeInsets.fromLTRB(16, 16, 16, 96),
                  children: [
                    Card(
                      child: Padding(
                        padding: const EdgeInsets.all(16),
                        child: Text(
                          'Temporary access never changes route ownership. Your Daily Route stays limited to your permanent areas. Each assigned Collector can approve or revoke only access to their own area.',
                          style: Theme.of(context).textTheme.bodyMedium,
                        ),
                      ),
                    ),
                    if (_errorMessage != null) ...[
                      const SizedBox(height: 12),
                      Text(
                        _errorMessage!,
                        style: TextStyle(color: Theme.of(context).colorScheme.error),
                      ),
                    ],
                    const SizedBox(height: 16),
                    _sectionTitle(context, 'Approved access'),
                    ..._visitorGrantCards(),
                    if (_visitorGrants.isEmpty)
                      const _EmptyCard('No temporary areas are approved for you right now.'),
                    const SizedBox(height: 20),
                    _sectionTitle(context, 'Requests for my areas'),
                    ..._incoming.map(_incomingCard),
                    if (_incoming.isEmpty)
                      const _EmptyCard('No Collector is waiting for your area approval.'),
                    const SizedBox(height: 20),
                    _sectionTitle(context, 'My requests'),
                    ..._outgoing.map(_outgoingCard),
                    if (_outgoing.isEmpty)
                      const _EmptyCard('You have not requested temporary access yet.'),
                    if (_grantorGrants.isNotEmpty) ...[
                      const SizedBox(height: 20),
                      _sectionTitle(context, 'Access I granted'),
                      ..._grantorGrants.map(_grantorCard),
                    ],
                  ],
                ),
              ),
      ),
    );
  }

  Widget _sectionTitle(BuildContext context, String value) {
    return Padding(
      padding: const EdgeInsets.only(bottom: 8),
      child: Text(value, style: Theme.of(context).textTheme.titleMedium),
    );
  }

  List<DelegatedAreaGrant> get _visitorGrants => _grants
      .where((grant) => grant.visitingCollectorUserId == widget.session.userId)
      .toList(growable: false);

  List<DelegatedAreaGrant> get _grantorGrants => _grants
      .where((grant) => grant.grantorUserId == widget.session.userId)
      .toList(growable: false);

  Iterable<Widget> _visitorGrantCards() => _visitorGrants.map(
        (grant) => Card(
          key: Key('delegated-active-${grant.grantId}'),
          child: ListTile(
            leading: const Icon(Icons.verified_user_outlined),
            title: Text(_scopeText(grant.scopes)),
            subtitle: Text(
              'Approved by ${grant.grantorName}\nUntil ${formatSpinaBusinessDateTime(grant.expiresAt)}',
            ),
            isThreeLine: true,
          ),
        ),
      );

  Widget _incomingCard(DelegatedAreaRequest request) {
    final busy = _busyIds.contains(request.requestId);
    return Card(
      key: Key('delegated-incoming-${request.requestId}'),
      child: Padding(
        padding: const EdgeInsets.all(14),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(request.requesterName, style: Theme.of(context).textTheme.titleSmall),
            const SizedBox(height: 4),
            Text(_scopeText(request.scopes)),
            Text('Reason: ${request.reason}'),
            Text('Until ${formatSpinaBusinessDateTime(request.requestedExpiresAt)}'),
            const SizedBox(height: 10),
            if (request.isPending)
              Row(
                mainAxisAlignment: MainAxisAlignment.end,
                children: [
                  TextButton(
                    key: Key('decline-delegated-${request.requestId}'),
                    onPressed: busy ? null : () => _decline(request),
                    child: const Text('Decline'),
                  ),
                  const SizedBox(width: 8),
                  FilledButton(
                    key: Key('approve-delegated-${request.requestId}'),
                    onPressed: busy ? null : () => _approve(request),
                    child: const Text('Allow Access'),
                  ),
                ],
              )
            else
              Text('Status: ${request.status}'),
          ],
        ),
      ),
    );
  }

  Widget _outgoingCard(DelegatedAreaRequest request) {
    final busy = _busyIds.contains(request.requestId);
    return Card(
      key: Key('delegated-outgoing-${request.requestId}'),
      child: ListTile(
        leading: Icon(request.isPending ? Icons.schedule : Icons.fact_check_outlined),
        title: Text('${request.requestedOwnerName} • ${request.status}'),
        subtitle: Text(
          '${_scopeText(request.scopes)}\nUntil ${formatSpinaBusinessDateTime(request.requestedExpiresAt)}',
        ),
        isThreeLine: true,
        trailing: request.isPending
            ? TextButton(
                key: Key('cancel-delegated-${request.requestId}'),
                onPressed: busy ? null : () => _cancel(request),
                child: const Text('Cancel'),
              )
            : null,
      ),
    );
  }

  Widget _grantorCard(DelegatedAreaGrant grant) {
    final busy = _busyIds.contains(grant.grantId);
    return Card(
      key: Key('delegated-granted-${grant.grantId}'),
      child: ListTile(
        leading: const Icon(Icons.share_location_outlined),
        title: Text(grant.visitingCollectorName),
        subtitle: Text(
          '${_scopeText(grant.scopes)}\nUntil ${formatSpinaBusinessDateTime(grant.expiresAt)}',
        ),
        isThreeLine: true,
        trailing: TextButton(
          key: Key('revoke-delegated-${grant.grantId}'),
          onPressed: busy ? null : () => _revoke(grant),
          child: const Text('Revoke'),
        ),
      ),
    );
  }

  String _scopeText(List<DelegatedAreaScope> scopes) {
    if (scopes.isEmpty) {
      return 'Assigned area scope';
    }
    return scopes
        .map(
          (scope) => scope.includeDescendants
              ? '${scope.areaPath} + sub-areas'
              : scope.areaPath,
        )
        .join(' • ');
  }
}

class _OwnerOption {
  _OwnerOption({
    required this.userId,
    required this.name,
    required this.areas,
  });

  final String userId;
  final String name;
  final List<String> areas;
}

class _AccessRequestDraft {
  const _AccessRequestDraft({
    required this.ownerUserId,
    required this.reason,
    required this.allOwners,
  });

  final String ownerUserId;
  final String reason;
  final bool allOwners;
}

class _EmptyCard extends StatelessWidget {
  const _EmptyCard(this.message);

  final String message;

  @override
  Widget build(BuildContext context) {
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Text(message),
      ),
    );
  }
}