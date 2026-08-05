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
    super.key,
  });

  final UserSession session;
  final DeviceIdentityProvider deviceIdentityProvider;
  final String remittanceId;
  final String remittanceNumber;
  final RemittancePhotoRepository? repository;

  @override
  State<RemittancePhotoViewerPage> createState() =>
      _RemittancePhotoViewerPageState();
}

class _RemittancePhotoViewerPageState
    extends State<RemittancePhotoViewerPage> {
  late final RemittancePhotoRepository _repository;
  Uint8List? _photoBytes;
  String? _errorMessage;
  bool _loading = true;

  @override
  void initState() {
    super.initState();
    _repository = widget.repository ?? SpinaRemittancePhotoRepository();
    _load();
  }

  Future<void> _load() async {
    setState(() {
      _loading = true;
      _errorMessage = null;
    });
    try {
      final identity = await widget.deviceIdentityProvider.load();
      final bytes = await _repository.loadLatest(
        widget.session,
        deviceId: identity.installationId,
        remittanceId: widget.remittanceId,
      );
      if (mounted) {
        setState(() => _photoBytes = bytes);
      }
    } on SpinaApiException catch (error) {
      if (mounted) {
        setState(() => _errorMessage = error.message);
      }
    } on Object {
      if (mounted) {
        setState(() => _errorMessage = 'The handover photo could not be loaded.');
      }
    } finally {
      if (mounted) {
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
            onPressed: _loading ? null : _load,
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
                          Text(
                            _errorMessage!,
                            textAlign: TextAlign.center,
                          ),
                          const SizedBox(height: 16),
                          FilledButton.icon(
                            onPressed: _load,
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
                            errorBuilder: (context, error, stackTrace) => const Padding(
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
