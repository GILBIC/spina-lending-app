import 'package:flutter/material.dart';
import 'package:gilbic_mobile/src/core/account/account_repository.dart';
import 'package:gilbic_mobile/src/core/auth/user_session.dart';
import 'package:gilbic_mobile/src/core/device/device_identity.dart';
import 'package:gilbic_mobile/src/core/network/spina_api.dart';

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
  late final AccountRepository _repository;
  AccountOverview? _overview;
  String? _error;
  String? _revokingDeviceId;
  bool _loading = true;

  @override
  void initState() {
    super.initState();
    _repository = widget.repository ??
        SpinaAccountRepository(
          deviceIdentityProvider: widget.deviceIdentityProvider,
        );
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
      final overview = await _repository.fetch(widget.session);
      if (!mounted) {
        return;
      }
      setState(() {
        _overview = overview;
        _loading = false;
      });
    } on SpinaApiException catch (error) {
      if (!mounted) {
        return;
      }
      setState(() {
        _error = error.message;
        _loading = false;
      });
    } on Exception {
      if (!mounted) {
        return;
      }
      setState(() {
        _error = 'Gilbic could not load your account settings.';
        _loading = false;
      });
    }
  }

  Future<void> _revoke(AccountDevice device) async {
    if (device.isCurrent || device.status != 'active') {
      return;
    }
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
    if (confirmed != true || !mounted) {
      return;
    }

    setState(() => _revokingDeviceId = device.id);
    try {
      final updated = await _repository.revokeDevice(widget.session, device.id);
      if (!mounted) {
        return;
      }
      setState(() {
        final overview = _overview;
        if (overview != null) {
          _overview = overview.replaceDevice(updated);
        }
        _revokingDeviceId = null;
      });
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('Device access revoked.')),
      );
    } on SpinaApiException catch (error) {
      if (!mounted) {
        return;
      }
      setState(() => _revokingDeviceId = null);
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text(error.message)),
      );
    } on Exception {
      if (!mounted) {
        return;
      }
      setState(() => _revokingDeviceId = null);
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('Device access could not be revoked.')),
      );
    }
  }

  String _dateTime(DateTime? value) {
    if (value == null) {
      return 'Not available';
    }
    final local = value.toLocal();
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
            Text('Current session', style: Theme.of(context).textTheme.titleLarge),
            const SizedBox(height: 12),
            const _DetailRow(label: 'State', value: 'Signed in'),
            _DetailRow(
              label: 'Session expires',
              value: _dateTime(widget.session.expiresAt),
            ),
            _DetailRow(
              label: 'Permission scope',
              value: '${widget.session.permissions.length} server permissions',
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
        child: _loading
            ? const Center(child: CircularProgressIndicator())
            : _error != null
                ? Center(
                    child: Padding(
                      padding: const EdgeInsets.all(24),
                      child: Column(
                        mainAxisSize: MainAxisSize.min,
                        children: [
                          const Icon(Icons.cloud_off_outlined, size: 42),
                          const SizedBox(height: 12),
                          Text(_error!, textAlign: TextAlign.center),
                          const SizedBox(height: 16),
                          FilledButton(
                            key: const Key('account-retry'),
                            onPressed: _load,
                            child: const Text('Try again'),
                          ),
                        ],
                      ),
                    ),
                  )
                : RefreshIndicator(
                    onRefresh: _load,
                    child: ListView(
                      padding: const EdgeInsets.all(16),
                      children: [
                        _profileCard(_overview!.profile),
                        _sessionCard(),
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
              style: Theme.of(context).textTheme.bodyMedium?.copyWith(
                    fontWeight: FontWeight.w600,
                  ),
            ),
          ),
          Expanded(child: Text(value)),
        ],
      ),
    );
  }
}
