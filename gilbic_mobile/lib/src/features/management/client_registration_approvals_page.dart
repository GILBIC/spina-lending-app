import 'package:flutter/material.dart';
import 'package:gilbic_mobile/src/core/auth/user_session.dart';
import 'package:gilbic_mobile/src/core/device/device_identity.dart';
import 'package:gilbic_mobile/src/core/management/client_registration_review.dart';
import 'package:gilbic_mobile/src/core/management/client_registration_review_repository.dart';
import 'package:gilbic_mobile/src/core/network/spina_api.dart';
import 'package:gilbic_mobile/src/features/management/review/management_review.dart';

class ClientRegistrationApprovalsPage extends StatefulWidget {
  const ClientRegistrationApprovalsPage({
    required this.session,
    required this.deviceIdentityProvider,
    this.repository,
    super.key,
  });

  final UserSession session;
  final DeviceIdentityProvider deviceIdentityProvider;
  final ClientRegistrationReviewRepository? repository;

  @override
  State<ClientRegistrationApprovalsPage> createState() =>
      _ClientRegistrationApprovalsPageState();
}

class _ClientRegistrationApprovalsPageState
    extends State<ClientRegistrationApprovalsPage> {
  late final ClientRegistrationReviewRepository _repository;
  List<ClientRegistrationReview> _registrations =
      const <ClientRegistrationReview>[];
  String? _deviceId;
  String? _errorMessage;
  bool _loading = true;

  @override
  void initState() {
    super.initState();
    _repository =
        widget.repository ?? SpinaClientRegistrationReviewRepository();
    _load();
  }

  Future<void> _load() async {
    setState(() {
      _loading = true;
      _errorMessage = null;
    });
    try {
      final identity = await widget.deviceIdentityProvider.load();
      final registrations = await _repository.loadPending(
        widget.session,
        deviceId: identity.installationId,
      );
      if (!mounted) {
        return;
      }
      setState(() {
        _deviceId = identity.installationId;
        _registrations = registrations;
      });
    } on SpinaApiException catch (error) {
      if (mounted) {
        setState(() => _errorMessage = error.message);
      }
    } on Object {
      if (mounted) {
        setState(
          () => _errorMessage = 'Client registrations could not be loaded.',
        );
      }
    } finally {
      if (mounted) {
        setState(() => _loading = false);
      }
    }
  }

  Future<void> _review(ClientRegistrationReview registration) async {
    final deviceId = _deviceId;
    if (deviceId == null) {
      return;
    }
    final changed = await Navigator.of(context).push<bool>(
      MaterialPageRoute<bool>(
        builder: (_) => ClientRegistrationLinkPage(
          session: widget.session,
          deviceId: deviceId,
          registration: registration,
          repository: _repository,
        ),
      ),
    );
    if (changed == true) {
      await _load();
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('Client Portal Approvals'),
        actions: [
          IconButton(
            tooltip: 'Refresh',
            onPressed: _loading ? null : _load,
            icon: const Icon(Icons.refresh),
          ),
        ],
      ),
      body: SafeArea(
        child: _loading
            ? const Center(child: CircularProgressIndicator())
            : _errorMessage != null
            ? _ErrorPanel(message: _errorMessage!, onRetry: _load)
            : _registrations.isEmpty
            ? const _EmptyApprovals()
            : ListView.separated(
                padding: const EdgeInsets.all(16),
                itemCount: _registrations.length,
                separatorBuilder: (_, __) => const SizedBox(height: 10),
                itemBuilder: (context, index) {
                  final item = _registrations[index];
                  return Card(
                    child: ListTile(
                      key: Key('client-registration-${item.userId}'),
                      leading: const CircleAvatar(
                        child: Icon(Icons.person_search),
                      ),
                      title: Text(item.fullName),
                      subtitle: Text(
                        'Claimed code: ${item.claimedClientCode}\n'
                        'Username: ${item.username}'
                        '${item.claimedPhoneNumber == null ? '' : '\nPhone: ${item.claimedPhoneNumber}'}',
                      ),
                      isThreeLine: true,
                      trailing: const Icon(Icons.chevron_right),
                      onTap: () => _review(item),
                    ),
                  );
                },
              ),
      ),
    );
  }
}

class ClientRegistrationLinkPage extends StatefulWidget {
  const ClientRegistrationLinkPage({
    required this.session,
    required this.deviceId,
    required this.registration,
    required this.repository,
    super.key,
  });

  final UserSession session;
  final String deviceId;
  final ClientRegistrationReview registration;
  final ClientRegistrationReviewRepository repository;

  @override
  State<ClientRegistrationLinkPage> createState() =>
      _ClientRegistrationLinkPageState();
}

class _ClientRegistrationLinkPageState
    extends State<ClientRegistrationLinkPage> {
  late final TextEditingController _searchController;
  final TextEditingController _noteController = TextEditingController();
  List<ClientLinkCandidate> _candidates = const <ClientLinkCandidate>[];
  ClientLinkCandidate? _selected;
  String? _errorMessage;
  bool _searching = false;
  bool _submitting = false;

  @override
  void initState() {
    super.initState();
    _searchController = TextEditingController(
      text: widget.registration.claimedClientCode,
    );
    _search();
  }

  @override
  void dispose() {
    _searchController.dispose();
    _noteController.dispose();
    super.dispose();
  }

  Future<void> _search() async {
    final query = _searchController.text.trim();
    if (query.length < 2 || _searching) {
      return;
    }
    setState(() {
      _searching = true;
      _errorMessage = null;
      _selected = null;
    });
    try {
      final candidates = await widget.repository.searchCandidates(
        widget.session,
        deviceId: widget.deviceId,
        query: query,
      );
      if (mounted) {
        setState(() => _candidates = candidates);
      }
    } on SpinaApiException catch (error) {
      if (mounted) {
        setState(() => _errorMessage = error.message);
      }
    } on Object {
      if (mounted) {
        setState(() => _errorMessage = 'Borrower search failed.');
      }
    } finally {
      if (mounted) {
        setState(() => _searching = false);
      }
    }
  }

  Future<void> _approve() async {
    final selected = _selected;
    if (selected == null || _submitting) {
      setState(() => _errorMessage = 'Select the borrower record to link.');
      return;
    }
    final confirmed = await showManagementReviewConfirmation(
      context,
      _registrationReview(
        nextAction: 'Approve and link this account',
        consequence:
            'This login will be linked to the selected existing client record; official financial records will not be edited.',
        additionalFacts: <ManagementReviewFact>[
          ManagementReviewFact(
            label: 'Existing client',
            value: '${selected.fullName} • ${selected.clientCode}',
          ),
        ],
      ),
    );
    if (!confirmed || !mounted) {
      return;
    }

    setState(() {
      _submitting = true;
      _errorMessage = null;
    });
    try {
      await widget.repository.approve(
        widget.session,
        deviceId: widget.deviceId,
        userId: widget.registration.userId,
        clientId: selected.id,
        reviewNote: _noteController.text,
      );
      if (!mounted) {
        return;
      }
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('Client account approved and linked.')),
      );
      Navigator.of(context).pop(true);
    } on SpinaApiException catch (error) {
      if (mounted) {
        setState(() => _errorMessage = error.message);
      }
    } on Object {
      if (mounted) {
        setState(() => _errorMessage = 'Client approval failed.');
      }
    } finally {
      if (mounted) {
        setState(() => _submitting = false);
      }
    }
  }

  Future<void> _reject() async {
    final reason = await showDialog<String>(
      context: context,
      builder: (context) => const _ClientRegistrationRejectionDialog(),
    );
    if (reason == null || !mounted) {
      return;
    }

    final confirmed = await showManagementReviewConfirmation(
      context,
      _registrationReview(
        nextAction: 'Reject this request',
        consequence:
            'This registration request will be rejected; official client and financial records will not be edited.',
        additionalFacts: <ManagementReviewFact>[
          ManagementReviewFact(label: 'Reason', value: reason),
        ],
      ),
    );
    if (!confirmed || !mounted) {
      return;
    }

    setState(() {
      _submitting = true;
      _errorMessage = null;
    });
    try {
      await widget.repository.reject(
        widget.session,
        deviceId: widget.deviceId,
        userId: widget.registration.userId,
        reviewNote: reason,
      );
      if (!mounted) {
        return;
      }
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('Client registration rejected.')),
      );
      Navigator.of(context).pop(true);
    } on SpinaApiException catch (error) {
      if (mounted) {
        setState(() => _errorMessage = error.message);
      }
    } on Object {
      if (mounted) {
        setState(() => _errorMessage = 'Client rejection failed.');
      }
    } finally {
      if (mounted) {
        setState(() => _submitting = false);
      }
    }
  }

  ManagementReviewPresentation _registrationReview({
    required String nextAction,
    required String consequence,
    List<ManagementReviewFact> additionalFacts = const <ManagementReviewFact>[],
  }) {
    final registration = widget.registration;
    return ManagementReviewPresentation.validated(
      surface: ManagementMutationSurface.clientRegistration,
      recordLabel: 'Client registration request',
      recordValue:
          '${registration.fullName} • ${registration.claimedClientCode}',
      statusLabel: plainManagementStatus(
        registration.registrationStatus,
        const <String, String>{'pending': 'Waiting for Management review'},
      ),
      statusDetail: 'Server status: ${registration.registrationStatus}',
      facts: <ManagementReviewFact>[
        ManagementReviewFact(label: 'Username', value: registration.username),
        ...additionalFacts,
      ],
      nextActionLabel: nextAction,
      consequence: consequence,
      risk: ManagementReviewRisk.privileged,
    );
  }

  @override
  Widget build(BuildContext context) {
    final registration = widget.registration;
    return Scaffold(
      appBar: AppBar(title: const Text('Review client registration')),
      body: SafeArea(
        child: ListView(
          padding: const EdgeInsets.all(16),
          children: [
            Card(
              child: Padding(
                padding: const EdgeInsets.all(16),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      registration.fullName,
                      style: Theme.of(context).textTheme.titleLarge,
                    ),
                    const SizedBox(height: 6),
                    Text('Username: ${registration.username}'),
                    if (registration.email != null)
                      Text('Email: ${registration.email}'),
                    Text(
                      'Claimed client code: ${registration.claimedClientCode}',
                    ),
                    if (registration.claimedPhoneNumber != null)
                      Text('Claimed phone: ${registration.claimedPhoneNumber}'),
                  ],
                ),
              ),
            ),
            const SizedBox(height: 12),
            TextField(
              key: const Key('borrower-link-search'),
              controller: _searchController,
              enabled: !_submitting,
              textInputAction: TextInputAction.search,
              onSubmitted: (_) => _search(),
              decoration: InputDecoration(
                labelText: 'Search unlinked borrower',
                hintText: 'Client code, name, or phone',
                prefixIcon: const Icon(Icons.search),
                border: const OutlineInputBorder(),
                suffixIcon: IconButton(
                  tooltip: 'Search',
                  onPressed: _searching || _submitting ? null : _search,
                  icon: _searching
                      ? const SizedBox.square(
                          dimension: 20,
                          child: CircularProgressIndicator(strokeWidth: 2),
                        )
                      : const Icon(Icons.arrow_forward),
                ),
              ),
            ),
            const SizedBox(height: 12),
            if (!_searching && _candidates.isEmpty)
              const Card(
                child: Padding(
                  padding: EdgeInsets.all(16),
                  child: Text(
                    'No unlinked active borrower matched this search.',
                    textAlign: TextAlign.center,
                  ),
                ),
              ),
            for (final candidate in _candidates) ...[
              Card(
                clipBehavior: Clip.antiAlias,
                child: ListTile(
                  key: Key('borrower-candidate-${candidate.id}'),
                  leading: Icon(
                    _selected?.id == candidate.id
                        ? Icons.check_circle
                        : Icons.circle_outlined,
                    color: _selected?.id == candidate.id
                        ? Theme.of(context).colorScheme.primary
                        : null,
                  ),
                  title: Text(candidate.fullName),
                  subtitle: Text(
                    '${candidate.clientCode}'
                    '${candidate.area == null ? '' : ' • ${candidate.area}'}'
                    '${candidate.phoneNumber == null ? '' : '\n${candidate.phoneNumber}'}',
                  ),
                  onTap: _submitting
                      ? null
                      : () => setState(() => _selected = candidate),
                ),
              ),
              const SizedBox(height: 8),
            ],
            const SizedBox(height: 4),
            TextField(
              controller: _noteController,
              enabled: !_submitting,
              maxLength: 500,
              minLines: 2,
              maxLines: 4,
              decoration: const InputDecoration(
                labelText: 'Approval note (optional)',
                border: OutlineInputBorder(),
              ),
            ),
            if (_errorMessage != null) ...[
              const SizedBox(height: 8),
              Text(
                _errorMessage!,
                key: const Key('client-approval-error'),
                style: TextStyle(color: Theme.of(context).colorScheme.error),
                textAlign: TextAlign.center,
              ),
            ],
            const SizedBox(height: 12),
            FilledButton.icon(
              key: const Key('approve-client-registration'),
              onPressed: _submitting || _selected == null ? null : _approve,
              icon: _submitting
                  ? const SizedBox.square(
                      dimension: 18,
                      child: CircularProgressIndicator(strokeWidth: 2),
                    )
                  : const Icon(Icons.link),
              label: const Text('Approve and link borrower'),
            ),
            const SizedBox(height: 8),
            OutlinedButton.icon(
              key: const Key('reject-client-registration'),
              onPressed: _submitting ? null : _reject,
              icon: const Icon(Icons.block),
              label: const Text('Reject registration'),
            ),
          ],
        ),
      ),
    );
  }
}

class _ClientRegistrationRejectionDialog extends StatefulWidget {
  const _ClientRegistrationRejectionDialog();

  @override
  State<_ClientRegistrationRejectionDialog> createState() =>
      _ClientRegistrationRejectionDialogState();
}

class _ClientRegistrationRejectionDialogState
    extends State<_ClientRegistrationRejectionDialog> {
  final TextEditingController _reason = TextEditingController();

  @override
  void dispose() {
    _reason.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return AlertDialog(
      title: const Text('Reject registration'),
      content: TextField(
        key: const Key('client-registration-rejection-reason'),
        controller: _reason,
        autofocus: true,
        minLines: 2,
        maxLines: 4,
        decoration: const InputDecoration(
          labelText: 'Required reason',
          border: OutlineInputBorder(),
        ),
      ),
      actions: [
        TextButton(
          onPressed: () => Navigator.pop(context),
          child: const Text('Cancel'),
        ),
        FilledButton(
          onPressed: () {
            final value = _reason.text.trim();
            if (value.length >= 3) {
              Navigator.pop(context, value);
            }
          },
          child: const Text('Reject'),
        ),
      ],
    );
  }
}

class _ErrorPanel extends StatelessWidget {
  const _ErrorPanel({required this.message, required this.onRetry});

  final String message;
  final VoidCallback onRetry;

  @override
  Widget build(BuildContext context) {
    return Center(
      child: Padding(
        padding: const EdgeInsets.all(24),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            Icon(
              Icons.error_outline,
              size: 48,
              color: Theme.of(context).colorScheme.error,
            ),
            const SizedBox(height: 12),
            Text(message, textAlign: TextAlign.center),
            const SizedBox(height: 16),
            FilledButton.icon(
              onPressed: onRetry,
              icon: const Icon(Icons.refresh),
              label: const Text('Try again'),
            ),
          ],
        ),
      ),
    );
  }
}

class _EmptyApprovals extends StatelessWidget {
  const _EmptyApprovals();

  @override
  Widget build(BuildContext context) {
    return const Center(
      child: Padding(
        padding: EdgeInsets.all(24),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            Icon(Icons.verified_user_outlined, size: 56),
            SizedBox(height: 12),
            Text(
              'No pending client registrations.',
              textAlign: TextAlign.center,
            ),
          ],
        ),
      ),
    );
  }
}
