import 'support/android_workflow_capture.dart';
import 'support/android_role_fixture.dart';
import 'package:flutter/material.dart';
import 'package:flutter/rendering.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:gilbic_mobile/src/core/auth/app_role.dart';
import 'package:gilbic_mobile/src/core/auth/user_session.dart';
import 'package:gilbic_mobile/src/core/device/device_identity.dart';
import 'package:gilbic_mobile/src/core/remittance/remittance.dart';
import 'package:gilbic_mobile/src/core/remittance/remittance_repository.dart';
import 'package:gilbic_mobile/src/features/collector/collector_remittance_page.dart';

void main() {
  testWidgets('shows server-calculated remittance summary and recipient', (
    tester,
  ) async {
    await tester.pumpWidget(
      MaterialApp(
        home: CollectorRemittancePage(
          session: _session,
          deviceIdentityProvider: _deviceIdentityProvider(),
          repository: _FakeRemittanceRepository(),
          collectionDate: DateTime(2026, 8, 2),
        ),
      ),
    );
    await tester.pumpAndSettle();

    expect(find.text('Remittance'), findsOneWidget);
    expect(find.textContaining('Cash to remit: ₱100.00'), findsOneWidget);
    expect(find.textContaining('Office Staff'), findsOneWidget);
    expect(find.text('Ana Client'), findsOneWidget);
    expect(find.textContaining('2026-08-02, 2026-08-04'), findsOneWidget);
    await tester.scrollUntilVisible(
      find.byKey(const Key('submit-remittance')),
      180,
      scrollable: find.byType(Scrollable).first,
    );
    await tester.pumpAndSettle();
    expect(find.byKey(const Key('submit-remittance')), findsOneWidget);
  });

  testWidgets('submission locks entries while custody remains with collector', (
    tester,
  ) async {
    final repository = _FakeRemittanceRepository();
    await pumpAndroidRoleFixture(
      tester,
      size: const Size(320, 640),
      textScaler: TextScaler.linear(2),
      viewInsets: const EdgeInsets.only(bottom: 220),
      home: CollectorRemittancePage(
        session: _session,
        deviceIdentityProvider: _deviceIdentityProvider(),
        repository: repository,
        collectionDate: DateTime(2026, 8, 2),
      ),
    );
    await tester.pumpAndSettle();

    final semantics = tester.ensureSemantics();
    final recipient = find.text('Office Staff • Employee');
    await tester.scrollUntilVisible(
      recipient,
      180,
      scrollable: find.byType(Scrollable).first,
    );
    await tester.pumpAndSettle();
    final paragraph = tester.renderObject<RenderParagraph>(
      find.descendant(of: recipient, matching: find.byType(RichText)),
    );
    final finalRole = paragraph
        .getBoxesForSelection(
          const TextSelection(baseOffset: 15, extentOffset: 23),
        )
        .last
        .toRect();
    expect(
      finalRole.bottom,
      lessThanOrEqualTo(paragraph.size.height + .5),
      reason: 'Selected recipient role must fit its painted text bounds',
    );
    await captureAndroidWorkflow(tester, 'C6-selected-recipient-full-role');
    await tester.tap(recipient);
    await tester.pumpAndSettle();
    await captureAndroidWorkflow(tester, 'C6-recipient-menu');
    await checkAndroidWorkflowSemantics(tester);
    await tester.tap(find.text('Office Staff • Employee').last);
    await tester.pumpAndSettle();
    expect(repository.submitCount, 0);
    await captureAndroidWorkflowScroll(tester, 'C6-remittance-summary');
    await tester.scrollUntilVisible(
      find.byKey(const Key('remittance-note')),
      180,
      scrollable: find.byType(Scrollable).first,
    );
    await tester.pumpAndSettle();
    await tester.enterText(
      find.byKey(const Key('remittance-note')),
      'Route cash handover',
    );
    await tester.scrollUntilVisible(
      find.byKey(const Key('submit-remittance')),
      180,
      scrollable: find.byType(Scrollable).first,
    );
    await tester.pumpAndSettle();
    await tester.tap(find.byKey(const Key('submit-remittance')));
    await tester.pumpAndSettle();

    expect(find.text('Submit remittance?'), findsOneWidget);
    expect(find.textContaining('permanently locked'), findsOneWidget);
    expect(
      find.textContaining('cash remains under your custody'),
      findsOneWidget,
    );

    await captureAndroidWorkflowScroll(tester, 'C6-remittance-confirmation');
    expect(
      find.descendant(
        of: find.byType(AlertDialog),
        matching: find.byType(Scrollable),
      ),
      findsOneWidget,
      reason: 'Full remittance custody consequences must be scroll-reachable',
    );
    await expectAndroidDialogConsequenceVisible(
      tester,
      'notification is accepted.',
    );
    await captureAndroidWorkflow(tester, 'C6-confirmation-consequence-end');
    await checkAndroidWorkflowSemantics(tester);
    await tester.tap(find.byKey(const Key('confirm-remittance-submission')));
    await tester.pumpAndSettle();

    await captureAndroidWorkflowScroll(tester, 'C6-remittance-waiting-custody');
    semantics.dispose();
    expect(repository.submitCount, 1);
    expect(repository.lastRecipient, 'office-1');
    expect(repository.lastNote, 'Route cash handover');
    expect(find.text('Remittance notification sent'), findsOneWidget);
    expect(find.text('REM-RC-1'), findsOneWidget);
    expect(
      find.textContaining('Waiting for Office Staff to accept'),
      findsOneWidget,
    );
    await tester.scrollUntilVisible(
      find.textContaining('cash is still under your custody'),
      180,
      scrollable: find.byType(Scrollable).first,
    );
    await tester.pumpAndSettle();
    expect(
      find.textContaining('cash is still under your custody'),
      findsOneWidget,
    );
  });
}

const UserSession _session = UserSession(
  userId: 'collector-1',
  username: 'collector.one',
  displayName: 'Test Collector',
  role: AppRole.collector,
  rawRole: 'Collector',
  accessToken: 'token',
  permissions: <String>['remittance.create', 'remittance.view'],
);

DeviceIdentityProvider _deviceIdentityProvider() {
  final store = MemoryDeviceIdentityStore()..value = 'device-one';
  return DeviceIdentityProvider(
    store: store,
    platformResolver: () => 'android',
    appVersionResolver: () async => '1.0.0-rc',
  );
}

RemittanceSummary _summary() {
  return RemittanceSummary(
    collectionDate: DateTime(2026, 8, 2),
    collectorName: 'Test Collector',
    transactionCount: 1,
    paymentCount: 1,
    unableToPayCount: 0,
    coveredPaymentCount: 1,
    clientCount: 1,
    totalAmount: 100,
    items: <RemittanceItem>[
      RemittanceItem(
        transactionId: 'transaction-1',
        clientName: 'Ana Client',
        loanType: 'Regular',
        entryType: 'advance',
        amount: 100,
        receiptNumber: 'GBC-1',
        coveredDates: <DateTime>[DateTime(2026, 8, 2), DateTime(2026, 8, 4)],
        note: 'Selected dates',
      ),
    ],
  );
}

class _FakeRemittanceRepository implements RemittanceRepository {
  int submitCount = 0;
  String? lastRecipient;
  String? lastNote;

  @override
  Future<List<RemittanceRecipient>> loadRecipients(
    UserSession session, {
    required String deviceId,
  }) async {
    return const <RemittanceRecipient>[
      RemittanceRecipient(
        userId: 'office-1',
        fullName: 'Office Staff',
        roleName: 'Employee',
      ),
    ];
  }

  @override
  Future<RemittanceSummary> loadPreview(
    UserSession session, {
    required String deviceId,
    required DateTime collectionDate,
  }) async {
    return _summary();
  }

  @override
  Future<RemittanceRecord> submit(
    UserSession session, {
    required String deviceId,
    required String recipientUserId,
    required DateTime collectionDate,
    String note = '',
  }) async {
    submitCount += 1;
    lastRecipient = recipientUserId;
    lastNote = note;
    return RemittanceRecord(
      remittanceId: 'remittance-rc-1',
      remittanceNumber: 'REM-RC-1',
      collectorUserId: 'collector-1',
      collectorName: 'Test Collector',
      recipientUserId: 'office-1',
      recipientName: 'Office Staff',
      status: 'submitted',
      summary: _summary(),
      note: note,
      submittedAt: DateTime.utc(2026, 8, 2, 8),
      receivedAt: null,
    );
  }

  @override
  Future<List<RemittanceRecord>> loadHistory(
    UserSession session, {
    required String deviceId,
  }) async {
    return const <RemittanceRecord>[];
  }

  @override
  Future<RemittanceRecord> confirmReceived(
    UserSession session, {
    required String deviceId,
    required String remittanceId,
  }) {
    throw UnimplementedError();
  }
}
