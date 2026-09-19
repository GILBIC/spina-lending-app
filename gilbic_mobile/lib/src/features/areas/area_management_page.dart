import 'package:flutter/material.dart';
import 'package:gilbic_mobile/src/core/areas/area_repository.dart';
import 'package:gilbic_mobile/src/core/auth/app_role.dart';
import 'package:gilbic_mobile/src/core/auth/user_session.dart';
import 'package:gilbic_mobile/src/core/device/device_identity.dart';
import 'package:gilbic_mobile/src/core/network/spina_api.dart';
import 'package:gilbic_mobile/src/core/network/staff_operations_client.dart';

class AreaManagementPage extends StatefulWidget {
  const AreaManagementPage({
    required this.session,
    required this.deviceIdentityProvider,
    this.repository,
    super.key,
  });
  final UserSession session;
  final DeviceIdentityProvider deviceIdentityProvider;
  final AreaRepository? repository;
  @override
  State<AreaManagementPage> createState() => _AreaManagementPageState();
}

class _AreaManagementPageState extends State<AreaManagementPage> {
  late final AreaRepository _repository =
      widget.repository ??
      AreaRepository(deviceIdentityProvider: widget.deviceIdentityProvider);
  final _search = TextEditingController();
  List<AreaNode> _areas = [];
  List<Map<String, dynamic>> _clients = [];
  String? _selectedId, _error, _notice;
  bool _busy = false,
      _ready = false,
      _uncertain = false,
      _attemptedWrite = false;
  UserSession get _session => widget.session;
  bool get _canWrite => !_busy && _ready && !_uncertain;
  AreaNode? get _selected {
    for (final node in _areas) {
      if (node.id == _selectedId) return node;
    }
    return null;
  }

  @override
  void initState() {
    super.initState();
    _refresh();
  }

  @override
  void dispose() {
    _areas = [];
    _clients = [];
    _search.dispose();
    if (widget.repository == null) _repository.close();
    super.dispose();
  }

  Future<void> _readTree() async {
    _ready = false;
    final areas = await _repository.tree(_session);
    if (!mounted) return;
    _areas = areas;
    if (!_areas.any((a) => a.id == _selectedId)) _selectedId = null;
    _ready = true;
  }

  Future<void> _operate(Future<void> Function() action) async {
    if (_busy) return;
    setState(() {
      _busy = true;
      _error = null;
      _notice = null;
      _attemptedWrite = false;
    });
    try {
      await action();
    } catch (error) {
      if (!mounted) return;
      _error = staffError(error);
      if (_attemptedWrite) {
        _uncertain = true;
        _ready = false;
      }
      if (staffAccessRejected(error)) {
        _search.clear();
        _areas = [];
        _clients = [];
        _selectedId = null;
        _ready = false;
      }
    } finally {
      if (mounted) {
        setState(() {
          _busy = false;
        });
      }
    }
  }

  Future<void> _refresh() => _operate(() async {
    _areas = [];
    _clients = [];
    _ready = false;
    await _readTree();
  });
  Future<Map<String, dynamic>> _change(
    Future<Map<String, dynamic>> Function() action,
  ) async {
    _attemptedWrite = true;
    final result = await action();
    _ready = false;
    await _readTree();
    if (!mounted) return result;
    _clients = [];
    _notice = 'Area records refreshed from the server.';
    return result;
  }

  Future<bool> _confirm(String title, String details) async {
    if (!mounted) return false;
    return await showDialog<bool>(
          context: context,
          builder: (c) => AlertDialog(
            title: Text(title),
            content: SingleChildScrollView(child: Text(details)),
            actions: [
              TextButton(
                onPressed: () => Navigator.pop(c, false),
                child: const Text('Cancel'),
              ),
              FilledButton(
                onPressed: () => Navigator.pop(c, true),
                child: const Text('Confirm'),
              ),
            ],
          ),
        ) ==
        true;
  }

  Future<String?> _name(String title, {String initial = ''}) async {
    var value = initial;
    return showDialog<String>(
      context: context,
      builder: (c) => AlertDialog(
        title: Text(title),
        content: TextFormField(
          initialValue: initial,
          onChanged: (text) => value = text,
          autofocus: true,
          maxLength: 200,
          decoration: const InputDecoration(labelText: 'Area name'),
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(c),
            child: const Text('Cancel'),
          ),
          FilledButton(
            onPressed: () {
              final name = value.trim();
              if (name.isNotEmpty) Navigator.pop(c, name);
            },
            child: const Text('Save'),
          ),
        ],
      ),
    );
  }

  Future<String?> _choose(String title, List<(String, String)> choices) async {
    if (!mounted) return null;
    return showDialog<String>(
      context: context,
      builder: (c) => SimpleDialog(
        title: Text(title),
        children: choices.isEmpty
            ? [
                const Padding(
                  padding: EdgeInsets.all(24),
                  child: Text('No eligible records available.'),
                ),
              ]
            : choices
                  .map(
                    (choice) => SimpleDialogOption(
                      onPressed: () => Navigator.pop(c, choice.$1),
                      child: Text(choice.$2),
                    ),
                  )
                  .toList(),
      ),
    );
  }

  bool _descendant(AreaNode candidate, AreaNode ancestor) {
    var current = candidate;
    final visited = <String>{};
    while (visited.add(current.id)) {
      if (current.id == ancestor.id) return true;
      final parents = _areas.where((a) => a.id == current.parentId);
      if (parents.isEmpty) return false;
      current = parents.first;
    }
    return true;
  }

  Future<void> _create(AreaNode? parent) => _operate(() async {
    final name = await _name(
      parent == null
          ? 'Create city / municipality'
          : 'Create child in ${parent.path}',
    );
    if (name == null || !mounted) return;
    await _change(() => _repository.create(_session, name, parent?.id));
  });
  Future<void> _rename(AreaNode area) => _operate(() async {
    final name = await _name('Rename ${area.path}', initial: area.name);
    if (name == null || !mounted || name == area.name) return;
    await _change(() => _repository.rename(_session, area.id, name));
  });
  Future<void> _move(AreaNode area) => _operate(() async {
    final choice = await _choose('Move under', [
      ('', 'Top level — city / municipality'),
      ..._areas
          .where((a) => a.active && !a.legacy && !_descendant(a, area))
          .map((a) => (a.id, a.path)),
    ]);
    if (choice == null || !mounted) return;
    final parent = choice.isEmpty ? null : choice;
    final preview = await _repository.movePreview(_session, area.id, parent);
    if (!await _confirm('Review area move', _moveSummary(preview))) return;
    await _change(() => _repository.move(_session, area.id, parent));
  });
  String _moveSummary(Map<String, dynamic> p) => [
    'From: ${requiredStaffText(p, 'old_path')}',
    'To: ${requiredStaffText(p, 'new_path')}',
    'Affected areas: ${_count(p, 'affected_node_count')}',
    'Affected clients: ${_count(p, 'clients_affected')}',
    'Collector before: ${firstNonEmptyString([stringMap(p['effective_collector_before'])['full_name']]) ?? 'Unassigned'}',
    'Collector after: ${firstNonEmptyString([stringMap(p['effective_collector_after'])['full_name']]) ?? 'Unassigned'}',
    'Stale delegated access: ${_count(p, 'stale_delegated_access_count')}',
    'The server will recheck current area rules when you confirm.',
  ].join('\n');
  String _count(Map<String, dynamic> p, String key) {
    if (p[key] is! int) {
      throw const SpinaApiException(
        'The server returned an incomplete area preview.',
      );
    }
    return p[key].toString();
  }

  Future<void> _order(AreaNode area, int delta) => _operate(() async {
    final siblings = _areas.where((a) => a.parentId == area.parentId).toList()
      ..sort((a, b) => a.sortOrder.compareTo(b.sortOrder));
    final index = siblings.indexWhere((a) => a.id == area.id);
    final next = index + delta;
    if (index < 0 || next < 0 || next >= siblings.length) return;
    siblings[index] = siblings[next];
    siblings[next] = area;
    if (!await _confirm(
      'Change area order?',
      siblings.map((a) => a.name).join('\n'),
    )) {
      return;
    }
    await _change(
      () => _repository.reorder(
        _session,
        area.parentId,
        siblings.map((a) => a.id).toList(),
      ),
    );
  });
  Future<void> _assign(AreaNode area) => _operate(() async {
    final collectors = await _repository.collectors(_session);
    if (!mounted) return;
    final id = await _choose(
      'Assign collector to ${area.path}',
      collectors
          .map(
            (c) => (
              requiredStaffText(c, 'user_id'),
              '${requiredStaffText(c, 'full_name')} · ${requiredStaffText(c, 'username')}',
            ),
          )
          .toList(),
    );
    if (id == null || !mounted) return;
    if (!await _confirm(
      'Assign collector?',
      'Replace the direct collector assignment for ${area.path}. Descendant areas without their own assignment inherit this collector.',
    )) {
      return;
    }
    await _change(() => _repository.assignCollector(_session, area.id, id));
  });
  Future<void> _remove(AreaNode area) => _operate(() async {
    if (!await _confirm(
      'Remove direct collector?',
      '${area.path}\nThis area will inherit its parent collector where available. The server checks active client coverage.',
    )) {
      return;
    }
    await _change(() => _repository.removeCollector(_session, area.id));
  });
  Future<void> _retire(AreaNode area) => _operate(() async {
    final preview = await _repository.retirementPreview(_session, area.id);
    final details = [
      requiredStaffText(preview, 'full_path'),
      'Active clients in subtree: ${_count(preview, 'active_subtree_client_count')}',
      'Active collector assignments: ${_count(preview, 'active_collector_assignment_count')}',
      'Pending transfer targets: ${_count(preview, 'pending_transfer_target_count')}',
      'Active descendants: ${_count(preview, 'active_descendant_count')}',
      'The server blocks retirement when these dependencies remain.',
    ].join('\n');
    if (!await _confirm(
      area.active ? 'Retire area?' : 'Reactivate area?',
      details,
    )) {
      return;
    }
    await _change(
      () => area.active
          ? _repository.retire(_session, area.id)
          : _repository.reactivate(_session, area.id),
    );
  });
  Future<void> _searchClients() => _operate(() async {
    _clients = [];
    final query = _search.text.trim();
    if (query.isEmpty) {
      _error = 'Enter a borrower name or code.';
      return;
    }
    final clients = await _repository.clients(_session, query);
    if (!mounted) return;
    for (final client in clients) {
      requiredStaffText(client, 'client_id');
      requiredStaffText(client, 'full_name');
    }
    _clients = clients;
    if (clients.isEmpty) _notice = 'No borrowers matched.';
  });
  Future<void> _transfer(Map<String, dynamic> client) => _operate(() async {
    final area = await _choose(
      'Transfer borrower to',
      _areas
          .where((a) => a.active && !a.legacy)
          .map((a) => (a.id, a.path))
          .toList(),
    );
    if (area == null || !mounted) return;
    final id = requiredStaffText(client, 'client_id');
    final preview = await _repository.transferPreview(_session, id, area);
    final date = requiredStaffText(preview, 'effective_date');
    final details = [
      requiredStaffText(client, 'full_name'),
      'From: ${preview['old_area_path']?.toString() ?? 'Unassigned'}',
      'To: ${requiredStaffText(preview, 'new_area_path')}',
      'Effective: $date',
      'Timing: ${requiredStaffText(preview, 'timing').replaceAll('_', ' ')}',
    ].join('\n');
    if (!await _confirm('Review borrower transfer', details)) return;
    final result = await _change(
      () => _repository.transfer(_session, id, area),
    );
    _notice =
        'Transfer recorded. Effective: ${requiredStaffText(result, 'effective_date')}.';
  });
  @override
  Widget build(BuildContext context) {
    final area = _selected;
    final manage = _session.hasPermission('area.manage');
    final assign = _session.hasPermission('area.collector.assign');
    final retire =
        _session.role == AppRole.management &&
        _session.hasPermission('area.retire');
    return Scaffold(
      appBar: AppBar(
        title: const Text('Area management'),
        actions: [
          IconButton(
            key: const Key('areas-refresh'),
            tooltip: 'Refresh areas',
            onPressed: _busy ? null : _refresh,
            icon: const Icon(Icons.refresh),
          ),
        ],
      ),
      body: SafeArea(
        child: ListView(
          padding: const EdgeInsets.all(16),
          children: [
            const Text(
              'City / municipality → Barangay → Subarea. Changes require the live server.',
            ),
            if (_busy) const LinearProgressIndicator(),
            if (_error != null)
              Padding(
                padding: const EdgeInsets.symmetric(vertical: 12),
                child: Text(
                  _error!,
                  style: TextStyle(color: Theme.of(context).colorScheme.error),
                ),
              ),
            if (_notice != null) Text(_notice!),
            if (_uncertain)
              Card(
                child: Padding(
                  padding: const EdgeInsets.all(12),
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      const Text(
                        'The previous action was not confirmed. Refresh and check the area or borrower record before making another change. Nothing will be retried automatically.',
                      ),
                      TextButton(
                        key: const Key('areas-reconciled'),
                        onPressed: !_busy && _ready
                            ? () async {
                                if (await _confirm(
                                  'Continue after checking?',
                                  'Confirm you checked the refreshed area and borrower records and understand the previous action may already have completed.',
                                )) {
                                  if (mounted) {
                                    setState(() {
                                      _uncertain = false;
                                    });
                                  }
                                }
                              }
                            : null,
                        child: const Text('I checked the current records'),
                      ),
                    ],
                  ),
                ),
              ),
            if (manage)
              FilledButton.icon(
                key: const Key('areas-create'),
                onPressed: _canWrite ? () => _create(null) : null,
                icon: const Icon(Icons.add),
                label: const Text('Create city / municipality'),
              ),
            if (_ready && _areas.isEmpty) const Text('No areas created yet.'),
            for (final node in _areas)
              Card(
                child: ListTile(
                  key: Key('area-${node.id}'),
                  selected: node.id == _selectedId,
                  title: Text(node.path),
                  subtitle: Text(
                    '${node.active ? 'Active' : 'Retired'} · ${node.clients} clients\nCollector: ${node.effectiveCollector ?? 'Unassigned'}${node.explicitCollector == null ? ' (inherited)' : ' (direct)'}',
                  ),
                  trailing: Icon(
                    node.id == _selectedId
                        ? Icons.check_circle
                        : Icons.chevron_right,
                  ),
                  onTap: _busy
                      ? null
                      : () => setState(() {
                          _selectedId = node.id;
                        }),
                ),
              ),
            if (area != null)
              Card(
                child: Padding(
                  padding: const EdgeInsets.all(12),
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text(
                        area.path,
                        style: Theme.of(context).textTheme.titleMedium,
                      ),
                      if (area.legacy)
                        const Text(
                          'Legacy unmapped area. Transfer borrowers to an active area.',
                        ),
                      Wrap(
                        spacing: 8,
                        runSpacing: 8,
                        children: [
                          if (manage && area.active && !area.legacy) ...[
                            OutlinedButton(
                              onPressed: _canWrite ? () => _create(area) : null,
                              child: const Text('Add child'),
                            ),
                            OutlinedButton(
                              onPressed: _canWrite ? () => _rename(area) : null,
                              child: const Text('Rename'),
                            ),
                            OutlinedButton(
                              onPressed: _canWrite ? () => _move(area) : null,
                              child: const Text('Move area'),
                            ),
                          ],
                          if (manage && !area.legacy) ...[
                            OutlinedButton(
                              onPressed: _canWrite
                                  ? () => _order(area, -1)
                                  : null,
                              child: const Text('Order up'),
                            ),
                            OutlinedButton(
                              onPressed: _canWrite
                                  ? () => _order(area, 1)
                                  : null,
                              child: const Text('Order down'),
                            ),
                          ],
                          if (assign && area.active && !area.legacy) ...[
                            OutlinedButton(
                              onPressed: _canWrite ? () => _assign(area) : null,
                              child: const Text('Assign collector'),
                            ),
                            if (area.explicitCollector != null)
                              OutlinedButton(
                                onPressed: _canWrite
                                    ? () => _remove(area)
                                    : null,
                                child: const Text('Remove collector'),
                              ),
                          ],
                          if (retire && !area.legacy)
                            OutlinedButton(
                              onPressed: _canWrite ? () => _retire(area) : null,
                              child: Text(
                                area.active ? 'Retire' : 'Reactivate',
                              ),
                            ),
                        ],
                      ),
                    ],
                  ),
                ),
              ),
            if (_session.hasPermission('area.client.assign')) ...[
              const SizedBox(height: 16),
              Text(
                'Borrower area transfer',
                style: Theme.of(context).textTheme.titleLarge,
              ),
              TextField(
                controller: _search,
                enabled: !_busy,
                maxLength: 200,
                decoration: const InputDecoration(
                  labelText: 'Borrower name or code',
                ),
                onSubmitted: (_) {
                  if (!_busy) _searchClients();
                },
              ),
              OutlinedButton(
                onPressed: _busy ? null : _searchClients,
                child: const Text('Search borrowers'),
              ),
              for (final client in _clients)
                ListTile(
                  title: Text(requiredStaffText(client, 'full_name')),
                  subtitle: Text(
                    '${client['client_code']?.toString() ?? ''} · ${client['area_path']?.toString() ?? 'Unassigned'}',
                  ),
                  trailing: TextButton(
                    onPressed: _canWrite ? () => _transfer(client) : null,
                    child: const Text('Transfer'),
                  ),
                ),
              if (_clients.length == 100)
                const Text(
                  'Showing the first 100 matches. Refine your search.',
                ),
            ],
          ],
        ),
      ),
    );
  }
}
