import 'dart:typed_data';

import 'package:flutter/material.dart';
import 'package:gilbic_mobile/src/core/auth/user_session.dart';
import 'package:gilbic_mobile/src/core/device/device_identity.dart';
import 'package:gilbic_mobile/src/core/network/spina_api.dart';
import 'package:gilbic_mobile/src/core/remittance/remittance.dart';
import 'package:gilbic_mobile/src/core/remittance/remittance_photo.dart';
import 'package:gilbic_mobile/src/core/remittance/remittance_photo_repository.dart';
import 'package:image_picker/image_picker.dart';

class RemittanceHandoverPhotoPage extends StatefulWidget {
  const RemittanceHandoverPhotoPage({
    required this.session,
    required this.remittance,
    required this.deviceIdentityProvider,
    this.repository,
    this.imagePicker,
    super.key,
  });

  final UserSession session;
  final RemittanceRecord remittance;
  final DeviceIdentityProvider deviceIdentityProvider;
  final RemittancePhotoRepository? repository;
  final ImagePicker? imagePicker;

  @override
  State<RemittanceHandoverPhotoPage> createState() =>
      _RemittanceHandoverPhotoPageState();
}

class _RemittanceHandoverPhotoPageState
    extends State<RemittanceHandoverPhotoPage> {
  late final RemittancePhotoRepository _repository;
  late final ImagePicker _imagePicker;

  RemittancePhotoDraft? _draft;
  RemittancePhotoUploadResult? _uploaded;
  String? _errorMessage;
  bool _picking = false;
  bool _uploading = false;

  @override
  void initState() {
    super.initState();
    _repository = widget.repository ?? SpinaRemittancePhotoRepository();
    _imagePicker = widget.imagePicker ?? ImagePicker();
  }

  Future<void> _pick(ImageSource source) async {
    if (_picking || _uploading) {
      return;
    }
    setState(() {
      _picking = true;
      _errorMessage = null;
    });
    try {
      final image = await _imagePicker.pickImage(
        source: source,
        imageQuality: 75,
        maxWidth: 1600,
        maxHeight: 1600,
        requestFullMetadata: false,
      );
      if (image == null || !mounted) {
        return;
      }
      final bytes = await image.readAsBytes();
      final draft = RemittancePhotoDraft.fromBytes(
        filename: image.name,
        bytes: Uint8List.fromList(bytes),
        suggestedContentType: image.mimeType,
      );
      final validationError = draft.validate();
      if (validationError != null) {
        setState(() => _errorMessage = validationError);
        return;
      }
      setState(() {
        _draft = draft;
        _uploaded = null;
      });
    } on Object {
      if (mounted) {
        setState(() {
          _errorMessage = 'The photo could not be opened. Try another picture.';
        });
      }
    } finally {
      if (mounted) {
        setState(() => _picking = false);
      }
    }
  }

  Future<void> _upload() async {
    final draft = _draft;
    if (_uploading || draft == null) {
      return;
    }
    setState(() {
      _uploading = true;
      _errorMessage = null;
    });
    try {
      final identity = await widget.deviceIdentityProvider.load();
      final result = await _repository.upload(
        widget.session,
        deviceId: identity.installationId,
        remittanceId: widget.remittance.remittanceId,
        draft: draft,
      );
      if (!mounted) {
        return;
      }
      setState(() => _uploaded = result);
    } on SpinaApiException catch (error) {
      if (mounted) {
        setState(() => _errorMessage = error.message);
      }
    } on Object {
      if (mounted) {
        setState(() {
          _errorMessage = 'The handover photo could not be saved.';
        });
      }
    } finally {
      if (mounted) {
        setState(() => _uploading = false);
      }
    }
  }

  @override
  Widget build(BuildContext context) {
    final draft = _draft;
    final uploaded = _uploaded;
    return Scaffold(
      appBar: AppBar(title: const Text('Handover Photo')),
      body: SafeArea(
        child: ListView(
          padding: const EdgeInsets.all(16),
          children: [
            Card(
              child: Padding(
                padding: const EdgeInsets.all(16),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      widget.remittance.remittanceNumber,
                      style: Theme.of(context).textTheme.titleLarge,
                    ),
                    const SizedBox(height: 4),
                    Text('Recipient: ${widget.remittance.recipientName}'),
                    Text(
                      'Cash: ₱${widget.remittance.summary.totalAmount.toStringAsFixed(2)}',
                    ),
                    const SizedBox(height: 8),
                    const Text(
                      'Take a clear photo showing that the cash was physically handed to the selected recipient. Do not include unrelated private documents.',
                    ),
                  ],
                ),
              ),
            ),
            const SizedBox(height: 12),
            Row(
              children: [
                Expanded(
                  child: FilledButton.icon(
                    key: const Key('take-handover-photo'),
                    onPressed: _picking || _uploading
                        ? null
                        : () => _pick(ImageSource.camera),
                    icon: const Icon(Icons.camera_alt_outlined),
                    label: const Text('Take Photo'),
                  ),
                ),
                const SizedBox(width: 10),
                Expanded(
                  child: OutlinedButton.icon(
                    key: const Key('choose-handover-photo'),
                    onPressed: _picking || _uploading
                        ? null
                        : () => _pick(ImageSource.gallery),
                    icon: const Icon(Icons.photo_library_outlined),
                    label: const Text('Gallery'),
                  ),
                ),
              ],
            ),
            const SizedBox(height: 14),
            if (_picking)
              const Center(child: CircularProgressIndicator())
            else if (draft == null)
              const Card(
                child: Padding(
                  padding: EdgeInsets.all(24),
                  child: Column(
                    children: [
                      Icon(Icons.add_a_photo_outlined, size: 48),
                      SizedBox(height: 8),
                      Text(
                        'No handover photo selected. This evidence is optional.',
                        textAlign: TextAlign.center,
                      ),
                    ],
                  ),
                ),
              )
            else
              Card(
                clipBehavior: Clip.antiAlias,
                child: Column(
                  children: [
                    AspectRatio(
                      aspectRatio: 4 / 3,
                      child: Image.memory(
                        draft.bytes,
                        fit: BoxFit.cover,
                        errorBuilder: (context, error, stackTrace) => const Center(
                          child: Text('Photo preview unavailable.'),
                        ),
                      ),
                    ),
                    Padding(
                      padding: const EdgeInsets.all(12),
                      child: Row(
                        children: [
                          Expanded(
                            child: Text(
                              '${draft.filename} • ${_fileSize(draft.bytes.length)}',
                              maxLines: 2,
                              overflow: TextOverflow.ellipsis,
                            ),
                          ),
                          TextButton(
                            onPressed: _uploading
                                ? null
                                : () => setState(() {
                                      _draft = null;
                                      _uploaded = null;
                                    }),
                            child: const Text('Remove'),
                          ),
                        ],
                      ),
                    ),
                  ],
                ),
              ),
            if (_errorMessage != null) ...[
              const SizedBox(height: 12),
              Card(
                child: Padding(
                  padding: const EdgeInsets.all(12),
                  child: Text(_errorMessage!),
                ),
              ),
            ],
            if (uploaded != null) ...[
              const SizedBox(height: 12),
              Card(
                child: Padding(
                  padding: const EdgeInsets.all(14),
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      const Row(
                        children: [
                          Icon(Icons.verified),
                          SizedBox(width: 8),
                          Text('Handover photo saved'),
                        ],
                      ),
                      const SizedBox(height: 6),
                      Text('Evidence version: ${uploaded.version}'),
                      Text('Uploaded: ${_dateTime(uploaded.uploadedAt)}'),
                      const Text(
                        'The selected recipient can now view this photo before accepting the remittance.',
                      ),
                    ],
                  ),
                ),
              ),
            ],
            const SizedBox(height: 16),
            if (uploaded == null)
              FilledButton.icon(
                key: const Key('upload-handover-photo'),
                onPressed: draft == null || _uploading ? null : _upload,
                icon: _uploading
                    ? const SizedBox(
                        width: 18,
                        height: 18,
                        child: CircularProgressIndicator(strokeWidth: 2),
                      )
                    : const Icon(Icons.cloud_upload_outlined),
                label: Text(
                  _uploading ? 'Saving photo...' : 'Save Handover Photo',
                ),
              )
            else
              FilledButton(
                onPressed: () => Navigator.of(context).pop(true),
                child: const Text('Done'),
              ),
            if (uploaded == null) ...[
              const SizedBox(height: 8),
              TextButton(
                onPressed: _uploading
                    ? null
                    : () => Navigator.of(context).pop(false),
                child: const Text('Skip Photo'),
              ),
            ],
          ],
        ),
      ),
    );
  }
}

String _fileSize(int bytes) {
  if (bytes >= 1024 * 1024) {
    return '${(bytes / (1024 * 1024)).toStringAsFixed(1)} MB';
  }
  return '${(bytes / 1024).toStringAsFixed(0)} KB';
}

String _dateTime(DateTime? value) {
  if (value == null) {
    return 'Server time unavailable';
  }
  final local = value.toLocal();
  return '${local.year.toString().padLeft(4, '0')}-'
      '${local.month.toString().padLeft(2, '0')}-'
      '${local.day.toString().padLeft(2, '0')} '
      '${local.hour.toString().padLeft(2, '0')}:'
      '${local.minute.toString().padLeft(2, '0')}';
}
