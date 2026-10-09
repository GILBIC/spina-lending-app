import 'package:gilbic_mobile/src/core/network/staff_operations_client.dart'
    show staffAccessRejected;
import 'dart:typed_data';

import 'package:flutter/material.dart';
import 'package:gilbic_mobile/src/core/auth/user_session.dart';
import 'package:gilbic_mobile/src/core/device/device_identity.dart';
import 'package:gilbic_mobile/src/core/network/spina_api.dart';
import 'package:gilbic_mobile/src/core/remittance/remittance_photo_repository.dart';

class RemittancePhotoViewerPage extends StatefulWidget {
  const RemittancePhotoViewerPage({
    required this.session,
    required this.deviceIdentityProvider,
    required this.remittanceId,
    required this.remittanceNumber,
    this.repository,
    this.onAuthorityDenied,
    super.key,
  });

  final UserSession session;
  final DeviceIdentityProvider deviceIdentityProvider;
  final String remittanceId;
  final String remittanceNumber;
  final RemittancePhotoRepository? repository;
  final ValueChanged<SpinaApiException>? onAuthorityDenied;

  @override
  State<RemittancePhotoViewerPage> createState() =>
      _RemittancePhotoViewerPageState();
}

class _RemittancePhotoViewerPageState extends State<RemittancePhotoViewerPage> {
  late RemittancePhotoRepository _repository;
  Uint8List? _photoBytes;
  String? _errorMessage;
  bool _loading = true;

  @override
  void initState() {
    super.initState();
    _repository = widget.repository ?? SpinaRemittancePhotoRepository();
    _load();
  }

  int _epoch = 0;
  int _request = 0;
  bool _denied = false;
  bool _active(int epoch) => mounted && !_denied && epoch == _epoch;
  bool _current(int epoch, int request) =>
      _active(epoch) && request == _request;

  void _clearPrivate() {
    final bytes = _photoBytes;
    if (bytes != null) MemoryImage(bytes).evict();
    _photoBytes = null;
  }

  void _dismissPrivateRoutes() {
    final route = ModalRoute.of(context);
    final navigator = Navigator.of(context);
    WidgetsBinding.instance.addPostFrameCallback((_) {
      if (mounted && route != null && route.isActive && !route.isCurrent) {
        navigator.popUntil((candidate) => candidate == route);
      }
    });
  }

  bool _deny(SpinaApiException error, int epoch) {
    if (!_active(epoch) || !staffAccessRejected(error)) return false;
    _epoch++;
    setState(() {
      _denied = true;
      _clearPrivate();
      _loading = false;
      _errorMessage = '${error.message} Sign in again before continuing.';
    });
    _dismissPrivateRoutes();
    if (error.statusCode == 401 || error.statusCode == 426) {
      widget.onAuthorityDenied?.call(error);
    }
    return true;
  }

  @override
  void didUpdateWidget(RemittancePhotoViewerPage oldWidget) {
    super.didUpdateWidget(oldWidget);
    final scopeChanged =
        oldWidget.session.authorizationScopeKey !=
        widget.session.authorizationScopeKey;
    if (scopeChanged ||
        oldWidget.deviceIdentityProvider != widget.deviceIdentityProvider ||
        oldWidget.repository != widget.repository ||
        oldWidget.remittanceId != widget.remittanceId) {
      _epoch++;
      if (scopeChanged) _denied = false;
      _clearPrivate();
      _repository = widget.repository ?? SpinaRemittancePhotoRepository();
      _dismissPrivateRoutes();
      if (!_denied) _load();
    }
  }

  @override
  void dispose() {
    _clearPrivate();
    super.dispose();
  }

  Future<void> _load() async {
    if (_denied) return;
    final epoch = _epoch;
    final request = ++_request;
    final session = widget.session;
    final repository = _repository;
    setState(() {
      _loading = true;
      _errorMessage = null;
    });
    try {
      final identity = await widget.deviceIdentityProvider.load();
      if (!_current(epoch, request)) return;
      final bytes = await repository.loadLatest(
        session,
        deviceId: identity.installationId,
        remittanceId: widget.remittanceId,
      );
      if (_current(epoch, request)) {
        setState(() {
          if (!identical(_photoBytes, bytes)) _clearPrivate();
          _photoBytes = bytes;
        });
      }
    } on SpinaApiException catch (error) {
      if (_deny(error, epoch)) return;
      if (_current(epoch, request)) {
        setState(() => _errorMessage = error.message);
      }
    } on Object {
      if (_current(epoch, request)) {
        setState(
          () => _errorMessage = 'The handover photo could not be loaded.',
        );
      }
    } finally {
      if (_current(epoch, request)) {
        setState(() => _loading = false);
      }
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('Handover Photo'),
        actions: [
          IconButton(
            tooltip: 'Reload photo',
            onPressed: _loading || _denied ? null : _load,
            icon: const Icon(Icons.refresh),
          ),
        ],
      ),
      body: SafeArea(
        child: _loading && _photoBytes == null
            ? const Center(child: CircularProgressIndicator())
            : _errorMessage != null && _photoBytes == null
            ? Center(
                child: Padding(
                  padding: const EdgeInsets.all(24),
                  child: Column(
                    mainAxisSize: MainAxisSize.min,
                    children: [
                      const Icon(Icons.broken_image_outlined, size: 48),
                      const SizedBox(height: 12),
                      Text(_errorMessage!, textAlign: TextAlign.center),
                      const SizedBox(height: 16),
                      FilledButton.icon(
                        onPressed: _denied ? null : _load,
                        icon: const Icon(Icons.refresh),
                        label: const Text('Try again'),
                      ),
                    ],
                  ),
                ),
              )
            : ListView(
                padding: const EdgeInsets.all(16),
                children: [
                  Text(
                    widget.remittanceNumber,
                    style: Theme.of(context).textTheme.titleLarge,
                  ),
                  const SizedBox(height: 6),
                  const Text(
                    'Review this optional handover evidence before accepting the remittance. Acceptance should still happen only after the cash is physically in your possession.',
                  ),
                  const SizedBox(height: 16),
                  Card(
                    clipBehavior: Clip.antiAlias,
                    child: InteractiveViewer(
                      minScale: 0.8,
                      maxScale: 4,
                      child: Image.memory(
                        _photoBytes!,
                        fit: BoxFit.contain,
                        errorBuilder: (context, error, stackTrace) =>
                            const Padding(
                              padding: EdgeInsets.all(32),
                              child: Text('The photo could not be displayed.'),
                            ),
                      ),
                    ),
                  ),
                  const SizedBox(height: 12),
                  Text(
                    'This image is private and available only to the collector and selected recipient.',
                    textAlign: TextAlign.center,
                    style: Theme.of(context).textTheme.bodySmall,
                  ),
                ],
              ),
      ),
    );
  }
}
