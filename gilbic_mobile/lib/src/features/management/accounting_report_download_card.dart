import 'package:flutter/material.dart';
import 'package:gilbic_mobile/src/core/auth/user_session.dart';
import 'package:gilbic_mobile/src/core/device/device_identity.dart';
import 'package:gilbic_mobile/src/core/documents/client_document_repository.dart';
import 'package:gilbic_mobile/src/core/documents/client_document_saver.dart';
import 'package:gilbic_mobile/src/core/management/accounting_export_repository.dart';
import 'package:gilbic_mobile/src/core/network/spina_api.dart';

class AccountingReportDownloadCard extends StatefulWidget {
  const AccountingReportDownloadCard({
    required this.session,
    required this.deviceIdentityProvider,
    required this.startDate,
    required this.endDate,
    required this.onAccessDenied,
    this.repository,
    this.saver = saveClientDocument,
    super.key,
  });
  final UserSession session;
  final DeviceIdentityProvider deviceIdentityProvider;
  final DateTime startDate, endDate;
  final void Function(SpinaApiException) onAccessDenied;
  final AccountingExportRepository? repository;
  final ClientDocumentSaver saver;
  @override
  State<AccountingReportDownloadCard> createState() =>
      _AccountingReportDownloadCardState();
}

class _AccountingReportDownloadCardState
    extends State<AccountingReportDownloadCard> {
  late final _start = TextEditingController(
    text: widget.startDate.toIso8601String().substring(0, 10),
  );
  late final _end = TextEditingController(
    text: widget.endDate.toIso8601String().substring(0, 10),
  );
  late final _repository = widget.repository ?? AccountingExportRepository();
  int _generation = 0;
  bool _busy = false, _denied = false;
  String? _status;

  @override
  void didUpdateWidget(covariant AccountingReportDownloadCard oldWidget) {
    super.didUpdateWidget(oldWidget);
    if (oldWidget.session != widget.session ||
        oldWidget.deviceIdentityProvider != widget.deviceIdentityProvider ||
        oldWidget.startDate != widget.startDate ||
        oldWidget.endDate != widget.endDate) {
      _generation++;
      _busy = false;
      _status = null;
      _start.text = widget.startDate.toIso8601String().substring(0, 10);
      _end.text = widget.endDate.toIso8601String().substring(0, 10);
    }
  }

  @override
  void dispose() {
    _generation++;
    _start.dispose();
    _end.dispose();
    super.dispose();
  }

  Future<void> _download() async {
    if (_busy || _denied) return;
    final generation = ++_generation, session = widget.session;
    final start = _start.text.trim(), end = _end.text.trim();
    setState(() {
      _busy = true;
      _status = null;
    });
    ClientDocumentFile? file;
    bool active() => mounted && generation == _generation && !_denied;
    try {
      final identity = await widget.deviceIdentityProvider.load();
      if (!active()) return;
      file = await _repository.download(
        session,
        deviceId: identity.installationId,
        startDate: start,
        endDate: end,
      );
      if (!active()) return;
      final saved = await widget.saver(file);
      if (active()) {
        setState(
          () =>
              _status = saved ? 'Reporting package saved.' : 'Save cancelled.',
        );
      }
    } on SpinaApiException catch (error) {
      if (!active()) return;
      if (const [401, 403, 426].contains(error.statusCode)) {
        _denied = true;
        widget.onAccessDenied(error);
      }
      if (mounted && generation == _generation) {
        setState(() => _status = error.message);
      }
    } on Object {
      if (active()) {
        setState(
          () =>
              _status = 'The reporting package could not be saved. Try again.',
        );
      }
    } finally {
      file?.bytes.fillRange(0, file.bytes.length, 0);
      if (mounted && generation == _generation) setState(() => _busy = false);
    }
  }

  @override
  Widget build(BuildContext context) => Card(
    child: ExpansionTile(
      title: const Text('Reporting review download'),
      childrenPadding: const EdgeInsets.all(16),
      children: [
        const Text(
          'Download books, each configured period’s statements and retained evidence. Choose complete consecutive accounting periods, up to 366 days. The package includes full-range statements, period details and unresolved review evidence.',
        ),
        TextField(
          controller: _start,
          enabled: !_busy && !_denied,
          decoration: const InputDecoration(
            labelText: 'Start date (YYYY-MM-DD)',
          ),
        ),
        TextField(
          controller: _end,
          enabled: !_busy && !_denied,
          decoration: const InputDecoration(labelText: 'End date (YYYY-MM-DD)'),
        ),
        const SizedBox(height: 12),
        OutlinedButton.icon(
          onPressed: _busy || _denied ? null : _download,
          icon: const Icon(Icons.download_outlined),
          label: Text(
            _busy ? 'Preparing package…' : 'Download reporting package (ZIP)',
          ),
        ),
        if (_status != null) Text(_status!),
      ],
    ),
  );
}
