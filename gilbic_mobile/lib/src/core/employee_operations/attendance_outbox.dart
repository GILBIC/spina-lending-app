import 'dart:async';
import 'dart:convert';
import 'dart:math';
import 'package:gilbic_mobile/src/core/network/spina_api.dart';

String employeeRequestId() {
  final random = Random.secure();
  final b = List.generate(16, (_) => random.nextInt(256));
  b[6] = (b[6] & 15) | 64;
  b[8] = (b[8] & 63) | 128;
  final s = b.map((v) => v.toRadixString(16).padLeft(2, '0')).join();
  return '${s.substring(0, 8)}-${s.substring(8, 12)}-${s.substring(12, 16)}-${s.substring(16, 20)}-${s.substring(20)}';
}

class AttendanceBinding {
  const AttendanceBinding({
    required this.userId,
    required this.installationId,
    required this.deviceId,
  });
  final String userId, installationId, deviceId;
  String get key => jsonEncode([userId, installationId, deviceId]);
}

class AttendanceEntry {
  AttendanceEntry(Map<String, dynamic> json)
    : command = Map<String, dynamic>.unmodifiable(json['command'] as Map),
      state = json['state'] as String,
      message = json['message'] as String? ?? '';
  final Map<String, dynamic> command;
  final String state, message;
}

/// Implementations must atomically read/replace the encrypted account-device row.
abstract interface class AttendanceVault {
  Future<Map<String, dynamic>?> read(String key);
  Future<void> update(
    String key,
    Map<String, dynamic> Function(Map<String, dynamic>?) change,
  );
}

/// Tests only. Production never falls back to unprotected or volatile storage.
class MemoryAttendanceVault implements AttendanceVault {
  final _rows = <String, String>{};
  Future<void> _tail = Future.value();
  @override
  Future<Map<String, dynamic>?> read(String key) async => _rows[key] == null
      ? null
      : jsonDecode(_rows[key]!) as Map<String, dynamic>;
  @override
  Future<void> update(
    String key,
    Map<String, dynamic> Function(Map<String, dynamic>?) change,
  ) {
    final work = _tail.then(
      (_) async => _rows[key] = jsonEncode(change(await read(key))),
    );
    _tail = work.then<void>((_) {}, onError: (Object _) {});
    return work;
  }
}

class UnavailableAttendanceVault implements AttendanceVault {
  @override
  Future<Map<String, dynamic>?> read(String key) async => null;
  @override
  Future<void> update(
    String key,
    Map<String, dynamic> Function(Map<String, dynamic>?) change,
  ) async => throw StateError(
    'Protected attendance storage is unavailable on this device.',
  );
}

typedef AttendanceSender =
    Future<Map<String, dynamic>> Function(Map<String, dynamic>);

String attendanceWorkDate(DateTime time) => time
    .toUtc()
    .add(const Duration(hours: 8))
    .toIso8601String()
    .substring(0, 10);

class AttendanceOutbox {
  AttendanceOutbox(this.vault);
  final AttendanceVault vault;
  int _epoch = 0;
  Future<void>? _syncing;

  void detach() => _epoch++;

  Future<void> authorize(
    AttendanceBinding binding, {
    Map<String, String> predecessors = const {},
    Map<String, int> sequences = const {},
  }) => vault.update(binding.key, (saved) {
    final row =
        saved ??
        {
          'events': <dynamic>[],
          'sequences': <String, dynamic>{},
          'predecessors': <String, dynamic>{},
        };
    row['authorized'] = true;
    for (final pair in sequences.entries) {
      final current = (row['sequences'] as Map)[pair.key] as int? ?? 0;
      if (pair.value > current) {
        (row['sequences'] as Map)[pair.key] = pair.value;
      }
    }
    for (final pair in predecessors.entries) {
      final pendingForDay = (row['events'] as List).any(
        (event) =>
            event['state'] == 'pending' &&
            attendanceWorkDate(
                  DateTime.parse(event['command']['captured_at'] as String),
                ) ==
                pair.key,
      );
      if (!pendingForDay) (row['predecessors'] as Map)[pair.key] = pair.value;
    }
    return row;
  });

  Future<bool> isAuthorized(AttendanceBinding binding) async =>
      (await vault.read(binding.key))?['authorized'] == true;

  Future<List<AttendanceEntry>> entries(AttendanceBinding binding) async {
    final row = await vault.read(binding.key);
    return ((row?['events'] as List?) ?? [])
        .map((e) => AttendanceEntry(Map<String, dynamic>.from(e as Map)))
        .toList();
  }

  Future<AttendanceEntry> capture(
    AttendanceBinding binding,
    String eventType, {
    DateTime? capturedAt,
    required bool offline,
  }) async {
    if (!const [
      'clock_in',
      'break_start',
      'break_end',
      'clock_out',
    ].contains(eventType)) {
      throw ArgumentError('Only attendance events can be queued.');
    }
    final requestId = employeeRequestId(), id = employeeRequestId();
    final time = (capturedAt ?? DateTime.now()).toUtc().toIso8601String();
    final day = attendanceWorkDate(DateTime.parse(time));
    late Map<String, dynamic> event;
    await vault.update(binding.key, (row) {
      if (row == null || row['authorized'] != true) {
        throw StateError(
          'Connect this account and device to Employee operations before recording attendance.',
        );
      }
      final sequence = ((row['sequences'] as Map)[day] as int? ?? 0) + 1;
      event = {
        'command': <String, dynamic>{
          'action': 'attendance_record',
          'request_id': requestId,
          'id': id,
          'employee_id': binding.userId,
          'expected_version': 0,
          'event_type': eventType,
          'captured_at': time,
          'device_id': binding.deviceId,
          'previous_event_id': (row['predecessors'] as Map)[day],
          'sequence': sequence,
          'offline': offline,
        },
        'state': 'pending',
        'message': 'Saved on this device; waiting for server confirmation.',
      };
      (row['events'] as List).add(event);
      (row['sequences'] as Map)[day] = sequence;
      (row['predecessors'] as Map)[day] = id;
      return row;
    });
    return AttendanceEntry(event);
  }

  Future<void> sync(AttendanceBinding binding, AttendanceSender send) {
    if (_syncing != null) return _syncing!;
    final epoch = _epoch;
    final work = _drain(binding, send, epoch);
    _syncing = work;
    return work.whenComplete(() {
      if (identical(_syncing, work)) _syncing = null;
    });
  }

  Future<void> _drain(
    AttendanceBinding binding,
    AttendanceSender send,
    int epoch,
  ) async {
    if (!await isAuthorized(binding) || epoch != _epoch) return;
    for (final entry in await entries(binding)) {
      if (epoch != _epoch) return;
      if (entry.state != 'pending') continue;
      try {
        final result = await send(Map<String, dynamic>.from(entry.command));
        if (result['request_id'] != entry.command['request_id'] ||
            result['id'] != entry.command['id'] ||
            result['version'] is! int ||
            (result['version'] as int) < 1 ||
            !const ['accepted', 'pending_review'].contains(result['status'])) {
          throw const FormatException('Attendance confirmation is incomplete.');
        }
        await _mark(
          binding,
          entry,
          result['status'] as String,
          result['message'] as String? ?? 'Received by server.',
        );
      } on SpinaApiException catch (error) {
        if (const [401, 403, 426].contains(error.statusCode)) {
          await vault.update(
            binding.key,
            (row) => row!..['authorized'] = false,
          );
        } else if (const [409, 422].contains(error.statusCode)) {
          await _mark(binding, entry, 'needs_attention', error.message);
        }
        return;
      } on Exception {
        // Uncertain outcomes retain the exact original request and event IDs.
        return;
      }
    }
  }

  Future<void> _mark(
    AttendanceBinding binding,
    AttendanceEntry entry,
    String state,
    String message,
  ) => vault.update(binding.key, (row) {
    for (final event in row!['events'] as List) {
      if ((event['command'] as Map)['id'] == entry.command['id']) {
        event['state'] = state;
        event['message'] = message;
      }
    }
    return row;
  });
}
