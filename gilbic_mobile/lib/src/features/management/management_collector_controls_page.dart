import 'dart:convert';
import 'dart:math';
import 'package:flutter/material.dart';
import 'package:gilbic_mobile/src/core/auth/app_role.dart';
import 'package:gilbic_mobile/src/core/auth/user_session.dart';
import 'package:gilbic_mobile/src/core/device/device_identity.dart';
import 'package:gilbic_mobile/src/core/management/accounting_readiness_repository.dart';
import 'package:gilbic_mobile/src/core/management/collector_control_schedule.dart';
import 'package:gilbic_mobile/src/core/management/source_accounting_repository.dart';
import 'package:gilbic_mobile/src/core/network/spina_api.dart';

class ManagementCollectorControlsPage extends StatefulWidget {
  const ManagementCollectorControlsPage({
    required this.session,
    required this.deviceIdentityProvider,
    this.repository,
    super.key,
  });
  final UserSession session;
  final DeviceIdentityProvider deviceIdentityProvider;
  final SourceAccountingRepository? repository;
  @override
  State<ManagementCollectorControlsPage> createState() =>
      _ManagementCollectorControlsPageState();
}

class _ManagementCollectorControlsPageState
    extends State<ManagementCollectorControlsPage> {
  late SourceAccountingRepository _repository;
  late String _sessionScope;
  final _date = TextEditingController();
  int _generation = 0, _offset = 0;
  bool _busy = true, _denied = false;
  String? _error, _bookId;
  Map<String, dynamic>? _schedule;
  String _scope(UserSession user) => jsonEncode([
    user.userId,
    user.accessToken,
    user.roles,
    user.rawRole,
    user.permissions,
  ]);
  bool _current(int generation) =>
      mounted &&
      generation == _generation &&
      _sessionScope == _scope(widget.session);
  bool get _can =>
      widget.session.hasRole(AppRole.management) &&
      widget.session.hasPermission('accounting.view');
  @override
  void initState() {
    super.initState();
    _repository = widget.repository ?? SpinaSourceAccountingRepository();
    _sessionScope = _scope(widget.session);
    _load();
  }

  @override
  void didUpdateWidget(covariant ManagementCollectorControlsPage oldWidget) {
    super.didUpdateWidget(oldWidget);
    if (_sessionScope != _scope(widget.session) ||
        oldWidget.repository != widget.repository ||
        oldWidget.deviceIdentityProvider != widget.deviceIdentityProvider) {
      _generation++;
      _schedule = null;
      _bookId = null;
      _offset = 0;
      _date.clear();
      _denied = false;
      _repository = widget.repository ?? SpinaSourceAccountingRepository();
      _sessionScope = _scope(widget.session);
      _load();
    }
  }

  @override
  void dispose() {
    _generation++;
    _schedule = null;
    _bookId = null;
    _date.dispose();
    super.dispose();
  }

  Future<void> _load() async {
    if (_denied) return;
    final generation = ++_generation, date = _date.text.trim();
    setState(() {
      _schedule = null;
      _error = null;
      _busy = true;
    });
    try {
      accountingCheck(
        _can,
        'Current Management accounting view permission is required.',
      );
      accountingCheck(
        date.isEmpty || accountingDate(date),
        'Enter a valid Manila cutoff date (YYYY-MM-DD).',
      );
      final device = await widget.deviceIdentityProvider.load();
      if (!_current(generation)) return;
      Future<Map<String, dynamic>> read(String path) => _repository.read(
        widget.session,
        deviceId: device.installationId,
        path: path,
      );
      final result = await read('$sourceAccountingBase/book');
      if (!_current(generation)) return;
      final book = AccountingBookIdentity.fromPayload(
        accountingObject(result['book']),
      );
      if (_bookId != null && (!book.configured || _bookId != book.bookId)) {
        throw const SpinaApiException(
          'Accounting book changed. Reopen this task.',
          code: 'accounting_scope_changed',
        );
      }
      accountingCheck(
        book.configured,
        'Configure the accounting book before reviewing Collector controls.',
      );
      _bookId = book.bookId;
      final query = Uri(
        queryParameters: {
          'limit': '100',
          'offset': '$_offset',
          if (date.isNotEmpty) 'as_of': date,
        },
      ).query;
      final payload = await read(
        '$sourceAccountingBase/collector/control-schedule?$query',
      );
      if (!_current(generation)) return;
      final value = validateCollectorControlSchedule(payload, bookId: _bookId!);
      accountingCheck(
        value['limit'] == 100 &&
            value['offset'] == _offset &&
            (date.isEmpty || value['as_of'] == date),
      );
      setState(() {
        _schedule = value;
        _date.text = value['as_of'] as String;
      });
    } on Object catch (error) {
      if (_current(generation)) {
        setState(() {
          _schedule = null;
          _error = error is SpinaApiException
              ? error.message
              : error is FormatException
              ? error.message
              : 'Collector controls could not be confirmed. Retry the read.';
          if (error is SpinaApiException &&
              ([401, 403, 426].contains(error.statusCode) ||
                  error.code == 'accounting_scope_changed')) {
            _bookId = null;
            _date.clear();
            _offset = 0;
            _denied = true;
          }
        });
      }
    } finally {
      if (_current(generation)) setState(() => _busy = false);
    }
  }

  Widget _button(String key, String label, VoidCallback action) => Padding(
    padding: const EdgeInsets.symmetric(vertical: 6),
    child: OutlinedButton(
      key: Key(key),
      onPressed: _busy ? null : action,
      child: Text(label),
    ),
  );
  @override
  Widget build(BuildContext context) {
    final data = _schedule,
        capacity = data == null
            ? null
            : accountingObject(data['current_capacity']);
    final movements = data == null
        ? <Map<String, dynamic>>[]
        : accountingRows(data['movements']);
    return Scaffold(
      appBar: AppBar(title: const Text('Collector controls')),
      body: ListView(
        key: ValueKey('collector-controls-$_generation'),
        padding: const EdgeInsets.all(16),
        children: [
          if (_busy) const LinearProgressIndicator(),
          if (_error != null)
            Text(_error!, key: const Key('collector-controls-error')),
          if (!_denied && _can) ...[
            TextField(
              key: const Key('collector-controls-date'),
              controller: _date,
              enabled: !_busy,
              decoration: const InputDecoration(
                labelText: 'Balances through Manila date',
                hintText: 'YYYY-MM-DD',
              ),
              onChanged: (_) => setState(() {
                _schedule = null;
                _offset = 0;
              }),
            ),
            _button('collector-controls-load', 'Load Collector controls', () {
              _offset = 0;
              _load();
            }),
          ],
          if (data != null) ...[
            Text('Book: ${accountingObject(data['book'])['entity_label']}'),
            Text('Balances through ${data['as_of']} · Asia/Manila'),
            Text(
              data['controls_reconciled'] == true
                  ? 'These Collector controls reconcile.'
                  : 'Collector control evidence needs review.',
            ),
            const Text('Full accounting readiness remains a separate review.'),
            for (final row in accountingRows(data['controls']))
              Card(
                child: Padding(
                  padding: const EdgeInsets.all(12),
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text(collectorControlRoles[row['account_code']]!.$2),
                      Text(
                        '${row['account_code']} · ${row['normal_balance']}-normal',
                      ),
                      Text('Ledger amount: PHP ${row['ledger_amount']}'),
                      Text('Source amount: PHP ${row['source_amount']}'),
                      Text(
                        'Difference (debits less credits): PHP ${row['difference']}',
                      ),
                      Text(
                        'Unregistered lines: ${row['unregistered_line_count']}',
                      ),
                    ],
                  ),
                ),
              ),
            const Text('Current operational capacity'),
            Text('Observed ${capacity!['observed_at']}'),
            const Text(
              'These current amounts are separate from the selected historical cutoff.',
            ),
            Text('Unidentified excess: PHP ${capacity['unidentified_amount']}'),
            Text('Outstanding credit: PHP ${capacity['outstanding_amount']}'),
            Text(
              'Reserved within outstanding: PHP ${capacity['reserved_amount']}',
            ),
            Text('Available credit: PHP ${capacity['available_amount']}'),
            const Text(
              'Reservations are included in outstanding credit; they do not add another liability.',
            ),
            const Text('Dated source movements'),
            Text(
              '${movements.isEmpty ? '0' : '${_offset + 1}–${_offset + movements.length}'} of ${data['movement_count']} source movements',
            ),
            Text(
              'Unproven movements: ${data['unproven_movement_count']} · Sources needing correction: ${data['correction_count']}',
            ),
            if (_offset > 0)
              _button(
                'collector-controls-previous',
                'Previous source page',
                () {
                  _offset = max(0, _offset - 100);
                  _load();
                },
              ),
            if (_offset + movements.length < (data['movement_count'] as int))
              _button('collector-controls-next', 'Next source page', () {
                _offset += 100;
                _load();
              }),
            for (final row in movements)
              Card(
                child: Padding(
                  padding: const EdgeInsets.all(12),
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text(
                        '${row['effective_date']} · ${row['account_code']} · PHP ${row['signed_amount']} (debits less credits)',
                      ),
                      Text('${row['source_type']} · ${row['source_id']}'),
                      Text(
                        row['exact_posted'] == true
                            ? 'Current exact posting proof'
                            : 'Exact posting proof required',
                      ),
                    ],
                  ),
                ),
              ),
          ],
        ],
      ),
    );
  }
}
