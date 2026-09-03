import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:gilbic_mobile/src/core/auth/app_role.dart';
import 'package:gilbic_mobile/src/core/auth/user_session.dart';
import 'package:gilbic_mobile/src/core/device/device_identity.dart';
import 'package:gilbic_mobile/src/core/loans/client_loan.dart';
import 'package:gilbic_mobile/src/core/loans/client_loan_repository.dart';
import 'package:gilbic_mobile/src/core/network/spina_api.dart';
import 'package:gilbic_mobile/src/features/client/client_dashboard.dart';
import 'package:gilbic_mobile/src/features/client/client_loans_page.dart';

void main() {
  testWidgets(
    'Client home separates current loan facts and uses compact next-action rows',
    (tester) async {
      await _setPhoneSurface(tester);
      final repository = _FakeClientLoanRepository(_portfolio());

      await tester.pumpWidget(
        MaterialApp(
          home: ClientDashboard(
            session: _session(),
            onSignOut: () async {},
            deviceIdentityProvider: _deviceIdentityProvider(),
            loanRepository: repository,
          ),
        ),
      );
      await tester.pumpAndSettle();

      expect(find.text('Welcome, Ana'), findsOneWidget);
      expect(find.text('2 active loans'), findsOneWidget);
      expect(
        find.byKey(const Key('client-home-loan-regular-loan')),
        findsOneWidget,
      );
      expect(
        find.byKey(const Key('client-home-loan-seven-by-seven-loan')),
        findsOneWidget,
      );
      expect(find.text('Regular'), findsOneWidget);
      expect(find.text('7x7'), findsOneWidget);
      expect(find.text('Official remaining balance'), findsNWidgets(2));
      expect(find.text('₱4,950.00'), findsOneWidget);
      expect(find.text('₱3,000.00'), findsOneWidget);
      expect(find.text('Scheduled daily amount'), findsNWidgets(2));
      expect(find.text('₱50.00'), findsOneWidget);
      expect(find.text('₱21.00'), findsOneWidget);
      expect(find.textContaining('amount due today'), findsNothing);

      expect(find.byKey(const Key('open-account-settings')), findsOneWidget);
      expect(find.byKey(const Key('open-notification-center')), findsOneWidget);
      expect(find.byKey(const Key('open-offline-policy')), findsOneWidget);
      expect(find.text('Daily Route'), findsNothing);
      expect(find.text('Financial Accounting'), findsNothing);

      await tester.scrollUntilVisible(
        find.byKey(const Key('client-home-support')),
        350,
        scrollable: find.byType(Scrollable).first,
      );
      expect(find.byKey(const Key('client-home-loans')), findsOneWidget);
      expect(find.byKey(const Key('client-home-payments')), findsOneWidget);
      expect(
        find.byKey(const Key('client-home-payment-updates')),
        findsOneWidget,
      );
      expect(find.byKey(const Key('client-home-renewal')), findsOneWidget);
      expect(find.byKey(const Key('client-home-support')), findsOneWidget);
      expect(repository.deviceId, 'client-home-device');
      expect(repository.userId, 'client-1');
      expect(tester.takeException(), isNull);
    },
  );

  testWidgets(
    'Client home opens the existing authoritative loan details page',
    (tester) async {
      await _setPhoneSurface(tester);
      final repository = _FakeClientLoanRepository(_portfolio());

      await tester.pumpWidget(
        MaterialApp(
          home: ClientDashboard(
            session: _session(),
            onSignOut: () async {},
            deviceIdentityProvider: _deviceIdentityProvider(),
            loanRepository: repository,
          ),
        ),
      );
      await tester.pumpAndSettle();

      await tester.tap(find.byKey(const Key('client-home-loan-regular-loan')));
      await tester.pumpAndSettle();

      expect(find.byType(ClientLoansPage), findsOneWidget);
      expect(find.text('My Loans'), findsOneWidget);
      expect(find.text('Official remaining balance'), findsWidgets);
    },
  );

  testWidgets('Client home honestly reports when there is no active loan', (
    tester,
  ) async {
    await _setPhoneSurface(tester);
    final emptyPortfolio = ClientLoanPortfolio(
      clientId: 'client-record-1',
      clientCode: 'CLIENT-001',
      clientName: 'Ana Client',
      clientStatus: 'active',
      loans: <ClientLoan>[_regularLoan(status: 'paid', remainingBalance: 0)],
    );

    await tester.pumpWidget(
      MaterialApp(
        home: ClientDashboard(
          session: _session(),
          onSignOut: () async {},
          deviceIdentityProvider: _deviceIdentityProvider(),
          loanRepository: _FakeClientLoanRepository(emptyPortfolio),
        ),
      ),
    );
    await tester.pumpAndSettle();

    expect(find.text('No active loan'), findsOneWidget);
    expect(
      find.text('Your loan history remains available in My loans.'),
      findsOneWidget,
    );
    expect(find.text('Official remaining balance'), findsNothing);
    expect(find.text('Scheduled daily amount'), findsNothing);
    expect(find.textContaining('amount due today'), findsNothing);
  });

  testWidgets('Client home gives safe retry guidance without server internals', (
    tester,
  ) async {
    await _setPhoneSurface(tester);
    final repository = _FakeClientLoanRepository.failure(
      const SpinaApiException(
        'column client_secret does not exist',
        statusCode: 500,
        code: 'internal_database_error',
      ),
    );

    await tester.pumpWidget(
      MaterialApp(
        home: ClientDashboard(
          session: _session(),
          onSignOut: () async {},
          deviceIdentityProvider: _deviceIdentityProvider(),
          loanRepository: repository,
        ),
      ),
    );
    await tester.pumpAndSettle();

    expect(
      find.text(
        'Your latest loan information could not be loaded. Try again in a moment.',
      ),
      findsOneWidget,
    );
    expect(find.textContaining('client_secret'), findsNothing);
    expect(find.byKey(const Key('client-home-retry')), findsOneWidget);
  });

  testWidgets('Client home remains usable at 360x640 and 1.3 text scale', (
    tester,
  ) async {
    await tester.binding.setSurfaceSize(const Size(360, 640));
    addTearDown(() async => tester.binding.setSurfaceSize(null));

    await tester.pumpWidget(
      MediaQuery(
        data: const MediaQueryData(textScaler: TextScaler.linear(1.3)),
        child: MaterialApp(
          home: ClientDashboard(
            session: _session(),
            onSignOut: () async {},
            deviceIdentityProvider: _deviceIdentityProvider(),
            loanRepository: _FakeClientLoanRepository(_portfolio()),
          ),
        ),
      ),
    );
    await tester.pumpAndSettle();

    expect(find.byKey(const Key('client-dashboard-list')), findsOneWidget);
    expect(tester.takeException(), isNull);
  });
}

UserSession _session() => UserSession(
  userId: 'client-1',
  username: 'ana.client',
  displayName: 'Ana',
  role: AppRole.client,
  rawRole: 'Client',
  accessToken: 'client-token',
  permissions: <String>['loan.self.view'],
);

DeviceIdentityProvider _deviceIdentityProvider() {
  final store = MemoryDeviceIdentityStore()..value = 'client-home-device';
  return DeviceIdentityProvider(
    store: store,
    platformResolver: () => 'android',
    appVersionResolver: () async => '1.0.0',
  );
}

ClientLoanPortfolio _portfolio() => ClientLoanPortfolio(
  clientId: 'client-record-1',
  clientCode: 'CLIENT-001',
  clientName: 'Ana Client',
  area: 'Area 1',
  clientStatus: 'active',
  loans: <ClientLoan>[
    _regularLoan(),
    ClientLoan(
      loanId: 'seven-by-seven-loan',
      loanNumber: '7X7-001',
      loanTypeCode: 'seven_by_seven',
      loanTypeName: '7x7',
      principal: 3000,
      dailyAmount: 21,
      status: 'active',
      remainingBalance: 3000,
      paidAmount: 0,
      passCount: 0,
      stateVersion: 0,
      paymentCount: 0,
    ),
  ],
);

ClientLoan _regularLoan({
  String status = 'active',
  double remainingBalance = 4950,
}) {
  return ClientLoan(
    loanId: 'regular-loan',
    loanNumber: 'REG-001',
    loanTypeCode: 'regular',
    loanTypeName: 'Regular',
    principal: 5000,
    dailyAmount: 50,
    dateReleased: DateTime(2026, 8, 1),
    dueDate: DateTime(2026, 11, 29),
    status: status,
    remainingBalance: remainingBalance,
    paidAmount: 50,
    passCount: 0,
    lastPaymentDate: DateTime(2026, 8, 2),
    stateVersion: 3,
    paymentCount: 1,
  );
}

class _FakeClientLoanRepository implements ClientLoanRepository {
  _FakeClientLoanRepository(this.portfolio) : failure = null;

  _FakeClientLoanRepository.failure(this.failure) : portfolio = null;

  final ClientLoanPortfolio? portfolio;
  final Object? failure;
  String? deviceId;
  String? userId;

  @override
  Future<ClientLoanPortfolio> loadPortfolio(
    UserSession session, {
    required String deviceId,
  }) async {
    this.deviceId = deviceId;
    userId = session.userId;
    if (failure != null) throw failure!;
    return portfolio!;
  }
}

Future<void> _setPhoneSurface(WidgetTester tester) async {
  await tester.binding.setSurfaceSize(const Size(430, 932));
  addTearDown(() async => tester.binding.setSurfaceSize(null));
}
