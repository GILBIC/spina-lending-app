import 'package:flutter/material.dart';
import 'package:gilbic_mobile/src/core/documents/client_document_repository.dart';
import 'package:gilbic_mobile/src/core/documents/client_document_saver.dart';
import 'package:gilbic_mobile/src/core/network/spina_api.dart';

/// Authentication remains inside [load]; only returned bytes reach the saver.
class ClientDocumentDownloadButton extends StatefulWidget {
  const ClientDocumentDownloadButton({
    required this.label,
    required this.load,
    this.saver = saveClientDocument,
    super.key,
  });
  final String label;
  final Future<ClientDocumentFile> Function() load;
  final ClientDocumentSaver saver;
  @override
  State<ClientDocumentDownloadButton> createState() =>
      _ClientDocumentDownloadButtonState();
}

class _ClientDocumentDownloadButtonState
    extends State<ClientDocumentDownloadButton> {
  bool _busy = false;
  Future<void> _download() async {
    setState(() => _busy = true);
    try {
      final document = await widget.load();
      if (!mounted) return;
      final saved = await widget.saver(document);
      if (mounted && saved) {
        ScaffoldMessenger.of(
          context,
        ).showSnackBar(const SnackBar(content: Text('Document saved.')));
      }
    } on SpinaApiException catch (error) {
      if (mounted) {
        ScaffoldMessenger.of(
          context,
        ).showSnackBar(SnackBar(content: Text(error.message)));
      }
    } on Object {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(
            content: Text('The document could not be saved. Try again.'),
          ),
        );
      }
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  @override
  Widget build(BuildContext context) => OutlinedButton.icon(
    onPressed: _busy ? null : _download,
    icon: _busy
        ? const SizedBox(
            width: 16,
            height: 16,
            child: CircularProgressIndicator(strokeWidth: 2),
          )
        : const Icon(Icons.download_outlined),
    label: Text(_busy ? 'Preparing document…' : widget.label),
  );
}
