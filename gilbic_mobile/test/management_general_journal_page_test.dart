import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:gilbic_mobile/src/core/auth/app_role.dart';
import 'package:gilbic_mobile/src/core/auth/user_session.dart';
import 'package:gilbic_mobile/src/core/device/device_identity.dart';
import 'package:gilbic_mobile/src/core/management/financial_accounting.dart';
import 'package:gilbic_mobile/src/core/management/general_journal.dart';
import 'package:gilbic_mobile/src/core/management/general_journal_repository.dart';
import 'package:gilbic_mobile/src/features/management/management_general_journal_page.dart';

void main() {
  testWidgets('Management sees protected journal and balanced trial balance', (
    tester,
  ) async {
    final repository = _FakeGeneralJournalRepository();

    await tester.pumpWidget(
      MaterialApp(
        home: ManagementGeneralJournalPage(
          session: _session,
          deviceIdentityProvider: _deviceIdentityProvider(),
          accounts: _accounts,
          periods: _periods,
          repository: repository,
        ),
      ),
    );
    await tester.pumpAndSettle();

    expect(find.text('General Journal'), findsWidgets);
    expect(find.text('Trial Balance'), findsOneWidget);
    expect(find.textContaining('Balanced'), findsOneWidget);
    expect(find.text('₱100.00 / ₱100.00'), findsOneWidget);
    expect(find.text('Draft journal'), findsOneWidget);
    expect(find.byKey(const Key('create-manual-journal')), findsOneWidget);
    expect(repository.deviceId, 'management-device');
  });
}

const UserSession _session = UserSession(
  userId: 'management-1',
  username: 'manager',
  displayName: 'Management',
  role: AppRole.management,
  rawRole: 'Management',
  accessToken: 'management-token',
  permissions: <String>['accounting.view', 'accounting.journal.manage'],
);

DeviceIdentityProvider _deviceIdentityProvider() {
  final store = MemoryDeviceIdentityStore()..value = 'management-device';
  return DeviceIdentityProvider(
    store: store,
    platformResolver: () => 'android',
    appVersionResolver: () async => '1.0.0',
  );
}

const _accounts = <AccountingAccount>[
  AccountingAccount(
    code: '1010',
    systemKey: 'cash_office',
    name: 'Cash - Office',
    accountType: 'asset',
    normalBalance: 'debit',
    isPosting: true,
    isActive: true,
  ),
  AccountingAccount(
    code: '3000',
    systemKey: 'capital',
    name: 'Capital',
    accountType: 'equity',
    normalBalance: 'credit',
    isPosting: true,
    isActive: true,
  ),
];

final _periods = <AccountingFiscalPeriod>[
  AccountingFiscalPeriod(
    periodId: 'period-1',
    label: 'August 2026',
    startDate: DateTime(2026, 8, 1),
    endDate: DateTime(2026, 8, 31),
    status: 'open',
    journalCount: 1,
    draftJournalCount: 1,
    postedJournalCount: 0,
  ),
];

class _FakeGeneralJournalRepository implements GeneralJournalRepository {
  String? deviceId;

  @override
  Future<GeneralJournalSnapshot> loadJournals(
    UserSession session, {
    required String deviceId,
  }) async {
    this.deviceId = deviceId;
    return GeneralJournalSnapshot(
      entries: <AccountingJournalEntry>[
        AccountingJournalEntry(
          entryId: 'entry-1',
          entryNumber: null,
          periodId: 'period-1',
          periodLabel: 'August 2026',
          postingDate: DateTime(2026, 8, 8),
          description: 'Test manual journal',
          status: 'draft',
          sourceType: 'manual',
          sourceReference: null,
          reversalOfEntryId: null,
          createdByName: 'Management',
          postedByName: null,
          createdAt: DateTime(2026, 8, 8),
          postedAt: null,
          totalDebit: 100,
          totalCredit: 100,
          lines: const <AccountingJournalLine>[
            AccountingJournalLine(
              lineNumber: 1,
              accountCode: '1010',
              accountName: 'Cash - Office',
              description: '',
              debit: 100,
              credit: 0,
            ),
            AccountingJournalLine(
              lineNumber: 2,
              accountCode: '3000',
              accountName: 'Capital',
              description: '',
              debit: 0,
              credit: 100,
            ),
          ],
        ),
      ],
      canManage: true,
      automaticLoanPostingEnabled: false,
    );
  }

  @override
  Future<AccountingTrialBalance> loadTrialBalance(
    UserSession session, {
    required String deviceId,
    String? periodId,
  }) async {
    return const AccountingTrialBalance(
      periodId: null,
      periodLabel: null,
      totalDebits: 100,
      totalCredits: 100,
      balanced: true,
      lines: <AccountingTrialBalanceLine>[
        AccountingTrialBalanceLine(
          accountCode: '1010',
          accountName: 'Cash - Office',
          accountType: 'asset',
          normalBalance: 'debit',
          totalDebit: 100,
          totalCredit: 0,
          debitBalance: 100,
          creditBalance: 0,
        ),
        AccountingTrialBalanceLine(
          accountCode: '3000',
          accountName: 'Capital',
          accountType: 'equity',
          normalBalance: 'credit',
          totalDebit: 0,
          totalCredit: 100,
          debitBalance: 0,
          creditBalance: 100,
        ),
      ],
    );
  }

  @override
  Future<AccountingJournalEntry> createDraft(
    UserSession session, {
    required String deviceId,
    required DateTime postingDate,
    required String description,
    required List<JournalLineDraft> lines,
  }) {
    throw UnimplementedError();
  }

  @override
  Future<AccountingJournalEntry> updateDraft(
    UserSession session, {
    required String deviceId,
    required String entryId,
    required DateTime postingDate,
    required String description,
    required List<JournalLineDraft> lines,
  }) {
    throw UnimplementedError();
  }

  @override
  Future<void> cancelDraft(
    UserSession session, {
    required String deviceId,
    required String entryId,
  }) {
    throw UnimplementedError();
  }

  @override
  Future<AccountingJournalEntry> postJournal(
    UserSession session, {
    required String deviceId,
    required String entryId,
  }) {
    throw UnimplementedError();
  }

  @override
  Future<AccountingJournalEntry> createReversalDraft(
    UserSession session, {
    required String deviceId,
    required String entryId,
    required DateTime postingDate,
    required String description,
  }) {
    throw UnimplementedError();
  }
}
