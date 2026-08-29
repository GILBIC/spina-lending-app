import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:gilbic_mobile/src/core/auth/app_role.dart';
import 'package:gilbic_mobile/src/core/auth/user_session.dart';
import 'package:gilbic_mobile/src/core/management/client_registration_review.dart';
import 'package:gilbic_mobile/src/core/management/client_registration_review_repository.dart';
import 'package:gilbic_mobile/src/features/management/client_registration_approvals_page.dart';

void main() {
  testWidgets(
    'approval shows server status and mutates only after confirmation',
    (tester) async {
      final repository = _RegistrationRepository();
      await _pumpLink(tester, repository);
      await tester.tap(find.byKey(const Key('open-registration-review')));
      await tester.pumpAndSettle();

      await tester.tap(find.byKey(const Key('borrower-candidate-client-1')));
      await tester.enterText(
        find.widgetWithText(TextField, 'Approval note (optional)'),
        'Verified at office',
      );
      await tester.tap(find.byKey(const Key('approve-client-registration')));
      await tester.pumpAndSettle();

      expect(
        find.byKey(const Key('management-review-client-registration')),
        findsOneWidget,
      );
      expect(find.text('Client registration request'), findsOneWidget);
      expect(find.text('Waiting for Management review'), findsOneWidget);
      expect(find.text('Approve and link this account'), findsWidgets);
      expect(
        find.text(
          'This login will be linked to the selected existing client record; official financial records will not be edited.',
        ),
        findsOneWidget,
      );
      expect(repository.approveCalls, 0);

      await tester.tap(find.byKey(const Key('cancel-client-registration')));
      await tester.pumpAndSettle();
      expect(repository.approveCalls, 0);

      await tester.tap(find.byKey(const Key('approve-client-registration')));
      await tester.pumpAndSettle();
      await tester.tap(find.byKey(const Key('confirm-client-registration')));
      await tester.pumpAndSettle();

      expect(repository.approveCalls, 1);
      expect(repository.lastUserId, 'user-1');
      expect(repository.lastClientId, 'client-1');
      expect(repository.lastReviewNote, 'Verified at office');
      expect(find.text('Changed: true'), findsOneWidget);
    },
  );

  testWidgets('rejection explains its consequence before repository write', (
    tester,
  ) async {
    final repository = _RegistrationRepository();
    await _pumpLink(tester, repository);
    await tester.tap(find.byKey(const Key('open-registration-review')));
    await tester.pumpAndSettle();

    await tester.tap(find.byKey(const Key('reject-client-registration')));
    await tester.pumpAndSettle();
    await tester.enterText(
      find.byKey(const Key('client-registration-rejection-reason')),
      'Identity does not match',
    );
    await tester.tap(find.widgetWithText(FilledButton, 'Reject'));
    await tester.pumpAndSettle();

    expect(
      find.byKey(const Key('management-review-client-registration')),
      findsOneWidget,
    );
    expect(find.text('Reject this request'), findsWidgets);
    expect(
      find.text(
        'This registration request will be rejected; official client and financial records will not be edited.',
      ),
      findsOneWidget,
    );
    expect(repository.rejectCalls, 0);

    await tester.tap(find.byKey(const Key('confirm-client-registration')));
    await tester.pumpAndSettle();

    expect(repository.rejectCalls, 1);
    expect(repository.lastUserId, 'user-1');
    expect(repository.lastReviewNote, 'Identity does not match');
  });
}

Future<void> _pumpLink(
  WidgetTester tester,
  _RegistrationRepository repository,
) async {
  await tester.pumpWidget(
    MaterialApp(home: _RegistrationHost(repository: repository)),
  );
}

class _RegistrationHost extends StatefulWidget {
  const _RegistrationHost({required this.repository});

  final ClientRegistrationReviewRepository repository;

  @override
  State<_RegistrationHost> createState() => _RegistrationHostState();
}

class _RegistrationHostState extends State<_RegistrationHost> {
  bool? _changed;

  Future<void> _open() async {
    final changed = await Navigator.of(context).push<bool>(
      MaterialPageRoute<bool>(
        builder: (_) => ClientRegistrationLinkPage(
          session: _session,
          deviceId: 'management-device',
          registration: _registration,
          repository: widget.repository,
        ),
      ),
    );
    if (mounted) setState(() => _changed = changed);
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      body: Column(
        children: <Widget>[
          FilledButton(
            key: const Key('open-registration-review'),
            onPressed: _open,
            child: const Text('Open'),
          ),
          if (_changed != null) Text('Changed: $_changed'),
        ],
      ),
    );
  }
}

class _RegistrationRepository implements ClientRegistrationReviewRepository {
  int approveCalls = 0;
  int rejectCalls = 0;
  String? lastUserId;
  String? lastClientId;
  String? lastReviewNote;

  @override
  Future<List<ClientRegistrationReview>> loadPending(
    UserSession session, {
    required String deviceId,
  }) async => <ClientRegistrationReview>[_registration];

  @override
  Future<List<ClientLinkCandidate>> searchCandidates(
    UserSession session, {
    required String deviceId,
    required String query,
  }) async => <ClientLinkCandidate>[_candidate];

  @override
  Future<void> approve(
    UserSession session, {
    required String deviceId,
    required String userId,
    required String clientId,
    String reviewNote = '',
  }) async {
    approveCalls += 1;
    lastUserId = userId;
    lastClientId = clientId;
    lastReviewNote = reviewNote;
  }

  @override
  Future<void> reject(
    UserSession session, {
    required String deviceId,
    required String userId,
    required String reviewNote,
  }) async {
    rejectCalls += 1;
    lastUserId = userId;
    lastReviewNote = reviewNote;
  }
}

const _session = UserSession(
  userId: 'management-1',
  username: 'manager.one',
  displayName: 'Manager One',
  role: AppRole.management,
  rawRole: 'management',
  accessToken: 'token',
  permissions: <String>['account.manage'],
);

final _registration = ClientRegistrationReview(
  userId: 'user-1',
  username: 'maria.santos',
  email: 'maria@example.com',
  fullName: 'Maria Santos',
  claimedClientCode: 'C-001',
  claimedPhoneNumber: '09171234567',
  registrationStatus: 'pending',
  submittedAt: DateTime.utc(2026, 8, 29),
);

const _candidate = ClientLinkCandidate(
  id: 'client-1',
  clientCode: 'C-001',
  fullName: 'Maria Santos',
  phoneNumber: '09171234567',
  area: 'North',
);
