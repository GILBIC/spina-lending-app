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
  bool _stateUncertain = false;
  bool _permissionDenied = false;
  bool _recordMissing = false;

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
    if (mounted) {
      setState(() {
        _loading = true;
        _permissionDenied = false;
        _recordMissing = false;
        _error = null;
      });
    }
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
        _recordMissing = false;
      });
    } on SpinaApiException catch (error) {
      final recordMissing = error.statusCode == 404;
      final directoryRefreshed = recordMissing
          ? await _refreshDirectoryAfterMissing()
          : false;
      if (!mounted) {
        return;
      }
      setState(() {
        _loading = false;
        _permissionDenied = error.statusCode == 403;
        _recordMissing = recordMissing;
        _error = recordMissing
            ? _missingRecordMessage(directoryRefreshed)
            : error.message;
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

  Future<void> _retryInitialLoad() => _initialize();

  Future<bool> _refreshDirectoryAfterMissing() async {
    try {
      await widget.onDirectoryRefresh();
      return true;
    } on Object {
      return false;
    }
  }

  Future<bool> _reloadCurrent({required bool clearMessages}) async {
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
        return false;
      }
      setState(() {
        _account = fresh;
        _selectedRole = _firstRole(fresh);
        _selectedStatus = fresh.status;
        _devices = devices;
        _stateUncertain = false;
        _permissionDenied = false;
        _recordMissing = false;
      });
      return true;
    } on SpinaApiException catch (error) {
      final recordMissing = error.statusCode == 404;
      final directoryRefreshed = recordMissing
          ? await _refreshDirectoryAfterMissing()
          : false;
      if (mounted) {
        setState(() {
          _permissionDenied = error.statusCode == 403;
          _recordMissing = recordMissing;
          _error = recordMissing
              ? _missingRecordMessage(directoryRefreshed)
              : error.message;
        });
      }
      return false;
    } on Object {
      if (mounted) {
        setState(
          () =>
              _error = 'The authoritative staff record could not be refreshed.',
        );
      }
      return false;
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
      destructive: true,
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
      destructive: requested == 'inactive' || requested == 'locked',
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
    final requested = _requestedDeviceStatus(device.status);
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
      destructive:
          requested == 'revoked' ||
          (device.status == 'pending' && _account.roles.contains('collector')),
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
    required bool destructive,
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
                style: destructive ? _destructiveFilledStyle(context) : null,
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
      var recovered = true;
      if (error.statusCode == 404) {
        recovered = await _refreshDirectoryAfterMissing();
      } else if (error.statusCode != 403) {
        recovered = await _reloadCurrent(clearMessages: false);
      }
      if (!mounted) {
        return;
      }
      if (_recordMissing && error.statusCode != 404) {
        setState(() {
          _mutating = false;
          _stateUncertain = false;
        });
        return;
      }
      setState(() {
        _mutating = false;
        _stateUncertain = error.statusCode == 404 ? false : !recovered;
        _permissionDenied = error.statusCode == 403;
        _recordMissing = error.statusCode == 404;
        _error = error.statusCode == 404
            ? _missingRecordMessage(recovered)
            : error.message;
      });
    } on Object {
      final recovered = await _reloadCurrent(clearMessages: false);
      if (!mounted) {
        return;
      }
      if (_recordMissing) {
        setState(() {
          _mutating = false;
          _stateUncertain = false;
        });
        return;
      }
      setState(() {
        _mutating = false;
        _stateUncertain = !recovered;
        _error = 'The change could not be confirmed by the server.';
      });
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
    if (_recordMissing) {
      return _DetailMessage(
        key: const Key('management-staff-detail-not-found'),
        title: 'Staff record unavailable',
        message:
            _error ??
            'This staff record is no longer available. The directory was refreshed.',
        actions: [
          TextButton.icon(
            key: const Key('management-staff-back'),
            onPressed: () => Navigator.of(context).maybePop(),
            icon: const Icon(Icons.arrow_back),
            label: const Text('Back to staff list'),
          ),
        ],
      );
    }
    if (_deviceId == null) {
      return _DetailMessage(
        key: const Key('management-staff-detail-load-error'),
        title: 'Staff record could not be loaded',
        message: _error ?? 'This installation identity could not be loaded.',
        actions: [
          FilledButton.icon(
            key: const Key('management-staff-detail-retry'),
            onPressed: _retryInitialLoad,
            icon: const Icon(Icons.refresh),
            label: const Text('Retry'),
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
                  const SizedBox(height: 10),
                  Text('Registered devices: ${_account.deviceCount}'),
                  const SizedBox(height: 3),
                  Text('Created: ${_formatTimestamp(_account.createdAt)}'),
                  const SizedBox(height: 3),
                  Text('Updated: ${_formatTimestamp(_account.updatedAt)}'),
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
          if (!_canManageAccounts && _canManageDevices) ...[
            const SizedBox(height: 12),
            const _PermissionExplanation(
              key: Key('management-staff-account-permission-explanation'),
              message:
                  'Your current server permissions allow phone administration, but not role or account-status changes.',
            ),
          ],
          if (!_canManageDevices && _canManageAccounts) ...[
            const SizedBox(height: 12),
            const _PermissionExplanation(
              key: Key('management-staff-device-permission-explanation'),
              message:
                  'Your current server permissions allow account administration, but not registered-phone details or changes.',
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
        !_stateUncertain &&
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
            if (_isOwnAccount) ...[
              const SizedBox(height: 6),
              const Text('You cannot change your own management role.'),
            ],
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
              onChanged: _mutating || _stateUncertain
                  ? null
                  : (value) => setState(() => _selectedRole = value),
            ),
            const SizedBox(height: 10),
            FilledButton(
              key: const Key('management-staff-role-save'),
              style: _destructiveFilledStyle(context),
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
        _isOwnAccount && requested != null && requested != 'active';
    final enabled =
        !_mutating &&
        !_stateUncertain &&
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
            if (_isOwnAccount) ...[
              const SizedBox(height: 6),
              const Text(
                'You cannot change your own account away from Active.',
              ),
            ],
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
              onChanged: _mutating || _stateUncertain
                  ? null
                  : (value) => setState(() => _selectedStatus = value),
            ),
            const SizedBox(height: 10),
            FilledButton(
              key: const Key('management-staff-status-save'),
              style: requested == 'inactive' || requested == 'locked'
                  ? _destructiveFilledStyle(context)
                  : null,
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
            if (_isOwnAccount) ...[
              const SizedBox(height: 6),
              const Text(
                'You cannot change phones for your own current account from this screen.',
              ),
            ],
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
    final requested = _requestedDeviceStatus(device.status);
    final actionLabel = switch ((device.status, requested)) {
      ('pending', 'active') => 'Approve phone',
      ('active', 'revoked') => 'Revoke phone',
      ('revoked', 'active') => 'Restore phone',
      _ => 'Keep current status',
    };
    final enabled =
        !_mutating &&
        !_stateUncertain &&
        !_isOwnAccount &&
        requested != device.status;
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Text(_label(device.platform)),
        const SizedBox(height: 3),
        Text('Status: ${_label(device.status)}'),
        const SizedBox(height: 3),
        Text('App version: ${device.appVersion ?? 'Not reported'}'),
        const SizedBox(height: 3),
        Text('Registered: ${_formatTimestamp(device.registeredAt)}'),
        const SizedBox(height: 3),
        Text(
          'Last seen: ${device.lastSeenAt == null ? 'Not yet reported' : _formatTimestamp(device.lastSeenAt!)}',
        ),
        const SizedBox(height: 8),
        OutlinedButton(
          key: index == 0
              ? const Key('management-device-action')
              : Key('management-device-action-$index'),
          style: requested == 'revoked'
              ? _destructiveOutlinedStyle(context)
              : null,
          onPressed: enabled ? () => _changeDevice(device) : null,
          child: Text(actionLabel),
        ),
      ],
    );
  }
}

String _missingRecordMessage(bool directoryRefreshed) {
  return directoryRefreshed
      ? 'This staff record is no longer available. The directory was refreshed.'
      : 'This staff record is no longer available. The staff list could not be refreshed.';
}

String _requestedDeviceStatus(String current) => switch (current) {
  'pending' => 'active',
  'active' => 'revoked',
  'revoked' => 'active',
  _ => current,
};

class _PermissionExplanation extends StatelessWidget {
  const _PermissionExplanation({required this.message, super.key});

  final String message;

  @override
  Widget build(BuildContext context) {
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(14),
        child: Row(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            const Icon(Icons.info_outline),
            const SizedBox(width: 10),
            Expanded(child: Text(message)),
          ],
        ),
      ),
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

String _formatTimestamp(DateTime value) {
  final utc = value.toUtc();
  String twoDigits(int number) => number.toString().padLeft(2, '0');
  return '${utc.year.toString().padLeft(4, '0')}-'
      '${twoDigits(utc.month)}-${twoDigits(utc.day)} '
      '${twoDigits(utc.hour)}:${twoDigits(utc.minute)} UTC';
}

ButtonStyle _destructiveFilledStyle(BuildContext context) {
  final colors = Theme.of(context).colorScheme;
  return FilledButton.styleFrom(
    backgroundColor: colors.error,
    foregroundColor: colors.onError,
  );
}

ButtonStyle _destructiveOutlinedStyle(BuildContext context) {
  final error = Theme.of(context).colorScheme.error;
  return OutlinedButton.styleFrom(
    foregroundColor: error,
    side: BorderSide(color: error),
  );
}
