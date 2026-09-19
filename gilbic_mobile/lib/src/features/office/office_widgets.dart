import 'dart:typed_data';
import 'package:flutter/material.dart';
import 'package:gilbic_mobile/src/core/documents/client_document_saver.dart';
import 'package:gilbic_mobile/src/core/documents/client_document_repository.dart';
import 'package:gilbic_mobile/src/core/network/spina_api.dart';
import 'package:gilbic_mobile/src/core/office/office_operation.dart';
import 'package:gilbic_mobile/src/core/office/office_repository.dart';
import 'package:gilbic_mobile/src/core/remittance/remittance_photo.dart';
import 'package:image_picker/image_picker.dart';

abstract class OfficeScreenState<T extends StatefulWidget> extends State<T> {
  final operation = OfficeOperation();
  void clearPrivate();
  void denyAccess() {
    if (mounted) {
      setState(() {
        operation.denied = true;
        operation.error = 'Office access is no longer available.';
        clearPrivate();
      });
    }
  }

  @override
  void initState() {
    super.initState();
    operation.addListener(_changed);
  }

  void _changed() {
    if (mounted) {
      setState(() {
        if (operation.denied) clearPrivate();
      });
    }
  }

  @override
  void dispose() {
    operation.removeListener(_changed);
    operation.dispose();
    super.dispose();
  }

  Widget screen(
    String title,
    List<Widget> children, {
    VoidCallback? reload,
  }) => Scaffold(
    appBar: AppBar(
      title: Text(title),
      actions: [
        if (reload != null)
          IconButton(
            tooltip: 'Reload saved record',
            onPressed: operation.busy || operation.denied ? null : reload,
            icon: const Icon(Icons.refresh),
          ),
      ],
    ),
    body: SafeArea(
      child: ListView(
        padding: const EdgeInsets.all(16),
        children: [
          if (operation.busy) const LinearProgressIndicator(),
          if (operation.error != null)
            Padding(
              padding: const EdgeInsets.symmetric(vertical: 12),
              child: Text(
                operation.error!,
                key: const Key('office-error'),
                style: TextStyle(color: Theme.of(context).colorScheme.error),
              ),
            ),
          if (operation.denied)
            const Text(
              'Office access is no longer available. Sign in again before continuing.',
            )
          else ...[
            if (operation.blocked)
              const Padding(
                padding: EdgeInsets.only(bottom: 12),
                child: Text(
                  'The outcome may already be recorded. Reload the saved record before another action.',
                ),
              ),
            ...children,
          ],
        ],
      ),
    ),
  );

  Future<void> saveDownload(
    Future<ClientDocumentFile> Function() fetch, {
    ClientDocumentSaver saver = saveClientDocument,
  }) async {
    final document = await operation.run(fetch);
    if (!mounted || document == null || operation.denied) return;
    try {
      final saved = await saver(document);
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(
            content: Text(saved ? 'Document saved.' : 'Save cancelled.'),
          ),
        );
      }
    } on Object {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(content: Text('The document could not be saved.')),
        );
      }
    }
  }
}

class OfficeFields {
  final values = <String, TextEditingController>{};
  TextEditingController controller(String name, [Object? initial]) =>
      values.putIfAbsent(
        name,
        () => TextEditingController(text: initial?.toString() ?? ''),
      );
  String text(String name) => controller(name).text.trim();
  String? optional(String name) => text(name).isEmpty ? null : text(name);
  void clear() {
    for (final value in values.values) {
      value.clear();
    }
  }

  void dispose() {
    for (final value in values.values) {
      value.dispose();
    }
    values.clear();
  }
}

Widget officeField(
  OfficeFields fields,
  String name,
  String label, {
  Object? initial,
  bool enabled = true,
  bool multiline = false,
  bool money = false,
  bool required = false,
  int? maxLength,
  ValueChanged<String>? onChanged,
}) => Padding(
  padding: const EdgeInsets.only(bottom: 14),
  child: TextFormField(
    key: Key('office-$name'),
    controller: fields.controller(name, initial),
    enabled: enabled,
    keyboardType: money
        ? const TextInputType.numberWithOptions(decimal: true)
        : multiline
        ? TextInputType.multiline
        : TextInputType.text,
    maxLines: multiline ? 3 : 1,
    maxLength: maxLength,
    autocorrect: false,
    enableSuggestions: false,
    decoration: InputDecoration(
      labelText: label,
      border: const OutlineInputBorder(),
    ),
    onChanged: onChanged,
    validator: required
        ? (value) => value == null || value.trim().isEmpty
              ? '$label is required.'
              : null
        : null,
  ),
);
Widget officeButton(
  String label,
  VoidCallback? onPressed, {
  bool primary = false,
  Key? key,
}) => Padding(
  padding: const EdgeInsets.only(bottom: 12),
  child: primary
      ? FilledButton(key: key, onPressed: onPressed, child: Text(label))
      : OutlinedButton(key: key, onPressed: onPressed, child: Text(label)),
);
Widget officeHeading(String text) => Padding(
  padding: const EdgeInsets.symmetric(vertical: 14),
  child: Text(
    text,
    style: const TextStyle(fontSize: 20, fontWeight: FontWeight.w700),
  ),
);
String officeLabel(String value) => value
    .replaceAll('_', ' ')
    .replaceFirstMapped(RegExp(r'^.'), (match) => match[0]!.toUpperCase());

/// Readable saved facts, including nested declared information and schedules.
class OfficeFacts extends StatelessWidget {
  const OfficeFacts(this.record, {super.key});
  final OfficeRecord record;
  @override
  Widget build(BuildContext context) => Column(
    crossAxisAlignment: CrossAxisAlignment.stretch,
    children: [
      for (final entry in record.entries)
        if (!entry.key.endsWith('_id') &&
            !entry.key.contains('sha256') &&
            ![
              'schema_version',
              'packet_hash',
              'snapshot_hash',
              'content_base64',
            ].contains(entry.key))
          if (entry.value is Map || entry.value is List)
            ExpansionTile(
              title: Text(officeLabel(entry.key)),
              children: [
                if (entry.value is Map)
                  Padding(
                    padding: const EdgeInsets.all(12),
                    child: OfficeFacts(stringMap(entry.value)),
                  )
                else
                  for (final item in entry.value as List)
                    Padding(
                      padding: const EdgeInsets.all(12),
                      child: item is Map
                          ? OfficeFacts(stringMap(item))
                          : Text(item.toString()),
                    ),
              ],
            )
          else
            Padding(
              padding: const EdgeInsets.only(bottom: 10),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(
                    officeLabel(entry.key),
                    style: Theme.of(context).textTheme.labelMedium,
                  ),
                  Text(
                    entry.value == null
                        ? 'Not recorded'
                        : entry.value is bool
                        ? (entry.value == true ? 'Yes' : 'No')
                        : entry.value.toString(),
                  ),
                ],
              ),
            ),
    ],
  );
}

class OfficePhoto {
  const OfficePhoto(this.bytes, this.mediaType);
  final Uint8List bytes;
  final String mediaType;
}

typedef OfficePhotoPicker = Future<OfficePhoto?> Function(ImageSource source);
Future<OfficePhoto?> pickOfficePhoto(ImageSource source) async {
  final image = await ImagePicker().pickImage(
    source: source,
    imageQuality: 90,
    requestFullMetadata: false,
  );
  if (image == null) return null;
  final bytes = await image.readAsBytes();
  final type = RemittancePhotoDraft.detectContentType(bytes) ?? '';
  validateOfficeEvidence(bytes, type);
  return OfficePhoto(bytes, type);
}

class OfficeEvidencePicker extends StatefulWidget {
  const OfficeEvidencePicker({
    required this.enabled,
    required this.onChanged,
    this.picker = pickOfficePhoto,
    super.key,
  });
  final bool enabled;
  final ValueChanged<OfficePhoto?> onChanged;
  final OfficePhotoPicker picker;
  @override
  State<OfficeEvidencePicker> createState() => _OfficeEvidencePickerState();
}

class _OfficeEvidencePickerState extends State<OfficeEvidencePicker> {
  OfficePhoto? _photo;
  String? _error;
  bool _picking = false;
  Future<void> _pick(ImageSource source) async {
    if (_picking || !widget.enabled) return;
    setState(() {
      _picking = true;
      _error = null;
    });
    try {
      final photo = await widget.picker(source);
      if (!mounted || photo == null || !widget.enabled) return;
      validateOfficeEvidence(photo.bytes, photo.mediaType);
      setState(() => _photo = photo);
      widget.onChanged(photo);
    } on Object catch (error) {
      if (mounted) {
        setState(
          () => _error = error is SpinaApiException
              ? error.message
              : 'The signed image could not be opened.',
        );
      }
    } finally {
      if (mounted) setState(() => _picking = false);
    }
  }

  @override
  void dispose() {
    _photo = null;
    super.dispose();
  }

  @override
  Widget build(BuildContext context) => Column(
    crossAxisAlignment: CrossAxisAlignment.stretch,
    children: [
      const Text(
        'Attach a clear image of the actual signed paper. Maximum 10 MiB.',
      ),
      Wrap(
        spacing: 8,
        children: [
          OutlinedButton.icon(
            onPressed: widget.enabled && !_picking
                ? () => _pick(ImageSource.camera)
                : null,
            icon: const Icon(Icons.camera_alt_outlined),
            label: const Text('Camera'),
          ),
          OutlinedButton.icon(
            onPressed: widget.enabled && !_picking
                ? () => _pick(ImageSource.gallery)
                : null,
            icon: const Icon(Icons.photo_library_outlined),
            label: const Text('Gallery'),
          ),
          if (_photo != null)
            TextButton(
              onPressed: widget.enabled && !_picking
                  ? () {
                      setState(() => _photo = null);
                      widget.onChanged(null);
                    }
                  : null,
              child: const Text('Clear image'),
            ),
        ],
      ),
      if (_picking) const LinearProgressIndicator(),
      if (_error != null) Text(_error!),
      if (_photo != null)
        Padding(
          padding: const EdgeInsets.only(bottom: 12),
          child: Image.memory(
            _photo!.bytes,
            height: 180,
            fit: BoxFit.contain,
            errorBuilder: (_, _, _) => const Text('Image selected.'),
          ),
        ),
    ],
  );
}
