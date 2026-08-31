import 'package:flutter/foundation.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:gilbic_mobile/src/features/management/review/management_review.dart';
import 'package:gilbic_mobile/src/theme/spina_theme.dart';

void main() {
  test(
    'catalog inventories every approved Management mutation surface once',
    () {
      const expected = <String, ({String owner, List<String> actions})>{
        'client-registration': (
          owner: 'ClientRegistrationApprovalsPage',
          actions: <String>['approve and link', 'reject'],
        ),
        'renewal-workflow': (
          owner: 'ManagementRenewalRequestsPage',
          actions: <String>[
            'record terms',
            'reject',
            'release to Collector',
            'review proof',
            'activate',
          ],
        ),
        'staff-invitation': (
          owner: 'ManagementStaffInvitePage',
          actions: <String>['invite', 'reconcile uncertain result'],
        ),
        'staff-access': (
          owner: 'ManagementStaffDetailPage',
          actions: <String>[
            'change role',
            'change account status',
            'approve or revoke device',
          ],
        ),
        'collection-void': (
          owner: 'ManagementCollectionVoidPage',
          actions: <String>['void eligible collection'],
        ),
        'contract-collection': (
          owner: 'ManagementContractCollectionActivationPage',
          actions: <String>['activate', 'deactivate'],
        ),
        'no-collection': (
          owner: 'ManagementNoCollectionPage',
          actions: <String>['declare', 'reverse'],
        ),
        'client-support': (
          owner: 'ManagementSupportRequestsPage',
          actions: <String>['answer', 'resolve', 'cancel'],
        ),
        'ecl-outcome-review': (
          owner: 'ManagementEclOutcomeReviewPage',
          actions: <String>['save historical outcome review'],
        ),
        'fiscal-period': (
          owner: 'ManagementFinancialAccountingPage',
          actions: <String>['create period', 'change status'],
        ),
        'general-journal': (
          owner: 'ManagementGeneralJournalPage',
          actions: <String>[
            'create or edit draft',
            'post',
            'cancel',
            'create reversal draft',
          ],
        ),
        'opening-workbook': (
          owner: 'ManagementOpeningBalanceWorkbookPage',
          actions: <String>[
            'initialize',
            'edit line or policy',
            'change status',
          ],
        ),
        'opening-journal': (
          owner: 'ManagementOpeningBalanceJournalPage',
          actions: <String>['prepare', 'post'],
        ),
        'period-close': (
          owner: 'ManagementPeriodClosePage',
          actions: <String>['prepare', 'post'],
        ),
        'ecl-allowance': (
          owner: 'ManagementEclAllowancePostingPage',
          actions: <String>['prepare', 'post'],
        ),
        'ecl-a5': (
          owner: 'ManagementEclA5AccountingPage',
          actions: <String>[
            'post remeasurement',
            'post full write-off',
            'review recovery evidence',
            'post recovery',
          ],
        ),
        'initial-capital': (
          owner: 'ManagementInitialCapitalFundingPage',
          actions: <String>['record evidence', 'prepare', 'post'],
        ),
        'tax-evidence': (
          owner: 'ManagementTaxEvidencePage',
          actions: <String>[
            'record rule',
            'record DST',
            'record percentage allocation',
          ],
        ),
        'tax-liability': (
          owner: 'ManagementTaxLiabilityPage',
          actions: <String>['prepare', 'post'],
        ),
        'tax-settlement': (
          owner: 'ManagementTaxSettlementPage',
          actions: <String>[
            'record return',
            'record payment',
            'prepare',
            'post',
          ],
        ),
        'tax-adjustment': (
          owner: 'ManagementTaxAdjustmentPage',
          actions: <String>['record evidence', 'prepare', 'post'],
        ),
        'additional-tax': (
          owner: 'ManagementAdditionalTaxPage',
          actions: <String>[
            'record amendment evidence',
            'prepare liability',
            'post liability',
            'record payment evidence',
            'prepare settlement',
            'post settlement',
          ],
        ),
        'tax-recoverable': (
          owner: 'ManagementTaxRecoverablePage',
          actions: <String>[
            'record refund evidence',
            'prepare refund',
            'post refund',
            'record credit evidence',
            'prepare credit',
            'post credit',
          ],
        ),
      };

      expect(managementMutationSurfaceCatalog, hasLength(23));
      expect(
        managementMutationSurfaceCatalog.map((entry) => entry.surface).toSet(),
        ManagementMutationSurface.values.toSet(),
      );

      final actual = <String, ({String owner, List<String> actions})>{
        for (final entry in managementMutationSurfaceCatalog)
          entry.surface.id: (owner: entry.owner, actions: entry.actions),
      };
      expect(actual, expected);
      expect(
        managementMutationSurfaceCatalog.every(
          (entry) =>
              entry.owner.trim().isNotEmpty &&
              entry.actions.isNotEmpty &&
              entry.actions.every((action) => action.trim().isNotEmpty),
        ),
        isTrue,
      );
    },
  );

  test('read-only Management containers stay outside the mutation catalog', () {
    const readOnlyOwners = <String>{
      'ManagementDashboard',
      'ManagementLoanPortfolioPage',
      'ManagementLoanOperationsPage',
      'ManagementAccountingMeasurementPage',
      'ManagementFinancialStatementsPage',
      'ManagementGeneralJournalLauncherPage',
      'ManagementStaffDevicesPage',
    };
    final mutationOwners = managementMutationSurfaceCatalog
        .map((entry) => entry.owner)
        .toSet();

    expect(mutationOwners.intersection(readOnlyOwners), isEmpty);
  });

  test('typed production bindings are complete and one-to-one', () {
    expect(
      managementMutationSurfaceCatalog,
      orderedEquals(ManagementMutationBinding.values),
    );
    expect(
      managementMutationSurfaceCatalog.map((entry) => entry.name),
      orderedEquals(
        managementMutationSurfaceCatalog.map((entry) => entry.surface.name),
      ),
    );
    expect(
      managementMutationSurfaceCatalog.map((entry) => entry.owner).toSet(),
      hasLength(managementMutationSurfaceCatalog.length),
    );
  });

  for (final risk in ManagementReviewRisk.values) {
    testWidgets(
      '${risk.name} review exposes its risk to assistive technology',
      (tester) async {
        final entry = managementMutationSurfaceCatalog.firstWhere(
          (candidate) => candidate.defaultRisk == risk,
        );
        final review = ManagementReviewPresentation.validated(
          binding: entry,
          recordLabel: 'Test record',
          recordValue: 'Record 1',
          statusLabel: 'Waiting for Management review',
          nextActionLabel: 'Review action',
          consequence: 'The server record will move to its reviewed state.',
        );

        await tester.pumpWidget(
          MaterialApp(
            home: Scaffold(body: ManagementReviewPanel(review: review)),
          ),
        );

        expect(
          find.bySemanticsLabel('${_riskLabel(risk)} Management review'),
          findsOneWidget,
        );
        expect(find.byKey(review.key), findsOneWidget);
      },
    );
  }

  for (final platform in <TargetPlatform>[
    TargetPlatform.android,
    TargetPlatform.iOS,
  ]) {
    testWidgets('the catalogued review contract renders on ${platform.name}', (
      tester,
    ) async {
      final previousPlatform = debugDefaultTargetPlatformOverride;
      debugDefaultTargetPlatformOverride = platform;
      await tester.binding.setSurfaceSize(const Size(430, 800));
      addTearDown(() async {
        debugDefaultTargetPlatformOverride = previousPlatform;
        await tester.binding.setSurfaceSize(null);
      });
      final reviews = managementMutationSurfaceCatalog
          .map(
            (entry) => ManagementReviewPresentation.validated(
              binding: entry,
              recordLabel: 'Protected record',
              recordValue: entry.surface.id,
              statusLabel: 'Waiting for Management review',
              nextActionLabel: 'Confirm ${entry.actions.first}',
              consequence:
                  'The shared backend will validate and audit this action.',
            ),
          )
          .toList(growable: false);

      try {
        await tester.pumpWidget(
          MaterialApp(
            theme: SpinaTheme.light,
            home: Scaffold(
              body: SingleChildScrollView(
                child: Column(
                  children: reviews
                      .map((review) => ManagementReviewPanel(review: review))
                      .toList(growable: false),
                ),
              ),
            ),
          ),
        );

        for (final review in reviews) {
          expect(
            find.byKey(review.key),
            findsOneWidget,
            reason: '${platform.name}:${review.surface.id}',
          );
        }
        expect(
          Theme.of(tester.element(find.byKey(reviews.first.key))).platform,
          platform,
        );
      } finally {
        debugDefaultTargetPlatformOverride = previousPlatform;
      }
    });
  }
}

String _riskLabel(ManagementReviewRisk risk) {
  return switch (risk) {
    ManagementReviewRisk.routine => 'Routine',
    ManagementReviewRisk.privileged => 'Privileged',
    ManagementReviewRisk.protectedFinancial => 'Protected financial',
  };
}
