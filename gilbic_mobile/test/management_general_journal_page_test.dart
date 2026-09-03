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
    expect(find.textContaining('₱100.00 / ₱100.00'), findsOneWidget);
    expect(find.byKey(const Key('create-manual-journal')), findsOneWidget);
    expect(repository.deviceId, 'management-device');

    final journalCard = find.byKey(const Key('journal-entry-1'));
    await tester.scrollUntilVisible(
      journalCard,
      350,
      scrollable: find.byType(Scrollable).first,
    );
    await tester.pumpAndSettle();
    expect(find.text('Draft journal'), findsOneWidget);
  });

  testWidgets(
    'Manual journal creation is reviewed and cancellation makes no write',
    (tester) async {
      final repository = _FakeGeneralJournalRepository();
      await _pumpCompactJournalPage(tester, repository);

      await tester.tap(find.byKey(const Key('create-manual-journal')));
      await tester.pumpAndSettle();
      await _fillBalancedDraft(tester, description: 'Office cash capital');
      await tester.tap(find.byKey(const Key('save-manual-journal')));
      await tester.pumpAndSettle();

      expect(
        find.byKey(const Key('management-review-general-journal')),
        findsOneWidget,
      );
      expect(
        find.text(
          'The entered journal will be sent as an unposted draft. The backend '
          'will revalidate balance and posting rules; no General Ledger balance '
          'changes until separate review and posting.',
        ),
        findsOneWidget,
      );
      expect(find.text('New unposted draft'), findsOneWidget);
      expect(find.text('Entered debit total'), findsOneWidget);
      expect(find.text('Entered credit total'), findsOneWidget);
      await tester.tap(find.byKey(const Key('cancel-general-journal')));
      await tester.pumpAndSettle();
      expect(repository.createCalls, 0);

      await tester.tap(find.byKey(const Key('create-manual-journal')));
      await tester.pumpAndSettle();
      await _fillBalancedDraft(tester, description: 'Office cash capital');
      await tester.tap(find.byKey(const Key('save-manual-journal')));
      await tester.pumpAndSettle();
      await tester.tap(find.byKey(const Key('confirm-general-journal')));
      await tester.pumpAndSettle();

      expect(repository.createCalls, 1);
      expect(repository.createdDescription, 'Office cash capital');
      expect(repository.createdLines, hasLength(2));
      expect(repository.createdLines![0].accountCode, '1010');
      expect(repository.createdLines![0].debit, 100);
      expect(repository.createdLines![0].credit, 0);
      expect(repository.createdLines![1].accountCode, '3000');
      expect(repository.createdLines![1].debit, 0);
      expect(repository.createdLines![1].credit, 100);
      expect(repository.createdPostingDate, isNotNull);
    },
  );

  testWidgets('Draft edit post and cancellation use separate reviews', (
    tester,
  ) async {
    final repository = _FakeGeneralJournalRepository();
    await _pumpCompactJournalPage(tester, repository);
    await _expandEntry(tester, title: 'Draft journal');

    final edit = find.byKey(const Key('edit-journal-entry-1'));
    await _scrollToEntryAction(tester, edit);
    await tester.tap(edit);
    await tester.pumpAndSettle();
    await tester.enterText(
      find.byKey(const Key('journal-description')),
      'Updated office cash capital',
    );
    await tester.tap(find.byKey(const Key('save-manual-journal')));
    await tester.pumpAndSettle();
    expect(repository.updateCalls, 0);
    await tester.tap(find.byKey(const Key('confirm-general-journal')));
    await tester.pumpAndSettle();
    expect(repository.updateCalls, 1);
    expect(repository.updatedEntryId, 'entry-1');
    expect(repository.updatedDescription, 'Updated office cash capital');
    expect(repository.updatedPostingDate, DateTime(2026, 8, 8));
    expect(repository.updatedLines, hasLength(2));
    expect(repository.updatedLines![0].accountCode, '1010');
    expect(repository.updatedLines![0].debit, 100);
    expect(repository.updatedLines![1].accountCode, '3000');
    expect(repository.updatedLines![1].credit, 100);

    final post = find.byKey(const Key('post-journal-entry-1'));
    await _scrollToEntryAction(tester, post);
    await tester.tap(post);
    await tester.pumpAndSettle();
    expect(
      find.text(
        'The journal will be posted immutably to the General Ledger. '
        'Corrections require a separate reversal with permanent audit evidence.',
      ),
      findsOneWidget,
    );
    await tester.tap(find.byKey(const Key('cancel-general-journal')));
    await tester.pumpAndSettle();
    expect(repository.postCalls, 0);
    await tester.tap(post);
    await tester.pumpAndSettle();
    await tester.tap(find.byKey(const Key('confirm-general-journal')));
    await tester.pumpAndSettle();
    expect(repository.postCalls, 1);
    expect(repository.postedEntryId, 'entry-1');

    final cancel = find.byKey(const Key('cancel-journal-entry-1'));
    await _scrollToEntryAction(tester, cancel);
    await tester.tap(cancel);
    await tester.pumpAndSettle();
    expect(
      find.text(
        'The draft will be cancelled while a permanent audit snapshot is '
        'retained. No posted ledger balance will change.',
      ),
      findsOneWidget,
    );
    await tester.tap(find.byKey(const Key('confirm-general-journal')));
    await tester.pumpAndSettle();
    expect(repository.cancelCalls, 1);
    expect(repository.cancelledEntryId, 'entry-1');
  });

  testWidgets('Posted journal reversal creates a separately reviewed draft', (
    tester,
  ) async {
    final repository = _FakeGeneralJournalRepository(posted: true);
    await _pumpCompactJournalPage(tester, repository);
    await _expandEntry(tester, title: 'GJ-0001');

    final reverse = find.byKey(const Key('reverse-journal-entry-1'));
    await _scrollToEntryAction(tester, reverse);
    await tester.tap(reverse);
    await tester.pumpAndSettle();
    await tester.tap(find.byKey(const Key('create-reversal-draft')));
    await tester.pumpAndSettle();

    expect(repository.reversalCalls, 0);
    expect(
      find.text(
        'A separate unposted reversal draft will be created with debit and '
        'credit lines swapped. It must be reviewed and posted separately.',
      ),
      findsOneWidget,
    );
    await tester.tap(find.byKey(const Key('confirm-general-journal')));
    await tester.pumpAndSettle();
    expect(repository.reversalCalls, 1);
    expect(repository.reversalEntryId, 'entry-1');
    expect(repository.reversalDescription, 'Reversal of GJ-0001');
    expect(repository.reversalPostingDate, isNotNull);
  });
}

Future<void> _pumpCompactJournalPage(
  WidgetTester tester,
  _FakeGeneralJournalRepository repository,
) async {
  await tester.binding.setSurfaceSize(const Size(360, 640));
  addTearDown(() async => tester.binding.setSurfaceSize(null));
  await tester.pumpWidget(
    MaterialApp(
      builder: (context, child) => MediaQuery(
        data: MediaQuery.of(
          context,
        ).copyWith(textScaler: const TextScaler.linear(1.3)),
        child: child!,
      ),
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
}

Future<void> _fillBalancedDraft(
  WidgetTester tester, {
  required String description,
}) async {
  await tester.enterText(
    find.byKey(const Key('journal-description')),
    description,
  );
  final journalDialogScroll = find
      .descendant(
        of: find.byType(AlertDialog),
        matching: find.byType(SingleChildScrollView),
      )
      .first;

  Future<void> selectAccount(int index, String label) async {
    final account = find.byKey(Key('journal-line-$index-account'));
    await tester.dragUntilVisible(
      account,
      journalDialogScroll,
      const Offset(0, -180),
    );
    await tester.tap(account);
    await tester.pumpAndSettle();
    await tester.tap(find.text(label).last);
    await tester.pumpAndSettle();
  }

  await selectAccount(0, '1010 • Cash - Office');
  await tester.enterText(find.byKey(const Key('journal-line-0-debit')), '100');
  await selectAccount(1, '3000 • Capital');
  await tester.enterText(find.byKey(const Key('journal-line-1-credit')), '100');
}

Future<void> _expandEntry(WidgetTester tester, {required String title}) async {
  final journalCard = find.byKey(const Key('journal-entry-1'));
  await tester.scrollUntilVisible(
    journalCard,
    300,
    scrollable: find.byType(Scrollable).first,
  );
  await tester.tap(find.text(title));
  await tester.pumpAndSettle();
}

Future<void> _scrollToEntryAction(WidgetTester tester, Finder action) async {
  await tester.scrollUntilVisible(
    action,
    300,
    scrollable: find.byType(Scrollable).first,
  );
  await tester.pumpAndSettle();
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
  _FakeGeneralJournalRepository({this.posted = false});

  final bool posted;
  String? deviceId;
  int createCalls = 0;
  int updateCalls = 0;
  int cancelCalls = 0;
  int postCalls = 0;
  int reversalCalls = 0;
  DateTime? createdPostingDate;
  String? createdDescription;
  List<JournalLineDraft>? createdLines;
  String? updatedEntryId;
  DateTime? updatedPostingDate;
  String? updatedDescription;
  List<JournalLineDraft>? updatedLines;
  String? cancelledEntryId;
  String? postedEntryId;
  String? reversalEntryId;
  DateTime? reversalPostingDate;
  String? reversalDescription;

  AccountingJournalEntry get _entry => AccountingJournalEntry(
    entryId: 'entry-1',
    entryNumber: posted ? 'GJ-0001' : null,
    periodId: 'period-1',
    periodLabel: 'August 2026',
    postingDate: DateTime(2026, 8, 8),
    description: 'Test manual journal',
    status: posted ? 'posted' : 'draft',
    sourceType: 'manual',
    sourceReference: null,
    reversalOfEntryId: null,
    createdByName: 'Management',
    postedByName: posted ? 'Management' : null,
    createdAt: DateTime(2026, 8, 8),
    postedAt: posted ? DateTime(2026, 8, 8) : null,
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
  );

  @override
  Future<GeneralJournalSnapshot> loadJournals(
    UserSession session, {
    required String deviceId,
  }) async {
    this.deviceId = deviceId;
    return GeneralJournalSnapshot(
      entries: <AccountingJournalEntry>[_entry],
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
  }) async {
    createCalls += 1;
    createdPostingDate = postingDate;
    createdDescription = description;
    createdLines = List<JournalLineDraft>.of(lines);
    return _entry;
  }

  @override
  Future<AccountingJournalEntry> updateDraft(
    UserSession session, {
    required String deviceId,
    required String entryId,
    required DateTime postingDate,
    required String description,
    required List<JournalLineDraft> lines,
  }) async {
    updateCalls += 1;
    updatedEntryId = entryId;
    updatedPostingDate = postingDate;
    updatedDescription = description;
    updatedLines = List<JournalLineDraft>.of(lines);
    return _entry;
  }

  @override
  Future<void> cancelDraft(
    UserSession session, {
    required String deviceId,
    required String entryId,
  }) async {
    cancelCalls += 1;
    cancelledEntryId = entryId;
  }

  @override
  Future<AccountingJournalEntry> postJournal(
    UserSession session, {
    required String deviceId,
    required String entryId,
  }) async {
    postCalls += 1;
    postedEntryId = entryId;
    return _entry;
  }

  @override
  Future<AccountingJournalEntry> createReversalDraft(
    UserSession session, {
    required String deviceId,
    required String entryId,
    required DateTime postingDate,
    required String description,
  }) async {
    reversalCalls += 1;
    reversalEntryId = entryId;
    reversalPostingDate = postingDate;
    reversalDescription = description;
    return _entry;
  }
}
