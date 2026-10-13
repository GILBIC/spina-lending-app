import 'package:flutter/material.dart';
import 'package:gilbic_mobile/src/core/auth/user_session.dart';
import 'package:gilbic_mobile/src/core/device/device_identity.dart';
import 'package:gilbic_mobile/src/core/documents/client_document_repository.dart';
import 'package:gilbic_mobile/src/core/documents/client_document_saver.dart';
import 'package:gilbic_mobile/src/core/network/spina_api.dart';
import 'package:gilbic_mobile/src/core/network/staff_operations_client.dart'
    show staffAccessRejected;
import 'package:gilbic_mobile/src/core/statements/client_statement.dart';
import 'package:gilbic_mobile/src/core/statements/client_statement_repository.dart';
import 'package:gilbic_mobile/src/features/client/client_document_download_button.dart';

class ClientStatementPage extends StatefulWidget {
  const ClientStatementPage({
    required this.session,
    required this.deviceIdentityProvider,
    this.repository,
    this.documentRepository,
    this.documentSaver = saveClientDocument,
    super.key,
  });

  final UserSession session;
  final DeviceIdentityProvider deviceIdentityProvider;
  final ClientStatementRepository? repository;
  final ClientDocumentRepository? documentRepository;
  final ClientDocumentSaver documentSaver;

  @override
  State<ClientStatementPage> createState() => _ClientStatementPageState();
}

class _ClientStatementPageState extends State<ClientStatementPage> {
  late ClientStatementRepository _repository;
  ClientStatement? _statement;
  String? _error;
  bool _loading = true;
  int _readEpoch = 0;
  int _requestId = 0;

  @override
  void initState() {
    super.initState();
    _repository = widget.repository ?? SpinaClientStatementRepository();
    _load();
  }

  @override
  void didUpdateWidget(ClientStatementPage oldWidget) {
    super.didUpdateWidget(oldWidget);
    if (oldWidget.session != widget.session ||
        oldWidget.deviceIdentityProvider != widget.deviceIdentityProvider ||
        oldWidget.repository != widget.repository) {
      _readEpoch++;
      _statement = null;
      _repository = widget.repository ?? SpinaClientStatementRepository();
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
      final result = await _repository.loadStatement(
        session,
        deviceId: identity.installationId,
      );
      if (_current(epoch, requestId)) {
        setState(() => _statement = result);
      }
    } on SpinaApiException catch (error) {
      if (mounted && epoch == _readEpoch && staffAccessRejected(error)) {
        // A denial also invalidates newer requests already in flight.
        _readEpoch++;
        setState(() {
          _statement = null;
          _error = error.message;
          _loading = false;
        });
        _dismissPrivateRoutes();
      } else if (_current(epoch, requestId)) {
        setState(() => _error = error.message);
      }
    } on Object {
      if (_current(epoch, requestId)) {
        setState(() => _error = 'Statement of Account could not be loaded.');
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
      appBar: AppBar(title: const Text('Statement of Account')),
      body: SafeArea(child: _body(context)),
    );
  }

  Widget _body(BuildContext context) {
    final statement = _statement;
    if (_loading && statement == null) {
      return const Center(child: CircularProgressIndicator());
    }
    if (statement == null) {
      return Center(
        child: Padding(
          padding: const EdgeInsets.all(24),
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: <Widget>[
              Text(_error ?? 'Statement of Account could not be loaded.'),
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
                    statement.clientName,
                    style: Theme.of(context).textTheme.titleLarge,
                  ),
                  Text(statement.clientCode),
                  const SizedBox(height: 8),
                  const Text(
                    'Read-only statement using loan balances and official payment records returned by the protected SPINA server.',
                  ),
                  const SizedBox(height: 8),
                  ClientDocumentDownloadButton(
                    label: 'Download statement record copy',
                    saver: widget.documentSaver,
                    load: () async {
                      final identity = await widget.deviceIdentityProvider
                          .load();
                      return (widget.documentRepository ??
                              SpinaClientDocumentRepository())
                          .downloadStatement(
                            widget.session,
                            deviceId: identity.installationId,
                          );
                    },
                  ),
                ],
              ),
            ),
          ),
          const SizedBox(height: 16),
          Text('Loans', style: Theme.of(context).textTheme.titleMedium),
          const SizedBox(height: 8),
          if (statement.loans.isEmpty)
            const Card(
              child: Padding(
                padding: EdgeInsets.all(16),
                child: Text('No loan records are available.'),
              ),
            )
          else
            for (final loan in statement.loans) ...<Widget>[
              Card(
                child: Padding(
                  padding: const EdgeInsets.all(16),
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: <Widget>[
                      Text(
                        loan.loanTypeName,
                        style: Theme.of(context).textTheme.titleMedium,
                      ),
                      Text(loan.loanNumber),
                      const Divider(height: 20),
                      _line('Principal', _money(loan.principal)),
                      _line('Current balance', _money(loan.remainingBalance)),
                      _line('Status', loan.status),
                    ],
                  ),
                ),
              ),
              const SizedBox(height: 8),
            ],
          const SizedBox(height: 16),
          Text(
            'Official payment history',
            style: Theme.of(context).textTheme.titleMedium,
          ),
          const SizedBox(height: 8),
          if (statement.payments.isEmpty)
            const Card(
              child: Padding(
                padding: EdgeInsets.all(16),
                child: Text('No official payments are recorded yet.'),
              ),
            )
          else
            for (final payment in statement.payments) ...<Widget>[
              Card(
                child: Padding(
                  padding: const EdgeInsets.all(16),
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: <Widget>[
                      Text(
                        _money(payment.amount),
                        style: Theme.of(context).textTheme.titleLarge,
                      ),
                      Text('Receipt: ${payment.receiptNumber}'),
                      Text('Loan: ${payment.loanNumber}'),
                      Text('Collection date: ${_date(payment.collectionDate)}'),
                      Text('Status: ${payment.status}'),
                      if (payment.officialBalance != null)
                        Text(
                          'Balance after: ${_money(payment.officialBalance!)}',
                        ),
                      if (payment.isVoided)
                        const Padding(
                          padding: EdgeInsets.only(top: 6),
                          child: Text(
                            'Voided — this receipt does not reduce the balance.',
                          ),
                        ),
                    ],
                  ),
                ),
              ),
              const SizedBox(height: 8),
            ],
        ],
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
  final match = RegExp(r'^([+-]?)(\d+)(?:\.(\d+))?$').firstMatch(value.trim());
  if (match == null) return value;
  final sign = match.group(1) ?? '';
  final whole = match.group(2) ?? '0';
  final fraction = match.group(3);
  final grouped = whole.replaceAllMapped(
    RegExp(r'\B(?=(\d{3})+(?!\d))'),
    (_) => ',',
  );
  return '${sign == '-'
      ? '-'
      : sign == '+'
      ? '+'
      : ''}₱$grouped${fraction == null ? '' : '.$fraction'}';
}

String _date(DateTime value) {
  return '${value.year.toString().padLeft(4, '0')}-'
      '${value.month.toString().padLeft(2, '0')}-'
      '${value.day.toString().padLeft(2, '0')}';
}
