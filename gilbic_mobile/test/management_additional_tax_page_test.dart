import 'dart:async';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:gilbic_mobile/src/core/auth/app_role.dart';
import 'package:gilbic_mobile/src/core/auth/user_session.dart';
import 'package:gilbic_mobile/src/core/device/device_identity.dart';
import 'package:gilbic_mobile/src/core/network/spina_api.dart';
import 'package:gilbic_mobile/src/core/management/additional_tax.dart';
import 'package:gilbic_mobile/src/core/management/additional_tax_repository.dart';
import 'package:gilbic_mobile/src/features/management/management_additional_tax_page.dart';

void main() {
  for (final status in [401, 503]) {
    testWidgets('additional tax delayed device after $status fences write', (
      tester,
    ) async {
      await tester.binding.setSurfaceSize(const Size(1000, 1700));
      addTearDown(() => tester.binding.setSurfaceSize(null));
      final store = _DelayedStore();
      final repository = _WritableRepository(status);
      await tester.pumpWidget(
        MaterialApp(
          home: ManagementAdditionalTaxPage(
            session: const UserSession(
              userId: 'management-1',
              username: 'manager',
              displayName: 'Management',
              role: AppRole.management,
              rawRole: 'Management',
              accessToken: 'token',
              permissions: [
                'accounting.tax.additional_amendment_evidence.record',
              ],
            ),
            deviceIdentityProvider: DeviceIdentityProvider(
              store: store,
              platformResolver: () => 'android',
              appVersionResolver: () async => '1.0',
            ),
            repository: repository,
          ),
        ),
      );
      await tester.pumpAndSettle();
      final refresh = tester
          .widget<RefreshIndicator>(find.byType(RefreshIndicator))
          .onRefresh;
      await tester.tap(find.text('Record'));
      await tester.pumpAndSettle();
      for (var i = 0; i < 5; i++) {
        await tester.enterText(
          find.byType(TextField).at(i),
          [
            '2026-10-09',
            'AM-1',
            'evidence-1',
            'a' * 64,
            'Exact retained evidence',
          ][i],
        );
      }
      await tester.tap(find.text('Review'));
      await tester.pumpAndSettle();
      await tester.tap(find.byKey(const Key('confirm-additional-tax')));
      await tester.pump();
      await tester.pump(const Duration(milliseconds: 400));
      expect(store.calls, 2);
      await refresh();
      await tester.pumpAndSettle();
      store.pending.complete('management-device');
      await tester.pumpAndSettle();
      expect(repository.writes, status == 401 ? 0 : 1);
    });
  }
  testWidgets('additional-tax workspace shows authoritative empty queues', (
    tester,
  ) async {
    await tester.binding.setSurfaceSize(const Size(390, 844));
    addTearDown(() async => tester.binding.setSurfaceSize(null));
    await tester.pumpWidget(
      MaterialApp(
        home: ManagementAdditionalTaxPage(
          session: _session,
          deviceIdentityProvider: _deviceProvider(),
          repository: _Repository(),
        ),
      ),
    );
    await tester.pumpAndSettle();
    expect(find.text('Additional Tax'), findsOneWidget);
    expect(find.byKey(const Key('additional-tax-summary')), findsOneWidget);
    expect(
      find.text('No exact upward-amendment candidates are eligible.'),
      findsOneWidget,
    );
    expect(
      find.text('No retained additional-tax amendments yet.'),
      findsOneWidget,
    );
  });
}

class _Repository extends Fake implements AdditionalTaxRepository {
  @override
  Future<AdditionalTaxOverview> load(
    UserSession session, {
    required String deviceId,
    String amendmentStatus = 'all',
    int limit = 100,
    int offset = 0,
  }) async => const AdditionalTaxOverview(
    summary: AdditionalTaxSummary(
      amendmentEvidenceCount: 0,
      amendmentReadyCount: 0,
      liabilityPreparedCount: 0,
      awaitingPaymentCount: 0,
      paymentReadyCount: 0,
      settlementPreparedCount: 0,
      settledCount: 0,
      reviewCount: 0,
      blockedCount: 0,
      recognizedAdditionalTaxTotal: '0.00',
      settledPaymentTotal: '0.00',
    ),
    items: <AdditionalTaxItem>[],
    candidates: <AdditionalTaxCandidate>[],
    permissions: AdditionalTaxPermissions(
      amendmentEvidenceRecord: false,
      liabilityPrepare: false,
      liabilityPost: false,
      paymentEvidenceRecord: false,
      settlementPrepare: false,
      settlementPost: false,
    ),
    amendmentStatus: 'all',
    limit: 100,
    offset: 0,
    notice: 'Original return and settlement history remains immutable.',
  );
}

class _DelayedStore extends MemoryDeviceIdentityStore {
  _DelayedStore() {
    value = 'management-device';
  }
  int calls = 0;
  final pending = Completer<String?>();
  @override
  Future<String?> readInstallationId() {
    calls++;
    return calls == 2 ? pending.future : super.readInstallationId();
  }
}

class _WritableRepository extends _Repository {
  _WritableRepository(this.status);
  final int status;
  int reads = 0;
  int writes = 0;
  @override
  Future<AdditionalTaxOverview> load(
    UserSession session, {
    required String deviceId,
    String amendmentStatus = 'all',
    int limit = 100,
    int offset = 0,
  }) async {
    reads++;
    if (reads > 1) {
      throw SpinaApiException('Refresh denied', statusCode: status);
    }
    final base = await super.load(session, deviceId: deviceId);
    return AdditionalTaxOverview(
      summary: base.summary,
      items: [],
      candidates: [_candidate],
      permissions: const AdditionalTaxPermissions(
        amendmentEvidenceRecord: true,
        liabilityPrepare: false,
        liabilityPost: false,
        paymentEvidenceRecord: false,
        settlementPrepare: false,
        settlementPost: false,
      ),
      amendmentStatus: 'all',
      limit: 100,
      offset: 0,
      notice: base.notice,
    );
  }

  @override
  dynamic noSuchMethod(Invocation invocation) {
    if (invocation.memberName == #recordAmendmentEvidence) {
      writes++;
      return Future<AdditionalTaxItem>.error(
        const SpinaApiException('Transient write failure', statusCode: 503),
      );
    }
    return super.noSuchMethod(invocation);
  }
}

const _candidate = AdditionalTaxCandidate(
  taxType: 'documentary_stamp_tax',
  taxReturnId: 'return-1',
  taxLiabilityPostingId: 'liability-1',
  originalEvidenceId: 'original-1',
  originalEvidenceVersion: 1,
  replacementEvidenceId: 'replacement-1',
  replacementEvidenceVersion: 2,
  sourceId: 'source-1',
  loanId: 'loan-1',
  clientId: 'client-1',
  originalDeclaredTaxDue: '75.00',
  revisedDeclaredTaxDue: '100.00',
  originalItemTaxDue: '75.00',
  replacementItemTaxDue: '100.00',
  additionalTaxDue: '25.00',
  paymentBasis: 'additional_due_after_settlement',
  paymentRequiredAmount: '25.00',
  filingDate: '2026-08-20',
  recognitionDate: '2026-08-15',
  originalEvidenceDigest: 'digest-1',
  replacementEvidenceDigest: 'digest-2',
  originalFiscalPeriodId: 'period-1',
  originalFiscalPeriodStart: '2026-08-01',
  originalFiscalPeriodEnd: '2026-08-31',
  originalSettlementPostingId: 'settled-1',
);

DeviceIdentityProvider _deviceProvider() {
  final store = MemoryDeviceIdentityStore()..value = 'management-device';
  return DeviceIdentityProvider(
    store: store,
    platformResolver: () => 'android',
    appVersionResolver: () async => '1.0.0',
  );
}

const _session = UserSession(
  userId: 'management-1',
  username: 'manager',
  displayName: 'Management',
  role: AppRole.management,
  rawRole: 'Management',
  accessToken: 'management-token',
  permissions: <String>[],
);
