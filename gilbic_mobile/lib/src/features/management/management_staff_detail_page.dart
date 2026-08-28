import 'dart:async';

import 'package:flutter/material.dart';
import 'package:gilbic_mobile/src/core/auth/user_session.dart';
import 'package:gilbic_mobile/src/core/device/device_identity.dart';
import 'package:gilbic_mobile/src/core/management/management_administration.dart';
import 'package:gilbic_mobile/src/core/management/management_administration_repository.dart';
import 'package:gilbic_mobile/src/core/network/spina_api.dart';

class ManagementStaffDetailPage extends StatefulWidget {
  const ManagementStaffDetailPage({
    required this.session,
    required this.account,
    required this.repository,
    required this.deviceIdentityProvider,
    required this.reloadAccount,
    required this.onDirectoryRefresh,
    super.key,
  });

  final UserSession session;
  final ManagementStaffAccount account;
  final ManagementAdministrationRepository repository;
  final DeviceIdentityProvider deviceIdentityProvider;
  final Future<ManagementStaffAccount> Function() reloadAccount;
  final Future<void> Function() onDirectoryRefresh;

  @override
  State<ManagementStaffDetailPage> createState() =>
      _ManagementStaffDetailPageState();
}

class _ManagementStaffDetailPageState extends State<ManagementStaffDetailPage> {
  late ManagementStaffAccount _account;
  List<ManagementDevice> _devices = const <ManagementDevice>[];
  String? _deviceId;
  String? _selectedRole;
  String? _selectedStatus;
  String? _error;
  String? _success;
  bool _loading = true;
  bool _mutating = false;
  bool _permissionDenied = false;

  bool get _canManageAccounts => widget.session.hasPermission('account.manage');
  bool get _canManageDevices => widget.session.hasPermission('device.manage');
  bool get _hasAnyPermission => _canManageAccounts || _canManageDevices;
  bool get _isOwnAccount => widget.session.userId == _account.id;

  @override
  void initState() {
    super.initState();
    _account = widget.account;
    _selectedRole = _firstRole(_account);
    _selectedStatus = _account.status;
    if (_hasAnyPermission) {
      unawaited(_initialize());
    } else {
      _loading = false;
      _permissionDenied = true;
    }
  }

  Future<void> _initialize() async {
    try {
      final identity = await widget.deviceIdentityProvider.load();
      var devices = const <ManagementDevice>[];
      if (_canManageDevices) {
        devices = await widget.repository.loadDevices(
          widget.session,
          deviceId: identity.installationId,
          userId: _account.id,
        );
      }
      if (!mounted) {
        return;
      }
      setState(() {
        _deviceId = identity.installationId;
        _devices = devices;
        _loading = false;
      });
    } on SpinaApiException catch (error) {
      if (!mounted) {
        return;
      }
      setState(() {
        _loading = false;
        _permissionDenied = error.statusCode == 403;
        _error = error.message;
      });
    } on Object {
      if (mounted) {
        setState(() {
          _loading = false;
          _error = 'The authoritative staff record could not be loaded.';
        });
      }
    }
  }

  Future<void> _refresh({bool clearMessages = true}) async {
    if (_mutating) {
      return;
    }
    await _reloadCurrent(clearMessages: clearMessages);
  }

  Future<void> _reloadCurrent({required bool clearMessages}) async {
    if (clearMessages && mounted) {
      setState(() {
        _error = null;
        _success = null;
      });
    }
    try {
      final fresh = await widget.reloadAccount();
      var devices = _devices;
      final deviceId = _deviceId;
      if (_canManageDevices && deviceId != null) {
        devices = await widget.repository.loadDevices(
          widget.session,
          deviceId: deviceId,
          userId: fresh.id,
        );
      }
      if (!mounted) {
        return;
      }
      setState(() {
        _account = fresh;
        _selectedRole = _firstRole(fresh);
        _selectedStatus = fresh.status;
        _devices = devices;
        _permissionDenied = false;
      });
    } on SpinaApiException catch (error) {
      if (mounted) {
        setState(() {
          _permissionDenied = error.statusCode == 403;
          _error = error.message;
        });
      }
    } on Object {
      if (mounted) {
        setState(
          () =>
              _error = 'The authoritative staff record could not be refreshed.',
        );
      }
    }
  }

  Future<void> _changeRole() async {
    final requested = _selectedRole;
    final current = _firstRole(_account);
    if (requested == null || current == null || requested == current) {
      return;
    }
    final confirmed = await _confirm(
      current: _label(current),
      requested: _label(requested),
      consequence:
          'Changing this role changes future access after the server approves it.',
    );
    if (!confirmed) {
      return;
    }
    await _runMutation(
      () => widget.repository.setRole(
        widget.session,
        deviceId: _deviceId!,
        userId: _account.id,
        role: requested,
      ),
      success: 'Role updated from the authoritative server record.',
    );
  }

  Future<void> _changeStatus() async {
    final requested = _selectedStatus;
    final current = _account.status;
    if (requested == null || requested == current) {
      return;
    }
    final confirmed = await _confirm(
      current: _label(current),
      requested: _label(requested),
      consequence:
          'This changes whether the staff account can use protected SPINA access.',
    );
    if (!confirmed) {
      return;
    }
    await _runMutation(
      () => widget.repository.setAccountStatus(
        widget.session,
        deviceId: _deviceId!,
        userId: _account.id,
        status: requested,
      ),
      success: 'Account status updated from the authoritative server record.',
    );
  }

  Future<void> _changeDevice(ManagementDevice device) async {
    final requested = switch (device.status) {
      'pending' => 'active',
      'active' => 'revoked',
      'revoked' => 'active',
      _ => device.status,
    };
    if (requested == device.status) {
      return;
    }
    final consequence = switch ((device.status, requested)) {
      ('pending', 'active') when _account.roles.contains('collector') =>
        'Approving this phone revokes any other active Collector phone.',
      ('pending', 'active') =>
        'Approving this phone allows protected access for this account.',
      ('active', 'revoked') =>
        'Revoking this phone blocks its future protected requests.',
      ('revoked', 'active') =>
        'Restoring this phone allows protected requests again.',
      _ => 'The phone keeps its current status.',
    };
    final confirmed = await _confirm(
      current: _label(device.status),
      requested: _label(requested),
      consequence: consequence,
    );
    if (!confirmed) {
      return;
    }
    await _runMutation(
      () => widget.repository.setDeviceStatus(
        widget.session,
        deviceId: _deviceId!,
        userId: _account.id,
        managedDeviceId: device.id,
        status: requested,
      ),
      success: 'Device status updated from the authoritative server record.',
    );
  }

  Future<bool> _confirm({
    required String current,
    required String requested,
    required String consequence,
  }) async {
    return await showDialog<bool>(
          context: context,
          builder: (context) => AlertDialog(
            title: Text(_account.fullName),
            content: Column(
              mainAxisSize: MainAxisSize.min,
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text('Current: $current'),
                const SizedBox(height: 6),
                Text('Requested: $requested'),
                const SizedBox(height: 12),
                Text(consequence),
              ],
            ),
            actions: [
              TextButton(
                onPressed: () => Navigator.of(context).pop(false),
                child: const Text('Cancel'),
              ),
              FilledButton(
                key: const Key('management-action-confirm'),
                onPressed: () => Navigator.of(context).pop(true),
                child: const Text('Confirm'),
              ),
            ],
          ),
        ) ??
        false;
  }

  Future<void> _runMutation(
    Future<Object?> Function() mutation, {
    required String success,
  }) async {
    if (_mutating || _deviceId == null) {
      return;
    }
    setState(() {
      _mutating = true;
      _error = null;
      _success = null;
    });
    try {
      await mutation();
      final fresh = await widget.reloadAccount();
      var devices = _devices;
      if (_canManageDevices) {
        devices = await widget.repository.loadDevices(
          widget.session,
          deviceId: _deviceId!,
          userId: fresh.id,
        );
      }
      if (!mounted) {
        return;
      }
      setState(() {
        _account = fresh;
        _selectedRole = _firstRole(fresh);
        _selectedStatus = fresh.status;
        _devices = devices;
        _success = success;
        _mutating = false;
      });
    } on SpinaApiException catch (error) {
      if (error.statusCode == 404) {
        await widget.onDirectoryRefresh();
      } else if (error.statusCode == 409) {
        await _reloadCurrent(clearMessages: false);
      }
      if (!mounted) {
        return;
      }
      setState(() {
        _mutating = false;
        _permissionDenied = error.statusCode == 403;
        _error = error.statusCode == 404
            ? 'This staff record is no longer available. The directory was refreshed.'
            : error.message;
      });
    } on Object {
      if (mounted) {
        setState(() {
          _mutating = false;
          _error = 'The change could not be confirmed by the server.';
        });
      }
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: Text(_account.fullName)),
      body: SafeArea(child: _buildBody(context)),
    );
  }

  Widget _buildBody(BuildContext context) {
    if (_loading) {
      return const Center(child: CircularProgressIndicator());
    }
    if (_permissionDenied || !_hasAnyPermission) {
      return _DetailMessage(
        key: const Key('management-staff-detail-permission-denied'),
        title: 'Permission required',
        message:
            'Your current server permissions no longer allow this staff record.',
        actions: [
          FilledButton.icon(
            key: const Key('management-staff-refresh'),
            onPressed: _mutating ? null : _refresh,
            icon: const Icon(Icons.refresh),
            label: const Text('Refresh'),
          ),
          TextButton.icon(
            key: const Key('management-staff-back'),
            onPressed: () => Navigator.of(context).maybePop(),
            icon: const Icon(Icons.arrow_back),
            label: const Text('Back'),
          ),
        ],
      );
    }

    return SingleChildScrollView(
      padding: const EdgeInsets.all(16),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          Card(
            child: Padding(
              padding: const EdgeInsets.all(16),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(
                    _account.fullName,
                    style: Theme.of(context).textTheme.titleLarge,
                  ),
                  const SizedBox(height: 4),
                  Text('@${_account.username}'),
                  if (_account.email != null) ...[
                    const SizedBox(height: 4),
                    Text(_account.email!),
                  ],
                  const SizedBox(height: 10),
                  Wrap(
                    spacing: 8,
                    runSpacing: 6,
                    children: [
                      for (final role in _account.roles)
                        Chip(label: Text(_label(role))),
                      Chip(label: Text(_label(_account.status))),
                    ],
                  ),
                ],
              ),
            ),
          ),
          if (_error != null) ...[
            const SizedBox(height: 12),
            Card(
              key: const Key('management-staff-mutation-error'),
              color: Theme.of(context).colorScheme.errorContainer,
              child: Padding(
                padding: const EdgeInsets.all(14),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(_error!),
                    const SizedBox(height: 8),
                    TextButton.icon(
                      key: const Key('management-staff-refresh'),
                      onPressed: _mutating ? null : _refresh,
                      icon: const Icon(Icons.refresh),
                      label: const Text('Refresh current state'),
                    ),
                  ],
                ),
              ),
            ),
          ],
          if (_success != null) ...[
            const SizedBox(height: 12),
            Card(
              key: const Key('management-staff-success'),
              child: Padding(
                padding: const EdgeInsets.all(14),
                child: Text(_success!),
              ),
            ),
          ],
          if (_canManageAccounts) ...[
            const SizedBox(height: 12),
            _roleControl(context),
            const SizedBox(height: 12),
            _statusControl(context),
          ],
          if (_canManageDevices) ...[
            const SizedBox(height: 12),
            _deviceSection(context),
          ],
        ],
      ),
    );
  }

  Widget _roleControl(BuildContext context) {
    final current = _firstRole(_account);
    final enabled =
        !_mutating &&
        !_isOwnAccount &&
        _selectedRole != null &&
        _selectedRole != current;
    return Card(
      key: const Key('management-staff-role-control'),
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            Text('Staff role', style: Theme.of(context).textTheme.titleMedium),
            const SizedBox(height: 10),
            DropdownButtonFormField<String>(
              key: const Key('management-staff-role-picker'),
              initialValue: _selectedRole,
              items: managementStaffRoles
                  .map(
                    (role) => DropdownMenuItem(
                      value: role,
                      child: Text(_label(role)),
                    ),
                  )
                  .toList(growable: false),
              onChanged: _mutating
                  ? null
                  : (value) => setState(() => _selectedRole = value),
            ),
            const SizedBox(height: 10),
            FilledButton(
              key: const Key('management-staff-role-save'),
              onPressed: enabled ? _changeRole : null,
              child: const Text('Change role'),
            ),
          ],
        ),
      ),
    );
  }

  Widget _statusControl(BuildContext context) {
    final requested = _selectedStatus;
    final selfDestructive =
        _isOwnAccount && (requested == 'inactive' || requested == 'locked');
    final enabled =
        !_mutating &&
        !selfDestructive &&
        requested != null &&
        requested != _account.status;
    return Card(
      key: const Key('management-staff-status-control'),
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            Text(
              'Account status',
              style: Theme.of(context).textTheme.titleMedium,
            ),
            const SizedBox(height: 10),
            DropdownButtonFormField<String>(
              key: const Key('management-staff-status-picker'),
              initialValue: _selectedStatus,
              items: managementAccountStatuses
                  .map(
                    (status) => DropdownMenuItem(
                      value: status,
                      child: Text(_label(status)),
                    ),
                  )
                  .toList(growable: false),
              onChanged: _mutating
                  ? null
                  : (value) => setState(() => _selectedStatus = value),
            ),
            const SizedBox(height: 10),
            FilledButton(
              key: const Key('management-staff-status-save'),
              onPressed: enabled ? _changeStatus : null,
              child: const Text('Change account status'),
            ),
          ],
        ),
      ),
    );
  }

  Widget _deviceSection(BuildContext context) {
    return Card(
      key: const Key('management-staff-devices-section'),
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            Text(
              'Registered phones',
              style: Theme.of(context).textTheme.titleMedium,
            ),
            const SizedBox(height: 10),
            if (_devices.isEmpty)
              const Text('No registered phones returned by the server.')
            else
              for (var index = 0; index < _devices.length; index++) ...[
                _deviceTile(_devices[index], index),
                if (index != _devices.length - 1) const Divider(),
              ],
          ],
        ),
      ),
    );
  }

  Widget _deviceTile(ManagementDevice device, int index) {
    final requested = switch (device.status) {
      'pending' => 'active',
      'active' => 'revoked',
      'revoked' => 'active',
      _ => device.status,
    };
    final actionLabel = switch ((device.status, requested)) {
      ('pending', 'active') => 'Approve phone',
      ('active', 'revoked') => 'Revoke phone',
      ('revoked', 'active') => 'Restore phone',
      _ => 'Keep current status',
    };
    final selfRevocation =
        _isOwnAccount && device.status == 'active' && requested == 'revoked';
    final enabled = !_mutating && !selfRevocation && requested != device.status;
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Text(_label(device.platform)),
        const SizedBox(height: 3),
        Text('Status: ${_label(device.status)}'),
        const SizedBox(height: 8),
        OutlinedButton(
          key: index == 0
              ? const Key('management-device-action')
              : Key('management-device-action-$index'),
          onPressed: enabled ? () => _changeDevice(device) : null,
          child: Text(actionLabel),
        ),
      ],
    );
  }
}

class _DetailMessage extends StatelessWidget {
  const _DetailMessage({
    required super.key,
    required this.title,
    required this.message,
    this.actions = const <Widget>[],
  });

  final String title;
  final String message;
  final List<Widget> actions;

  @override
  Widget build(BuildContext context) {
    return Center(
      child: SingleChildScrollView(
        padding: const EdgeInsets.all(24),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            const Icon(Icons.lock_outline, size: 42),
            const SizedBox(height: 12),
            Text(title, style: Theme.of(context).textTheme.titleLarge),
            const SizedBox(height: 8),
            Text(message, textAlign: TextAlign.center),
            if (actions.isNotEmpty) ...[
              const SizedBox(height: 16),
              Wrap(spacing: 8, children: actions),
            ],
          ],
        ),
      ),
    );
  }
}

String _label(String value) {
  if (value.isEmpty) {
    return value;
  }
  return '${value[0].toUpperCase()}${value.substring(1)}';
}

String? _firstRole(ManagementStaffAccount account) {
  return account.roles.isEmpty ? null : account.roles.first;
}
