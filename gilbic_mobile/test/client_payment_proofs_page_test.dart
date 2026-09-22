import 'dart:typed_data';
import 'dart:convert';

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:gilbic_mobile/src/core/auth/user_session.dart';
import 'package:gilbic_mobile/src/core/media/image_recovery_controller.dart';
import 'package:gilbic_mobile/src/features/shared/image_recovery_scope.dart';
import 'package:gilbic_mobile/src/core/device/device_identity.dart';
import 'package:gilbic_mobile/src/core/documents/client_document_repository.dart';
import 'package:gilbic_mobile/src/core/network/spina_api.dart';
import 'package:gilbic_mobile/src/core/loans/client_loan.dart';
import 'package:gilbic_mobile/src/core/loans/client_loan_repository.dart';
import 'package:gilbic_mobile/src/core/payments/client_payment_proof_repository.dart';
import 'package:gilbic_mobile/src/features/client/client_payment_proofs_page.dart';
import 'package:image_picker/image_picker.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';

import 'client_documents_repository_test.dart' show session;
import 'client_payment_proof_repository_test.dart' as fixture;

void main() {
  testWidgets('photo selection binds the owned loan and correction version', (
    tester,
  ) async {
    await tester.binding.setSurfaceSize(const Size(1000, 1600));
    addTearDown(() => tester.binding.setSurfaceSize(null));
    final recovery = _RecordingRecovery();
    for (final correction in [false, true]) {
      await tester.pumpWidget(
        MaterialApp(
          home: ImageRecoveryScope(
            controller: recovery,
            child: ClientPaymentProofUploadPage(
              key: ValueKey(correction),
              session: session,
              deviceIdentityProvider: device(),
              repository: _Repository(),
              capability: capability(),
              loanRepository: _Loans(),
              proof: correction
                  ? ClientPaymentProof.fromPayload(fixture.proof)
                  : null,
              imagePicker: _Picker(),
            ),
          ),
        ),
      );
      await tester.pumpAndSettle();
      await tester.tap(find.byKey(const Key('proof-gallery')));
      await tester.pumpAndSettle();
      expect(recovery.contexts.length, correction ? 2 : 1);
    }
    expect(recovery.contexts[0].purpose, 'client_payment_proof');
    expect(jsonDecode(recovery.contexts[0].target), {
      'loan_id': 'loan-1',
      'proof_id': null,
      'version': null,
    });
    expect(jsonDecode(recovery.contexts[1].target), {
      'loan_id': 'loan-1',
      'proof_id': 'proof-1',
      'version': 1,
    });
  });
  testWidgets(
    'a truncated successful response keeps the exact raw upload retry',
    (tester) async {
      await tester.binding.setSurfaceSize(const Size(1000, 1600));
      addTearDown(() => tester.binding.setSurfaceSize(null));
      final posts = <http.Request>[];
      final repository = SpinaClientPaymentProofRepository(
        client: MockClient((request) async {
          posts.add(request);
          return posts.length == 1
              ? http.Response('{', 201)
              : http.Response(
                  jsonEncode({'success': true, 'data': fixture.detail}),
                  201,
                );
        }),
      );
      await tester.pumpWidget(
        MaterialApp(
          home: ClientPaymentProofUploadPage(
            session: session,
            deviceIdentityProvider: device(),
            repository: repository,
            capability: capability(),
            proof: ClientPaymentProof.fromPayload(fixture.proof),
            imagePicker: _Picker(),
            requestIdGenerator: () => 'stable-malformed-retry',
          ),
        ),
      );
      await tester.pumpAndSettle();
      await tester.enterText(
        find.byKey(const Key('proof-note')),
        'Actual uploaded note',
      );
      await tester.tap(find.byKey(const Key('proof-gallery')));
      await tester.pumpAndSettle();
      await tester.tap(find.byKey(const Key('submit-payment-proof')));
      await tester.pumpAndSettle();
      expect(find.text('Retry same upload'), findsOneWidget);
      expect(
        tester.widget<TextField>(find.byKey(const Key('proof-note'))).enabled,
        false,
      );
      await tester.tap(find.byKey(const Key('submit-payment-proof')));
      await tester.pumpAndSettle();
      expect(posts.length, 2);
      expect(posts[1].url, posts[0].url);
      expect(posts[1].bodyBytes, posts[0].bodyBytes);
      expect(posts[1].headers, posts[0].headers);
    },
  );

  testWidgets(
    'new proof chooses an owned loan and submits evidence without payment amount',
    (tester) async {
      await tester.binding.setSurfaceSize(const Size(1000, 1600));
      addTearDown(() => tester.binding.setSurfaceSize(null));
      final repository = _Repository();
      await tester.pumpWidget(
        MaterialApp(
          home: ClientPaymentProofUploadPage(
            session: session,
            deviceIdentityProvider: device(),
            repository: repository,
            capability: capability(),
            loanRepository: _Loans(),
            imagePicker: _Picker(),
            requestIdGenerator: () => 'new-request',
          ),
        ),
      );
      await tester.pumpAndSettle();
      expect(find.text('LN-1 · Regular'), findsOneWidget);
      expect(find.text('Amount'), findsNothing);
      await tester.tap(find.byKey(const Key('proof-gallery')));
      await tester.pumpAndSettle();
      await tester.tap(find.byKey(const Key('submit-payment-proof')));
      await tester.pumpAndSettle();
      expect(repository.requests.single, {
        'id': 'new-request',
        'loan': 'loan-1',
        'note': '',
        'bytes': png,
        'device': 'device',
      });
    },
  );

  testWidgets(
    'proof history shows rejection reason and keeps reviewed distinct from paid',
    (tester) async {
      await tester.binding.setSurfaceSize(const Size(1000, 1600));
      addTearDown(() => tester.binding.setSurfaceSize(null));
      final repository = _Repository();
      await tester.pumpWidget(
        MaterialApp(
          home: ClientPaymentProofsPage(
            session: session,
            deviceIdentityProvider: device(),
            repository: repository,
          ),
        ),
      );
      await tester.pumpAndSettle();
      await tester.tap(find.byKey(const Key('payment-proof-proof-1')));
      await tester.pumpAndSettle();
      expect(find.text('Proof status and history'), findsOneWidget);
      expect(find.text('Reference is not visible'), findsOneWidget);
      expect(find.text('Version history'), findsOneWidget);
      expect(find.text('Version 1'), findsOneWidget);
      expect(find.text('Upload corrected proof'), findsOneWidget);
      expect(find.text('Payment posted'), findsNothing);
      expect(
        find.textContaining('does not post a payment or change your balance'),
        findsOneWidget,
      );
      expect(find.text('Download proof version 1'), findsOneWidget);
    },
  );

  testWidgets('unknown capability hides upload and correction controls', (
    tester,
  ) async {
    final repository = _Repository(available: false);
    await tester.pumpWidget(
      MaterialApp(
        home: ClientPaymentProofsPage(
          session: session,
          deviceIdentityProvider: device(),
          repository: repository,
        ),
      ),
    );
    await tester.pumpAndSettle();
    expect(find.byKey(const Key('new-payment-proof')), findsNothing);
    await tester.tap(find.byKey(const Key('payment-proof-proof-1')));
    await tester.pumpAndSettle();
    expect(find.byKey(const Key('correct-payment-proof')), findsNothing);
  });

  testWidgets(
    'uncertain reupload freezes draft and retries same id/version/bytes',
    (tester) async {
      await tester.binding.setSurfaceSize(const Size(1000, 1600));
      addTearDown(() => tester.binding.setSurfaceSize(null));
      final repository = _Repository(failOnce: true);
      await tester.pumpWidget(
        MaterialApp(
          home: ClientPaymentProofUploadPage(
            session: session,
            deviceIdentityProvider: device(),
            repository: repository,
            capability: capability(),
            proof: ClientPaymentProof.fromPayload(fixture.proof),
            imagePicker: _Picker(),
            requestIdGenerator: () => 'stable-request',
          ),
        ),
      );
      await tester.pumpAndSettle();
      await tester.enterText(
        find.byKey(const Key('proof-note')),
        'Correct reference 456',
      );
      await tester.tap(find.byKey(const Key('proof-gallery')));
      await tester.pumpAndSettle();
      await tester.tap(find.byKey(const Key('submit-payment-proof')));
      await tester.pumpAndSettle();
      expect(find.text('Retry same upload'), findsOneWidget);
      expect(
        tester.widget<TextField>(find.byKey(const Key('proof-note'))).enabled,
        false,
      );
      expect(
        tester
            .widget<OutlinedButton>(find.byKey(const Key('proof-gallery')))
            .onPressed,
        isNull,
      );
      await tester.tap(find.byKey(const Key('submit-payment-proof')));
      await tester.pumpAndSettle();
      expect(repository.requests, hasLength(2));
      expect(repository.requests[0], repository.requests[1]);
      expect(repository.requests[0], {
        'id': 'stable-request',
        'version': 1,
        'note': 'Correct reference 456',
        'bytes': png,
        'device': 'device',
      });
    },
  );

  testWidgets(
    'cancelled image selection cannot submit and oversized file is rejected',
    (tester) async {
      for (final picker in [_Picker(cancel: true), _Picker(oversize: true)]) {
        await tester.pumpWidget(
          MaterialApp(
            home: ClientPaymentProofUploadPage(
              key: UniqueKey(),
              session: session,
              deviceIdentityProvider: device(),
              repository: _Repository(),
              capability: capability(),
              proof: ClientPaymentProof.fromPayload(fixture.proof),
              imagePicker: picker,
            ),
          ),
        );
        await tester.pumpAndSettle();
        await tester.tap(find.byKey(const Key('proof-gallery')));
        await tester.pumpAndSettle();
        expect(
          tester
              .widget<FilledButton>(
                find.byKey(const Key('submit-payment-proof')),
              )
              .onPressed,
          isNull,
        );
        if (picker.oversize) {
          expect(
            find.textContaining('exceeds the upload size'),
            findsOneWidget,
          );
        }
      }
    },
  );

  testWidgets('version conflict cannot silently submit another correction', (
    tester,
  ) async {
    final repository = _Repository(conflict: true);
    await tester.binding.setSurfaceSize(const Size(1000, 1600));
    addTearDown(() => tester.binding.setSurfaceSize(null));
    await tester.pumpWidget(
      MaterialApp(
        home: ClientPaymentProofUploadPage(
          session: session,
          deviceIdentityProvider: device(),
          repository: repository,
          capability: capability(),
          proof: ClientPaymentProof.fromPayload(fixture.proof),
          imagePicker: _Picker(),
        ),
      ),
    );
    await tester.pumpAndSettle();
    await tester.tap(find.byKey(const Key('proof-gallery')));
    await tester.pumpAndSettle();
    await tester.tap(find.byKey(const Key('submit-payment-proof')));
    await tester.pumpAndSettle();
    expect(find.textContaining('refresh the latest version'), findsOneWidget);
    expect(
      tester
          .widget<FilledButton>(find.byKey(const Key('submit-payment-proof')))
          .onPressed,
      isNull,
    );
  });
}

class _RecordingRecovery extends ImageRecoveryController {
  _RecordingRecovery() : super(enabled: false);
  final contexts = <ImagePickContext>[];
  @override
  bool get ready => true;
  @override
  Future<XFile?> pick(
    ImagePickContext context,
    Future<XFile?> Function() launch,
  ) {
    contexts.add(context);
    return launch();
  }
}

DeviceIdentityProvider device() => DeviceIdentityProvider(
  store: MemoryDeviceIdentityStore()..value = 'device',
  platformResolver: () => 'android',
  appVersionResolver: () async => '1',
);
PaymentProofList capability({bool available = true}) =>
    PaymentProofList.fromPayload({
      'proofs': [fixture.proof],
      'has_more': false,
      'capability': {
        'upload_available': available,
        'posts_payment': false,
        'allowed_media_types': ['image/png', 'image/jpeg'],
        'max_bytes': 100,
        'message': 'Evidence only',
      },
    });
final png = Uint8List.fromList([137, 80, 78, 71, 13, 10, 26, 10]);

class _Picker extends ImagePicker {
  _Picker({this.cancel = false, this.oversize = false});
  final bool cancel;
  final bool oversize;
  @override
  Future<XFile?> pickImage({
    required ImageSource source,
    double? maxWidth,
    double? maxHeight,
    int? imageQuality,
    CameraDevice preferredCameraDevice = CameraDevice.rear,
    bool requestFullMetadata = true,
  }) async => cancel
      ? null
      : XFile.fromData(
          oversize ? Uint8List(101) : png,
          name: 'proof.png',
          mimeType: 'image/png',
        );
}

class _Repository implements ClientPaymentProofRepository {
  _Repository({
    this.available = true,
    this.failOnce = false,
    this.conflict = false,
  });
  final bool available;
  final bool failOnce;
  final bool conflict;
  final List<Map<String, Object>> requests = [];
  @override
  Future<PaymentProofList> list(
    UserSession session, {
    required String deviceId,
    int offset = 0,
  }) async => capability(available: available);
  @override
  Future<PaymentProofDetail> load(
    UserSession session, {
    required String deviceId,
    required String proofId,
  }) async => PaymentProofDetail.fromPayload(fixture.detail);
  @override
  Future<PaymentProofDetail> reupload(
    UserSession session, {
    required String deviceId,
    required String proofId,
    required String requestId,
    required int expectedVersion,
    required String note,
    required PaymentProofDraft draft,
  }) async {
    requests.add({
      'id': requestId,
      'version': expectedVersion,
      'note': note,
      'bytes': draft.bytes,
      'device': deviceId,
    });
    if (conflict) {
      throw const SpinaApiException('Version changed', statusCode: 409);
    }
    if (failOnce && requests.length == 1) {
      throw const SpinaApiException(
        'Network interrupted',
        code: 'network_unavailable',
      );
    }
    return PaymentProofDetail.fromPayload(fixture.detail);
  }

  @override
  Future<PaymentProofDetail> upload(
    UserSession session, {
    required String deviceId,
    required String loanId,
    required String requestId,
    required String note,
    required PaymentProofDraft draft,
  }) async {
    requests.add({
      'id': requestId,
      'loan': loanId,
      'note': note,
      'bytes': draft.bytes,
      'device': deviceId,
    });
    return PaymentProofDetail.fromPayload(fixture.detail);
  }

  @override
  Future<ClientDocumentFile> download(
    UserSession session, {
    required String deviceId,
    required String proofId,
    required PaymentProofVersion version,
  }) async => ClientDocumentFile(
    filename: 'proof.png',
    bytes: png,
    mediaType: 'image/png',
  );
}

class _Loans implements ClientLoanRepository {
  @override
  Future<ClientLoanPortfolio> loadPortfolio(
    UserSession session, {
    required String deviceId,
  }) async => const ClientLoanPortfolio(
    clientId: 'client',
    clientCode: 'C1',
    clientName: 'Client',
    clientStatus: 'active',
    loans: [
      ClientLoan(
        loanId: 'loan-1',
        loanNumber: 'LN-1',
        loanTypeName: 'Regular',
        principal: '5000.00',
        dailyAmount: '50.00',
        status: 'active',
        remainingBalance: '4950.00',
        paidAmount: '50.00',
        passCount: 0,
        stateVersion: 1,
        paymentCount: 1,
      ),
    ],
  );
}
