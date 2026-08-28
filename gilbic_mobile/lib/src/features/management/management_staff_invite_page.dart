import 'package:flutter/material.dart';
import 'package:gilbic_mobile/src/core/auth/user_session.dart';
import 'package:gilbic_mobile/src/core/device/device_identity.dart';
import 'package:gilbic_mobile/src/core/management/management_administration_repository.dart';
import 'package:gilbic_mobile/src/core/network/spina_api.dart';

class ManagementStaffInvitePage extends StatefulWidget {
  const ManagementStaffInvitePage({
    required this.session,
    required this.repository,
    required this.deviceIdentityProvider,
    required this.onUncertainResult,
    super.key,
  });

  final UserSession session;
  final ManagementAdministrationRepository repository;
  final DeviceIdentityProvider deviceIdentityProvider;
  final Future<void> Function() onUncertainResult;

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
    if (_submitting) {
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
      if (error.code == 'network_unavailable') {
        setState(() {
          _error =
              'Refresh the staff list before trying this invitation again.';
        });
        try {
          await widget.onUncertainResult();
        } on Object {
          // Keep the invitation blocked until this explicit refresh finishes.
        }
      } else {
        setState(() => _error = error.message);
      }
      if (mounted) {
        setState(() => _submitting = false);
      }
    } on Object {
      if (!mounted) {
        return;
      }
      setState(() {
        _error = 'Refresh the staff list before trying this invitation again.';
      });
      try {
        await widget.onUncertainResult();
      } on Object {
        // The displayed guidance remains authoritative when refresh also fails.
      }
      if (mounted) {
        setState(() => _submitting = false);
      }
    }
  }

  @override
  Widget build(BuildContext context) {
    final canInvite = widget.session.hasPermission('account.manage');
    return Scaffold(
      appBar: AppBar(title: const Text('Invite staff')),
      body: SafeArea(
        child: canInvite
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
                    enabled: !_submitting,
                    textCapitalization: TextCapitalization.words,
                    decoration: const InputDecoration(labelText: 'Full name'),
                  ),
                  const SizedBox(height: 12),
                  TextField(
                    key: const Key('management-staff-username'),
                    controller: _username,
                    enabled: !_submitting,
                    autocorrect: false,
                    decoration: const InputDecoration(labelText: 'Username'),
                  ),
                  const SizedBox(height: 12),
                  TextField(
                    key: const Key('management-staff-email'),
                    controller: _email,
                    enabled: !_submitting,
                    keyboardType: TextInputType.emailAddress,
                    autocorrect: false,
                    decoration: const InputDecoration(labelText: 'Email'),
                  ),
                  const SizedBox(height: 12),
                  DropdownButtonFormField<String>(
                    key: const Key('management-staff-invite-role'),
                    initialValue: _role,
                    decoration: const InputDecoration(labelText: 'Staff role'),
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
                    onChanged: _submitting
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
                    onPressed: _submitting || _deviceId == null
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
                      _submitting ? 'Sending invitation...' : 'Send invitation',
                    ),
                  ),
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
    );
  }
}
