import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:gilbic_mobile/src/core/auth/app_role.dart';
import 'package:gilbic_mobile/src/core/auth/user_session.dart';
import 'package:gilbic_mobile/src/core/device/device_identity.dart';
import 'package:gilbic_mobile/src/core/management/management_loan.dart';
import 'package:gilbic_mobile/src/core/management/management_loan_repository.dart';
import 'package:gilbic_mobile/src/core/management/management_no_collection.dart';
import 'package:gilbic_mobile/src/core/management/management_no_collection_preview.dart';
import 'package:gilbic_mobile/src/core/management/management_no_collection_repository.dart';
import 'package:gilbic_mobile/src/features/management/management_no_collection_page.dart';

void main() {
  testWidgets(
    'Management reviews and confirms an exact No Collection declaration',
    (tester) async {
      final repository = _FakeNoCollectionRepository();
      await tester.binding.setSurfaceSize(const Size(360, 640));
      addTearDown(() async => tester.binding.setSurfaceSize(null));

      await _pumpPage(
        tester,
        repository,
        textScaler: const TextScaler.linear(1.3),
      );
      await _selectLoan(tester);

      await _scrollTo(tester, const Key('choose-no-collection-date'));
      await tester.tap(find.byKey(const Key('choose-no-collection-date')));
      await tester.pumpAndSettle();
      await tester.tap(find.text('OK'));
      await tester.pumpAndSettle();

      await _scrollTo(tester, const Key('preview-no-collection'));
      await tester.tap(find.byKey(const Key('preview-no-collection')));
      await tester.pumpAndSettle();

      await _scrollTo(tester, const Key('no-collection-reason'));
      await tester.enterText(
        find.byKey(const Key('no-collection-reason')),
        'Office closure confirmed by Management',
      );
      await _scrollTo(tester, const Key('save-no-collection'));
      await tester.tap(find.byKey(const Key('save-no-collection')));
      await tester.pumpAndSettle();

      expect(
        find.byKey(const Key('management-review-no-collection')),
        findsOneWidget,
      );
      expect(
        find.text(
          'The server will record the No Collection date and shift the '
          'reviewed unpaid installments while preserving the contractual '
          'schedule and audit evidence.',
        ),
        findsOneWidget,
      );
      expect(repository.declareCalls, 0);

      await tester.tap(find.byKey(const Key('cancel-no-collection')));
      await tester.pumpAndSettle();
      expect(repository.declareCalls, 0);

      await tester.tap(find.byKey(const Key('save-no-collection')));
      await tester.pumpAndSettle();
      await tester.tap(find.byKey(const Key('confirm-no-collection')));
      await tester.pumpAndSettle();

      expect(repository.declareCalls, 1);
      expect(repository.loanId, 'loan-1');
      expect(repository.expectedOperationalVersion, 4);
      expect(repository.noCollectionDate, DateTime(2026, 8, 10));
      expect(repository.reason, 'Office closure confirmed by Management');
      expect(repository.deviceId, 'management-device');
    },
  );

  testWidgets(
    'Management reviews a No Collection reversal before repository write',
    (tester) async {
      final repository = _FakeNoCollectionRepository();

      await _pumpPage(tester, repository);
      await _selectLoan(tester);

      await _scrollTo(tester, const Key('reverse-no-collection-adjustment-1'));
      await tester.tap(
        find.byKey(const Key('reverse-no-collection-adjustment-1')),
      );
      await tester.pumpAndSettle();

      await tester.enterText(
        find.byKey(const Key('no-collection-reversal-reason')),
        'Office reopened and collection resumed',
      );
      await tester.tap(find.byKey(const Key('confirm-no-collection-reversal')));
      await tester.pumpAndSettle();

      expect(
        find.byKey(const Key('management-review-no-collection')),
        findsOneWidget,
      );
      expect(
        find.text(
          'The server will reverse this No Collection adjustment against the '
          'current operational version and preserve both actions in audit history.',
        ),
        findsOneWidget,
      );
      expect(repository.reverseCalls, 0);

      await tester.tap(find.byKey(const Key('confirm-no-collection')));
      await tester.pumpAndSettle();

      expect(repository.reverseCalls, 1);
      expect(repository.adjustmentId, 'adjustment-1');
      expect(repository.expectedOperationalVersion, 4);
      expect(repository.reason, 'Office reopened and collection resumed');
    },
  );
}

Future<void> _pumpPage(
  WidgetTester tester,
  _FakeNoCollectionRepository repository, {
  TextScaler textScaler = TextScaler.noScaling,
}) async {
  await tester.pumpWidget(
    MaterialApp(
      builder: (context, child) => MediaQuery(
        data: MediaQuery.of(context).copyWith(textScaler: textScaler),
        child: child!,
      ),
      home: ManagementNoCollectionPage(
        session: _session,
        loanRepository: _FakeManagementLoanRepository(),
        repository: repository,
        deviceIdentityProvider: _deviceIdentityProvider(),
      ),
    ),
  );
  await tester.pumpAndSettle();
}

Future<void> _selectLoan(WidgetTester tester) async {
  await tester.enterText(
    find.byKey(const Key('no-collection-loan-search')),
    'TEST-REG-001',
  );
  await tester.tap(find.byKey(const Key('search-no-collection-loans')));
  await tester.pumpAndSettle();
  await _scrollTo(tester, const Key('no-collection-loan-loan-1'));
  await tester.tap(find.byKey(const Key('no-collection-loan-loan-1')));
  await tester.pumpAndSettle();
}

Future<void> _scrollTo(WidgetTester tester, Key key) async {
  await tester.scrollUntilVisible(
    find.byKey(key),
    300,
    scrollable: find.byType(Scrollable).first,
  );
  await tester.pumpAndSettle();
}

const _session = UserSession(
  userId: 'management-1',
  username: 'manager',
  displayName: 'Management',
  role: AppRole.management,
  rawRole: 'Management',
  accessToken: 'management-token',
  permissions: <String>['lending.no_collection.manage'],
);

DeviceIdentityProvider _deviceIdentityProvider() {
  final store = MemoryDeviceIdentityStore()..value = 'management-device';
  return DeviceIdentityProvider(
    store: store,
    platformResolver: () => 'android',
    appVersionResolver: () async => '1.0.0',
  );
}

class _FakeManagementLoanRepository implements ManagementLoanRepository {
  @override
  Future<ManagementLoanPortfolio> loadPortfolio(
    UserSession session, {
    required String deviceId,
    required String query,
    required String status,
  }) async {
    return ManagementLoanPortfolio(
      summary: const ManagementLoanSummary(
        activeLoanCount: 1,
        activeClientCount: 1,
        activePrincipalTotal: 5000,
        activeRemainingTotal: 4900,
        overdueActiveCount: 0,
        activeSevenBySevenCount: 0,
        approvedRenewalCount: 0,
      ),
      notice: 'Test portfolio',
      loans: <ManagementLoanItem>[_loan],
    );
  }
}

class _FakeNoCollectionRepository implements ManagementNoCollectionRepository {
  int declareCalls = 0;
  int reverseCalls = 0;
  String? deviceId;
  String? loanId;
  String? adjustmentId;
  int? expectedOperationalVersion;
  DateTime? noCollectionDate;
  String? reason;

  @override
  Future<ManagementNoCollectionLoanState> loadLoanState(
    UserSession session, {
    required String deviceId,
    required String loanId,
  }) async {
    this.deviceId = deviceId;
    this.loanId = loanId;
    return _loanState;
  }

  @override
  Future<ManagementNoCollectionPreview> preview(
    UserSession session, {
    required String deviceId,
    required String loanId,
    required int expectedOperationalVersion,
    required DateTime noCollectionDate,
  }) async {
    this.deviceId = deviceId;
    this.loanId = loanId;
    this.expectedOperationalVersion = expectedOperationalVersion;
    this.noCollectionDate = noCollectionDate;
    return ManagementNoCollectionPreview(
      loanId: loanId,
      operationalVersion: expectedOperationalVersion,
      noCollectionDate: noCollectionDate,
      paymentFrequency: 'daily',
      shifts: <ManagementNoCollectionShift>[_shift],
    );
  }

  @override
  Future<ManagementNoCollectionAdjustmentResult> declare(
    UserSession session, {
    required String deviceId,
    required String loanId,
    required int expectedOperationalVersion,
    required DateTime noCollectionDate,
    required String reason,
  }) async {
    declareCalls += 1;
    this.deviceId = deviceId;
    this.loanId = loanId;
    this.expectedOperationalVersion = expectedOperationalVersion;
    this.noCollectionDate = noCollectionDate;
    this.reason = reason;
    return _result(adjustmentType: 'declaration', reason: reason);
  }

  @override
  Future<ManagementNoCollectionAdjustmentResult> reverse(
    UserSession session, {
    required String deviceId,
    required String adjustmentId,
    required int expectedOperationalVersion,
    required String reason,
  }) async {
    reverseCalls += 1;
    this.deviceId = deviceId;
    this.adjustmentId = adjustmentId;
    this.expectedOperationalVersion = expectedOperationalVersion;
    this.reason = reason;
    return _result(
      adjustmentType: 'reversal',
      reason: reason,
      reversesAdjustmentId: adjustmentId,
    );
  }
}

final _loan = ManagementLoanItem(
  loanId: 'loan-1',
  loanNumber: 'TEST-REG-20260802',
  clientId: 'client-1',
  clientCode: 'TEST-REG-001',
  clientName: 'TEST CLIENT REGULAR',
  clientArea: 'GILBIC TEST AREA',
  clientStatus: 'active',
  loanTypeCode: 'REG',
  loanTypeName: 'Regular',
  calculationMode: 'fixed_daily',
  principal: 5000,
  dailyAmount: 50,
  interestRate: 20,
  remainingBalance: 4900,
  paidAmount: 100,
  paidPercent: 2,
  dateReleased: DateTime(2026, 8, 1),
  dueDate: DateTime(2026, 11, 29),
  loanStatus: 'active',
  lastPaymentDate: DateTime(2026, 8, 6),
  advanceUntil: DateTime(2026, 8, 5),
  passCount: 0,
  paymentCount: 2,
  stateVersion: 3,
  renewalRequestStatus: null,
  isOverdue: false,
);

final _loanState = ManagementNoCollectionLoanState(
  loanId: 'loan-1',
  loanNumber: 'TEST-REG-20260802',
  clientId: 'client-1',
  clientName: 'TEST CLIENT REGULAR',
  loanType: 'Regular',
  scheduleId: 'schedule-1',
  scheduleVersion: 2,
  paymentFrequency: 'daily',
  contractReference: 'CONTRACT-001',
  operationalVersion: 4,
  installments: <ManagementNoCollectionInstallment>[
    ManagementNoCollectionInstallment(
      installmentId: 1,
      installmentNumber: 1,
      contractualDueDate: DateTime(2026, 8, 10),
      effectiveDueDate: DateTime(2026, 8, 10),
      contractualAmount: 50,
      allocatedAmount: 0,
      remainingAmount: 50,
      isPaid: false,
      isPartlyPaid: false,
    ),
  ],
  activeNoCollection: <ManagementNoCollectionActiveAdjustment>[
    ManagementNoCollectionActiveAdjustment(
      adjustmentId: 'adjustment-1',
      noCollectionDate: DateTime(2026, 8, 9),
      reason: 'Office was closed',
      resultingOperationalVersion: 4,
      actorName: 'Management',
      createdAt: DateTime.utc(2026, 8, 9, 7),
    ),
  ],
);

final _shift = ManagementNoCollectionShift(
  installmentId: 1,
  installmentNumber: 1,
  contractualDueDate: DateTime(2026, 8, 10),
  priorEffectiveDueDate: DateTime(2026, 8, 10),
  newEffectiveDueDate: DateTime(2026, 8, 11),
  contractualAmount: 50,
);

ManagementNoCollectionAdjustmentResult _result({
  required String adjustmentType,
  required String reason,
  String? reversesAdjustmentId,
}) {
  return ManagementNoCollectionAdjustmentResult(
    adjustmentId: '$adjustmentType-result',
    loanId: 'loan-1',
    scheduleId: 'schedule-1',
    scheduleVersion: 2,
    paymentFrequency: 'daily',
    adjustmentType: adjustmentType,
    noCollectionDate: DateTime(2026, 8, 10),
    reason: reason,
    expectedOperationalVersion: 4,
    resultingOperationalVersion: 5,
    reversesAdjustmentId: reversesAdjustmentId,
    createdAt: DateTime.utc(2026, 8, 10, 7),
    shifts: <ManagementNoCollectionShift>[_shift],
  );
}
