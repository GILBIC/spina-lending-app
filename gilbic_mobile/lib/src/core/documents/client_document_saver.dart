import 'package:file_saver/file_saver.dart';
import 'package:gilbic_mobile/src/core/documents/client_document_repository.dart';

typedef ClientDocumentSaver =
    Future<bool> Function(ClientDocumentFile document);

Future<bool> saveClientDocument(ClientDocumentFile document) async {
  final dot = document.filename.lastIndexOf('.');
  final result = await FileSaver.instance.saveAs(
    name: dot > 0 ? document.filename.substring(0, dot) : document.filename,
    fileExtension: dot > 0 ? document.filename.substring(dot + 1) : '',
    bytes: document.bytes,
    mimeType: MimeType.custom,
    customMimeType: document.mediaType,
  );
  return result != null;
}
