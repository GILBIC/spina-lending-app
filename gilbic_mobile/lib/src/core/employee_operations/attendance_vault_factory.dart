import 'package:flutter/foundation.dart';
import 'package:gilbic_mobile/src/core/employee_operations/attendance_outbox.dart';
import 'package:gilbic_mobile/src/core/employee_operations/attendance_vault_sqlcipher.dart';

AttendanceVault createAttendanceVault() =>
    !kIsWeb &&
        const [
          TargetPlatform.android,
          TargetPlatform.iOS,
        ].contains(defaultTargetPlatform)
    ? SqlCipherAttendanceVault()
    : UnavailableAttendanceVault();
