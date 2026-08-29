import 'package:flutter/material.dart';
import 'package:gilbic_mobile/src/core/auth/user_session.dart';
import 'package:gilbic_mobile/src/core/device/device_identity.dart';
import 'package:gilbic_mobile/src/core/management/management_administration.dart';
import 'package:gilbic_mobile/src/core/management/management_administration_repository.dart';
import 'package:gilbic_mobile/src/core/network/spina_api.dart';
import 'package:gilbic_mobile/src/features/management/review/management_review.dart';

typedef InvitationReconciler =
    Future<ManagementStaffAccount?> Function({
      required String username,
      required String email,
    });

class ManagementStaffInvitePage extends StatefulWidget {
  const ManagementStaffInvitePage({
    required this.session,
    required this.repository,
    required this.deviceIdentityProvider,
    required this.onUncertainResult,
    required this.onDirectoryRefresh,
    super.key,
  });

  final UserSession session;
  final ManagementAdministrationRepository repository;
  final DeviceIdentityProvider deviceIdentityProvider;
  final InvitationReconciler onUncertainResult;
  final Future<void> Function() onDirectoryRefresh;

  @override
  State<ManagementStaffInvitePage> createState() =>
      _ManagementStaffInvitePageState();
}

class _ManagementStaffInvitePageState extends State<ManagementStaffInvitePage> {
  final TextEditingController _fullName = TextEditingController();
  final TextEditingController _username = TextEditingController();
  final TextEditingController _email = TextEditingController();
  String? _deviceId;
  String? _role;
  String? _error;
  bool _submitting = false;
  bool _retryBlocked = false;
  bool _permissionDenied = false;
  String? _uncertainUsername;
  String? _uncertainEmail;

  @override
  void initState() {
    super.initState();
    _loadIdentity();
  }

  @override
  void dispose() {
    _fullName.dispose();
    _username.dispose();
    _email.dispose();
    super.dispose();
  }

  Future<void> _loadIdentity() async {
    try {
      final identity = await widget.deviceIdentityProvider.load();
      if (mounted) {
        setState(() => _deviceId = identity.installationId);
      }
    } on Object catch (error) {
      if (mounted) {
        setState(() {
          _error = error is SpinaApiException
              ? error.message
              : 'This installation identity could not be loaded.';
        });
      }
    }
  }

  Future<void> _submit() async {
    if (_submitting || _retryBlocked) {
      return;
    }
    final deviceId = _deviceId;
    final fullName = _fullName.text.trim();
    final username = _username.text.trim();
    final email = _email.text.trim().toLowerCase();
    final role = _role;
    if (deviceId == null ||
        fullName.isEmpty ||
        username.isEmpty ||
        email.isEmpty ||
        role == null) {
      setState(() => _error = 'Complete all staff invitation fields.');
      return;
    }

    final confirmed = await showManagementReviewConfirmation(
      context,
      _invitationReview(
        fullName: fullName,
        username: username,
        email: email,
        role: role,
      ),
    );
    if (!confirmed || !mounted) {
      return;
    }

    setState(() {
      _submitting = true;
      _error = null;
    });
    try {
      final account = await widget.repository.inviteStaff(
        widget.session,
        deviceId: deviceId,
        username: username,
        email: email,
        fullName: fullName,
        role: role,
      );
      if (!mounted) {
        return;
      }
      Navigator.of(context).pop(account);
    } on SpinaApiException catch (error) {
      if (!mounted) {
        return;
      }
      if (error.statusCode == 403) {
        setState(() {
          _submitting = false;
          _retryBlocked = true;
          _permissionDenied = true;
          _error = error.message;
        });
        return;
      }
      if (_isUncertainInvitationError(error)) {
        await _recoverUncertainResult(username: username, email: email);
      } else {
        setState(() => _error = error.message);
        setState(() => _submitting = false);
      }
    } on Object {
      if (!mounted) {
        return;
      }
      await _recoverUncertainResult(username: username, email: email);
    }
  }

  Future<void> _recoverUncertainResult({
    required String username,
    required String email,
  }) async {
    setState(() {
      _retryBlocked = true;
      _uncertainUsername = username;
      _uncertainEmail = email;
      _error = 'Refresh the staff list before trying this invitation again.';
    });
    await _recheckUncertainResult();
  }

  Future<void> _recheckUncertainResult() async {
    final username = _uncertainUsername;
    final email = _uncertainEmail;
    if (username == null || email == null) {
      return;
    }
    setState(() => _submitting = true);
    try {
      final account = await widget.onUncertainResult(
        username: username,
        email: email,
      );
      if (account == null) {
        if (mounted) {
          setState(() {
            _submitting = false;
            _retryBlocked = true;
            _error =
                'The invitation result is still unconfirmed. Check the staff list again before sending another invitation.';
          });
        }
        return;
      }
      if (mounted) {
        Navigator.of(context).pop(account);
      }
      return;
    } on Object {
      // Keep retry blocked until Management returns to a refreshed list.
    }
    if (mounted) {
      setState(() {
        _submitting = false;
        _retryBlocked = true;
      });
    }
  }

  Future<void> _refreshAfterPermissionDenied() async {
    try {
      await widget.onDirectoryRefresh();
      if (mounted) {
        Navigator.of(context).pop();
      }
    } on Object {
      if (mounted) {
        setState(() => _error = 'The staff list could not be refreshed.');
      }
    }
  }

  @override
  Widget build(BuildContext context) {
    final hasInvitePermission = widget.session.hasPermission('account.manage');
    return PopScope(
      canPop: !_submitting,
      child: Scaffold(
        appBar: AppBar(title: const Text('Invite staff')),
        body: SafeArea(
          child: _permissionDenied
              ? _InvitePermissionDeniedState(
                  message:
                      _error ??
                      'Your current server permissions no longer allow staff invitations.',
                  onRefresh: _refreshAfterPermissionDenied,
                  onBack: () => Navigator.of(context).maybePop(),
                )
              : hasInvitePermission
              ? ListView(
                  padding: const EdgeInsets.all(16),
                  children: [
                    const Text(
                      'SPINA sends an invitation. Management never creates or '
                      'views the staff member’s password.',
                    ),
                    const SizedBox(height: 16),
                    TextField(
                      key: const Key('management-staff-full-name'),
                      controller: _fullName,
                      enabled: !_submitting && !_retryBlocked,
                      textCapitalization: TextCapitalization.words,
                      decoration: const InputDecoration(labelText: 'Full name'),
                    ),
                    const SizedBox(height: 12),
                    TextField(
                      key: const Key('management-staff-username'),
                      controller: _username,
                      enabled: !_submitting && !_retryBlocked,
                      autocorrect: false,
                      decoration: const InputDecoration(labelText: 'Username'),
                    ),
                    const SizedBox(height: 12),
                    TextField(
                      key: const Key('management-staff-email'),
                      controller: _email,
                      enabled: !_submitting && !_retryBlocked,
                      keyboardType: TextInputType.emailAddress,
                      autocorrect: false,
                      decoration: const InputDecoration(labelText: 'Email'),
                    ),
                    const SizedBox(height: 12),
                    DropdownButtonFormField<String>(
                      key: const Key('management-staff-invite-role'),
                      initialValue: _role,
                      decoration: const InputDecoration(
                        labelText: 'Staff role',
                      ),
                      items: const <DropdownMenuItem<String>>[
                        DropdownMenuItem(
                          value: 'collector',
                          child: Text('Collector'),
                        ),
                        DropdownMenuItem(
                          value: 'employee',
                          child: Text('Employee'),
                        ),
                        DropdownMenuItem(
                          value: 'management',
                          child: Text('Management'),
                        ),
                      ],
                      onChanged: _submitting || _retryBlocked
                          ? null
                          : (value) => setState(() => _role = value),
                    ),
                    if (_error != null) ...[
                      const SizedBox(height: 14),
                      Text(
                        _error!,
                        key: const Key('management-staff-invite-error'),
                        style: TextStyle(
                          color: Theme.of(context).colorScheme.error,
                        ),
                      ),
                    ],
                    const SizedBox(height: 18),
                    FilledButton.icon(
                      key: const Key('management-staff-invite-submit'),
                      onPressed:
                          _submitting || _retryBlocked || _deviceId == null
                          ? null
                          : _submit,
                      icon: _submitting
                          ? const SizedBox.square(
                              dimension: 18,
                              child: CircularProgressIndicator(
                                strokeWidth: 2,
                                color: Colors.white,
                              ),
                            )
                          : const Icon(Icons.send_outlined),
                      label: Text(
                        _submitting
                            ? 'Sending invitation...'
                            : 'Send invitation',
                      ),
                    ),
                    if (_retryBlocked && !_permissionDenied) ...[
                      const SizedBox(height: 10),
                      ManagementReviewPanel(
                        review: ManagementReviewPresentation.validated(
                          surface: ManagementMutationSurface.staffInvitation,
                          recordLabel: 'Staff invitation',
                          recordValue:
                              '${_uncertainUsername ?? 'Not provided by the server'} • ${_uncertainEmail ?? 'Not provided by the server'}',
                          statusLabel: 'Server result is not yet confirmed',
                          nextActionLabel: 'Check the server result',
                          consequence:
                              'SPINA will check the authoritative staff directory; it will not send a second invitation.',
                          risk: ManagementReviewRisk.privileged,
                          actionEnabled: !_submitting,
                        ),
                        compact: true,
                      ),
                      const SizedBox(height: 10),
                      OutlinedButton.icon(
                        key: const Key('management-staff-invite-reconcile'),
                        onPressed: _submitting ? null : _recheckUncertainResult,
                        icon: const Icon(Icons.manage_search_outlined),
                        label: const Text('Check staff list again'),
                      ),
                    ],
                  ],
                )
              : const Center(
                  child: Padding(
                    padding: EdgeInsets.all(24),
                    child: Text(
                      'Your current server permissions do not allow staff invitations.',
                      textAlign: TextAlign.center,
                    ),
                  ),
                ),
        ),
      ),
    );
  }
}

ManagementReviewPresentation _invitationReview({
  required String fullName,
  required String username,
  required String email,
  required String role,
}) {
  return ManagementReviewPresentation.validated(
    surface: ManagementMutationSurface.staffInvitation,
    recordLabel: 'Staff invitation',
    recordValue: '$fullName • @$username',
    statusLabel: 'Waiting for Management confirmation',
    facts: <ManagementReviewFact>[
      ManagementReviewFact(label: 'Email', value: email),
      ManagementReviewFact(
        label: 'Canonical role',
        value: _inviteRoleLabel(role),
      ),
    ],
    nextActionLabel: 'Send staff invitation',
    consequence:
        'A pending staff account will be created with the selected canonical role; access still depends on server status and device approval.',
    risk: ManagementReviewRisk.privileged,
  );
}

String _inviteRoleLabel(String role) {
  return switch (role) {
    'collector' => 'Collector',
    'employee' => 'Employee',
    'management' => 'Management',
    _ => 'Status needs review',
  };
}

class _InvitePermissionDeniedState extends StatelessWidget {
  const _InvitePermissionDeniedState({
    required this.message,
    required this.onRefresh,
    required this.onBack,
  });

  final String message;
  final VoidCallback onRefresh;
  final VoidCallback onBack;

  @override
  Widget build(BuildContext context) {
    return Center(
      key: const Key('management-staff-invite-permission-denied'),
      child: SingleChildScrollView(
        padding: const EdgeInsets.all(24),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            const Icon(Icons.lock_outline, size: 42),
            const SizedBox(height: 12),
            Text(
              'Permission required',
              style: Theme.of(context).textTheme.titleLarge,
            ),
            const SizedBox(height: 8),
            Text(message, textAlign: TextAlign.center),
            const SizedBox(height: 16),
            FilledButton.icon(
              key: const Key('management-staff-invite-permission-refresh'),
              onPressed: onRefresh,
              icon: const Icon(Icons.refresh),
              label: const Text('Refresh staff list'),
            ),
            TextButton.icon(
              key: const Key('management-staff-invite-permission-back'),
              onPressed: onBack,
              icon: const Icon(Icons.arrow_back),
              label: const Text('Back'),
            ),
          ],
        ),
      ),
    );
  }
}

bool _isUncertainInvitationError(SpinaApiException error) {
  return error.statusCode == null ||
      error.statusCode! >= 500 ||
      error.code == 'network_unavailable' ||
      error.code == 'invalid_server_response';
}
