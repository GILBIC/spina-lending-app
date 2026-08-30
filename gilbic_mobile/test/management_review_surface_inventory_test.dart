import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:gilbic_mobile/src/features/management/review/management_review.dart';

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
      };

      expect(managementMutationSurfaceCatalog, hasLength(14));
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

  for (final risk in ManagementReviewRisk.values) {
    testWidgets(
      '${risk.name} review exposes its risk to assistive technology',
      (tester) async {
        final entry = managementMutationSurfaceCatalog.firstWhere(
          (candidate) => candidate.defaultRisk == risk,
        );
        final review = ManagementReviewPresentation.validated(
          surface: entry.surface,
          recordLabel: 'Test record',
          recordValue: 'Record 1',
          statusLabel: 'Waiting for Management review',
          nextActionLabel: 'Review action',
          consequence: 'The server record will move to its reviewed state.',
          risk: risk,
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
}

String _riskLabel(ManagementReviewRisk risk) {
  return switch (risk) {
    ManagementReviewRisk.routine => 'Routine',
    ManagementReviewRisk.privileged => 'Privileged',
    ManagementReviewRisk.protectedFinancial => 'Protected financial',
  };
}
