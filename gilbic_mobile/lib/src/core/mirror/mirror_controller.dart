import 'dart:async';
import 'package:flutter/foundation.dart';
import 'package:flutter/scheduler.dart';
import 'package:gilbic_mobile/src/core/auth/app_role.dart';
import 'package:gilbic_mobile/src/core/auth/user_session.dart';
import 'package:gilbic_mobile/src/core/mirror/mirror_repository.dart';

typedef MirrorCapture = Future<Uint8List?> Function();

/// Memory-only sharing state. Every asynchronous result belongs to one epoch.
class MirrorController extends ChangeNotifier {
  MirrorController(
    this.repository, {
    bool automatic = true,
    DateTime Function()? now,
  }) : _now = now ?? DateTime.now,
       _automatic = automatic;

  final bool _automatic;
  final MirrorRepository repository;
  final DateTime Function() _now;
  Timer? _timer, _freshnessTimer;
  UserSession? _session;
  String _scope = '';
  String? _deviceScope;
  bool _foreground = true, _busy = false, _disposed = false;
  int _epoch = 0, _sequence = 0, _seen = 0;
  DateTime? _lastPending, _lastImage, _lastPublished;
  MirrorCapture? _capture;
  MirrorSession? sharing;
  List<MirrorSession> incoming = [];
  Uint8List? viewerBytes;
  String? notice;
  bool get busy => _busy;
  bool get mayView =>
      _session?.hasRole(AppRole.management) == true &&
      _session!.hasPermission('screen_share.view');
  bool get viewing =>
      sharing?.viewerUserId == _session?.userId && sharing != null;
  bool get canAccept =>
      _foreground && _capture != null && !_busy && sharing == null;
  bool _current(int epoch) =>
      !_disposed &&
      epoch == _epoch &&
      _foreground &&
      _session != null &&
      !_session!.isExpired;
  void _emit() {
    if (_disposed) return;
    if (SchedulerBinding.instance.schedulerPhase ==
        SchedulerPhase.persistentCallbacks) {
      SchedulerBinding.instance.addPostFrameCallback((_) {
        if (!_disposed) notifyListeners();
      });
    } else {
      notifyListeners();
    }
  }

  bool deviceChanged(String value) {
    final changed = _deviceScope != null && _deviceScope != value;
    if (changed) {
      stop();
      incoming = [];
    }
    _deviceScope = value;
    return !changed;
  }

  void _schedulePolling() {
    _timer?.cancel();
    _timer = null;
    if (!_automatic || _disposed || !_foreground || _session == null) return;
    _timer = Timer.periodic(
      Duration(seconds: sharing == null ? 15 : 1),
      (_) => unawaited(tick()),
    );
  }

  void attach(UserSession? session) {
    final roles = [...?session?.roles]..sort();
    final permissions = [...?session?.permissions]..sort();
    final scope = session == null
        ? ''
        : '${session.userId}|${session.rawRole}|$roles|$permissions';
    if (_scope != scope) {
      stop();
      _capture = null;
      incoming = [];
      _lastPending = null;
      _scope = scope;
    }
    _session = session;
    _schedulePolling();
  }

  void foreground(bool value) {
    _foreground = value;
    _schedulePolling();
    if (!value) {
      stop();
      incoming = [];
    }
  }

  /// Called synchronously before navigation, dialogs or surface replacement.
  void surfaceChanged(MirrorCapture? capture) {
    if (_capture == capture) return;
    _epoch++;
    _capture = capture;
    if (capture == null && sharing != null) stop();
    _emit();
  }

  void navigating({required bool eligible}) {
    _epoch++;
    _capture = null;
    if (!eligible || viewing) stop();
  }

  void _clearImage() {
    _freshnessTimer?.cancel();
    _freshnessTimer = null;
    viewerBytes?.fillRange(0, viewerBytes!.length, 0);
    viewerBytes = null;
    _lastImage = null;
  }

  void stop({String? message}) {
    final prior = sharing;
    _epoch++;
    sharing = null;
    _clearImage();
    _sequence = _seen = 0;
    _lastPublished = null;
    notice = message;
    _schedulePolling();
    if (prior != null) {
      unawaited(
        repository.action(prior, 'stop').catchError((Object _) => prior),
      );
    }
    _emit();
  }

  Future<void> accept(MirrorSession pending) async {
    if (!canAccept ||
        pending.holderUserId != _session?.userId ||
        pending.state != 'pending') {
      return;
    }
    final epoch = _epoch;
    _busy = true;
    _emit();
    try {
      final accepted = await repository.action(pending, 'accept');
      if (!_current(epoch)) {
        unawaited(
          repository
              .action(accepted, 'stop')
              .catchError((Object _) => accepted),
        );
        return;
      }
      if (accepted.id != pending.id ||
          accepted.holderUserId != _session!.userId ||
          accepted.state != 'active') {
        throw const FormatException('Invalid consent');
      }
      sharing = accepted;
      _schedulePolling();
      incoming = [];
      notice = null;
    } on Object {
      if (_current(epoch)) stop(message: 'Screen sharing could not start.');
    } finally {
      _busy = false;
      _emit();
    }
  }

  Future<void> decline(MirrorSession pending) async {
    incoming = [];
    _emit();
    try {
      await repository.action(pending, 'decline');
    } on Object {
      /* Pending requests expire server-side. */
    }
  }

  Future<void> request(MirrorTarget target) async {
    if (!mayView || _busy || sharing != null) return;
    final epoch = _epoch;
    _busy = true;
    _emit();
    try {
      final requested = await repository.request(target);
      if (!_current(epoch)) {
        unawaited(
          repository
              .action(requested, 'stop')
              .catchError((Object _) => requested),
        );
        return;
      }
      if (requested.viewerUserId != _session!.userId ||
          requested.holderUserId != target.userId ||
          requested.state != 'pending') {
        throw const FormatException('Invalid request');
      }
      sharing = requested;
      _schedulePolling();
      notice = null;
    } on Object {
      if (_current(epoch)) {
        stop(message: 'The screen-viewing request could not be sent.');
      }
    } finally {
      _busy = false;
      _emit();
    }
  }

  void expireImage() {
    if (_lastImage != null &&
        _now().difference(_lastImage!) >= const Duration(seconds: 3)) {
      _clearImage();
      _emit();
    }
  }

  Future<void> checkIncoming() async {
    _lastPending = null;
    await tick();
  }

  Future<void> tick() async {
    expireImage();
    if (_disposed || _busy || !_foreground || _session == null) return;
    if (_session!.isExpired) {
      stop(message: 'Sign in again to share.');
      return;
    }
    final epoch = _epoch;
    _busy = true;
    Uint8List? bytes;
    try {
      var grant = sharing;
      if (grant == null) {
        if (_lastPending != null &&
            _now().difference(_lastPending!) < const Duration(seconds: 15)) {
          return;
        }
        _lastPending = _now();
        final result = await repository.pending();
        if (_current(epoch)) {
          incoming = result
              .where(
                (item) =>
                    item.holderUserId == _session!.userId &&
                    item.state == 'pending' &&
                    item.expiresAt.isAfter(_now()),
              )
              .toList();
        }
        return;
      }
      if (!grant.expiresAt.isAfter(_now())) {
        stop(message: 'Screen sharing ended.');
        return;
      }
      if (viewing) {
        if (grant.state == 'pending') {
          final status = await repository.status(grant.id);
          if (!_current(epoch)) return;
          if (status.id != grant.id ||
              status.viewerUserId != _session!.userId ||
              status.generation != grant.generation ||
              status.terminal) {
            stop(message: 'Screen sharing ended.');
            return;
          }
          sharing = grant = status;
          if (grant.state != 'active') return;
        }
        final frame = await repository.frame(grant);
        if (frame == null) return;
        bytes = frame.bytes;
        if (!_current(epoch)) return;
        if (frame.generation != grant.generation || frame.sequence < _seen) {
          throw const FormatException('Stale frame generation');
        }
        if (frame.sequence == _seen) return;
        _clearImage();
        viewerBytes = bytes;
        bytes = null;
        _seen = frame.sequence;
        _lastImage = _now();
        if (_automatic) {
          _freshnessTimer = Timer(const Duration(seconds: 3), expireImage);
        }
      } else {
        final capture = _capture;
        if (capture == null) return;
        if (grant.state != 'active') {
          stop();
          return;
        }
        if (_lastPublished != null &&
            _now().difference(_lastPublished!) < const Duration(seconds: 1)) {
          return;
        }
        bytes = await capture();
        if (!_current(epoch) || bytes == null || bytes.length > 524288) return;
        final uploadGrant = grant;
        await repository.publish(
          uploadGrant,
          ++_sequence,
          bytes,
          stillCurrent: () =>
              _current(epoch) &&
              sharing?.id == uploadGrant.id &&
              sharing?.generation == uploadGrant.generation,
        );
        // Eligible navigation invalidates captures, not an already accepted upload.
        if (sharing?.id == grant.id &&
            sharing?.generation == grant.generation) {
          _lastPublished = _now();
        }
      }
    } on Object {
      if (_current(epoch)) {
        stop(
          message:
              'Screen sharing stopped. Request consent again to reconnect.',
        );
      }
    } finally {
      bytes?.fillRange(0, bytes.length, 0);
      _busy = false;
      _emit();
    }
  }

  @override
  void dispose() {
    _disposed = true;
    stop();
    _timer?.cancel();
    _freshnessTimer?.cancel();
    repository.close();
    super.dispose();
  }
}
