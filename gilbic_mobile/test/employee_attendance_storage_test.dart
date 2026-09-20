import 'dart:convert';
import 'package:flutter/services.dart';
import 'package:flutter_secure_storage/flutter_secure_storage.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:gilbic_mobile/src/core/employee_operations/attendance_outbox.dart';
import 'package:gilbic_mobile/src/core/employee_operations/attendance_vault_sqlcipher.dart';

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();
  test(
    'native outbox requires secure SQLCipher key and commits before reporting capture; failed storage never claims saved',
    () async {
      FlutterSecureStorage.setMockInitialValues({});
      const channel = MethodChannel('com.davidmartos96.sqflite_sqlcipher');
      final rows = <String, String>{};
      final transactionStatements = <String>[];
      var encrypted = false, failWrite = false;
      TestDefaultBinaryMessengerBinding.instance.defaultBinaryMessenger
          .setMockMethodCallHandler(channel, (call) async {
            final args = call.arguments as Map? ?? {};
            switch (call.method) {
              case 'getDatabasesPath':
                return 'C:/synthetic-attendance-test';
              case 'openDatabase':
                encrypted =
                    args['password'] is String &&
                    base64Url.decode(args['password'] as String).length == 32;
                expect(
                  args['path'].toString().endsWith('gilbic_attendance.db'),
                  isTrue,
                );
                return 101;
              case 'query':
                if (args['sql'] == 'PRAGMA user_version') {
                  return [
                    {'user_version': 1},
                  ];
                }
                final binding = (args['arguments'] as List).first as String;
                return rows.containsKey(binding)
                    ? [
                        {'binding': binding, 'payload': rows[binding]},
                      ]
                    : [];
              case 'execute':
                transactionStatements.add(args['sql'] as String);
                return null;
              case 'insert':
                if (failWrite) throw PlatformException(code: 'disk_full');
                final values = args['arguments'] as List;
                rows[values[0] as String] = values[1] as String;
                return 1;
              default:
                return null;
            }
          });
      addTearDown(
        () => TestDefaultBinaryMessengerBinding.instance.defaultBinaryMessenger
            .setMockMethodCallHandler(channel, null),
      );
      final vault = SqlCipherAttendanceVault();
      final queue = AttendanceOutbox(vault);
      const binding = AttendanceBinding(
        userId: 'owner-of-capture',
        installationId: 'installation',
        deviceId: 'registered-device',
      );
      await queue.authorize(binding);
      final event = await queue.capture(binding, 'clock_in', offline: true);
      expect(encrypted, isTrue);
      expect(transactionStatements.last, 'COMMIT');
      final restarted = AttendanceOutbox(SqlCipherAttendanceVault());
      expect((await restarted.entries(binding)).single.command, event.command);
      failWrite = true;
      await expectLater(
        queue.capture(binding, 'clock_out', offline: true),
        throwsA(isA<PlatformException>()),
      );
      expect((await restarted.entries(binding)).length, 1);
      expect(transactionStatements.last, 'ROLLBACK');
    },
  );
}
