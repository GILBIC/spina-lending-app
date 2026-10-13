import 'package:flutter/material.dart';
import 'package:gilbic_mobile/src/core/network/spina_api.dart';

/// A denial ends this page's authority lifetime. Connectivity failures do not.
/// The shell creates fresh page state when the session's authority changes.
mixin PrivateAccessState<T extends StatefulWidget> on State<T> {
  SpinaApiException? _accessDenial;

  bool get privateAccessActive => mounted && _accessDenial == null;
  bool get privateAccessDenied => _accessDenial != null;

  void clearPrivateData();

  void requirePrivateAccess() {
    if (!privateAccessActive) {
      throw StateError('This private page is no longer active.');
    }
  }

  void revokePrivateAccess(Object error) {
    if (!privateAccessActive ||
        error is! SpinaApiException ||
        !const [401, 403, 426].contains(error.statusCode)) {
      return;
    }
    super.setState(() {
      _accessDenial = error;
      clearPrivateData();
    });
    final route = ModalRoute.of(context);
    final navigator = Navigator.of(context);
    WidgetsBinding.instance.addPostFrameCallback((_) {
      if (mounted && route != null && route.isActive && !route.isCurrent) {
        navigator.popUntil((candidate) => candidate == route);
      }
    });
  }

  @override
  void setState(VoidCallback fn) {
    // An older read/action may complete after another request revoked access.
    if (privateAccessActive) super.setState(fn);
  }

  Widget privateAccessDeniedPage() => Scaffold(
    appBar: AppBar(title: const Text('Access unavailable')),
    body: Center(
      child: Padding(
        padding: const EdgeInsets.all(24),
        child: Text(_accessDenial!.message, textAlign: TextAlign.center),
      ),
    ),
  );
}
