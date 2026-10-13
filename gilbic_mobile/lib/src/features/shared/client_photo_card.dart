import 'dart:typed_data';
import 'dart:ui' as ui;
import 'package:flutter/material.dart';
import 'package:gilbic_mobile/src/core/auth/user_session.dart';
import 'package:gilbic_mobile/src/core/clients/client_photo_repository.dart';
import 'package:gilbic_mobile/src/core/device/device_identity.dart';
import 'package:gilbic_mobile/src/core/media/image_recovery_controller.dart';
import 'package:gilbic_mobile/src/core/network/spina_api.dart';
import 'package:gilbic_mobile/src/core/office/office_repository.dart';
import 'package:gilbic_mobile/src/core/remittance/remittance_photo.dart';
import 'package:gilbic_mobile/src/features/office/office_widgets.dart';
import 'package:gilbic_mobile/src/features/shared/image_recovery_scope.dart';
import 'package:image_picker/image_picker.dart';

class ClientPhotoCard extends StatefulWidget {
  const ClientPhotoCard({
    required this.session,
    required this.clientId,
    required this.clientName,
    this.deviceId,
    this.deviceIdentityProvider,
    this.repository,
    this.allowUpload = false,
    this.picker,
    super.key,
  });
  final UserSession session;
  final String clientId;
  final String clientName;
  final String? deviceId;
  final DeviceIdentityProvider? deviceIdentityProvider;
  final ClientPhotoRepository? repository;
  final bool allowUpload;
  final OfficePhotoPicker? picker;
  @override
  State<ClientPhotoCard> createState() => _ClientPhotoCardState();
}

class _ClientPhotoCardState extends State<ClientPhotoCard>
    with AutomaticKeepAliveClientMixin<ClientPhotoCard> {
  // CIF and portfolio use lazy lists. Scrolling is not a client/session change
  // and must not discard a selection or the identity of an uncertain upload.
  @override
  bool get wantKeepAlive => true;
  late ClientPhotoRepository _repository;
  ClientPhotoRecord? _record;
  OfficePhoto? _draft;
  _PhotoAttempt? _attempt;
  ui.Image? _image;
  String? _deviceId;
  String? _error;
  String? _notice;
  bool _busy = false;
  bool _editing = false;
  bool _confirmingLeave = false;
  int _revision = 0;

  bool get _protectRoute =>
      _draft != null || _attempt != null || (_busy && _editing);

  bool get _canUpload =>
      widget.allowUpload &&
      canManageClientPhoto(widget.session) &&
      _record?.canUpload == true;
  bool _current(int revision) => mounted && revision == _revision;

  @override
  void initState() {
    super.initState();
    _repository = widget.repository ?? ClientPhotoRepository();
    _load();
  }

  @override
  void didUpdateWidget(ClientPhotoCard oldWidget) {
    super.didUpdateWidget(oldWidget);
    if (oldWidget.session != widget.session ||
        oldWidget.clientId != widget.clientId ||
        oldWidget.deviceId != widget.deviceId ||
        oldWidget.deviceIdentityProvider != widget.deviceIdentityProvider ||
        oldWidget.repository != widget.repository ||
        oldWidget.allowUpload != widget.allowUpload) {
      _revision++;
      _clearPrivate();
      if (oldWidget.repository != widget.repository) {
        if (oldWidget.repository == null) _repository.close();
        _repository = widget.repository ?? ClientPhotoRepository();
      }
      _load();
    }
  }

  void _replaceImage(ui.Image? image) {
    final previous = _image;
    _image = image;
    if (previous != null) {
      WidgetsBinding.instance.addPostFrameCallback((_) => previous.dispose());
    }
  }

  void _clearDraft() {
    final pending = _attempt?.photo.bytes;
    if (pending != null) pending.fillRange(0, pending.length, 0);
    final draft = _draft?.bytes;
    if (draft != null && !identical(draft, pending)) {
      draft.fillRange(0, draft.length, 0);
    }
    _attempt = null;
    _draft = null;
    _editing = false;
  }

  void _clearPrivate() {
    _clearDraft();
    _replaceImage(null);
    _record = null;
    _deviceId = null;
    _error = null;
    _notice = null;
    _busy = false;
    _confirmingLeave = false;
  }

  Future<void> _requestLeave(Object? result) async {
    if (_attempt != null || (_busy && _editing)) {
      setState(() {
        _notice = _attempt != null
            ? 'Finish saving or retrying this photo upload before leaving.'
            : 'Finish choosing a photo before leaving.';
      });
      return;
    }
    if (_draft == null || _confirmingLeave) return;
    _confirmingLeave = true;
    final revision = _revision;
    final route = ModalRoute.of(context);
    final discard = await showDialog<bool>(
      context: context,
      builder: (context) => AlertDialog(
        title: const Text('Discard photo change?'),
        content: const Text('This preview has not been saved.'),
        actions: [
          TextButton(
            onPressed: () => Navigator.of(context).pop(false),
            child: const Text('Keep editing'),
          ),
          TextButton(
            onPressed: () => Navigator.of(context).pop(true),
            child: const Text('Discard photo'),
          ),
        ],
      ),
    );
    if (!_current(revision)) return;
    _confirmingLeave = false;
    if (discard != true || _attempt != null || _busy) return;
    setState(() {
      _clearDraft();
      _replaceImage(null);
    });
    // Rebuild this PopScope before asking the navigator to leave, while still
    // honoring any other guard owned by the enclosing CIF or portfolio page.
    await WidgetsBinding.instance.endOfFrame;
    if (mounted &&
        _current(revision) &&
        route?.isCurrent == true &&
        !_protectRoute) {
      await Navigator.of(context).maybePop(result);
    }
  }

  Future<ui.Image> _decode(Uint8List bytes) async {
    // RawImage bypasses the application-wide ImageCache. Each screen owns and
    // disposes its decoded image; encoded server bytes are cleared after use.
    final codec = await ui.instantiateImageCodec(
      bytes,
      targetWidth: 240,
      allowUpscaling: false,
    );
    try {
      return (await codec.getNextFrame()).image;
    } finally {
      codec.dispose();
    }
  }

  Future<void> _showSaved(ClientPhotoRecord record, int revision) async {
    final session = widget.session;
    final device = _deviceId!;
    final bytes = await _repository.content(session, device, record);
    if (bytes == null) return;
    try {
      if (!_current(revision)) return;
      final image = await _decode(bytes);
      if (!_current(revision)) {
        image.dispose();
        return;
      }
      setState(() => _replaceImage(image));
    } finally {
      bytes.fillRange(0, bytes.length, 0);
    }
  }

  Future<void> _load() async {
    if (_attempt != null) return;
    final revision = ++_revision;
    final session = widget.session;
    final clientId = widget.clientId;
    final repository = _repository;
    setState(() {
      _clearPrivate();
      _busy = true;
    });
    try {
      officeCheck(officeUuid(clientId));
      final deviceId =
          widget.deviceId ??
          (await (widget.deviceIdentityProvider ?? DeviceIdentityProvider())
                  .load())
              .installationId;
      if (!_current(revision)) return;
      _deviceId = deviceId;
      final record = await repository.load(session, deviceId, clientId);
      if (!_current(revision)) return;
      await _showSaved(record, revision);
      if (_current(revision)) setState(() => _record = record);
    } on Object catch (error) {
      if (_current(revision)) {
        setState(() {
          _clearPrivate();
          _error = error is SpinaApiException
              ? error.message
              : 'This photo could not be opened.';
        });
      }
    } finally {
      if (_current(revision)) setState(() => _busy = false);
    }
  }

  Future<void> _pick(ImageSource source) async {
    if (_busy || !_canUpload || _attempt != null) return;
    final revision = _revision;
    final recoveryContext = ImagePickContext(
      purpose: 'client_photo',
      target: widget.clientId,
      label: 'Client photo for ${widget.clientName}',
    );
    setState(() {
      _busy = true;
      _error = null;
      _notice = null;
    });
    Uint8List? ownedBytes;
    try {
      OfficePhoto? selected;
      if (widget.picker != null) {
        selected = await widget.picker!(source);
      } else {
        final file = await pickRecoverableImage(
          context,
          recoveryContext: recoveryContext,
          // This form renders its own uncached preview beside the client name.
          showRecoveryPreview: false,
          pick: () => ImagePicker().pickImage(
            source: source,
            requestFullMetadata: false,
          ),
        );
        if (!_current(revision) || file == null) return;
        if (await file.length() > clientPhotoMaxBytes) {
          throw const SpinaApiException('Choose a photo no larger than 5 MiB.');
        }
        final bytes = await file.readAsBytes();
        ownedBytes = bytes;
        selected = OfficePhoto(
          bytes,
          RemittancePhotoDraft.detectContentType(bytes) ?? '',
        );
      }
      if (!_current(revision) || selected == null) return;
      validateClientPhoto(selected.bytes, selected.mediaType);
      ownedBytes ??= Uint8List.fromList(selected.bytes);
      final image = await _decode(ownedBytes);
      if (!_current(revision)) {
        image.dispose();
        return;
      }
      final draft = OfficePhoto(ownedBytes, selected.mediaType);
      ownedBytes = null;
      setState(() {
        _clearDraft();
        _draft = draft;
        _editing = true;
        _replaceImage(image);
      });
    } on Object catch (error) {
      if (_current(revision)) {
        setState(
          () => _error = error is SpinaApiException
              ? error.message
              : 'Choose another JPEG or PNG photo.',
        );
      }
    } finally {
      ownedBytes?.fillRange(0, ownedBytes.length, 0);
      if (_current(revision)) setState(() => _busy = false);
    }
  }

  Future<void> _save() async {
    if (_busy || !_canUpload || _draft == null || _deviceId == null) return;
    final revision = _revision;
    final session = widget.session;
    final clientId = widget.clientId;
    final deviceId = _deviceId!;
    final pending = _attempt ??= _PhotoAttempt(
      _draft!,
      officeRequestId(),
      _record!.version,
    );
    setState(() {
      _busy = true;
      _error = null;
    });
    try {
      final saved = await _repository.upload(
        session,
        deviceId,
        clientId,
        requestId: pending.requestId,
        expectedVersion: pending.expectedVersion,
        bytes: pending.photo.bytes,
        contentType: pending.photo.mediaType,
      );
      if (!_current(revision)) return;
      setState(() {
        _clearDraft();
        _replaceImage(null);
        _record = saved;
        _notice = saved.version > pending.expectedVersion + 1
            ? 'Your upload was saved. Showing a newer client photo.'
            : 'Photo saved.';
      });
      // The server normalizes orientation and strips metadata. Display its
      // current bytes, never promote the original draft to the saved image.
      await _showSaved(saved, revision);
    } on Object catch (error) {
      if (!_current(revision)) return;
      final status = error is SpinaApiException ? error.statusCode : null;
      setState(() {
        _error = error is SpinaApiException
            ? error.message
            : 'The photo could not be saved.';
        if ([401, 403, 404, 426].contains(status)) {
          _clearDraft();
          _replaceImage(null);
          _record = null;
        } else if (identical(_attempt, pending)) {
          if (!pending.uncertain &&
              [400, 409, 413, 415, 422].contains(status)) {
            _clearDraft();
            _replaceImage(null);
            _record = null;
          } else {
            pending.uncertain = true;
            _error =
                'The upload may already be saved. Retry the same upload to check safely.';
          }
        }
      });
    } finally {
      if (_current(revision)) setState(() => _busy = false);
    }
  }

  @override
  void dispose() {
    _revision++;
    _clearDraft();
    _image?.dispose();
    _image = null;
    if (widget.repository == null) _repository.close();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    super.build(context);
    return PopScope<Object?>(
      canPop: !_protectRoute,
      onPopInvokedWithResult: (didPop, result) {
        if (!didPop) _requestLeave(result);
      },
      child: Card(
        child: Padding(
          padding: const EdgeInsets.all(12),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: [
              Row(
                children: [
                  Semantics(
                    label: _draft != null
                        ? 'Client photo preview'
                        : 'Client photo',
                    image: true,
                    child: ClipRRect(
                      borderRadius: BorderRadius.circular(12),
                      child: SizedBox(
                        width: 76,
                        height: 76,
                        child: _image == null
                            ? const ColoredBox(
                                color: Color(0xffeeeeee),
                                child: Icon(Icons.person_outline, size: 40),
                              )
                            : RawImage(
                                key: Key(
                                  _draft != null
                                      ? 'client-photo-preview'
                                      : 'client-photo-saved',
                                ),
                                image: _image,
                                fit: BoxFit.cover,
                              ),
                      ),
                    ),
                  ),
                  const SizedBox(width: 12),
                  Expanded(
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Text(
                          widget.clientName,
                          style: Theme.of(context).textTheme.titleMedium,
                        ),
                        if (_draft != null)
                          const Text('Preview — not saved')
                        else if (!_busy &&
                            _record?.photoId == null &&
                            _error == null)
                          const Text('No client photo'),
                      ],
                    ),
                  ),
                ],
              ),
              if (_busy)
                const Padding(
                  padding: EdgeInsets.only(top: 8),
                  child: LinearProgressIndicator(),
                ),
              if (_error != null)
                Padding(
                  padding: const EdgeInsets.only(top: 8),
                  child: Text(
                    _error!,
                    style: TextStyle(
                      color: Theme.of(context).colorScheme.error,
                    ),
                  ),
                ),
              if (_notice != null) Text(_notice!),
              if (_canUpload && !_editing)
                TextButton(
                  onPressed: _busy
                      ? null
                      : () => setState(() => _editing = true),
                  child: Text(
                    _record?.photoId == null ? 'Add photo' : 'Change photo',
                  ),
                ),
              if (_canUpload && _editing) ...[
                const Padding(
                  padding: EdgeInsets.only(top: 8),
                  child: Text(
                    'JPEG or PNG, up to 5 MiB. This photo is optional and does not perform face or liveness verification.',
                  ),
                ),
                Wrap(
                  spacing: 8,
                  children: [
                    for (final source in ImageSource.values)
                      OutlinedButton.icon(
                        onPressed: _busy || _attempt != null
                            ? null
                            : () => _pick(source),
                        icon: Icon(
                          source == ImageSource.camera
                              ? Icons.camera_alt_outlined
                              : Icons.photo_library_outlined,
                        ),
                        label: Text(
                          source == ImageSource.camera ? 'Camera' : 'Gallery',
                        ),
                      ),
                  ],
                ),
                if (_draft != null)
                  FilledButton(
                    onPressed: _busy ? null : _save,
                    child: Text(
                      _attempt != null ? 'Retry same upload' : 'Save photo',
                    ),
                  ),
                if (_attempt == null)
                  TextButton(
                    onPressed: _busy ? null : _load,
                    child: const Text('Cancel photo change'),
                  ),
              ],
              if (!_editing)
                TextButton(
                  onPressed: _busy || _attempt != null ? null : _load,
                  child: const Text('Reload photo'),
                ),
            ],
          ),
        ),
      ),
    );
  }
}

class _PhotoAttempt {
  _PhotoAttempt(this.photo, this.requestId, this.expectedVersion);
  final OfficePhoto photo;
  final String requestId;
  final int expectedVersion;
  bool uncertain = false;
}
