import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:gilbic_mobile/src/core/auth/app_role.dart';
import 'package:gilbic_mobile/src/core/auth/user_session.dart';
import 'package:gilbic_mobile/src/core/device/device_identity.dart';
import 'package:gilbic_mobile/src/core/management/opening_balance_workbook.dart';
import 'package:gilbic_mobile/src/core/management/opening_balance_workbook_repository.dart';
import 'package:gilbic_mobile/src/features/management/management_opening_balance_workbook_page.dart';

void main() {
  testWidgets('Management sees non-posting opening workbook source state', (
    tester,
  ) async {
    final repository = _FakeWorkbookRepository(initialized: false);

    await tester.pumpWidget(
      MaterialApp(
        home: ManagementOpeningBalanceWorkbookPage(
          session: _session,
          deviceIdentityProvider: _deviceIdentityProvider(),
          repository: repository,
        ),
      ),
    );
    await tester.pumpAndSettle();

    expect(find.text('Opening Balance Workbook'), findsOneWidget);
    expect(find.text('Workbook not initialized'), findsOneWidget);
    expect(find.textContaining('does not post'), findsWidgets);
    expect(find.byKey(const Key('initialize-opening-balance-workbook')), findsOneWidget);
    expect(find.text('Cash - Collector Custody'), findsOneWidget);
    expect(find.text('₱200.00'), findsOneWidget);
    expect(repository.deviceId, 'management-device');
  });

  testWidgets('Initialized workbook shows protected review gates', (tester) async {
    final repository = _FakeWorkbookRepository(initialized: true);

    await tester.pumpWidget(
      MaterialApp(
        home: ManagementOpeningBalanceWorkbookPage(
          session: _session,
          deviceIdentityProvider: _deviceIdentityProvider(),
          repository: repository,
        ),
      ),
    );
    await tester.pumpAndSettle();

    expect(find.byKey(const Key('opening-workbook-summary')), findsOneWidget);
    expect(find.text('2026-08-08'), findsOneWidget);
    expect(find.text('0 / 11'), findsOneWidget);
    expect(find.text('Ready to post'), findsOneWidget);
    expect(find.text('No'), findsWidgets);
    expect(find.byKey(const Key('opening-workbook-policy')), findsOneWidget);
    expect(find.byKey(const Key('opening-workbook-line-1020')), findsOneWidget);
    expect(find.byKey(const Key('edit-opening-workbook-line-1020')), findsOneWidget);
    expect(find.byKey(const Key('opening-workbook-mark-review-ready')), findsOneWidget);
    expect(
      tester.widget<FilledButton>(
        find.byKey(const Key('opening-workbook-mark-review-ready')),
      ).onPressed,
      isNull,
    );
    expect(
      find.textContaining('Opening journal posting: Disabled'),
      findsOneWidget,
    );
  });
}

const _session = UserSession(
  userId: 'management-1',
  username: 'manager',
  displayName: 'Management',
  role: AppRole.management,
  rawRole: 'Management',
  accessToken: 'management-token',
  permissions: <String>['accounting.cutover.manage'],
);

DeviceIdentityProvider _deviceIdentityProvider() {
  final store = MemoryDeviceIdentityStore()..value = 'management-device';
  return DeviceIdentityProvider(
    store: store,
    platformResolver: () => 'android',
    appVersionResolver: () async => '1.0.0',
  );
}

class _FakeWorkbookRepository implements OpeningBalanceWorkbookRepository {
  _FakeWorkbookRepository({required this.initialized});

  final bool initialized;
  String? deviceId;

  OpeningBalanceWorkbookData _data() {
    return OpeningBalanceWorkbookData(
      managementEnabled: true,
      notice:
          'Stage 5C workbook values remain outside the General Ledger. Saving and verifying do not post an opening journal.',
      summary: OpeningBalanceWorkbookSummary(
        workbookId: initialized ? 'workbook-1' : null,
        cutoverDate: initialized ? DateTime(2026, 8, 8) : null,
        status: initialized ? 'draft' : 'source_review_required',
        lineCount: 11,
        sourceReferenceCount: 4,
        verifiedLineCount: 0,
        pendingLineCount: 11,
        profitLossPolicyConfirmed: false,
        profitLossPolicyNote: null,
        totalDebit: 0,
        totalCredit: 0,
        balanceVariance: 0,
        worksheetBalanced: false,
        readyForReview: false,
        readyToPost: false,
        openingBalancePostingEnabled: false,
        automaticSourcePostingEnabled: false,
      ),
      lines: const <OpeningBalanceWorkbookLine>[
        OpeningBalanceWorkbookLine(
          workbookId: null,
          accountCode: '1020',
          systemKey: 'cash_collector_custody',
          accountName: 'Cash - Collector Custody',
          accountType: 'asset',
          normalBalance: 'debit',
          sourceReferenceAmount: 200,
          sourceBasis: 'collection_custody_reference',
          requirementType: 'reconciliation_required',
          guidance: 'Reconcile to physical collector cash.',
          proposedDebit: null,
          proposedCredit: null,
          verificationStatus: 'pending',
          evidenceNote: null,
        ),
      ],
    );
  }

  @override
  Future<OpeningBalanceWorkbookData> load(
    UserSession session, {
    required String deviceId,
  }) async {
    this.deviceId = deviceId;
    return _data();
  }

  @override
  Future<OpeningBalanceWorkbookData> create(
    UserSession session, {
    required String deviceId,
    required DateTime cutoverDate,
  }) async {
    this.deviceId = deviceId;
    return _data();
  }

  @override
  Future<OpeningBalanceWorkbookData> updateLine(
    UserSession session, {
    required String deviceId,
    required String workbookId,
    required String accountCode,
    required double? debit,
    required double? credit,
    required String verificationStatus,
    required String? evidenceNote,
  }) async {
    this.deviceId = deviceId;
    return _data();
  }

  @override
  Future<OpeningBalanceWorkbookData> updatePolicy(
    UserSession session, {
    required String deviceId,
    required String workbookId,
    required bool confirmed,
    required String? policyNote,
  }) async {
    this.deviceId = deviceId;
    return _data();
  }

  @override
  Future<OpeningBalanceWorkbookData> changeStatus(
    UserSession session, {
    required String deviceId,
    required String workbookId,
    required String status,
  }) async {
    this.deviceId = deviceId;
    return _data();
  }
}
