import 'package:flutter/material.dart';
import 'package:gilbic_mobile/src/core/auth/user_session.dart';
import 'package:gilbic_mobile/src/core/device/device_identity.dart';
import 'package:gilbic_mobile/src/core/network/spina_api.dart';
import 'package:gilbic_mobile/src/core/renewals/renewal_signature_tasks_repository.dart';

class RenewalSignatureTasksPage extends StatefulWidget {
  const RenewalSignatureTasksPage({
    required this.session,
    required this.deviceIdentityProvider,
    this.repository,
    super.key,
  });

  final UserSession session;
  final DeviceIdentityProvider deviceIdentityProvider;
  final RenewalSignatureTasksRepository? repository;

  @override
  State<RenewalSignatureTasksPage> createState() =>
      _RenewalSignatureTasksPageState();
}

class _RenewalSignatureTasksPageState extends State<RenewalSignatureTasksPage> {
  late final RenewalSignatureTasksRepository _repository;
  List<RenewalSignatureTask> _tasks = const <RenewalSignatureTask>[];
  String? _deviceId;
  String? _error;
  bool _loading = true;
  final Set<String> _busy = <String>{};

  @override
  void initState() {
    super.initState();
    _repository = widget.repository ?? SpinaRenewalSignatureTasksRepository();
    _load();
  }

  Future<void> _load() async {
    if (mounted) {
      setState(() {
        _loading = true;
        _error = null;
      });
    }
    try {
      final identity = await widget.deviceIdentityProvider.load();
      final tasks = await _repository.list(
        widget.session,
        deviceId: identity.installationId,
      );
      if (!mounted) return;
      setState(() {
        _deviceId = identity.installationId;
        _tasks = tasks;
      });
    } on SpinaApiException catch (error) {
      if (mounted) setState(() => _error = error.message);
    } on Object {
      if (mounted) {
        setState(() => _error = 'Renewal signature tasks could not be loaded.');
      }
    } finally {
      if (mounted) setState(() => _loading = false);
    }
  }

  Future<void> _sign(RenewalSignatureTask task) async {
    final deviceId = _deviceId;
    if (deviceId == null || !task.readyToSign || _busy.contains(task.signerId)) {
      return;
    }

    final confirmed = await showDialog<bool>(
          context: context,
          builder: (context) => AlertDialog(
            title: const Text('Sign renewal?'),
            content: Text(
              'You are signing from your own Gilbic account as '
              '${_roleLabel(task.partyRole)} for ${task.borrowerName}. '
              'Do not sign for another person.',
            ),
            actions: [
              TextButton(
                onPressed: () => Navigator.pop(context, false),
                child: const Text('Cancel'),
              ),
              FilledButton(
                key: const Key('confirm-renewal-signature'),
                onPressed: () => Navigator.pop(context, true),
                child: const Text('Sign'),
              ),
            ],
          ),
        ) ??
        false;
    if (!confirmed || !mounted) return;

    setState(() => _busy.add(task.signerId));
    try {
      await _repository.sign(
        widget.session,
        deviceId: deviceId,
        requestId: task.requestId,
        signerId: task.signerId,
      );
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('Renewal signature recorded.')),
      );
      await _load();
    } on SpinaApiException catch (error) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text(error.message)),
        );
      }
    } on Object {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(content: Text('Renewal signature could not be saved.')),
        );
      }
    } finally {
      if (mounted) setState(() => _busy.remove(task.signerId));
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      key: const Key('renewal-signature-tasks-page'),
      appBar: AppBar(
        title: const Text('My Renewal Signatures'),
        actions: [
          IconButton(
            tooltip: 'Refresh signatures',
            onPressed: _loading ? null : _load,
            icon: const Icon(Icons.refresh),
          ),
        ],
      ),
      body: RefreshIndicator(
        onRefresh: _load,
        child: ListView(
          physics: const AlwaysScrollableScrollPhysics(),
          padding: const EdgeInsets.all(16),
          children: [
            Card(
              child: const Padding(
                padding: EdgeInsets.all(16),
                child: Text(
                  'Only sign a renewal when Gilbic shows the role assigned to your own account. '
                  'Borrower acceptance and required identity verification must be complete first.',
                ),
              ),
            ),
            const SizedBox(height: 10),
            if (_loading && _tasks.isEmpty)
              const Padding(
                padding: EdgeInsets.all(36),
                child: Center(child: CircularProgressIndicator()),
              )
            else if (_error != null && _tasks.isEmpty)
              _MessageCard(message: _error!, onRetry: _load)
            else if (_tasks.isEmpty)
              const _MessageCard(
                message: 'No renewal signatures are assigned to this account.',
              )
            else ...[
              if (_error != null) _MessageCard(message: _error!, onRetry: _load),
              for (final task in _tasks) ...[
                _SignatureTaskCard(
                  task: task,
                  busy: _busy.contains(task.signerId),
                  onSign: () => _sign(task),
                ),
                const SizedBox(height: 10),
              ],
            ],
          ],
        ),
      ),
    );
  }
}

class _SignatureTaskCard extends StatelessWidget {
  const _SignatureTaskCard({
    required this.task,
    required this.busy,
    required this.onSign,
  });

  final RenewalSignatureTask task;
  final bool busy;
  final VoidCallback onSign;

  @override
  Widget build(BuildContext context) {
    return Card(
      key: Key('renewal-signature-${task.signerId}'),
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              children: [
                const Icon(Icons.draw_outlined),
                const SizedBox(width: 10),
                Expanded(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text(
                        _roleLabel(task.partyRole),
                        style: Theme.of(context).textTheme.titleMedium,
                      ),
                      Text(task.fullName),
                    ],
                  ),
                ),
                Chip(label: Text(_statusLabel(task))),
              ],
            ),
            const Divider(height: 24),
            _LabelValue('Borrower', task.borrowerName),
            _LabelValue('Loan', task.loanNumber),
            _LabelValue(
              'Borrower acceptance',
              task.borrowerAccepted ? 'Accepted' : 'Pending',
            ),
            _LabelValue(
              'Government ID',
              task.governmentIdVerified ? 'Verified' : 'Pending',
            ),
            _LabelValue(
              'Selfie / photo',
              task.selfieVerified ? 'Verified' : 'Pending',
            ),
            if (task.officeProcessingRequired) ...[
              const SizedBox(height: 10),
              const Text(
                'Office Processing Required — remote signing is disabled for this renewal.',
                style: TextStyle(fontWeight: FontWeight.w700),
              ),
            ] else if (!task.borrowerAccepted) ...[
              const SizedBox(height: 10),
              const Text('Waiting for the borrower to Accept & Continue.'),
            ] else if (!task.governmentIdVerified || !task.selfieVerified) ...[
              const SizedBox(height: 10),
              const Text(
                'Identity verification is still pending. Gilbic will keep remote signing locked.',
              ),
            ],
            const SizedBox(height: 12),
            SizedBox(
              width: double.infinity,
              child: FilledButton.icon(
                key: Key('sign-renewal-${task.signerId}'),
                onPressed: task.readyToSign && !busy ? onSign : null,
                icon: busy
                    ? const SizedBox.square(
                        dimension: 16,
                        child: CircularProgressIndicator(strokeWidth: 2),
                      )
                    : Icon(task.signed ? Icons.check_circle : Icons.draw_outlined),
                label: Text(task.signed ? 'Signed' : 'Sign renewal'),
              ),
            ),
          ],
        ),
      ),
    );
  }
}

class _LabelValue extends StatelessWidget {
  const _LabelValue(this.label, this.value);

  final String label;
  final String value;

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 3),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Expanded(child: Text(label)),
          const SizedBox(width: 12),
          Flexible(child: Text(value, textAlign: TextAlign.right)),
        ],
      ),
    );
  }
}

class _MessageCard extends StatelessWidget {
  const _MessageCard({required this.message, this.onRetry});

  final String message;
  final VoidCallback? onRetry;

  @override
  Widget build(BuildContext context) {
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(24),
        child: Column(
          children: [
            Text(message, textAlign: TextAlign.center),
            if (onRetry != null)
              TextButton(onPressed: onRetry, child: const Text('Retry')),
          ],
        ),
      ),
    );
  }
}

String _roleLabel(String role) {
  return switch (role) {
    'borrower' => 'Borrower',
    'guarantor' => 'Guarantor',
    'solidary_co_maker' => 'Solidary Co-Maker',
    'surety' => 'Surety',
    _ => role.replaceAll('_', ' '),
  };
}

String _statusLabel(RenewalSignatureTask task) {
  if (task.signed) return 'Signed';
  if (task.officeProcessingRequired) return 'Office';
  if (!task.borrowerAccepted) return 'Waiting';
  if (!task.governmentIdVerified || !task.selfieVerified) return 'Verify ID';
  return 'Ready';
}
