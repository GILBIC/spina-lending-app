import 'dart:async';
import 'package:flutter/material.dart';
import 'package:gilbic_mobile/src/core/auth/user_session.dart';
import 'package:gilbic_mobile/src/core/device/device_identity.dart';
import 'package:gilbic_mobile/src/core/network/staff_operations_client.dart';
import 'package:gilbic_mobile/src/core/employee_operations/attendance_outbox.dart';
import 'package:gilbic_mobile/src/core/employee_operations/attendance_vault_factory.dart';
import 'package:gilbic_mobile/src/core/employee_operations/employee_operations_repository.dart';

/// Only attendance is queued. This coordinator is owned by the signed-in app,
/// so reopening/resuming the app syncs pending captures without visiting HR.
class EmployeeOperationsService extends ChangeNotifier {
  EmployeeOperationsService({
    required this.deviceIdentityProvider,
    EmployeeOperationsRepository? repository,
    AttendanceOutbox? outbox,
  }) : repository =
           repository ??
           EmployeeOperationsRepository(
             StaffOperationsClient(
               deviceIdentityProvider: deviceIdentityProvider,
             ),
           ),
       outbox = outbox ?? AttendanceOutbox(createAttendanceVault());
  final DeviceIdentityProvider deviceIdentityProvider;
  final EmployeeOperationsRepository repository;
  final AttendanceOutbox outbox;
  UserSession? _session;
  String? _authenticationKey;
  AttendanceBinding? binding;
  Timer? _timer;
  int _epoch = 0;
  bool _foreground = true;
  bool _working = false;
  bool _disposed = false;
  String? syncMessage;
  bool accessDenied = false;

  String _bindingKey(String userId, String installationId) =>
      'actor|$userId|$installationId';
  void attach(UserSession? session) {
    final authentication = session == null
        ? null
        : '${session.userId}|${session.accessToken}';
    final changed = authentication != _authenticationKey;
    if (changed) {
      _epoch++;
      outbox.detach();
      binding = null;
      accessDenied = false;
    }
    _authenticationKey = authentication;
    _session = session;
    _timer?.cancel();
    if (session != null && _foreground) {
      unawaited(
        changed ? _resumeAfterAuthentication(session, authentication!) : sync(),
      );
      _timer = Timer.periodic(
        const Duration(seconds: 45),
        (_) => unawaited(sync()),
      );
    }
  }

  Future<void> _resumeAfterAuthentication(
    UserSession session,
    String authentication,
  ) async {
    try {
      await restoreBinding();
      if (_disposed ||
          _authenticationKey != authentication ||
          !_foreground ||
          session.isExpired) {
        return;
      }
      if (binding == null) {
        final device = await deviceIdentityProvider.load();
        final saved = await outbox.vault.read(
          _bindingKey(session.userId, device.installationId),
        );
        if (saved?['device_id'] is String) {
          final workspace = await repository.workspace(session);
          if (_disposed || _authenticationKey != authentication || !_foreground) {
            return;
          }
          await acceptWorkspace(session, workspace);
        }
      }
      if (!_disposed && _authenticationKey == authentication) await sync();
    } on Object catch (error) {
      if (!_disposed &&
          _authenticationKey == authentication &&
          staffAccessRejected(error)) {
        await denyAttendance();
        if (!_disposed) notifyListeners();
      }
      // Authentication/storage/network failure never discards an original capture.
    }
  }

  void foreground(bool active) {
    _foreground = active;
    if (!active) {
      _timer?.cancel();
      _epoch++;
      outbox.detach();
    } else {
      attach(_session);
    }
  }

  Future<void> acceptWorkspace(
    UserSession session,
    EmployeeWorkspace workspace,
  ) async {
    final epoch = ++_epoch;
    outbox.detach();
    final device = await deviceIdentityProvider.load();
    if (_disposed || epoch != _epoch || _session?.userId != session.userId) {
      return;
    }
    final id = workspace.actor['device_id'];
    if (!workspace.can('can_self_service') || id is! String || id.isEmpty) {
      await denyAttendance(accessRevoked: false);
      return;
    }
    final bound = AttendanceBinding(
      userId: session.userId,
      installationId: device.installationId,
      deviceId: id,
    );
    final events =
        workspace
            .records('attendance')
            .where((row) => row['employee_id'] == session.userId)
            .toList()
          ..sort(
            (a, b) =>
                DateTime.parse(
                  (a['payload'] as Map)['captured_at'] as String,
                ).compareTo(
                  DateTime.parse(
                    (b['payload'] as Map)['captured_at'] as String,
                  ),
                ),
          );
    final predecessors = <String, String>{};
    final sequences = <String, int>{};
    for (final event in events) {
      final payload = event['payload'] as Map;
      final day = attendanceWorkDate(
        DateTime.parse(payload['captured_at'] as String),
      );
      predecessors[day] = event['id'] as String;
      if (payload['device_id'] == id) {
        final sequence = payload['sequence'] as int;
        if (sequence > (sequences[day] ?? 0)) sequences[day] = sequence;
      }
    }
    await outbox.authorize(
      bound,
      predecessors: predecessors,
      sequences: sequences,
    );
    await outbox.vault.update(
      _bindingKey(session.userId, device.installationId),
      (_) => {'device_id': id},
    );
    if (_session?.userId == session.userId && !_disposed && epoch == _epoch) {
      binding = bound;
      accessDenied = false;
    }
  }

  Future<void> denyAttendance({bool accessRevoked = true}) async {
    _epoch++;
    outbox.detach();
    try {
      await restoreBinding();
    } on Object {
      // Access revocation must not depend on reading local storage.
    }
    final current = binding;
    binding = null;
    accessDenied = accessRevoked;
    if (current != null) {
      try {
        await outbox.vault.update(
          current.key,
          (row) => row!..['authorized'] = false,
        );
      } on Object {
        // Retain unconfirmed captures; this live service is still detached.
      }
    }
  }

  Future<void> restoreBinding() async {
    final session = _session;
    final epoch = _epoch;
    if (session == null) return;
    final device = await deviceIdentityProvider.load();
    final saved = await outbox.vault.read(
      _bindingKey(session.userId, device.installationId),
    );
    final id = saved?['device_id'];
    if (id is String && epoch == _epoch && !_disposed) {
      final candidate = AttendanceBinding(
        userId: session.userId,
        installationId: device.installationId,
        deviceId: id,
      );
      if (await outbox.isAuthorized(candidate) &&
          epoch == _epoch &&
          !_disposed) {
        binding = candidate;
      }
    }
  }

  Future<void> sync() async {
    final session = _session;
    final epoch = _epoch;
    if (_disposed ||
        accessDenied ||
        _working ||
        !_foreground ||
        session == null ||
        session.isExpired) {
      return;
    }
    _working = true;
    try {
      if (binding == null) await restoreBinding();
      final current = binding;
      if (current == null || epoch != _epoch) return;
      await outbox.sync(current, (body) async {
        if (epoch != _epoch || _session?.userId != current.userId) {
          throw Exception('Session changed.');
        }
        return repository.submit(session, EmployeeAttempt(body));
      });
      if (!await outbox.isAuthorized(current) && epoch == _epoch) {
        binding = null;
        accessDenied = true;
      }
      syncMessage = null;
    } on Object {
      syncMessage = 'Saved attendance is waiting for a secure connection.';
    } finally {
      _working = false;
      if (!_disposed) notifyListeners();
    }
  }

  @override
  void dispose() {
    _disposed = true;
    _epoch++;
    outbox.detach();
    _timer?.cancel();
    repository.close();
    super.dispose();
  }
}

class EmployeeOperationsScope extends InheritedWidget {
  const EmployeeOperationsScope({
    required this.service,
    required super.child,
    super.key,
  });
  final EmployeeOperationsService service;
  static EmployeeOperationsService? maybeOf(BuildContext context) => context
      .dependOnInheritedWidgetOfExactType<EmployeeOperationsScope>()
      ?.service;
  @override
  bool updateShouldNotify(EmployeeOperationsScope oldWidget) =>
      oldWidget.service != service;
}
