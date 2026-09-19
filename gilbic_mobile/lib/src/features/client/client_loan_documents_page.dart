import 'package:flutter/material.dart';
import 'package:gilbic_mobile/src/core/auth/user_session.dart';
import 'package:gilbic_mobile/src/core/device/device_identity.dart';
import 'package:gilbic_mobile/src/core/documents/client_document_repository.dart';
import 'package:gilbic_mobile/src/core/documents/client_document_saver.dart';
import 'package:gilbic_mobile/src/core/network/spina_api.dart';
import 'package:gilbic_mobile/src/features/client/client_document_download_button.dart';

class ClientLoanDocumentsPage extends StatefulWidget {
  const ClientLoanDocumentsPage({
    required this.session,
    required this.deviceIdentityProvider,
    required this.loanId,
    required this.loanNumber,
    this.repository,
    this.saver = saveClientDocument,
    super.key,
  });
  final UserSession session;
  final DeviceIdentityProvider deviceIdentityProvider;
  final String loanId;
  final String loanNumber;
  final ClientDocumentRepository? repository;
  final ClientDocumentSaver saver;
  @override
  State<ClientLoanDocumentsPage> createState() =>
      _ClientLoanDocumentsPageState();
}

class _ClientLoanDocumentsPageState extends State<ClientLoanDocumentsPage> {
  late final ClientDocumentRepository _repository;
  List<ClientDocument>? _documents;
  String? _error;
  bool _loading = true;
  @override
  void initState() {
    super.initState();
    _repository = widget.repository ?? SpinaClientDocumentRepository();
    _load();
  }

  Future<void> _load() async {
    setState(() {
      _loading = true;
      _error = null;
    });
    try {
      final identity = await widget.deviceIdentityProvider.load();
      final documents = await _repository.listLoanDocuments(
        widget.session,
        deviceId: identity.installationId,
        loanId: widget.loanId,
      );
      if (mounted) setState(() => _documents = documents);
    } on SpinaApiException catch (error) {
      if (mounted) setState(() => _error = error.message);
    } on Object {
      if (mounted) {
        setState(() => _error = 'Loan documents could not be loaded.');
      }
    } finally {
      if (mounted) setState(() => _loading = false);
    }
  }

  @override
  Widget build(BuildContext context) => Scaffold(
    appBar: AppBar(
      title: const Text('Loan documents'),
      actions: [
        IconButton(
          onPressed: _loading ? null : _load,
          tooltip: 'Refresh documents',
          icon: const Icon(Icons.refresh),
        ),
      ],
    ),
    body: _loading
        ? const Center(child: CircularProgressIndicator())
        : ListView(
            padding: const EdgeInsets.all(16),
            children: [
              Text(
                widget.loanNumber,
                style: Theme.of(context).textTheme.titleLarge,
              ),
              const SizedBox(height: 12),
              const Text(
                'Finalized documents supplied by SPINA for your released loan.',
              ),
              if (_error != null) ...[
                Text(_error!),
                OutlinedButton(
                  onPressed: _load,
                  child: const Text('Try again'),
                ),
              ] else if (_documents?.isEmpty ?? true)
                const Padding(
                  padding: EdgeInsets.symmetric(vertical: 24),
                  child: Text(
                    'No finalized document is available for this loan. Contact SPINA if you need a copy.',
                  ),
                )
              else
                for (final document in _documents!)
                  Card(
                    child: Padding(
                      padding: const EdgeInsets.all(16),
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          Text(
                            document.label,
                            style: Theme.of(context).textTheme.titleMedium,
                          ),
                          Text('Released: ${document.releasedAt}'),
                          ClientDocumentDownloadButton(
                            label: 'Download ${document.label.toLowerCase()}',
                            saver: widget.saver,
                            load: () async {
                              final identity = await widget
                                  .deviceIdentityProvider
                                  .load();
                              return _repository.downloadLoanDocument(
                                widget.session,
                                deviceId: identity.installationId,
                                loanId: widget.loanId,
                                documentId: document.documentId,
                              );
                            },
                          ),
                        ],
                      ),
                    ),
                  ),
            ],
          ),
  );
}
