import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:gilbic_mobile/src/core/auth/app_role.dart';
import 'package:gilbic_mobile/src/core/auth/user_session.dart';
import 'package:gilbic_mobile/src/core/device/device_identity.dart';
import 'package:gilbic_mobile/src/core/management/contract_collection_activation.dart';
import 'package:gilbic_mobile/src/core/management/contract_collection_activation_repository.dart';
import 'package:gilbic_mobile/src/features/management/management_contract_collection_activation_page.dart';

void main() {
  testWidgets('Management sees ready and blocked contract loans', (
    tester,
  ) async {
    final repository = _FakeRepository();

    await tester.pumpWidget(
      MaterialApp(
        home: ManagementContractCollectionActivationPage(
          session: _session,
          deviceIdentityProvider: _deviceIdentityProvider(),
          repository: repository,
        ),
      ),
    );
    await tester.pumpAndSettle();

    expect(find.text('Contract Collection'), findsOneWidget);
    expect(
      find.byKey(const Key('contract-collection-summary')),
      findsOneWidget,
    );
    expect(find.text('Ready to activate'), findsWidgets);
    expect(find.text('Synthetic Ready Client'), findsOneWidget);
    expect(repository.deviceId, 'management-device');

    expect(
      find.byKey(const Key('activate-contract-collection-ready-loan')),
      findsOneWidget,
    );

    final blocked = find.byKey(
      const Key('contract-collection-loan-blocked-loan'),
    );
    await tester.scrollUntilVisible(blocked, 250);
    await tester.pumpAndSettle();
    expect(find.text('Synthetic Blocked Client'), findsOneWidget);
    await tester.tap(blocked);
    await tester.pumpAndSettle();
    expect(find.text('Signed contract required'), findsWidgets);
    expect(
      find.byKey(const Key('activate-contract-collection-blocked-loan')),
      findsNothing,
    );
  });

  testWidgets('activation requires a note and explicit confirmation', (
    tester,
  ) async {
    final repository = _FakeRepository();

    await tester.pumpWidget(
      MaterialApp(
        home: ManagementContractCollectionActivationPage(
          session: _session,
          deviceIdentityProvider: _deviceIdentityProvider(),
          repository: repository,
        ),
      ),
    );
    await tester.pumpAndSettle();

    final activate = find.byKey(
      const Key('activate-contract-collection-ready-loan'),
    );
    await tester.scrollUntilVisible(activate, 200);
    await tester.pumpAndSettle();
    await tester.tap(activate);
    await tester.pumpAndSettle();

    expect(
      find.byKey(const Key('management-review-contract-collection')),
      findsOneWidget,
    );
    expect(
      find.text(
        'Mobile collection will be available only for this verified current '
        'contract schedule.',
      ),
      findsOneWidget,
    );

    final confirm = find.byKey(const Key('confirm-contract-activation-action'));
    expect(tester.widget<FilledButton>(confirm).onPressed, isNull);

    await tester.enterText(
      find.byKey(const Key('contract-activation-note')),
      'Verified against synthetic signed-contract schedule.',
    );
    await tester.ensureVisible(
      find.byKey(const Key('contract-activation-confirm')),
    );
    await tester.pumpAndSettle();
    await tester.tap(find.byKey(const Key('contract-activation-confirm')));
    await tester.pump();
    expect(tester.widget<FilledButton>(confirm).onPressed, isNotNull);

    await tester.tap(confirm);
    await tester.pumpAndSettle();

    expect(repository.activatedLoanId, 'ready-loan');
    expect(
      repository.activationNote,
      'Verified against synthetic signed-contract schedule.',
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
  permissions: <String>['lending.contract_collection.activate'],
);

DeviceIdentityProvider _deviceIdentityProvider() {
  final store = MemoryDeviceIdentityStore()..value = 'management-device';
  return DeviceIdentityProvider(
    store: store,
    platformResolver: () => 'android',
    appVersionResolver: () async => '1.0.0',
  );
}

class _FakeRepository implements ContractCollectionActivationRepository {
  String? deviceId;
  String? activatedLoanId;
  String? activationNote;

  @override
  Future<ContractCollectionActivationData> load(
    UserSession session, {
    required String deviceId,
  }) async {
    this.deviceId = deviceId;
    return ContractCollectionActivationData(
      permission: true,
      activeCount: 0,
      readyToActivateCount: 1,
      notice: 'One loan at a time. No automatic activation.',
      loans: const <ContractCollectionActivationLoan>[_ready, _blocked],
    );
  }

  @override
  Future<ContractCollectionActivationLoan> activate(
    UserSession session, {
    required String deviceId,
    required String loanId,
    required String activationNote,
  }) async {
    this.deviceId = deviceId;
    activatedLoanId = loanId;
    this.activationNote = activationNote;
    return _ready;
  }

  @override
  Future<ContractCollectionActivationLoan> deactivate(
    UserSession session, {
    required String deviceId,
    required String loanId,
    required String activationNote,
  }) async {
    this.deviceId = deviceId;
    return _ready;
  }
}

const _ready = ContractCollectionActivationLoan(
  loanId: 'ready-loan',
  loanNumber: 'LN-READY',
  clientName: 'Synthetic Ready Client',
  loanTypeName: 'Regular',
  loanStatus: 'active',
  remainingBalance: 270,
  mobileCollectionsEnabled: true,
  mobileBalanceMode: 'direct_remaining_balance',
  scheduleId: 'schedule-ready',
  scheduleVersion: 1,
  paymentFrequency: 'daily',
  contractReference: 'SYNTH-SIGNED-001',
  dpdDataStatus: 'ready',
  contractualScheduleTotal: 270,
  allocatedScheduleTotal: 0,
  unpaidContractualAmount: 270,
  scheduleVerified: true,
  balanceReconciled: true,
  accountingSafe: true,
  activationEventId: null,
  activationAction: '',
  activationScheduleId: null,
  activationNote: '',
  activationActedAt: null,
  isActive: false,
  activeForCurrentSchedule: false,
  canActivate: true,
  canDeactivate: false,
  blockers: <String>[],
);

const _blocked = ContractCollectionActivationLoan(
  loanId: 'blocked-loan',
  loanNumber: 'LN-BLOCKED',
  clientName: 'Synthetic Blocked Client',
  loanTypeName: 'Regular',
  loanStatus: 'active',
  remainingBalance: 5000,
  mobileCollectionsEnabled: true,
  mobileBalanceMode: 'direct_remaining_balance',
  scheduleId: null,
  scheduleVersion: null,
  paymentFrequency: '',
  contractReference: '',
  dpdDataStatus: 'contract_schedule_required',
  contractualScheduleTotal: 0,
  allocatedScheduleTotal: 0,
  unpaidContractualAmount: 0,
  scheduleVerified: false,
  balanceReconciled: false,
  accountingSafe: true,
  activationEventId: null,
  activationAction: '',
  activationScheduleId: null,
  activationNote: '',
  activationActedAt: null,
  isActive: false,
  activeForCurrentSchedule: false,
  canActivate: false,
  canDeactivate: false,
  blockers: <String>[
    'Signed-contract schedule has not been registered.',
    'Contract schedule/payment allocation is not DPD-ready (contract_schedule_required).',
  ],
);
