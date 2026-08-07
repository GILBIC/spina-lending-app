import 'package:flutter/material.dart';
import 'package:gilbic_mobile/src/core/auth/user_session.dart';
import 'package:gilbic_mobile/src/core/device/device_identity.dart';
import 'package:gilbic_mobile/src/core/network/spina_api.dart';
import 'package:gilbic_mobile/src/core/support/support_repository.dart';
import 'package:gilbic_mobile/src/core/support/support_request.dart';

class ClientSupportPage extends StatefulWidget {
  const ClientSupportPage({
    required this.session,
    required this.deviceIdentityProvider,
    this.repository,
    super.key,
  });

  final UserSession session;
  final DeviceIdentityProvider deviceIdentityProvider;
  final ClientSupportRepository? repository;

  @override
  State<ClientSupportPage> createState() => _ClientSupportPageState();
}

class _ClientSupportPageState extends State<ClientSupportPage> {
  late final ClientSupportRepository _repository;
  ClientSupportPortal? _portal;
  String? _deviceId;
  String? _errorMessage;
  bool _loading = true;
  bool _submitting = false;

  @override
  void initState() {
    super.initState();
    _repository = widget.repository ?? SpinaSupportRepository();
    _load();
  }

  Future<void> _load() async {
    setState(() {
      _loading = true;
      _errorMessage = null;
    });
    try {
      final identity = await widget.deviceIdentityProvider.load();
      final portal = await _repository.loadPortal(
        widget.session,
        deviceId: identity.installationId,
      );
      if (!mounted) {
        return;
      }
      setState(() {
        _deviceId = identity.installationId;
        _portal = portal;
      });
    } on SpinaApiException catch (error) {
      if (mounted) {
        setState(() => _errorMessage = error.message);
      }
    } on Object {
      if (mounted) {
        setState(() => _errorMessage = 'Support could not be loaded.');
      }
    } finally {
      if (mounted) {
        setState(() => _loading = false);
      }
    }
  }

  Future<void> _createRequest() async {
    final draft = await showDialog<_SupportDraft>(
      context: context,
      builder: (context) => const _SupportRequestDialog(),
    );
    if (draft == null || _deviceId == null) {
      return;
    }
    setState(() => _submitting = true);
    try {
      await _repository.submit(
        widget.session,
        deviceId: _deviceId!,
        category: draft.category,
        subject: draft.subject,
        message: draft.message,
        referenceText: draft.referenceText,
      );
      if (!mounted) {
        return;
      }
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(
          content: Text('Support request sent to SPINA Management.'),
        ),
      );
      await _load();
    } on SpinaApiException catch (error) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text(error.message)),
        );
      }
    } finally {
      if (mounted) {
        setState(() => _submitting = false);
      }
    }
  }

  Future<void> _cancelRequest(SupportRequestItem request) async {
    final confirmed = await showDialog<bool>(
      context: context,
      builder: (context) => AlertDialog(
        title: const Text('Cancel support request?'),
        content: Text('Cancel “${request.subject}”?'),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(context, false),
            child: const Text('Keep request'),
          ),
          FilledButton(
            onPressed: () => Navigator.pop(context, true),
            child: const Text('Cancel request'),
          ),
        ],
      ),
    );
    if (confirmed != true || _deviceId == null) {
      return;
    }
    setState(() => _submitting = true);
    try {
      await _repository.cancel(
        widget.session,
        deviceId: _deviceId!,
        requestId: request.requestId,
      );
      if (!mounted) {
        return;
      }
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('Support request cancelled.')),
      );
      await _load();
    } on SpinaApiException catch (error) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text(error.message)),
        );
      }
    } finally {
      if (mounted) {
        setState(() => _submitting = false);
      }
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('Support'),
        actions: [
          IconButton(
            tooltip: 'Refresh',
            onPressed: _loading || _submitting ? null : _load,
            icon: const Icon(Icons.refresh),
          ),
        ],
      ),
      floatingActionButton: FloatingActionButton.extended(
        key: const Key('create-support-request'),
        onPressed: _loading || _submitting ? null : _createRequest,
        icon: const Icon(Icons.add_comment_outlined),
        label: const Text('Ask for assistance'),
      ),
      body: SafeArea(child: _buildBody(context)),
    );
  }

  Widget _buildBody(BuildContext context) {
    final portal = _portal;
    if (_loading && portal == null) {
      return const Center(child: CircularProgressIndicator());
    }
    if (_errorMessage != null && portal == null) {
      return Center(
        child: Padding(
          padding: const EdgeInsets.all(24),
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              const Icon(Icons.support_agent, size: 48),
              const SizedBox(height: 12),
              Text(_errorMessage!, textAlign: TextAlign.center),
              const SizedBox(height: 16),
              FilledButton.icon(
                onPressed: _load,
                icon: const Icon(Icons.refresh),
                label: const Text('Try again'),
              ),
            ],
          ),
        ),
      );
    }
    if (portal == null) {
      return const SizedBox.shrink();
    }

    return RefreshIndicator(
      onRefresh: _load,
      child: ListView(
        physics: const AlwaysScrollableScrollPhysics(),
        padding: const EdgeInsets.fromLTRB(16, 16, 16, 100),
        children: [
          if (_errorMessage != null)
            Card(
              child: Padding(
                padding: const EdgeInsets.all(12),
                child: Text(_errorMessage!),
              ),
            ),
          Card(
            child: Padding(
              padding: const EdgeInsets.all(16),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(
                    portal.clientName,
                    style: Theme.of(context).textTheme.titleLarge,
                  ),
                  const SizedBox(height: 2),
                  Text(portal.clientCode),
                ],
              ),
            ),
          ),
          const SizedBox(height: 12),
          Card(
            child: Padding(
              padding: const EdgeInsets.all(14),
              child: Row(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  const Icon(Icons.info_outline),
                  const SizedBox(width: 12),
                  Expanded(child: Text(portal.notice)),
                ],
              ),
            ),
          ),
          const SizedBox(height: 18),
          Row(
            children: [
              Text(
                'Request history',
                style: Theme.of(context).textTheme.titleMedium,
              ),
              const Spacer(),
              Text('${portal.requests.length} requests'),
            ],
          ),
          const SizedBox(height: 8),
          if (portal.requests.isEmpty)
            const Card(
              child: Padding(
                padding: EdgeInsets.all(24),
                child: Text(
                  'No support request has been submitted yet.',
                  textAlign: TextAlign.center,
                ),
              ),
            )
          else
            for (final request in portal.requests) ...[
              _SupportRequestCard(
                request: request,
                busy: _submitting,
                onCancel: () => _cancelRequest(request),
              ),
              const SizedBox(height: 10),
            ],
        ],
      ),
    );
  }
}

class _SupportRequestCard extends StatelessWidget {
  const _SupportRequestCard({
    required this.request,
    required this.busy,
    required this.onCancel,
  });

  final SupportRequestItem request;
  final bool busy;
  final VoidCallback onCancel;

  @override
  Widget build(BuildContext context) {
    final scheme = Theme.of(context).colorScheme;
    final statusColor = switch (request.status.toLowerCase()) {
      'answered' => scheme.secondaryContainer,
      'resolved' => scheme.primaryContainer,
      'cancelled' => scheme.surfaceContainerHighest,
      _ => scheme.tertiaryContainer,
    };
    return Card(
      key: Key('support-request-${request.requestId}'),
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                const Icon(Icons.support_agent),
                const SizedBox(width: 10),
                Expanded(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text(
                        request.subject,
                        style: Theme.of(context).textTheme.titleMedium,
                      ),
                      Text(request.categoryLabel),
                    ],
                  ),
                ),
                Container(
                  padding:
                      const EdgeInsets.symmetric(horizontal: 10, vertical: 6),
                  decoration: BoxDecoration(
                    color: statusColor,
                    borderRadius: BorderRadius.circular(10),
                  ),
                  child: Text(request.statusLabel),
                ),
              ],
            ),
            const SizedBox(height: 12),
            Text(request.message),
            if (request.referenceText.isNotEmpty) ...[
              const SizedBox(height: 8),
              Text('Reference: ${request.referenceText}'),
            ],
            const SizedBox(height: 8),
            Text('Submitted: ${_dateTime(request.createdAt)}'),
            if (request.managementResponse.isNotEmpty) ...[
              const Divider(height: 24),
              Text(
                'SPINA response',
                style: Theme.of(context).textTheme.titleSmall,
              ),
              const SizedBox(height: 4),
              Text(request.managementResponse),
              const SizedBox(height: 6),
              Text('Handled by: ${request.managedByName ?? 'Management'}'),
              if (request.respondedAt != null)
                Text('Responded: ${_dateTime(request.respondedAt!)}'),
              if (request.resolvedAt != null)
                Text('Resolved: ${_dateTime(request.resolvedAt!)}'),
            ],
            if (request.isOpen) ...[
              const SizedBox(height: 12),
              Align(
                alignment: Alignment.centerRight,
                child: TextButton.icon(
                  onPressed: busy ? null : onCancel,
                  icon: const Icon(Icons.cancel_outlined),
                  label: const Text('Cancel request'),
                ),
              ),
            ],
          ],
        ),
      ),
    );
  }
}

class _SupportRequestDialog extends StatefulWidget {
  const _SupportRequestDialog();

  @override
  State<_SupportRequestDialog> createState() => _SupportRequestDialogState();
}

class _SupportRequestDialogState extends State<_SupportRequestDialog> {
  String _category = 'payment';
  final TextEditingController _subjectController = TextEditingController();
  final TextEditingController _messageController = TextEditingController();
  final TextEditingController _referenceController = TextEditingController();
  String? _error;

  @override
  void dispose() {
    _subjectController.dispose();
    _messageController.dispose();
    _referenceController.dispose();
    super.dispose();
  }

  void _submit() {
    final subject = _subjectController.text.trim();
    final message = _messageController.text.trim();
    if (subject.length < 3 || message.length < 3) {
      setState(() {
        _error = 'Enter a subject and details with at least 3 characters.';
      });
      return;
    }
    Navigator.pop(
      context,
      _SupportDraft(
        category: _category,
        subject: subject,
        message: message,
        referenceText: _referenceController.text.trim(),
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    return AlertDialog(
      title: const Text('Ask for assistance'),
      content: SingleChildScrollView(
        child: Column(
          mainAxisSize: MainAxisSize.min,
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            DropdownButtonFormField<String>(
              key: const Key('support-category'),
              initialValue: _category,
              decoration: const InputDecoration(labelText: 'Concern type'),
              items: const [
                DropdownMenuItem(value: 'payment', child: Text('Payment')),
                DropdownMenuItem(value: 'loan', child: Text('Loan')),
                DropdownMenuItem(value: 'renewal', child: Text('Renewal')),
                DropdownMenuItem(value: 'account', child: Text('Account')),
                DropdownMenuItem(value: 'other', child: Text('Other')),
              ],
              onChanged: (value) {
                if (value != null) {
                  setState(() => _category = value);
                }
              },
            ),
            const SizedBox(height: 12),
            TextField(
              key: const Key('support-subject'),
              controller: _subjectController,
              maxLength: 120,
              decoration: const InputDecoration(labelText: 'Subject'),
            ),
            const SizedBox(height: 8),
            TextField(
              key: const Key('support-message'),
              controller: _messageController,
              maxLength: 2000,
              maxLines: 5,
              decoration: const InputDecoration(
                labelText: 'Explain what assistance you need',
                alignLabelWithHint: true,
              ),
            ),
            const SizedBox(height: 8),
            TextField(
              key: const Key('support-reference'),
              controller: _referenceController,
              maxLength: 120,
              decoration: const InputDecoration(
                labelText: 'Receipt or loan reference (optional)',
              ),
            ),
            if (_error != null) ...[
              const SizedBox(height: 4),
              Text(
                _error!,
                style: TextStyle(color: Theme.of(context).colorScheme.error),
              ),
            ],
            const SizedBox(height: 4),
            const Text(
              'This sends a request only. It does not change a payment, balance, or loan.',
            ),
          ],
        ),
      ),
      actions: [
        TextButton(
          onPressed: () => Navigator.pop(context),
          child: const Text('Back'),
        ),
        FilledButton(
          key: const Key('submit-support-request'),
          onPressed: _submit,
          child: const Text('Send request'),
        ),
      ],
    );
  }
}

class _SupportDraft {
  const _SupportDraft({
    required this.category,
    required this.subject,
    required this.message,
    required this.referenceText,
  });

  final String category;
  final String subject;
  final String message;
  final String referenceText;
}

String _dateTime(DateTime value) {
  final local = value.toLocal();
  return '${local.year.toString().padLeft(4, '0')}-'
      '${local.month.toString().padLeft(2, '0')}-'
      '${local.day.toString().padLeft(2, '0')} '
      '${local.hour.toString().padLeft(2, '0')}:'
      '${local.minute.toString().padLeft(2, '0')}';
}
