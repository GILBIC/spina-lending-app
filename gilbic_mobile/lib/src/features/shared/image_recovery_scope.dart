import 'dart:async';
import 'dart:convert';
import 'dart:typed_data';

import 'package:flutter/material.dart';
import 'package:gilbic_mobile/src/core/auth/user_session.dart';
import 'package:gilbic_mobile/src/core/config/api_config.dart';
import 'package:gilbic_mobile/src/core/device/device_identity.dart';
import 'package:gilbic_mobile/src/core/media/image_recovery_controller.dart';
import 'package:image_picker/image_picker.dart';

class ImageRecoveryScope extends InheritedNotifier<ImageRecoveryController> {
  const ImageRecoveryScope({
    required ImageRecoveryController controller,
    required super.child,
    super.key,
  }) : super(notifier: controller);

  static ImageRecoveryController? of(BuildContext context) => context
      .dependOnInheritedWidgetOfExactType<ImageRecoveryScope>()
      ?.notifier;
}

Future<XFile?> pickRecoverableImage(
  BuildContext context, {
  required ImagePickContext recoveryContext,
  required Future<XFile?> Function() pick,
  String recoveryActionLabel = 'Use photo',
}) async {
  final recovery = ImageRecoveryScope.of(context);
  // Standalone page tests and non-app hosts retain the normal picker contract.
  if (recovery == null) return pick();
  if (!recovery.ready || recovery.busy) {
    throw StateError('Please wait for photo recovery to finish.');
  }
  // The native gallery copies results asynchronously; it may finish after the
  // resume check. Drain the original context before offering a new selection.
  await recovery.recoverPending();
  if (!context.mounted) return null;
  final recovered = recovery.recovered;
  final pending = recovery.pending;
  if (recovered != null || pending != null) {
    final matches =
        recovered != null && recovery.recoveredFor(recoveryContext) != null;
    final action = await showDialog<String>(
      context: context,
      builder: (dialogContext) => AlertDialog(
        title: Text(
          pending != null
              ? 'Photo selection interrupted'
              : matches
              ? 'Recover photo?'
              : 'A different form has a recovered photo',
        ),
        content: SingleChildScrollView(
          child: Column(
            mainAxisSize: MainAxisSize.min,
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text(
                pending != null
                    ? 'The previous selection for ${pending.label} has not finished restoring. Keep it to check again later, or discard it before choosing another photo.'
                    : matches
                    ? 'Spina restarted while choosing this photo for ${recoveryContext.label}. Review it before continuing. Nothing has been submitted.'
                    : 'The recovered photo belongs to ${recovered!.context.label}. Return to that form to use it, or discard it before choosing another.',
              ),
              if (matches) ...[
                const SizedBox(height: 12),
                _RecoveredPhotoPreview(file: recovered.file),
              ],
            ],
          ),
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(dialogContext),
            child: const Text('Keep for later'),
          ),
          TextButton(
            onPressed: () => Navigator.pop(dialogContext, 'discard'),
            child: const Text('Discard and choose another'),
          ),
          if (matches)
            FilledButton(
              onPressed: () => Navigator.pop(dialogContext, 'use'),
              child: Text(recoveryActionLabel),
            ),
        ],
      ),
    );
    if (!context.mounted || action == null) return null;
    if (action == 'use') return recovery.takeRecovered(recoveryContext);
    await recovery.discard();
    if (!context.mounted) return null;
  }
  return recovery.pick(recoveryContext, pick);
}

class _RecoveredPhotoPreview extends StatefulWidget {
  const _RecoveredPhotoPreview({required this.file});
  final XFile file;
  @override
  State<_RecoveredPhotoPreview> createState() => _RecoveredPhotoPreviewState();
}

class _RecoveredPhotoPreviewState extends State<_RecoveredPhotoPreview> {
  late final Future<Uint8List?> bytes = _read();
  Future<Uint8List?> _read() async {
    if (await widget.file.length() > 10 * 1024 * 1024) return null;
    return widget.file.readAsBytes();
  }

  @override
  Widget build(BuildContext context) => FutureBuilder<Uint8List?>(
    future: bytes,
    builder: (context, snapshot) {
      if (snapshot.connectionState != ConnectionState.done) {
        return const LinearProgressIndicator();
      }
      final data = snapshot.data;
      if (data == null) {
        return const Text(
          'Preview unavailable. The form will check the image before submission.',
        );
      }
      return Image.memory(
        data,
        height: 180,
        cacheWidth: 480,
        fit: BoxFit.contain,
        errorBuilder: (context, error, stack) =>
            const Text('Preview unavailable. Choose another image if needed.'),
      );
    },
  );
}

/// Lives beneath MaterialApp but uses the app-owned coordinator so route/auth
/// resets never create competing readers of Android's one lost-result cache.
class ImageRecoveryHost extends StatefulWidget {
  const ImageRecoveryHost({
    required this.controller,
    required this.session,
    required this.sessionRestored,
    required this.deviceIdentityProvider,
    required this.child,
    super.key,
  });
  final ImageRecoveryController controller;
  final UserSession? session;
  final bool sessionRestored;
  final DeviceIdentityProvider deviceIdentityProvider;
  final Widget child;
  @override
  State<ImageRecoveryHost> createState() => _ImageRecoveryHostState();
}

class _ImageRecoveryHostState extends State<ImageRecoveryHost>
    with WidgetsBindingObserver {
  int _binding = 0;
  bool _bound = false;
  String _scope(UserSession? session) {
    if (session == null) return 'signed-out';
    final roles = [...session.roles]..sort();
    final permissions = [...session.permissions]..sort();
    return jsonEncode([
      session.userId,
      session.rawRole.toLowerCase(),
      roles,
      permissions,
    ]);
  }

  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addObserver(this);
    _bind();
  }

  @override
  void didChangeAppLifecycleState(AppLifecycleState state) {
    if (state == AppLifecycleState.resumed && _bound) {
      unawaited(widget.controller.recoverPending());
    }
  }

  @override
  void didUpdateWidget(ImageRecoveryHost oldWidget) {
    super.didUpdateWidget(oldWidget);
    if (oldWidget.sessionRestored != widget.sessionRestored ||
        _scope(oldWidget.session) != _scope(widget.session) ||
        oldWidget.controller != widget.controller) {
      _bind();
    }
  }

  Future<void> _bind() async {
    final revision = ++_binding;
    _bound = false;
    widget.controller.suspend();
    if (!widget.sessionRestored) return;
    final controller = widget.controller;
    final session = widget.session;
    try {
      if (session == null) {
        await controller.initialize(null);
      } else {
        final identity = await widget.deviceIdentityProvider.load();
        if (!mounted || revision != _binding) return;
        await controller.initialize(
          jsonEncode([
            ApiConfig.baseUrl,
            identity.installationId,
            _scope(session),
          ]),
        );
      }
    } on Object {
      // Device identity failures cannot attach an old photo to an unknown user.
      if (mounted && revision == _binding) await controller.initialize(null);
    }
    if (mounted && revision == _binding) {
      setState(() => _bound = true);
      if (WidgetsBinding.instance.lifecycleState == AppLifecycleState.resumed) {
        await controller.recoverPending();
      }
    }
  }

  @override
  void dispose() {
    _binding++;
    WidgetsBinding.instance.removeObserver(this);
    super.dispose();
  }

  @override
  Widget build(BuildContext context) => ImageRecoveryScope(
    controller: widget.controller,
    child: ListenableBuilder(
      listenable: widget.controller,
      builder: (context, _) {
        if (widget.sessionRestored && !_bound) {
          return const Scaffold(
            body: Center(child: CircularProgressIndicator()),
          );
        }
        final recovered = widget.session == null
            ? null
            : widget.controller.recovered;
        final error = widget.session == null ? null : widget.controller.error;
        final pending = widget.session == null
            ? null
            : widget.controller.pending;
        return Column(
          children: [
            if (recovered != null || error != null || pending != null)
              Material(
                color: Theme.of(context).colorScheme.secondaryContainer,
                child: SafeArea(
                  bottom: false,
                  child: Padding(
                    padding: const EdgeInsets.all(12),
                    child: Row(
                      children: [
                        const Icon(Icons.photo_outlined),
                        const SizedBox(width: 10),
                        Expanded(
                          child: Text(
                            recovered != null
                                ? 'Photo recovered for ${recovered.context.label}. Open that form and choose a photo to review it.'
                                : error ??
                                      'Photo selection was interrupted. Return to the original form and choose a photo to continue.',
                          ),
                        ),
                      ],
                    ),
                  ),
                ),
              ),
            Expanded(child: widget.child),
          ],
        );
      },
    ),
  );
}
