import 'dart:convert';

import 'package:flutter_test/flutter_test.dart';
import 'package:gilbic_mobile/src/core/auth/app_role.dart';
import 'package:gilbic_mobile/src/core/auth/user_session.dart';
import 'package:gilbic_mobile/src/core/network/spina_api.dart';
import 'package:gilbic_mobile/src/core/payments/payment_submission.dart';
import 'package:gilbic_mobile/src/core/payments/payment_submission_repository.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';

void main() {
  test('sends bearer authentication and the same idempotency key', () async {
    late http.Request captured;
    final repository = SpinaPaymentSubmissionRepository(
      submissionUri: Uri.parse('https://api.example.test/collections'),
      client: MockClient((request) async {
        captured = request;
        return http.Response(
          jsonEncode(<String, Object?>{
            'success': true,
            'data': <String, Object?>{
              'status': 'accepted',
              'message': 'Collection accepted',
              'transaction_id': 'server-1',
              'receipt_number': 'OR-000001',
              'official_balance': 4600,
              'accepted_at': '2026-07-31T05:20:00Z',
            },
          }),
          201,
          headers: const <String, String>{
            'content-type': 'application/json',
          },
        );
      }),
    );

    final result = await repository.submit(_session, _paymentDraft);
    final body = jsonDecode(captured.body) as Map<String, dynamic>;

    expect(captured.method, 'POST');
    expect(captured.headers['authorization'], 'Bearer session-token');
    expect(captured.headers['idempotency-key'], 'transaction-1');
    expect(captured.headers['x-client-transaction-id'], 'transaction-1');
    expect(captured.headers['x-device-id'], 'device-1');
    expect(body['client_transaction_id'], 'transaction-1');
    expect(body['entry_type'], 'payment');
    expect(result.disposition, PaymentSubmissionDisposition.accepted);
    expect(result.receiptNumber, 'OR-000001');
    expect(result.officialBalance, 4600);
  });

  test('treats a replayed idempotency key as duplicate success', () async {
    final repository = SpinaPaymentSubmissionRepository(
      client: MockClient(
        (_) async => http.Response(
          jsonEncode(<String, Object?>{
            'success': true,
            'data': <String, Object?>{
              'duplicate': true,
              'message': 'Previously accepted',
              'transaction_id': 'server-1',
              'receipt_number': 'OR-000001',
              'official_balance': 4600,
            },
          }),
          200,
        ),
      ),
    );

    final result = await repository.submit(_session, _paymentDraft);

    expect(result.disposition, PaymentSubmissionDisposition.duplicate);
    expect(result.isFinalSuccess, isTrue);
    expect(result.serverTransactionId, 'server-1');
  });

  test('returns typed conflicts for stale server data', () async {
    final repository = SpinaPaymentSubmissionRepository(
      client: MockClient(
        (_) async => http.Response(
          jsonEncode(<String, Object?>{
            'success': false,
            'message': 'The route changed after download.',
            'error': <String, Object?>{'code': 'stale_route'},
            'route_revision': 'route-v4',
          }),
          409,
        ),
      ),
    );

    final result = await repository.submit(_session, _paymentDraft);

    expect(result.disposition, PaymentSubmissionDisposition.conflict);
    expect(result.code, 'stale_route');
    expect(result.message, contains('route changed'));
    expect(result.routeRevision, 'route-v4');
  });

  test('returns typed rejection for invalid collection rules', () async {
    final repository = SpinaPaymentSubmissionRepository(
      client: MockClient(
        (_) async => http.Response(
          jsonEncode(<String, Object?>{
            'success': false,
            'message': 'This loan is already closed.',
            'error': <String, Object?>{'code': 'loan_closed'},
          }),
          422,
        ),
      ),
    );

    final result = await repository.submit(_session, _paymentDraft);

    expect(result.disposition, PaymentSubmissionDisposition.rejected);
    expect(result.code, 'loan_closed');
    expect(result.isFinalSuccess, isFalse);
  });

  test('network failures require retrying the same transaction key', () async {
    final repository = SpinaPaymentSubmissionRepository(
      client: MockClient((_) async => throw Exception('offline')),
    );

    await expectLater(
      repository.submit(_session, _paymentDraft),
      throwsA(
        isA<SpinaApiException>()
            .having((error) => error.code, 'code', 'network_unavailable')
            .having((error) => error.message, 'message', contains('same')),
      ),
    );
  });

  test('invalid drafts fail before making a network request', () async {
    var requestCount = 0;
    final repository = SpinaPaymentSubmissionRepository(
      client: MockClient((_) async {
        requestCount += 1;
        return http.Response('{}', 200);
      }),
    );
    final invalid = PaymentSubmissionDraft(
      idempotencyKey: '',
      routeEntryId: 'route-entry-1',
      clientId: 'client-1',
      loanId: 'loan-1',
      collectionDate: DateTime(2026, 7, 31),
      entryType: CollectionEntryType.payment,
      amount: 200,
      recordedAt: DateTime.utc(2026, 7, 31, 5, 15),
      deviceId: 'device-1',
      deviceSequence: 1,
    );

    await expectLater(
      repository.submit(_session, invalid),
      throwsA(
        isA<SpinaApiException>().having(
          (error) => error.code,
          'code',
          'invalid_payment_draft',
        ),
      ),
    );
    expect(requestCount, 0);
  });
}

const UserSession _session = UserSession(
  userId: 'collector-1',
  username: 'collector.one',
  displayName: 'Collector One',
  role: AppRole.collector,
  rawRole: 'Collector',
  accessToken: 'session-token',
  permissions: <String>['collection.create'],
);

final PaymentSubmissionDraft _paymentDraft = PaymentSubmissionDraft(
  idempotencyKey: 'transaction-1',
  routeEntryId: 'route-entry-1',
  clientId: 'client-1',
  loanId: 'loan-1',
  collectionDate: DateTime(2026, 7, 31),
  entryType: CollectionEntryType.payment,
  amount: 200,
  recordedAt: DateTime.utc(2026, 7, 31, 5, 15),
  deviceId: 'device-1',
  deviceSequence: 7,
  note: 'Paid at home',
  routeRevision: 'route-v3',
);
