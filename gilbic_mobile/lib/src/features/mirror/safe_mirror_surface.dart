import 'dart:math' as math;
import 'dart:typed_data';
import 'dart:ui' as ui;
import 'package:flutter/material.dart';
import 'package:flutter/rendering.dart';
import 'package:gilbic_mobile/src/core/mirror/mirror_controller.dart';

class MirrorScope extends InheritedNotifier<MirrorController> {
  const MirrorScope({
    required MirrorController controller,
    required super.child,
    super.key,
  }) : super(notifier: controller);
  static MirrorController? maybeOf(BuildContext context) =>
      context.getInheritedWidgetOfExactType<MirrorScope>()?.notifier;
}

/// Explicit route allowlist. Unnamed routes, dialogs and native activities fail closed.
class MirrorNavigationObserver extends NavigatorObserver {
  MirrorNavigationObserver(this.controller);
  final MirrorController controller;
  static const safeNames = {
    '/',
    '/mirror-safe/collector-review',
    '/mirror-safe/management-portfolio',
  };
  void _transition(Route<dynamic>? route) => controller.navigating(
    eligible: route is PageRoute && safeNames.contains(route.settings.name),
  );
  @override
  void didPush(Route<dynamic> route, Route<dynamic>? previousRoute) =>
      _transition(route);
  @override
  void didPop(Route<dynamic> route, Route<dynamic>? previousRoute) =>
      _transition(previousRoute);
  @override
  void didRemove(Route<dynamic> route, Route<dynamic>? previousRoute) =>
      _transition(null);
  @override
  void didReplace({Route<dynamic>? newRoute, Route<dynamic>? oldRoute}) =>
      _transition(newRoute);
  @override
  void didStartUserGesture(
    Route<dynamic> route,
    Route<dynamic>? previousRoute,
  ) => controller.navigating(eligible: false);
}

/// Never wrap the Navigator or a credential/media surface with this widget.
class SafeMirrorSurface extends StatefulWidget {
  const SafeMirrorSurface({required this.child, super.key});
  final Widget child;
  @override
  State<SafeMirrorSurface> createState() => _SafeMirrorSurfaceState();
}

class _SafeMirrorSurfaceState extends State<SafeMirrorSurface> {
  final _boundary = GlobalKey();
  MirrorController? _controller;
  Route<dynamic>? _route;
  bool _scheduled = false;
  bool get _eligible =>
      mounted &&
      _route?.isCurrent == true &&
      MirrorNavigationObserver.safeNames.contains(_route?.settings.name);
  @override
  void didChangeDependencies() {
    super.didChangeDependencies();
    _controller = MirrorScope.maybeOf(context);
    _route = ModalRoute.of(context);
    _registerAfterPaint();
  }

  @override
  void didUpdateWidget(covariant SafeMirrorSurface oldWidget) {
    super.didUpdateWidget(oldWidget);
    _registerAfterPaint();
  }

  void _registerAfterPaint() {
    if (_scheduled) return;
    _scheduled = true;
    WidgetsBinding.instance.addPostFrameCallback((_) {
      _scheduled = false;
      if (_eligible) _controller?.surfaceChanged(_capture);
    });
  }

  Future<Uint8List?> _capture() async {
    if (!_eligible ||
        WidgetsBinding.instance.lifecycleState != AppLifecycleState.resumed) {
      return null;
    }
    final boundary = _boundary.currentContext?.findRenderObject();
    if (boundary is! RenderRepaintBoundary ||
        !boundary.attached ||
        boundary.debugNeedsPaint ||
        boundary.size.isEmpty) {
      return null;
    }
    final ratio = math.min(
      1.0,
      720 / math.max(boundary.size.width, boundary.size.height),
    );
    ui.Image? image;
    try {
      image = await boundary.toImage(pixelRatio: ratio);
      if (!_eligible) return null;
      final encoded = await image.toByteData(format: ui.ImageByteFormat.png);
      if (!_eligible || encoded == null || encoded.lengthInBytes > 524288) {
        return null;
      }
      return Uint8List.fromList(
        encoded.buffer.asUint8List(
          encoded.offsetInBytes,
          encoded.lengthInBytes,
        ),
      );
    } finally {
      image?.dispose();
    }
  }

  @override
  void dispose() {
    // Route transitions already invalidate synchronously through the observer.
    if (_route?.isCurrent == true) _controller?.navigating(eligible: false);
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    _registerAfterPaint();
    return RepaintBoundary(key: _boundary, child: widget.child);
  }
}
