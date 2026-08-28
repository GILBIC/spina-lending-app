import 'dart:async';

import 'package:flutter/material.dart';
import 'package:gilbic_mobile/src/core/auth/user_session.dart';
import 'package:gilbic_mobile/src/core/device/device_identity.dart';
import 'package:gilbic_mobile/src/core/management/management_administration.dart';
import 'package:gilbic_mobile/src/core/management/management_administration_repository.dart';
import 'package:gilbic_mobile/src/core/network/spina_api.dart';
import 'package:gilbic_mobile/src/features/management/management_staff_detail_page.dart';
import 'package:gilbic_mobile/src/features/management/management_staff_invite_page.dart';

class ManagementStaffDevicesPage extends StatefulWidget {
  const ManagementStaffDevicesPage({
    required this.session,
    required this.deviceIdentityProvider,
    this.repository,
    super.key,
  });

  final UserSession session;
  final DeviceIdentityProvider deviceIdentityProvider;
  final ManagementAdministrationRepository? repository;

  @override
  State<ManagementStaffDevicesPage> createState() =>
      _ManagementStaffDevicesPageState();
}

class _ManagementStaffDevicesPageState
    extends State<ManagementStaffDevicesPage> {
  static const int _pageSize = 50;
  static const Duration _searchDelay = Duration(milliseconds: 350);

  late final ManagementAdministrationRepository _repository;
  final TextEditingController _searchController = TextEditingController();
  final List<ManagementStaffAccount> _items = <ManagementStaffAccount>[];
  Timer? _searchTimer;
  String? _deviceId;
  String _query = '';
  String? _role;
  String? _status;
  String? _errorMessage;
  int _nextOffset = 0;
  int _requestGeneration = 0;
  bool _hasMore = false;
  bool _loading = true;
  bool _loadingMore = false;
  bool _permissionDenied = false;

  bool get _hasFilters =>
      _query.trim().isNotEmpty || _role != null || _status != null;

  @override
  void initState() {
    super.initState();
    _repository =
        widget.repository ?? SpinaManagementAdministrationRepository();
    unawaited(_initialize());
  }

  @override
  void dispose() {
    _requestGeneration += 1;
    _searchTimer?.cancel();
    _searchController.dispose();
    super.dispose();
  }

  Future<void> _initialize() async {
    try {
      final identity = await widget.deviceIdentityProvider.load();
      if (!mounted) {
        return;
      }
      _deviceId = identity.installationId;
      await _load(reset: true);
    } on Object catch (error) {
      if (!mounted) {
        return;
      }
      setState(() {
        _loading = false;
        _permissionDenied = false;
        _errorMessage = error is SpinaApiException
            ? error.message
            : 'This installation identity could not be loaded.';
      });
    }
  }

  Future<void> _load({required bool reset}) async {
    final deviceId = _deviceId;
    if (deviceId == null) {
      return;
    }
    final generation = ++_requestGeneration;
    final offset = reset ? 0 : _nextOffset;
    setState(() {
      _errorMessage = null;
      _permissionDenied = false;
      if (reset) {
        _items.clear();
        _nextOffset = 0;
        _hasMore = false;
        _loading = true;
        _loadingMore = false;
      } else {
        _loadingMore = true;
      }
    });

    try {
      final page = await _repository.loadStaff(
        widget.session,
        deviceId: deviceId,
        query: _query.trim().isEmpty ? null : _query.trim(),
        role: _role,
        status: _status,
        limit: _pageSize,
        offset: offset,
      );
      if (!mounted || generation != _requestGeneration) {
        return;
      }
      setState(() {
        if (reset) {
          _items
            ..clear()
            ..addAll(_deduplicated(page.items));
        } else {
          final knownIds = _items.map((item) => item.id).toSet();
          _items.addAll(page.items.where((item) => knownIds.add(item.id)));
        }
        _nextOffset = page.nextOffset;
        _hasMore = page.hasMore;
        _loading = false;
        _loadingMore = false;
      });
    } on Object catch (error) {
      if (!mounted || generation != _requestGeneration) {
        return;
      }
      final message = error is SpinaApiException
          ? error.message
          : 'The staff directory could not be loaded.';
      if (!reset && _items.isNotEmpty) {
        setState(() => _loadingMore = false);
        ScaffoldMessenger.of(
          context,
        ).showSnackBar(SnackBar(content: Text(message)));
        return;
      }
      setState(() {
        _loading = false;
        _loadingMore = false;
        _errorMessage = message;
        _permissionDenied =
            error is SpinaApiException && error.statusCode == 403;
      });
    }
  }

  List<ManagementStaffAccount> _deduplicated(
    List<ManagementStaffAccount> values,
  ) {
    final ids = <String>{};
    return values.where((item) => ids.add(item.id)).toList(growable: false);
  }

  Future<void> _refresh() {
    _searchTimer?.cancel();
    return _load(reset: true);
  }

  void _onSearchChanged(String value) {
    _query = value;
    _searchTimer?.cancel();
    _searchTimer = Timer(_searchDelay, () {
      if (mounted) {
        unawaited(_load(reset: true));
      }
    });
  }

  void _setRole(String? value) {
    setState(() => _role = value);
    unawaited(_load(reset: true));
  }

  void _setStatus(String? value) {
    setState(() => _status = value);
    unawaited(_load(reset: true));
  }

  void _clearFilters() {
    _searchTimer?.cancel();
    _searchController.clear();
    setState(() {
      _query = '';
      _role = null;
      _status = null;
    });
    unawaited(_load(reset: true));
  }

  Future<void> _openInvite() async {
    final account = await Navigator.of(context).push<ManagementStaffAccount>(
      MaterialPageRoute<ManagementStaffAccount>(
        builder: (_) => ManagementStaffInvitePage(
          session: widget.session,
          repository: _repository,
          deviceIdentityProvider: widget.deviceIdentityProvider,
          onUncertainResult: _refresh,
        ),
      ),
    );
    if (!mounted || account == null) {
      return;
    }
    setState(() {
      _items.removeWhere((item) => item.id == account.id);
      _items.insert(0, account);
    });
  }

  Future<void> _openDetail(ManagementStaffAccount account) async {
    await Navigator.of(context).push<void>(
      MaterialPageRoute<void>(
        builder: (_) => ManagementStaffDetailPage(
          session: widget.session,
          account: account,
          repository: _repository,
          deviceIdentityProvider: widget.deviceIdentityProvider,
          reloadAccount: () => _reloadAccount(account),
          onDirectoryRefresh: _refresh,
        ),
      ),
    );
  }

  Future<ManagementStaffAccount> _reloadAccount(
    ManagementStaffAccount account,
  ) async {
    final deviceId = _deviceId;
    if (deviceId == null) {
      throw const SpinaApiException(
        'This installation identity is unavailable.',
        code: 'network_unavailable',
      );
    }
    final page = await _repository.loadStaff(
      widget.session,
      deviceId: deviceId,
      query: account.username,
      limit: _pageSize,
      offset: 0,
    );
    final fresh = page.items.where((item) => item.id == account.id).firstOrNull;
    if (fresh == null) {
      throw const SpinaApiException(
        'This staff record is no longer available.',
        statusCode: 404,
      );
    }
    if (mounted) {
      setState(() {
        final index = _items.indexWhere((item) => item.id == fresh.id);
        if (index >= 0) {
          _items[index] = fresh;
        }
      });
    }
    return fresh;
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('Staff & devices'),
        actions: [
          if (widget.session.hasPermission('account.manage'))
            IconButton(
              key: const Key('management-staff-invite'),
              tooltip: 'Invite staff',
              onPressed: _openInvite,
              icon: const Icon(Icons.person_add_alt_1_outlined),
            ),
        ],
      ),
      body: SafeArea(
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            Padding(
              padding: const EdgeInsets.fromLTRB(16, 12, 16, 8),
              child: Text(
                'Server permissions control which staff and device actions '
                'are available to this Management account.',
                style: Theme.of(context).textTheme.bodyMedium,
              ),
            ),
            Padding(
              padding: const EdgeInsets.symmetric(horizontal: 16),
              child: TextField(
                key: const Key('management-staff-search'),
                controller: _searchController,
                onChanged: _onSearchChanged,
                textInputAction: TextInputAction.search,
                decoration: const InputDecoration(
                  labelText: 'Search staff',
                  hintText: 'Name, username, or email',
                  prefixIcon: Icon(Icons.search),
                ),
              ),
            ),
            Padding(
              padding: const EdgeInsets.fromLTRB(16, 10, 16, 8),
              child: Wrap(
                spacing: 8,
                runSpacing: 8,
                crossAxisAlignment: WrapCrossAlignment.center,
                children: [
                  SizedBox(
                    width: 156,
                    child: DropdownButtonFormField<String>(
                      key: const Key('management-staff-role-filter'),
                      initialValue: _role,
                      isExpanded: true,
                      decoration: const InputDecoration(labelText: 'Role'),
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
                      onChanged: _loading ? null : _setRole,
                    ),
                  ),
                  SizedBox(
                    width: 156,
                    child: DropdownButtonFormField<String>(
                      key: const Key('management-staff-status-filter'),
                      initialValue: _status,
                      isExpanded: true,
                      decoration: const InputDecoration(labelText: 'Status'),
                      items: const <DropdownMenuItem<String>>[
                        DropdownMenuItem(
                          value: 'active',
                          child: Text('Active'),
                        ),
                        DropdownMenuItem(
                          value: 'inactive',
                          child: Text('Inactive'),
                        ),
                        DropdownMenuItem(
                          value: 'locked',
                          child: Text('Locked'),
                        ),
                        DropdownMenuItem(
                          value: 'pending',
                          child: Text('Pending'),
                        ),
                      ],
                      onChanged: _loading ? null : _setStatus,
                    ),
                  ),
                  if (_hasFilters)
                    TextButton.icon(
                      key: const Key('management-staff-clear-filters'),
                      onPressed: _loading ? null : _clearFilters,
                      icon: const Icon(Icons.filter_alt_off_outlined),
                      label: const Text('Clear'),
                    ),
                ],
              ),
            ),
            Expanded(child: _buildState(context)),
          ],
        ),
      ),
    );
  }

  Widget _buildState(BuildContext context) {
    if (_loading) {
      return const Center(
        key: Key('management-staff-loading'),
        child: CircularProgressIndicator(),
      );
    }
    if (_permissionDenied) {
      return _PermissionDeniedState(
        onRefresh: _refresh,
        onBack: () => Navigator.of(context).maybePop(),
      );
    }
    if (_errorMessage != null) {
      return _MessageState(
        key: const Key('management-staff-error'),
        icon: Icons.cloud_off_outlined,
        title: 'Staff directory unavailable',
        message: _errorMessage!,
        action: FilledButton.icon(
          key: const Key('management-staff-retry'),
          onPressed: _refresh,
          icon: const Icon(Icons.refresh),
          label: const Text('Retry'),
        ),
      );
    }
    if (_items.isEmpty) {
      return _MessageState(
        key: Key(
          _hasFilters
              ? 'management-staff-filtered-empty'
              : 'management-staff-empty',
        ),
        icon: _hasFilters ? Icons.manage_search_outlined : Icons.people_outline,
        title: _hasFilters ? 'No matching staff' : 'No staff accounts yet',
        message: _hasFilters
            ? 'Try a different search or clear the filters.'
            : 'Staff accounts returned by the server will appear here.',
        action: _hasFilters
            ? TextButton(
                onPressed: _clearFilters,
                child: const Text('Clear filters'),
              )
            : null,
      );
    }
    return RefreshIndicator(
      onRefresh: _refresh,
      child: ListView.separated(
        key: const Key('management-staff-list'),
        physics: const AlwaysScrollableScrollPhysics(),
        padding: const EdgeInsets.fromLTRB(16, 4, 16, 24),
        itemCount: _items.length + (_hasMore ? 1 : 0),
        separatorBuilder: (_, __) => const SizedBox(height: 8),
        itemBuilder: (context, index) {
          if (index == _items.length) {
            return Center(
              child: OutlinedButton.icon(
                key: const Key('management-staff-load-more'),
                onPressed: _loadingMore ? null : () => _load(reset: false),
                icon: _loadingMore
                    ? const SizedBox.square(
                        dimension: 16,
                        child: CircularProgressIndicator(strokeWidth: 2),
                      )
                    : const Icon(Icons.expand_more),
                label: Text(_loadingMore ? 'Loading...' : 'Load more'),
              ),
            );
          }
          return _StaffCard(
            key: index == 0
                ? const Key('management-staff-open')
                : Key('management-staff-open-$index'),
            account: _items[index],
            onTap: () => _openDetail(_items[index]),
          );
        },
      ),
    );
  }
}

class _StaffCard extends StatelessWidget {
  const _StaffCard({required this.account, required this.onTap, super.key});

  final ManagementStaffAccount account;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    final role = account.roles.map(_label).join(', ');
    final devices = account.deviceCount == 1
        ? '1 device'
        : '${account.deviceCount} devices';
    return Card(
      margin: EdgeInsets.zero,
      clipBehavior: Clip.antiAlias,
      child: InkWell(
        onTap: onTap,
        child: Padding(
          padding: const EdgeInsets.all(16),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text(
                account.fullName,
                style: Theme.of(context).textTheme.titleMedium,
              ),
              const SizedBox(height: 3),
              Text('@${account.username}'),
              const SizedBox(height: 10),
              Wrap(
                spacing: 8,
                runSpacing: 6,
                crossAxisAlignment: WrapCrossAlignment.center,
                children: [
                  Chip(label: Text(role)),
                  Chip(label: Text(_label(account.status))),
                  Row(
                    mainAxisSize: MainAxisSize.min,
                    children: [
                      const Icon(Icons.devices_outlined, size: 18),
                      const SizedBox(width: 5),
                      Text(devices),
                    ],
                  ),
                ],
              ),
            ],
          ),
        ),
      ),
    );
  }
}

class _PermissionDeniedState extends StatelessWidget {
  const _PermissionDeniedState({required this.onRefresh, required this.onBack});

  final Future<void> Function() onRefresh;
  final VoidCallback onBack;

  @override
  Widget build(BuildContext context) {
    return _MessageState(
      key: const Key('management-staff-permission-denied'),
      icon: Icons.lock_outline,
      title: 'Permission required',
      message:
          'Your current server permissions no longer allow this directory.',
      action: Wrap(
        alignment: WrapAlignment.center,
        spacing: 8,
        children: [
          FilledButton.icon(
            key: const Key('management-staff-permission-refresh'),
            onPressed: onRefresh,
            icon: const Icon(Icons.refresh),
            label: const Text('Refresh'),
          ),
          TextButton.icon(
            key: const Key('management-staff-permission-back'),
            onPressed: onBack,
            icon: const Icon(Icons.arrow_back),
            label: const Text('Back'),
          ),
        ],
      ),
    );
  }
}

class _MessageState extends StatelessWidget {
  const _MessageState({
    required super.key,
    required this.icon,
    required this.title,
    required this.message,
    this.action,
  });

  final IconData icon;
  final String title;
  final String message;
  final Widget? action;

  @override
  Widget build(BuildContext context) {
    return Center(
      child: SingleChildScrollView(
        padding: const EdgeInsets.all(24),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            Icon(icon, size: 42),
            const SizedBox(height: 12),
            Text(title, style: Theme.of(context).textTheme.titleLarge),
            const SizedBox(height: 8),
            Text(message, textAlign: TextAlign.center),
            if (action != null) ...[const SizedBox(height: 16), action!],
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

extension on Iterable<ManagementStaffAccount> {
  ManagementStaffAccount? get firstOrNull {
    final iterator = this.iterator;
    return iterator.moveNext() ? iterator.current : null;
  }
}
