import 'package:gilbic_mobile/src/core/network/spina_api.dart';

class CrossRemittanceTarget {
  const CrossRemittanceTarget({
    required this.recipientUserId,
    required this.recipientName,
    required this.transactionCount,
    required this.clientCount,
    required this.totalAmount,
  });

  final String recipientUserId;
  final String recipientName;
  final int transactionCount;
  final int clientCount;
  final double totalAmount;

  static CrossRemittanceTarget? fromPayload(Object? value) {
    final data = stringMap(value);
    final recipientUserId = firstNonEmptyString(<Object?>[
      data['recipient_user_id'],
      data['user_id'],
    ]);
    final recipientName = firstNonEmptyString(<Object?>[
      data['recipient_name'],
      data['full_name'],
    ]);
    if (recipientUserId == null || recipientName == null) {
      return null;
    }
    return CrossRemittanceTarget(
      recipientUserId: recipientUserId,
      recipientName: recipientName,
      transactionCount:
          firstNumber(<Object?>[data['transaction_count']])?.toInt() ?? 0,
      clientCount: firstNumber(<Object?>[data['client_count']])?.toInt() ?? 0,
      totalAmount: firstNumber(<Object?>[data['total_amount']])?.toDouble() ?? 0,
    );
  }
}
