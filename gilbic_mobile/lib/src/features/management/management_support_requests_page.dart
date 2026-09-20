import 'package:flutter/material.dart';
import 'package:gilbic_mobile/src/core/auth/user_session.dart';
import 'package:gilbic_mobile/src/core/device/device_identity.dart';
import 'package:gilbic_mobile/src/core/network/spina_api.dart';
import 'package:gilbic_mobile/src/core/support/support_repository.dart';
import 'package:gilbic_mobile/src/core/support/support_request.dart';
import 'package:gilbic_mobile/src/features/management/review/management_review.dart';

class ManagementSupportRequestsPage extends StatefulWidget {
  const ManagementSupportRequestsPage({
    required this.session,
    required this.deviceIdentityProvider,
    this.repository,
    super.key,
  });

  final UserSession session;
  final DeviceIdentityProvider deviceIdentityProvider;
  final ManagementSupportRepository? repository;

  @override
  State<ManagementSupportRequestsPage> createState() =>
      _ManagementSupportRequestsPageState();
}

class _ManagementSupportRequestsPageState
    extends State<ManagementSupportRequestsPage> {
  late final ManagementSupportRepository _repository;
  List<SupportRequestItem> _requests = const [];
  String _status = 'open';
  String? _deviceId;
  String? _errorMessage;
  bool _loading = true;
  bool _submitting = false;
  bool _reviewing = false;
  bool _loadInFlight = false;
  bool _fresh = false;
  bool _denied = false;

  bool get _canReview => _fresh && !_loading && !_submitting && !_denied;

  @override
  void initState() {
    super.initState();
    _repository = widget.repository ?? SpinaSupportRepository();
    _load();
  }

  Future<void> _load({bool afterReview = false}) async {
    if (_loadInFlight ||
        _denied ||
        ((_submitting || _reviewing) && !afterReview)) {
      return;
    }
    _loadInFlight = true;
    setState(() {
      _loading = true;
      _fresh = false;
      _errorMessage = null;
    });
    try {
      final identity = await widget.deviceIdentityProvider.load();
      if (!widget.session.hasPermission('support.manage') ||
          identity.installationId.trim().isEmpty) {
        throw const SpinaApiException(
          'Support access is unavailable.',
          statusCode: 403,
        );
      }
      final requests = await _repository.loadRequests(
        widget.session,
        deviceId: identity.installationId,
        status: _status,
      );
      if (!mounted) {
        return;
      }
      setState(() {
        _deviceId = identity.installationId;
        _requests = requests;
        _fresh = true;
      });
    } on SpinaApiException catch (error) {
      if (mounted) {
        setState(() => _failed(error));
      }
    } on Object {
      if (mounted) {
        setState(() => _errorMessage = 'Support requests could not be loaded.');
      }
    } finally {
      _loadInFlight = false;
      if (mounted) {
        setState(() => _loading = false);
      }
    }
  }

  void _failed(SpinaApiException error) {
    _fresh = false;
    _errorMessage = error.message;
    if ([401, 403, 426].contains(error.statusCode)) {
      _denied = true;
      _requests = const [];
      _deviceId = null;
    }
  }

  Future<void> _review(
    SupportRequestItem request, {
    required String action,
  }) async {
    if (!_canReview || _reviewing) return;
    setState(() => _reviewing = true);
    try {
      final response = await showDialog<String>(
        context: context,
        builder: (context) => _SupportResponseDialog(
          action: action,
          initialResponse: request.managementResponse,
        ),
      );
      if (response == null || _deviceId == null || !mounted || !_canReview) {
        return;
      }
      final (nextActionLabel, consequence) = switch (action) {
        'resolved' => (
          'Resolve support request',
          'The request will be closed as resolved with this response in '
              'communication history. Official financial records will not be edited.',
        ),
        _ => (
          'Send support response',
          'The response will be saved to the client communication history. '
              'Official financial records will not be edited.',
        ),
      };
      final confirmed = await showManagementReviewConfirmation(
        context,
        ManagementReviewPresentation.validated(
          binding: ManagementMutationBinding.clientSupport,
          recordLabel: 'Client support request',
          recordValue: '${request.clientName} • ${request.clientCode}',
          statusLabel:
              plainManagementStatus(request.status, const <String, String>{
                'open': 'Open and awaiting Management',
                'answered': 'Answered and still open',
                'resolved': 'Resolved and closed',
                'cancelled': 'Cancelled and closed',
              }),
          facts: <ManagementReviewFact>[
            ManagementReviewFact(
              label: 'Category',
              value: request.categoryLabel,
            ),
            ManagementReviewFact(label: 'Subject', value: request.subject),
            ManagementReviewFact(label: 'Response', value: response),
            if (request.referenceText.trim().isNotEmpty)
              ManagementReviewFact(
                label: 'Client reference',
                value: request.referenceText,
              ),
          ],
          nextActionLabel: nextActionLabel,
          consequence: consequence,
          secondaryReferences: <ManagementReviewFact>[
            ManagementReviewFact(label: 'Request ID', value: request.requestId),
          ],
        ),
      );
      if (!confirmed || !mounted || !_canReview) {
        return;
      }
      setState(() {
        _submitting = true;
        _fresh = false;
      });
      try {
        await _repository.review(
          widget.session,
          deviceId: _deviceId!,
          requestId: request.requestId,
          action: action,
          response: response,
        );
        if (!mounted) {
          return;
        }
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(
            content: Text(switch (action) {
              'resolved' => 'Support request resolved.',
              _ => 'Response sent to the client.',
            }),
          ),
        );
        await _load(afterReview: true);
      } on SpinaApiException catch (error) {
        if (mounted) {
          setState(() => _failed(error));
        }
      } on Object {
        if (mounted) {
          setState(() {
            _fresh = false;
            _errorMessage =
                'The response could not be confirmed. Refresh saved requests before choosing another action.';
          });
        }
      } finally {
        if (mounted) {
          setState(() => _submitting = false);
        }
      }
    } finally {
      if (mounted) setState(() => _reviewing = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('Client Support'),
        actions: [
          IconButton(
            tooltip: 'Refresh',
            onPressed: _loading || _submitting || _reviewing || _denied
                ? null
                : _load,
            icon: const Icon(Icons.refresh),
          ),
        ],
      ),
      body: SafeArea(
        child: RefreshIndicator(
          onRefresh: _load,
          child: ListView(
            physics: const AlwaysScrollableScrollPhysics(),
            padding: const EdgeInsets.fromLTRB(16, 16, 16, 28),
            children: [
              const Card(
                child: Padding(
                  padding: EdgeInsets.all(14),
                  child: Row(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Icon(Icons.support_agent),
                      SizedBox(width: 12),
                      Expanded(
                        child: Text(
                          'Responses here are assistance records only. They do not edit balances, payments, or loans.',
                        ),
                      ),
                    ],
                  ),
                ),
              ),
              const SizedBox(height: 12),
              DropdownButtonFormField<String>(
                key: const Key('support-status-filter'),
                initialValue: _status,
                decoration: const InputDecoration(labelText: 'Request status'),
                items: const [
                  DropdownMenuItem(value: 'open', child: Text('Open')),
                  DropdownMenuItem(value: 'answered', child: Text('Answered')),
                  DropdownMenuItem(value: 'resolved', child: Text('Resolved')),
                  DropdownMenuItem(
                    value: 'cancelled',
                    child: Text('Cancelled'),
                  ),
                ],
                onChanged: _loading || _submitting || _reviewing || _denied
                    ? null
                    : (value) {
                        if (value != null && value != _status) {
                          setState(() => _status = value);
                          _load();
                        }
                      },
              ),
              const SizedBox(height: 16),
              if (_loading && _requests.isEmpty)
                const Padding(
                  padding: EdgeInsets.all(40),
                  child: Center(child: CircularProgressIndicator()),
                )
              else if (_errorMessage != null)
                Card(
                  child: Padding(
                    padding: const EdgeInsets.all(20),
                    child: Column(
                      children: [
                        Text(_errorMessage!, textAlign: TextAlign.center),
                        if (!_denied) ...[
                          const SizedBox(height: 12),
                          FilledButton.icon(
                            onPressed: _load,
                            icon: const Icon(Icons.refresh),
                            label: const Text('Try again'),
                          ),
                        ],
                      ],
                    ),
                  ),
                ),
              if (!_loading && _errorMessage == null && _requests.isEmpty)
                Card(
                  child: Padding(
                    padding: const EdgeInsets.all(24),
                    child: Text(
                      'No ${_statusLabel(_status).toLowerCase()} support requests.',
                      textAlign: TextAlign.center,
                    ),
                  ),
                )
              else
                for (final request in _requests) ...[
                  _ManagementSupportCard(
                    request: request,
                    busy: !_canReview || _reviewing,
                    onAnswer: () => _review(request, action: 'answered'),
                    onResolve: () => _review(request, action: 'resolved'),
                  ),
                  const SizedBox(height: 10),
                ],
            ],
          ),
        ),
      ),
    );
  }
}

class _ManagementSupportCard extends StatelessWidget {
  const _ManagementSupportCard({
    required this.request,
    required this.busy,
    required this.onAnswer,
    required this.onResolve,
  });

  final SupportRequestItem request;
  final bool busy;
  final VoidCallback onAnswer;
  final VoidCallback onResolve;

  @override
  Widget build(BuildContext context) {
    final isOpen = request.status.toLowerCase() == 'open';
    final isAnswered = request.status.toLowerCase() == 'answered';
    return Card(
      key: Key('management-support-${request.requestId}'),
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
                        request.clientName,
                        style: Theme.of(context).textTheme.titleMedium,
                      ),
                      Text(request.clientCode),
                    ],
                  ),
                ),
                Chip(label: Text(request.statusLabel)),
              ],
            ),
            const Divider(height: 24),
            Text(
              request.subject,
              style: Theme.of(context).textTheme.titleSmall,
            ),
            const SizedBox(height: 2),
            Text(request.categoryLabel),
            const SizedBox(height: 10),
            Text(request.message),
            if (request.referenceText.isNotEmpty) ...[
              const SizedBox(height: 8),
              Text('Reference: ${request.referenceText}'),
            ],
            const SizedBox(height: 8),
            Text('Submitted: ${_dateTime(request.createdAt)}'),
            if (request.managementResponse.isNotEmpty) ...[
              const Divider(height: 24),
              Text('Current response: ${request.managementResponse}'),
              Text('Handled by: ${request.managedByName ?? 'Management'}'),
            ],
            if (isOpen || isAnswered) ...[
              const SizedBox(height: 14),
              Row(
                children: [
                  if (isOpen)
                    Expanded(
                      child: OutlinedButton.icon(
                        key: Key('answer-support-${request.requestId}'),
                        onPressed: busy ? null : onAnswer,
                        icon: const Icon(Icons.reply),
                        label: const Text('Answer'),
                      ),
                    ),
                  if (isOpen) const SizedBox(width: 10),
                  Expanded(
                    child: FilledButton.icon(
                      key: Key('resolve-support-${request.requestId}'),
                      onPressed: busy ? null : onResolve,
                      icon: const Icon(Icons.check_circle_outline),
                      label: const Text('Resolve'),
                    ),
                  ),
                ],
              ),
            ],
          ],
        ),
      ),
    );
  }
}

class _SupportResponseDialog extends StatefulWidget {
  const _SupportResponseDialog({
    required this.action,
    required this.initialResponse,
  });

  final String action;
  final String initialResponse;

  @override
  State<_SupportResponseDialog> createState() => _SupportResponseDialogState();
}

class _SupportResponseDialogState extends State<_SupportResponseDialog> {
  late final TextEditingController _controller;
  String? _error;

  @override
  void initState() {
    super.initState();
    _controller = TextEditingController(text: widget.initialResponse);
  }

  @override
  void dispose() {
    _controller.dispose();
    super.dispose();
  }

  void _submit() {
    final response = _controller.text.trim();
    if (response.length < 3) {
      setState(() => _error = 'Enter a response with at least 3 characters.');
      return;
    }
    Navigator.pop(context, response);
  }

  @override
  Widget build(BuildContext context) {
    final resolving = widget.action == 'resolved';
    return AlertDialog(
      title: Text(resolving ? 'Resolve support request' : 'Answer client'),
      content: TextField(
        key: const Key('management-support-response'),
        controller: _controller,
        maxLength: 2000,
        maxLines: 6,
        decoration: InputDecoration(
          labelText: resolving ? 'Resolution' : 'Response to client',
          alignLabelWithHint: true,
          errorText: _error,
        ),
      ),
      actions: [
        TextButton(
          onPressed: () => Navigator.pop(context),
          child: const Text('Back'),
        ),
        FilledButton(
          key: const Key('submit-management-support-response'),
          onPressed: _submit,
          child: Text(resolving ? 'Resolve' : 'Send response'),
        ),
      ],
    );
  }
}

String _statusLabel(String status) {
  return switch (status) {
    'answered' => 'Answered',
    'resolved' => 'Resolved',
    'cancelled' => 'Cancelled',
    _ => 'Open',
  };
}

String _dateTime(DateTime value) {
  final local = value.toLocal();
  return '${local.year.toString().padLeft(4, '0')}-'
      '${local.month.toString().padLeft(2, '0')}-'
      '${local.day.toString().padLeft(2, '0')} '
      '${local.hour.toString().padLeft(2, '0')}:'
      '${local.minute.toString().padLeft(2, '0')}';
}
