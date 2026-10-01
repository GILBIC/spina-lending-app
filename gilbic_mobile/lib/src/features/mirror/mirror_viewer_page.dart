import 'dart:typed_data';
import 'dart:ui' as ui;
import 'package:flutter/material.dart';
import 'package:gilbic_mobile/src/core/mirror/mirror_controller.dart';
import 'package:gilbic_mobile/src/core/mirror/mirror_repository.dart';

class MirrorViewerPage extends StatefulWidget {
  const MirrorViewerPage({required this.controller, super.key});
  final MirrorController controller;
  @override
  State<MirrorViewerPage> createState() => _MirrorViewerPageState();
}

class _MirrorViewerPageState extends State<MirrorViewerPage> {
  List<MirrorTarget>? _targets;
  String? _error;
  @override
  void initState() {
    super.initState();
    _load();
  }

  Future<void> _load() async {
    if (!widget.controller.mayView) return;
    try {
      final targets = await widget.controller.repository.targets();
      if (mounted) setState(() => _targets = targets);
    } on Object {
      if (mounted) setState(() => _error = 'Screen viewing is unavailable.');
    }
  }

  @override
  void dispose() {
    widget.controller.stop();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) => Scaffold(
    appBar: AppBar(title: const Text('Consented screen view')),
    body: AnimatedBuilder(
      animation: widget.controller,
      builder: (context, _) {
        final controller = widget.controller;
        if (!controller.mayView) {
          return const Center(
            child: Text('Your account does not have access to screen viewing.'),
          );
        }
        if (controller.sharing != null) {
          return Column(
            children: [
              const Padding(
                padding: EdgeInsets.all(12),
                child: Text(
                  'View only. The account holder can stop at any time.',
                ),
              ),
              Expanded(
                child: controller.viewerBytes == null
                    ? Center(
                        child: Text(
                          controller.sharing!.state == 'pending'
                              ? 'Waiting for the account holder to allow viewing…'
                              : 'Waiting for a fresh screen…',
                        ),
                      )
                    : MirrorFrameView(
                        bytes: controller.viewerBytes!,
                        onInvalid: () => controller.stop(
                          message: 'The shared screen could not be displayed.',
                        ),
                      ),
              ),
            ],
          );
        }
        return ListView(
          padding: const EdgeInsets.all(16),
          children: [
            if (controller.notice != null) Text(controller.notice!),
            if (_error != null) Text(_error!),
            const Text(
              'Choose an account device. Viewing starts only after its holder allows it.',
            ),
            if (_targets == null && _error == null)
              const LinearProgressIndicator(),
            for (final target in _targets ?? <MirrorTarget>[])
              ListTile(
                title: Text(target.name),
                subtitle: Text(target.deviceName),
                trailing: const Icon(Icons.visibility_outlined),
                onTap: controller.busy
                    ? null
                    : () => controller.request(target),
              ),
            if (_targets?.isEmpty == true)
              const Text('No eligible account devices.'),
          ],
        );
      },
    ),
  );
}

/// RawImage avoids Flutter's global ImageCache retaining private frames.
typedef MirrorImageDecoder = Future<ui.Image> Function(Uint8List bytes);
Future<ui.Image> _decodeFrame(Uint8List bytes) async {
  final codec = await ui.instantiateImageCodec(bytes);
  try {
    return (await codec.getNextFrame()).image;
  } finally {
    codec.dispose();
  }
}

class MirrorFrameView extends StatefulWidget {
  const MirrorFrameView({
    required this.bytes,
    required this.onInvalid,
    this.decoder = _decodeFrame,
    super.key,
  });
  final Uint8List bytes;
  final VoidCallback onInvalid;
  final MirrorImageDecoder decoder;
  @override
  State<MirrorFrameView> createState() => _MirrorFrameViewState();
}

class _MirrorFrameViewState extends State<MirrorFrameView> {
  ui.Image? _image;
  int _generation = 0;
  @override
  void initState() {
    super.initState();
    _decode();
  }

  @override
  void didUpdateWidget(covariant MirrorFrameView oldWidget) {
    super.didUpdateWidget(oldWidget);
    if (!identical(oldWidget.bytes, widget.bytes)) _decode();
  }

  Future<void> _decode() async {
    final generation = ++_generation;
    _image?.dispose();
    _image = null;
    ui.Image? image;
    try {
      image = await widget.decoder(widget.bytes);
      if (!mounted || generation != _generation) return;
      setState(() {
        _image = image;
        image = null;
      });
    } on Object {
      if (mounted && generation == _generation) widget.onInvalid();
    } finally {
      image?.dispose();
    }
  }

  @override
  void dispose() {
    _generation++;
    _image?.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) =>
      RawImage(image: _image, fit: BoxFit.contain);
}
