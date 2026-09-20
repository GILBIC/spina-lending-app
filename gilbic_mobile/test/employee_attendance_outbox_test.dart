import 'dart:async';
import 'package:flutter_test/flutter_test.dart';
import 'package:gilbic_mobile/src/core/employee_operations/attendance_outbox.dart';
import 'package:gilbic_mobile/src/core/network/spina_api.dart';

const binding = AttendanceBinding(
  userId: 'user-a',
  installationId: 'install-a',
  deviceId: 'device-a',
);
void main() {
  test(
    'Manila midnight resets sequence and predecessor after restart; another device hydrates the employee chain',
    () async {
      final vault = MemoryAttendanceVault();
      final queue = AttendanceOutbox(vault);
      await queue.authorize(binding);
      final yesterday = await queue.capture(
        binding,
        'clock_out',
        capturedAt: DateTime.utc(2026, 9, 20, 15, 59),
        offline: true,
      );
      final restarted = AttendanceOutbox(vault);
      final today = await restarted.capture(
        binding,
        'clock_in',
        capturedAt: DateTime.utc(2026, 9, 20, 16, 0),
        offline: true,
      );
      expect(today.command['sequence'], 1);
      expect(today.command['previous_event_id'], isNull);
      expect(today.command['id'], isNot(yesterday.command['id']));
      const otherDevice = AttendanceBinding(
        userId: 'user-a',
        installationId: 'install-b',
        deviceId: 'device-b',
      );
      await restarted.authorize(
        otherDevice,
        predecessors: {'2026-09-21': today.command['id'] as String},
      );
      final moved = await restarted.capture(
        otherDevice,
        'break_start',
        capturedAt: DateTime.utc(2026, 9, 21, 2),
        offline: false,
      );
      expect(moved.command['previous_event_id'], today.command['id']);
      expect(moved.command['sequence'], 1);
      expect((await restarted.entries(binding)).length, 2);
    },
  );
  test(
    'restart retains exact command and identity after uncertain send; then sends chain once',
    () async {
      final vault = MemoryAttendanceVault();
      final first = AttendanceOutbox(vault);
      await first.authorize(binding);
      final captured = await first.capture(
        binding,
        'clock_in',
        capturedAt: DateTime.utc(2026, 9, 20, 1),
        offline: true,
      );
      final sent = <Map<String, dynamic>>[];
      await first.sync(binding, (body) async {
        sent.add(body);
        throw TimeoutException('lost response');
      });
      final restarted = AttendanceOutbox(vault);
      final second = await restarted.capture(
        binding,
        'break_start',
        capturedAt: DateTime.utc(2026, 9, 20, 5),
        offline: true,
      );
      expect(second.command['previous_event_id'], captured.command['id']);
      expect(second.command['sequence'], 2);
      await restarted.sync(binding, (body) async {
        sent.add(body);
        return {
          'id': body['id'],
          'request_id': body['request_id'],
          'version': 1,
          'status': 'accepted',
        };
      });
      expect(sent[0], sent[1]);
      expect(sent[2]['id'], second.command['id']);
      expect(
        (await restarted.entries(binding)).every((e) => e.state == 'accepted'),
        isTrue,
      );
      await restarted.sync(
        binding,
        (_) async => throw StateError('must not resend accepted'),
      );
    },
  );
  test(
    'account/device boundaries and revocation retain private pending events',
    () async {
      final queue = AttendanceOutbox(MemoryAttendanceVault());
      await queue.authorize(binding);
      await queue.capture(binding, 'clock_in', offline: true);
      const other = AttendanceBinding(
        userId: 'user-b',
        installationId: 'install-a',
        deviceId: 'device-a',
      );
      expect(await queue.entries(other), isEmpty);
      await expectLater(
        queue.capture(other, 'clock_in', offline: true),
        throwsA(isA<StateError>()),
      );
      await queue.sync(
        binding,
        (_) async => throw const SpinaApiException('revoked', statusCode: 403),
      );
      await expectLater(
        queue.capture(binding, 'clock_out', offline: true),
        throwsA(isA<StateError>()),
      );
      expect((await queue.entries(binding)).single.state, 'pending');
      await queue.authorize(binding);
      await queue.sync(
        binding,
        (body) async => {
          'id': body['id'],
          'request_id': body['request_id'],
          'version': 1,
          'status': 'pending_review',
        },
      );
      expect((await queue.entries(binding)).single.state, 'pending_review');
    },
  );
  test(
    'malformed success stays pending and detaching stops the next queued request',
    () async {
      final queue = AttendanceOutbox(MemoryAttendanceVault());
      await queue.authorize(binding);
      await queue.capture(binding, 'clock_in', offline: true);
      await queue.capture(binding, 'clock_out', offline: true);
      await queue.sync(binding, (_) async => {});
      expect(
        (await queue.entries(
          binding,
        )).where((e) => e.state == 'pending').length,
        2,
      );
      var sent = 0;
      await queue.sync(binding, (body) async {
        sent++;
        queue.detach();
        return {
          'id': body['id'],
          'request_id': body['request_id'],
          'version': 1,
          'status': 'accepted',
        };
      });
      expect(sent, 1);
      expect((await queue.entries(binding)).last.state, 'pending');
    },
  );
}
