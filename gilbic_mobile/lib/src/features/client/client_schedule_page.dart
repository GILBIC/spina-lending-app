import 'package:flutter/material.dart';
import 'package:gilbic_mobile/src/core/auth/user_session.dart';
import 'package:gilbic_mobile/src/core/device/device_identity.dart';
import 'package:gilbic_mobile/src/core/loans/client_schedule.dart';
import 'package:gilbic_mobile/src/core/loans/client_schedule_repository.dart';
import 'package:gilbic_mobile/src/core/network/spina_api.dart';

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
  late final ClientScheduleRepository _repository;
  ClientLoanSchedule? _schedule;
  String? _error;
  bool _loading = true;

  @override
  void initState() {
    super.initState();
    _repository = widget.repository ?? SpinaClientScheduleRepository();
    _load();
  }

  Future<void> _load() async {
    setState(() {
      _loading = true;
      _error = null;
    });
    try {
      final identity = await widget.deviceIdentityProvider.load();
      final schedule = await _repository.loadSchedule(
        widget.session,
        deviceId: identity.installationId,
        loanId: widget.loanId,
      );
      if (mounted) setState(() => _schedule = schedule);
    } on SpinaApiException catch (error) {
      if (mounted) setState(() => _error = error.message);
    } on Object {
      if (mounted) setState(() => _error = 'Payment schedule could not be loaded.');
    } finally {
      if (mounted) setState(() => _loading = false);
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
                  _line('Contractual maturity', _date(schedule.contractualMaturity)),
                  _line('Current operational completion', _date(schedule.operationalMaturity)),
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
            Text(_date(row.paymentDate), style: Theme.of(context).textTheme.titleMedium),
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

String _money(String value) {
  final text = value.trim();
  final match = RegExp(r'^([+-]?)(\d+)(?:\.(\d+))?$').firstMatch(text);
  if (match == null) return text;
  final sign = match.group(1) ?? '';
  final whole = match.group(2) ?? '0';
  final fraction = match.group(3);
  final grouped = whole.replaceAllMapped(
    RegExp(r'\B(?=(\d{3})+(?!\d))'),
    (_) => ',',
  );
  return '${sign == '-' ? '-' : sign == '+' ? '+' : ''}₱$grouped${fraction == null ? '' : '.$fraction'}';
}

String _date(DateTime? value) {
  if (value == null) return 'Not available';
  const months = <String>['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];
  return '${months[value.month - 1]} ${value.day}, ${value.year}';
}
