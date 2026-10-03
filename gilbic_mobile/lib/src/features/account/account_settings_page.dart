import 'package:flutter/material.dart';
import 'package:gilbic_mobile/src/core/time/spina_business_time.dart';
import 'package:gilbic_mobile/src/core/account/account_repository.dart';
import 'package:gilbic_mobile/src/core/auth/app_role.dart';
import 'package:gilbic_mobile/src/core/auth/user_session.dart';
import 'package:gilbic_mobile/src/core/device/device_identity.dart';
import 'package:gilbic_mobile/src/core/network/spina_api.dart';
import 'package:gilbic_mobile/src/features/account/client_password_reset_page.dart';
import 'package:gilbic_mobile/src/features/renewals/renewal_signature_tasks_page.dart';
import 'package:gilbic_mobile/src/features/shared/daily_workspace_widgets.dart';

class AccountSettingsPage extends StatefulWidget {
  const AccountSettingsPage({
    required this.session,
    required this.onSignOut,
    required this.deviceIdentityProvider,
    this.repository,
    super.key,
  });

  final UserSession session;
  final Future<void> Function() onSignOut;
  final DeviceIdentityProvider deviceIdentityProvider;
  final AccountRepository? repository;

  @override
  State<AccountSettingsPage> createState() => _AccountSettingsPageState();
}

class _AccountSettingsPageState extends State<AccountSettingsPage> {
  late AccountRepository _repository;
  AccountOverview? _overview;
  String? _error;
  String? _revokingDeviceId;
  bool _loading = false;
  int _generation = 0;
  int? _failureStatus;
  bool get _denied =>
      _failureStatus == 401 || _failureStatus == 403 || _failureStatus == 426;
  bool _current(int generation) => mounted && generation == _generation;

  bool get _canResetClientPassword {
    final role = widget.session.role;
    return widget.session.permissions.contains('client.credential.manage') &&
        (role == AppRole.employee || role == AppRole.management);
  }

  @override
  void initState() {
    super.initState();
    _repository =
        widget.repository ??
        SpinaAccountRepository(
          deviceIdentityProvider: widget.deviceIdentityProvider,
        );
    _load();
  }

  @override
  void didUpdateWidget(AccountSettingsPage oldWidget) {
    super.didUpdateWidget(oldWidget);
    if (oldWidget.session != widget.session ||
        oldWidget.deviceIdentityProvider != widget.deviceIdentityProvider ||
        oldWidget.repository != widget.repository) {
      _generation++;
      _overview = null;
      _revokingDeviceId = null;
      _loading = false;
      _failureStatus = null;
      _repository =
          widget.repository ??
          SpinaAccountRepository(
            deviceIdentityProvider: widget.deviceIdentityProvider,
          );
      _load();
    }
  }

  @override
  void dispose() {
    _generation++;
    super.dispose();
  }

  void _failedRead(Object error, int generation) {
    if (!_current(generation)) return;
    setState(() {
      _failureStatus = error is SpinaApiException ? error.statusCode : null;
      _error = _failureStatus == 401
          ? 'Your session has expired. Sign in again to view your account.'
          : _failureStatus == 403
          ? 'Your account access is unavailable. Return to Account or contact SPINA for help.'
          : _failureStatus == 426
          ? 'SPINA must be updated before these records can be used. Return to sign-in to check app access.'
          : 'SPINA could not load your account settings. Check your connection and retry.';
      _loading = false;
      if (_denied) {
        _generation++;
        _overview = null;
        _revokingDeviceId = null;
      }
    });
  }

  Widget _readNotice() => WorkspaceReadNotice(
    key: const Key('account-retry'),
    message: _error!,
    stale: _overview != null,
    actionLabel: _failureStatus == 401
        ? 'Sign in again'
        : _failureStatus == 403
        ? 'Access unavailable'
        : _failureStatus == 426
        ? 'Return to sign-in'
        : 'Retry',
    onAction: _failureStatus == 401 || _failureStatus == 426
        ? widget.onSignOut
        : _denied || _loading
        ? null
        : _load,
  );

  Future<void> _load() async {
    if (!mounted || _loading || _denied) return;
    final generation = _generation;
    final session = widget.session;
    final repository = _repository;
    setState(() {
      _loading = true;
      _error = null;
      _failureStatus = null;
    });
    try {
      final overview = await repository.fetch(session);
      if (!_current(generation)) return;
      setState(() {
        _overview = overview;
        _loading = false;
      });
    } on Object catch (error) {
      _failedRead(error, generation);
    }
  }

  Future<void> _revoke(AccountDevice device) async {
    if (!mounted ||
        _denied ||
        _overview == null ||
        device.isCurrent ||
        device.status != 'active') {
      return;
    }
    final generation = _generation;
    final confirmed = await showDialog<bool>(
      context: context,
      builder: (context) => AlertDialog(
        title: const Text('Revoke device?'),
        content: Text(
          'This ${device.platform.toUpperCase()} device will lose access to this account. '
          'Management must reactivate it before it can sign in again.',
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.of(context).pop(false),
            child: const Text('Cancel'),
          ),
          FilledButton(
            onPressed: () => Navigator.of(context).pop(true),
            child: const Text('Revoke'),
          ),
        ],
      ),
    );
    if (confirmed != true || !_current(generation) || _denied) {
      return;
    }

    setState(() => _revokingDeviceId = device.id);
    try {
      final updated = await _repository.revokeDevice(widget.session, device.id);
      if (!mounted || !_current(generation)) {
        return;
      }
      setState(() {
        final overview = _overview;
        if (overview != null) {
          _overview = overview.replaceDevice(updated);
        }
        _revokingDeviceId = null;
      });
      ScaffoldMessenger.of(
        context,
      ).showSnackBar(const SnackBar(content: Text('Device access revoked.')));
    } on SpinaApiException catch (error) {
      if (!mounted || !_current(generation)) {
        return;
      }
      if (error.statusCode == 401 ||
          error.statusCode == 403 ||
          error.statusCode == 426) {
        _failedRead(error, generation);
        return;
      }
      setState(() => _revokingDeviceId = null);
      ScaffoldMessenger.of(
        context,
      ).showSnackBar(SnackBar(content: Text(error.message)));
    } on Exception {
      if (!mounted || !_current(generation)) {
        return;
      }
      setState(() => _revokingDeviceId = null);
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('Device access could not be revoked.')),
      );
    }
  }

  Future<void> _changePassword() async {
    if (!mounted ||
        _denied ||
        _overview == null ||
        widget.session.role == AppRole.client) {
      return;
    }
    final generation = _generation;
    final changed = await showDialog<bool>(
      context: context,
      barrierDismissible: false,
      builder: (context) => _ChangePasswordDialog(
        session: widget.session,
        repository: _repository,
      ),
    );
    if (changed == true && mounted && _current(generation) && !_denied) {
      ScaffoldMessenger.of(
        context,
      ).showSnackBar(const SnackBar(content: Text('Password changed.')));
    }
  }

  void _openClientPasswordReset() {
    if (!mounted || _denied || _overview == null || !_canResetClientPassword) {
      return;
    }
    Navigator.of(context).push(
      MaterialPageRoute<void>(
        builder: (context) => ClientPasswordResetPage(
          session: widget.session,
          deviceIdentityProvider: widget.deviceIdentityProvider,
        ),
      ),
    );
  }

  void _openRenewalSignatures() {
    if (!mounted || _denied || _overview == null) return;
    Navigator.of(context).push(
      MaterialPageRoute<void>(
        builder: (context) => RenewalSignatureTasksPage(
          session: widget.session,
          deviceIdentityProvider: widget.deviceIdentityProvider,
        ),
      ),
    );
  }

  String _dateTime(DateTime? value) {
    if (value == null) {
      return 'Not available';
    }
    final local = spinaBusinessWallClock(value);
    String two(int value) => value.toString().padLeft(2, '0');
    return '${local.year}-${two(local.month)}-${two(local.day)} '
        '${two(local.hour)}:${two(local.minute)}';
  }

  Widget _profileCard(AccountProfile profile) {
    final email = profile.email?.trim() ?? '';
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(18),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text('Profile', style: Theme.of(context).textTheme.titleLarge),
            const SizedBox(height: 12),
            _DetailRow(label: 'Name', value: profile.fullName),
            _DetailRow(label: 'Username', value: profile.username),
            if (email.isNotEmpty) _DetailRow(label: 'Email', value: email),
            _DetailRow(label: 'Role', value: profile.role),
            _DetailRow(label: 'Account status', value: profile.status),
          ],
        ),
      ),
    );
  }

  Widget _sessionCard() {
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(18),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(
              'Current session',
              style: Theme.of(context).textTheme.titleLarge,
            ),
            const SizedBox(height: 12),
            const _DetailRow(label: 'State', value: 'Signed in'),
            _DetailRow(
              label: 'Session expires',
              value: _dateTime(widget.session.expiresAt),
            ),
            if (widget.session.role == AppRole.client)
              const _DetailRow(
                label: 'Your access',
                value: 'Only your own linked loan and account records',
              )
            else
              _DetailRow(
                label: 'Permission scope',
                value:
                    '${widget.session.permissions.length} server permissions',
              ),
            const SizedBox(height: 10),
            FilledButton.icon(
              key: const Key('account-sign-out'),
              onPressed: widget.onSignOut,
              icon: const Icon(Icons.logout),
              label: const Text('Sign out on this device'),
            ),
          ],
        ),
      ),
    );
  }

  Widget _passwordCard() {
    return Card(
      child: ListTile(
        key: const Key('account-change-password'),
        contentPadding: const EdgeInsets.symmetric(horizontal: 18, vertical: 8),
        leading: const Icon(Icons.password_outlined),
        title: const Text('Change my password'),
        subtitle: const Text(
          'Changes only the password for your signed-in staff account.',
        ),
        trailing: const Icon(Icons.chevron_right),
        onTap: _changePassword,
      ),
    );
  }

  Widget _clientPasswordResetCard() {
    return Card(
      child: ListTile(
        key: const Key('account-reset-client-password'),
        contentPadding: const EdgeInsets.symmetric(horizontal: 18, vertical: 8),
        leading: const Icon(Icons.manage_accounts_outlined),
        title: const Text('Reset Client password'),
        subtitle: const Text(
          'Find an existing Client account and generate a new borrower password.',
        ),
        trailing: const Icon(Icons.chevron_right),
        onTap: _openClientPasswordReset,
      ),
    );
  }

  Widget _renewalSignaturesCard() {
    return Card(
      child: ListTile(
        key: const Key('account-renewal-signatures'),
        contentPadding: const EdgeInsets.symmetric(horizontal: 18, vertical: 8),
        leading: const Icon(Icons.draw_outlined),
        title: const Text('My renewal signatures'),
        subtitle: const Text(
          'Review borrower, guarantor, solidary co-maker, or surety signatures assigned to this account.',
        ),
        trailing: const Icon(Icons.chevron_right),
        onTap: _openRenewalSignatures,
      ),
    );
  }

  Widget _deviceCard(AccountDevice device) {
    final revoking = _revokingDeviceId == device.id;
    return Card(
      key: Key('account-device-${device.id}'),
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Row(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Icon(
              device.platform == 'ios' ? Icons.phone_iphone : Icons.smartphone,
            ),
            const SizedBox(width: 12),
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Row(
                    children: [
                      Expanded(
                        child: Text(
                          device.platform.toUpperCase(),
                          style: Theme.of(context).textTheme.titleMedium,
                        ),
                      ),
                      if (device.isCurrent)
                        const Chip(label: Text('This device')),
                    ],
                  ),
                  Text('Status: ${device.status}'),
                  if ((device.appVersion ?? '').isNotEmpty)
                    Text('App: ${device.appVersion}'),
                  Text('Registered: ${_dateTime(device.registeredAt)}'),
                  Text('Last seen: ${_dateTime(device.lastSeenAt)}'),
                  if (!device.isCurrent && device.status == 'active') ...[
                    const SizedBox(height: 8),
                    TextButton.icon(
                      key: Key('revoke-device-${device.id}'),
                      onPressed: revoking ? null : () => _revoke(device),
                      icon: revoking
                          ? const SizedBox.square(
                              dimension: 16,
                              child: CircularProgressIndicator(strokeWidth: 2),
                            )
                          : const Icon(Icons.phonelink_erase),
                      label: Text(revoking ? 'Revoking…' : 'Revoke device'),
                    ),
                  ],
                ],
              ),
            ),
          ],
        ),
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      key: const Key('account-settings-page'),
      appBar: AppBar(title: const Text('Profile & security')),
      body: SafeArea(
        child: _loading && _overview == null
            ? const Center(child: CircularProgressIndicator())
            : _overview == null && _error != null
            ? Center(
                child: Padding(
                  padding: const EdgeInsets.all(24),
                  child: _readNotice(),
                ),
              )
            : RefreshIndicator(
                onRefresh: _load,
                child: ListView(
                  padding: const EdgeInsets.all(16),
                  children: [
                    if (_loading) const LinearProgressIndicator(),
                    if (_error != null) _readNotice(),
                    _profileCard(_overview!.profile),
                    _sessionCard(),
                    if (widget.session.role != AppRole.client) _passwordCard(),
                    if (_canResetClientPassword) _clientPasswordResetCard(),
                    _renewalSignaturesCard(),
                    const SizedBox(height: 8),
                    Text(
                      'Registered devices',
                      style: Theme.of(context).textTheme.titleLarge,
                    ),
                    const SizedBox(height: 8),
                    if (_overview!.devices.isEmpty)
                      const Card(
                        child: Padding(
                          padding: EdgeInsets.all(18),
                          child: Text('No registered devices were returned.'),
                        ),
                      )
                    else
                      ..._overview!.devices.map(_deviceCard),
                    const SizedBox(height: 12),
                    Text(
                      'Device identifiers are never shown here. Only platform, '
                      'app version, status, and activity timestamps are displayed.',
                      style: Theme.of(context).textTheme.bodySmall,
                    ),
                  ],
                ),
              ),
      ),
    );
  }
}

class _ChangePasswordDialog extends StatefulWidget {
  const _ChangePasswordDialog({
    required this.session,
    required this.repository,
  });

  final UserSession session;
  final AccountRepository repository;

  @override
  State<_ChangePasswordDialog> createState() => _ChangePasswordDialogState();
}

class _ChangePasswordDialogState extends State<_ChangePasswordDialog> {
  final TextEditingController _passwordController = TextEditingController();
  final TextEditingController _confirmController = TextEditingController();
  String _errorMessage = '';
  bool _submitting = false;

  @override
  void dispose() {
    _passwordController.dispose();
    _confirmController.dispose();
    super.dispose();
  }

  Future<void> _submit() async {
    final password = _passwordController.text;
    if (password.isEmpty || password.length > 200) {
      setState(() => _errorMessage = 'Enter a valid new password.');
      return;
    }
    if (password != _confirmController.text) {
      setState(() => _errorMessage = 'Passwords do not match.');
      return;
    }
    setState(() {
      _submitting = true;
      _errorMessage = '';
    });
    try {
      await widget.repository.changePassword(widget.session, password);
      if (!mounted) {
        return;
      }
      Navigator.of(context).pop(true);
    } on SpinaApiException catch (error) {
      if (!mounted) {
        return;
      }
      setState(() {
        _submitting = false;
        _errorMessage = error.message;
      });
    } on Exception {
      if (!mounted) {
        return;
      }
      setState(() {
        _submitting = false;
        _errorMessage = 'Password could not be changed.';
      });
    }
  }

  @override
  Widget build(BuildContext context) {
    return PopScope(
      canPop: !_submitting,
      child: AlertDialog(
        title: const Text('Change my password'),
        content: SingleChildScrollView(
          child: Column(
            mainAxisSize: MainAxisSize.min,
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              const Text(
                'Choose a new password for your signed-in SPINA staff account.',
              ),
              const SizedBox(height: 16),
              TextField(
                key: const Key('account-password-new'),
                controller: _passwordController,
                enabled: !_submitting,
                obscureText: true,
                enableSuggestions: false,
                autocorrect: false,
                decoration: const InputDecoration(labelText: 'New password'),
              ),
              const SizedBox(height: 12),
              TextField(
                key: const Key('account-password-confirm'),
                controller: _confirmController,
                enabled: !_submitting,
                obscureText: true,
                enableSuggestions: false,
                autocorrect: false,
                decoration: const InputDecoration(
                  labelText: 'Confirm new password',
                ),
              ),
              if (_errorMessage.isNotEmpty) ...[
                const SizedBox(height: 12),
                Text(
                  _errorMessage,
                  style: TextStyle(color: Theme.of(context).colorScheme.error),
                ),
              ],
            ],
          ),
        ),
        actions: [
          TextButton(
            onPressed: _submitting
                ? null
                : () => Navigator.of(context).pop(false),
            child: const Text('Cancel'),
          ),
          FilledButton(
            key: const Key('account-password-submit'),
            onPressed: _submitting ? null : _submit,
            child: _submitting
                ? const SizedBox.square(
                    dimension: 18,
                    child: CircularProgressIndicator(strokeWidth: 2),
                  )
                : const Text('Change password'),
          ),
        ],
      ),
    );
  }
}

class _DetailRow extends StatelessWidget {
  const _DetailRow({required this.label, required this.value});

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
            width: 132,
            child: Text(
              label,
              style: Theme.of(
                context,
              ).textTheme.bodyMedium?.copyWith(fontWeight: FontWeight.w600),
            ),
          ),
          Expanded(child: Text(value)),
        ],
      ),
    );
  }
}
