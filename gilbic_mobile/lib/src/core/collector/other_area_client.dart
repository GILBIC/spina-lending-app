import 'package:gilbic_mobile/src/core/collector/collector_route.dart';
import 'package:gilbic_mobile/src/core/network/spina_api.dart';

class OtherAreaClient {
  const OtherAreaClient({
    required this.entry,
    required this.clientCode,
    required this.phoneNumber,
    required this.assignedCollectorUserId,
    required this.assignedCollectorName,
  });

  final CollectorRouteEntry entry;
  final String clientCode;
  final String phoneNumber;
  final String? assignedCollectorUserId;
  final String assignedCollectorName;

  static OtherAreaClient? fromPayload(Object? value) {
    final data = stringMap(value);
    final entry = CollectorRouteEntry.fromPayload(data);
    if (entry == null) {
      return null;
    }
    return OtherAreaClient(
      entry: entry,
      clientCode: firstNonEmptyString(<Object?>[
            data['client_code'],
            data['code'],
          ]) ??
          '',
      phoneNumber: firstNonEmptyString(<Object?>[
            data['phone_number'],
            data['phone'],
          ]) ??
          '',
      assignedCollectorUserId: firstNonEmptyString(<Object?>[
        data['assigned_collector_user_id'],
      ]),
      assignedCollectorName: firstNonEmptyString(<Object?>[
            data['assigned_collector_name'],
          ]) ??
          'Unassigned',
    );
  }
}
