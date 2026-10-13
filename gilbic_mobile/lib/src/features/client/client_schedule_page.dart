import 'package:gilbic_mobile/src/core/formatting/spina_display.dart';
import 'package:flutter/material.dart';
import 'package:gilbic_mobile/src/core/auth/user_session.dart';
import 'package:gilbic_mobile/src/core/device/device_identity.dart';
import 'package:gilbic_mobile/src/core/loans/client_schedule.dart';
import 'package:gilbic_mobile/src/core/loans/client_schedule_repository.dart';
import 'package:gilbic_mobile/src/core/network/spina_api.dart';
import 'package:gilbic_mobile/src/core/network/staff_operations_client.dart'
    show staffAccessRejected;

class ClientSchedulePage extends StatefulWidget {
  const ClientSchedulePage({
    required this.session,
    required this.deviceIdentityProvider,
    required this.loanId,
    required this.loanNumber,
    this.repository,
    super.key,
  });

  final UserSession session;
  final DeviceIdentityProvider deviceIdentityProvider;
  final String loanId;
  final String loanNumber;
  final ClientScheduleRepository? repository;

  @override
  State<ClientSchedulePage> createState() => _ClientSchedulePageState();
}

class _ClientSchedulePageState extends State<ClientSchedulePage> {
  late ClientScheduleRepository _repository;
  ClientLoanSchedule? _schedule;
  String? _error;
  bool _loading = true;
  int _readEpoch = 0;
  int _requestId = 0;

  @override
  void initState() {
    super.initState();
    _repository = widget.repository ?? SpinaClientScheduleRepository();
    _load();
  }

  @override
  void didUpdateWidget(ClientSchedulePage oldWidget) {
    super.didUpdateWidget(oldWidget);
    if (oldWidget.session != widget.session ||
        oldWidget.loanId != widget.loanId ||
        oldWidget.deviceIdentityProvider != widget.deviceIdentityProvider ||
        oldWidget.repository != widget.repository) {
      _readEpoch++;
      _schedule = null;
      _repository = widget.repository ?? SpinaClientScheduleRepository();
      _dismissPrivateRoutes();
      _load();
    }
  }

  bool _current(int epoch, int requestId) =>
      mounted && epoch == _readEpoch && requestId == _requestId;

  void _dismissPrivateRoutes() {
    final route = ModalRoute.of(context);
    final navigator = Navigator.of(context);
    // Widget updates can happen while Navigator is building its routes.
    WidgetsBinding.instance.addPostFrameCallback((_) {
      if (mounted && route != null && route.isActive && !route.isCurrent) {
        navigator.popUntil((candidate) => candidate == route);
      }
    });
  }

  Future<void> _load() async {
    final epoch = _readEpoch;
    final requestId = ++_requestId;
    final session = widget.session;
    setState(() {
      _loading = true;
      _error = null;
    });
    try {
      final identity = await widget.deviceIdentityProvider.load();
      if (!_current(epoch, requestId)) return;
      final result = await _repository.loadSchedule(
        session,
        deviceId: identity.installationId,
        loanId: widget.loanId,
      );
      if (_current(epoch, requestId)) {
        setState(() => _schedule = result);
      }
    } on SpinaApiException catch (error) {
      if (mounted && epoch == _readEpoch && staffAccessRejected(error)) {
        // A denial also invalidates newer requests already in flight.
        _readEpoch++;
        setState(() {
          _schedule = null;
          _error = error.message;
          _loading = false;
        });
        _dismissPrivateRoutes();
      } else if (_current(epoch, requestId)) {
        setState(() => _error = error.message);
      }
    } on Object {
      if (_current(epoch, requestId)) {
        setState(() => _error = 'Payment schedule could not be loaded.');
      }
    } finally {
      if (_current(epoch, requestId)) {
        setState(() => _loading = false);
      }
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('Payment schedule')),
      body: SafeArea(child: _body(context)),
    );
  }

  Widget _body(BuildContext context) {
    final schedule = _schedule;
    if (_loading && schedule == null) {
      return const Center(child: CircularProgressIndicator());
    }
    if (schedule == null) {
      return Center(
        child: Padding(
          padding: const EdgeInsets.all(24),
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: <Widget>[
              Text(_error ?? 'Payment schedule could not be loaded.'),
              const SizedBox(height: 12),
              FilledButton(onPressed: _load, child: const Text('Try again')),
            ],
          ),
        ),
      );
    }

    return RefreshIndicator(
      onRefresh: _load,
      child: ListView(
        physics: const AlwaysScrollableScrollPhysics(),
        padding: const EdgeInsets.all(16),
        children: <Widget>[
          Card(
            child: Padding(
              padding: const EdgeInsets.all(16),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: <Widget>[
                  Text(
                    'Authoritative SPINA schedule',
                    style: Theme.of(context).textTheme.titleLarge,
                  ),
                  const SizedBox(height: 4),
                  const Text(
                    'Read-only. Dates, amounts and status come from the protected SPINA server schedule.',
                  ),
                  const Divider(height: 24),
                  _line('Loan', schedule.loanNumber),
                  _line('Type', schedule.loanType),
                  _line(
                    'Contractual maturity',
                    _date(schedule.contractualMaturity),
                  ),
                  _line(
                    'Current operational completion',
                    _date(schedule.operationalMaturity),
                  ),
                  _line('Past due', _money(schedule.pastDueAmount)),
                  _line('Schedule status', schedule.maturityStatus),
                ],
              ),
            ),
          ),
          const SizedBox(height: 12),
          if (schedule.rows.isEmpty)
            const Card(
              child: Padding(
                padding: EdgeInsets.all(16),
                child: Text('No schedule rows are available for this loan.'),
              ),
            )
          else
            for (final row in schedule.rows) ...<Widget>[
              _rowCard(context, row),
              const SizedBox(height: 8),
            ],
        ],
      ),
    );
  }

  Widget _rowCard(BuildContext context, ClientScheduleRow row) {
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: <Widget>[
            Text(
              _date(row.paymentDate),
              style: Theme.of(context).textTheme.titleMedium,
            ),
            Text(row.status),
            const SizedBox(height: 8),
            _line('Required amount', _money(row.amount)),
            _line('Remaining for this date', _money(row.remainingAmount)),
            if ((row.note ?? '').isNotEmpty) Text(row.note!),
          ],
        ),
      ),
    );
  }

  Widget _line(String label, String value) {
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 2),
      child: Row(
        children: <Widget>[
          Expanded(child: Text(label)),
          Text(value, style: const TextStyle(fontWeight: FontWeight.w700)),
        ],
      ),
    );
  }
}

String _money(String value) => formatSpinaMoney(value);

String _date(DateTime? value) => formatSpinaCalendarDate(
  value == null
      ? null
      : '${value.year.toString().padLeft(4, '0')}-${value.month.toString().padLeft(2, '0')}-${value.day.toString().padLeft(2, '0')}',
);
