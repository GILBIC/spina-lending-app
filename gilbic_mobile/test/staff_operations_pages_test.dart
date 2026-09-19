import 'dart:convert';

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:gilbic_mobile/src/core/areas/area_repository.dart';
import 'package:gilbic_mobile/src/core/auth/app_role.dart';
import 'package:gilbic_mobile/src/core/auth/user_session.dart';
import 'package:gilbic_mobile/src/core/device/device_identity.dart';
import 'package:gilbic_mobile/src/core/management/staff_operations_repository.dart';
import 'package:gilbic_mobile/src/features/account/managed_client_account_page.dart';
import 'package:gilbic_mobile/src/features/areas/area_management_page.dart';
import 'package:gilbic_mobile/src/features/management/management_past_due_reasons_page.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';

void main() {
  testWidgets('staff tools remain usable on a small phone with larger text', (
    tester,
  ) async {
    await tester.binding.setSurfaceSize(const Size(360, 640));
    addTearDown(() => tester.binding.setSurfaceSize(null));
    final pages = <Widget>[
      _areaPage(_areas((request) async => _ok(_tree()))),
      _accountPage(_staff((request) async => _ok(_candidates()))),
      ManagementPastDueReasonsPage(
        session: _session(),
        deviceIdentityProvider: _identity(),
        repository: _staff((request) async => _ok(_report())),
      ),
    ];
    for (final page in pages) {
      await tester.pumpWidget(
        MaterialApp(
          home: MediaQuery(
            data: const MediaQueryData(textScaler: TextScaler.linear(1.3)),
            child: page,
          ),
        ),
      );
      await tester.pumpAndSettle();
      if (page is AreaManagementPage) {
        await tester.tap(find.byKey(const Key('area-a')));
        await tester.pumpAndSettle();
      }
      await tester.drag(find.byType(ListView).first, const Offset(0, -500));
      await tester.pumpAndSettle();
      expect(
        tester.takeException(),
        isNull,
        reason: page.runtimeType.toString(),
      );
    }
  });

  for (final role in <AppRole>[
    AppRole.employee,
    AppRole.collector,
    AppRole.client,
  ]) {
    testWidgets(
      '${role.name} cannot open Management account creation or past-due data even with permission strings',
      (tester) async {
        var requests = 0;
        final repository = _staff((request) async {
          requests++;
          return _ok(_report());
        });
        final session = _session(role: role);
        await _pump(
          tester,
          ManagedClientAccountPage(
            session: session,
            deviceIdentityProvider: _identity(),
            repository: repository,
          ),
        );
        expect(find.byKey(const Key('managed-client-search')), findsNothing);
        await _pump(
          tester,
          ManagementPastDueReasonsPage(
            session: session,
            deviceIdentityProvider: _identity(),
            repository: repository,
          ),
        );
        expect(find.byKey(const Key('past-due-load')), findsNothing);
        expect(requests, 0);
      },
    );
  }

  testWidgets(
    'Management without relevant permissions cannot search either private surface',
    (tester) async {
      final session = _session(permissions: const []);
      await _pump(
        tester,
        ManagedClientAccountPage(
          session: session,
          deviceIdentityProvider: _identity(),
        ),
      );
      expect(find.byKey(const Key('managed-client-search')), findsNothing);
      await _pump(
        tester,
        ManagementPastDueReasonsPage(
          session: session,
          deviceIdentityProvider: _identity(),
        ),
      );
      expect(find.byKey(const Key('past-due-load')), findsNothing);
    },
  );

  testWidgets(
    'Collector direct area page cannot load private tree or enable a mutation',
    (tester) async {
      var requests = 0;
      await _pump(
        tester,
        _areaPage(
          _areas((request) async {
            requests++;
            return _ok(_tree());
          }),
          session: _session(role: AppRole.collector),
        ),
      );
      expect(requests, 0);
      expect(find.byKey(const Key('area-a')), findsNothing);
      expect(
        tester
            .widget<FilledButton>(find.byKey(const Key('areas-create')))
            .onPressed,
        isNull,
      );
    },
  );

  testWidgets(
    'Employee sees only permitted area management actions and never retirement',
    (tester) async {
      await _pump(
        tester,
        _areaPage(
          _areas((request) async => _ok(_tree())),
          session: _session(
            role: AppRole.employee,
            permissions: const ['area.manage', 'area.retire'],
          ),
        ),
      );
      await tester.tap(find.byKey(const Key('area-a')));
      await tester.pumpAndSettle();
      expect(
        tester
            .widget<FilledButton>(find.byKey(const Key('areas-create')))
            .onPressed,
        isNotNull,
      );
      expect(find.text('Move area'), findsOneWidget);
      expect(find.text('Assign collector'), findsNothing);
      expect(find.text('Retire'), findsNothing);
      expect(find.text('Search borrowers'), findsNothing);
    },
  );

  for (final status in <int>[401, 403, 426]) {
    testWidgets(
      'area refresh rejection $status removes selection and disables writes',
      (tester) async {
        var denied = false;
        await _pump(
          tester,
          _areaPage(
            _areas(
              (request) async =>
                  denied ? http.Response('Rejected', status) : _ok(_tree()),
            ),
          ),
        );
        await tester.tap(find.byKey(const Key('area-a')));
        await tester.pumpAndSettle();
        expect(find.text('Move area'), findsOneWidget);
        denied = true;
        await tester.tap(find.byKey(const Key('areas-refresh')));
        await tester.pumpAndSettle();
        expect(find.byKey(const Key('area-a')), findsNothing);
        expect(find.text('Move area'), findsNothing);
        expect(
          tester
              .widget<FilledButton>(find.byKey(const Key('areas-create')))
              .onPressed,
          isNull,
        );
      },
    );
  }

  testWidgets(
    'area move displays authoritative impact before posting only the selected parent',
    (tester) async {
      final writes = <http.Request>[];
      final previews = <http.Request>[];
      await _pump(
        tester,
        _areaPage(
          _areas((request) async {
            if (request.url.path.endsWith('/move-preview')) {
              previews.add(request);
              return _ok(_move());
            }
            if (request.method == 'POST') {
              writes.add(request);
              return _ok(_move());
            }
            return _ok(_tree());
          }),
        ),
      );
      await tester.tap(find.byKey(const Key('area-a')));
      await tester.pumpAndSettle();
      await _tapText(tester, 'Move area');
      await tester.tap(find.widgetWithText(SimpleDialogOption, 'Binangonan'));
      await _pumpDialog(tester);
      expect(previews, hasLength(1));
      expect(previews.single.method, 'GET');
      expect(previews.single.url.path, '/api/v1/areas/a/move-preview');
      expect(previews.single.url.queryParameters, {'new_parent_area_id': 'b'});
      expect(find.textContaining('Affected clients: 3'), findsOneWidget);
      expect(
        find.textContaining('Collector after: Bea Collector'),
        findsOneWidget,
      );
      expect(writes, isEmpty);
      await _confirm(tester);
      expect(writes, hasLength(1));
      expect(writes.single.url.path, '/api/v1/areas/a/move');
      expect(jsonDecode(writes.single.body), {'new_parent_area_id': 'b'});
      expect(
        find.text('Area records refreshed from the server.'),
        findsOneWidget,
      );
    },
  );

  testWidgets(
    'borrower transfer confirms server date then sends the selected client and target only',
    (tester) async {
      final writes = <http.Request>[];
      await _pump(
        tester,
        _areaPage(
          _areas((request) async {
            if (request.url.path == '/api/v1/areas/clients') {
              expect(request.url.queryParameters['q'], 'Maria');
              return _ok({
                'clients': [
                  {
                    'client_id': 'borrower-1',
                    'client_code': 'C-1',
                    'full_name': 'Maria Santos',
                    'area_id': 'a',
                    'area_path': 'Cardona',
                    'effective_collector': null,
                  },
                ],
              });
            }
            if (request.url.path.endsWith('area-transfer-preview')) {
              expect(
                request.url.path,
                '/api/v1/clients/borrower-1/area-transfer-preview',
              );
              expect(request.url.queryParameters, {'target_area_id': 'b'});
              return _ok(_transfer());
            }
            if (request.method == 'POST') {
              writes.add(request);
              return _ok(_transfer());
            }
            return _ok(_tree());
          }),
        ),
      );
      await tester.enterText(find.byType(TextField), 'Maria');
      await _tapText(tester, 'Search borrowers');
      await _tapText(tester, 'Transfer');
      await tester.tap(find.widgetWithText(SimpleDialogOption, 'Binangonan'));
      await _pumpDialog(tester);
      expect(find.textContaining('Effective: 2026-09-20'), findsOneWidget);
      expect(
        find.textContaining('Timing: next collection day'),
        findsOneWidget,
      );
      expect(writes, isEmpty);
      await _confirm(tester);
      expect(writes, hasLength(1));
      expect(
        writes.single.url.path,
        '/api/v1/clients/borrower-1/area-transfer',
      );
      expect(jsonDecode(writes.single.body), {'target_area_id': 'b'});
      expect(
        find.text('Transfer recorded. Effective: 2026-09-20.'),
        findsOneWidget,
      );
    },
  );

  testWidgets(
    'area name dialog saves a trimmed name without a controller lifetime error',
    (tester) async {
      final writes = <http.Request>[];
      await _pump(
        tester,
        _areaPage(
          _areas((request) async {
            if (request.method == 'POST') writes.add(request);
            return _ok(
              request.method == 'POST' ? {'area_id': 'new-area'} : _tree(),
            );
          }),
        ),
      );
      await tester.tap(find.byKey(const Key('areas-create')));
      await _pumpDialog(tester);
      await tester.enterText(
        find.descendant(
          of: find.byType(AlertDialog),
          matching: find.byType(TextField),
        ),
        '  Taytay  ',
      );
      await tester.tap(find.widgetWithText(FilledButton, 'Save'));
      await tester.pumpAndSettle();
      expect(tester.takeException(), isNull);
      expect(writes, hasLength(1));
      expect(jsonDecode(writes.single.body), {
        'name': 'Taytay',
        'parent_area_id': null,
      });
    },
  );

  testWidgets(
    'lost create response requires fresh search and explicit acknowledgment; eventual credentials stay masked',
    (tester) async {
      var creates = 0;
      final repository = _staff((request) async {
        if (request.method == 'GET') return _ok(_candidates());
        creates++;
        expect(request.url.path, '/api/v1/management/client-accounts');
        expect(jsonDecode(request.body), {
          'client_id': 'borrower-1',
          'email': 'maria@example.com',
        });
        if (creates == 1) throw http.ClientException('Response lost');
        return _ok(_credentials());
      });
      await _pump(tester, _accountPage(repository));
      await _searchCandidates(tester);
      await _createAccount(tester);
      expect(creates, 1);
      expect(
        find.textContaining('Account creation was not confirmed.'),
        findsOneWidget,
      );
      expect(
        tester
            .widget<TextButton>(
              find.byKey(const Key('managed-client-reconciled')),
            )
            .onPressed,
        isNull,
      );
      await _searchCandidates(tester);
      expect(creates, 1);
      expect(
        tester
            .widget<ListTile>(
              find.byKey(const Key('managed-candidate-borrower-1')),
            )
            .onTap,
        isNull,
      );
      await tester.tap(find.byKey(const Key('managed-client-reconciled')));
      await tester.pumpAndSettle();
      await _confirm(tester);
      await _createAccount(tester);
      expect(creates, 2);
      expect(find.text('Client account created'), findsOneWidget);
      expect(find.text('one-time-secret'), findsNothing);
      await _tapText(tester, 'Reveal password');
      expect(find.text('one-time-secret'), findsOneWidget);
      await _tapText(tester, 'Hide password');
      expect(find.text('one-time-secret'), findsNothing);
    },
  );

  testWidgets(
    'denied account creation clears selected borrower and prevents cached repeat',
    (tester) async {
      var creates = 0;
      await _pump(
        tester,
        _accountPage(
          _staff((request) async {
            if (request.method == 'GET') return _ok(_candidates());
            creates++;
            return http.Response('Denied', 403);
          }),
        ),
      );
      await _searchCandidates(tester);
      await _createAccount(tester);
      expect(creates, 1);
      expect(find.text('Maria Santos'), findsNothing);
      expect(find.byKey(const Key('managed-client-create')), findsNothing);
      expect(
        find.byKey(const Key('managed-candidate-borrower-1')),
        findsNothing,
      );
    },
  );

  for (final status in <int>[403, 503]) {
    testWidgets(
      'past-due report preserves exact cents and clears figures after refresh failure $status',
      (tester) async {
        var requests = 0;
        await _pump(
          tester,
          ManagementPastDueReasonsPage(
            session: _session(),
            deviceIdentityProvider: _identity(),
            repository: _staff((request) async {
              requests++;
              expect(request.method, 'GET');
              expect(request.url.path, '/api/v1/management/past-due/reasons');
              return requests == 1
                  ? _ok(_report())
                  : http.Response('Unavailable', status);
            }),
          ),
        );
        expect(find.text('Past due: ₱90071992547409.93'), findsOneWidget);
        expect(find.text('Remaining: ₱0.01'), findsOneWidget);
        expect(find.text('Maria Santos'), findsOneWidget);
        await tester.tap(find.byKey(const Key('past-due-load')));
        await tester.pumpAndSettle();
        expect(requests, 2);
        expect(find.textContaining('90071992547409.93'), findsNothing);
        expect(find.text('Maria Santos'), findsNothing);
      },
    );
  }
}

UserSession _session({
  AppRole role = AppRole.management,
  List<String> permissions = const [
    'area.manage',
    'area.collector.assign',
    'area.client.assign',
    'area.retire',
    'management.dashboard.view',
    'account.manage',
  ],
}) => UserSession(
  userId: 'staff',
  username: 'staff',
  displayName: 'Staff',
  role: role,
  rawRole: role.name,
  accessToken: 'token',
  permissions: permissions,
);
DeviceIdentityProvider _identity() => DeviceIdentityProvider(
  store: MemoryDeviceIdentityStore()..value = 'test-device',
  platformResolver: () => 'android',
  appVersionResolver: () async => '1',
);
AreaRepository _areas(Future<http.Response> Function(http.Request) handler) =>
    AreaRepository(
      deviceIdentityProvider: _identity(),
      client: MockClient(handler),
    );
StaffOperationsRepository _staff(
  Future<http.Response> Function(http.Request) handler,
) => StaffOperationsRepository(
  deviceIdentityProvider: _identity(),
  client: MockClient(handler),
);
Widget _areaPage(AreaRepository repository, {UserSession? session}) =>
    AreaManagementPage(
      session: session ?? _session(),
      deviceIdentityProvider: _identity(),
      repository: repository,
    );
Widget _accountPage(StaffOperationsRepository repository) =>
    ManagedClientAccountPage(
      session: _session(),
      deviceIdentityProvider: _identity(),
      repository: repository,
    );

Future<void> _pump(WidgetTester tester, Widget page) async {
  await tester.binding.setSurfaceSize(const Size(650, 1400));
  addTearDown(() => tester.binding.setSurfaceSize(null));
  await tester.pumpWidget(MaterialApp(home: page));
  await tester.pumpAndSettle();
}

Future<void> _tapText(WidgetTester tester, String text) async {
  final target = find.text(text);
  await tester.ensureVisible(target);
  await tester.tap(target);
  await _pumpDialog(tester);
}

// A pending confirmation intentionally keeps the page's progress indicator
// animating, so pump just the dialog transition instead of waiting for idle.
Future<void> _pumpDialog(WidgetTester tester) async {
  await tester.pump();
  await tester.pump(const Duration(milliseconds: 300));
}

Future<void> _confirm(WidgetTester tester) async {
  await tester.tap(find.widgetWithText(FilledButton, 'Confirm'));
  await tester.pumpAndSettle();
}

Future<void> _searchCandidates(WidgetTester tester) async {
  await tester.enterText(
    find.byKey(const Key('managed-client-search')),
    'Maria',
  );
  await tester.tap(find.byKey(const Key('managed-client-search-submit')));
  await tester.pumpAndSettle();
}

Future<void> _createAccount(WidgetTester tester) async {
  await tester.tap(find.byKey(const Key('managed-candidate-borrower-1')));
  await tester.pumpAndSettle();
  await tester.enterText(
    find.byKey(const Key('managed-client-email')),
    ' Maria@Example.COM ',
  );
  await tester.tap(find.byKey(const Key('managed-client-create')));
  await _pumpDialog(tester);
  await _confirm(tester);
}

http.Response _ok(Object data) => http.Response(
  jsonEncode({'success': true, 'data': data}),
  200,
  headers: {'content-type': 'application/json; charset=utf-8'},
);
Map<String, Object?> _tree() => {
  'areas': [_node('a', 'Cardona'), _node('b', 'Binangonan')],
};
Map<String, Object?> _node(String id, String name) => {
  'area_id': id,
  'parent_area_id': null,
  'name': name,
  'full_path': name,
  'is_active': true,
  'is_legacy_unmapped': false,
  'depth': 0,
  'sort_order': id == 'a' ? 0 : 1,
  'subtree_client_count': 3,
  'explicit_collector': null,
  'effective_collector': {'full_name': 'Ana Collector'},
};
Map<String, Object?> _move() => {
  'area_id': 'a',
  'old_parent_area_id': null,
  'new_parent_area_id': 'b',
  'old_path': 'Cardona',
  'new_path': 'Binangonan › Cardona',
  'affected_node_count': 1,
  'clients_affected': 3,
  'descendant_areas_affected': 0,
  'effective_collector_before': {'full_name': 'Ana Collector'},
  'effective_collector_after': {'full_name': 'Bea Collector'},
  'stale_delegated_access_count': 0,
};
Map<String, Object?> _transfer() => {
  'client_id': 'borrower-1',
  'old_area_id': 'a',
  'old_area_path': 'Cardona',
  'new_area_id': 'b',
  'new_area_path': 'Binangonan',
  'old_effective_collector_user_id': 'collector-a',
  'new_effective_collector_user_id': 'collector-b',
  'effective_date': '2026-09-20',
  'timing': 'next_collection_day',
};
Map<String, Object?> _candidates() => {
  'clients': [
    {
      'id': 'borrower-1',
      'full_name': 'Maria Santos',
      'client_code': 'C-1',
      'area': 'Cardona',
    },
  ],
};
Map<String, Object?> _credentials() => {
  'account': {'username': 'maria.client'},
  'credentials': {'username': 'maria.client', 'password': 'one-time-secret'},
  'delivery': {'sent': true, 'detail': 'Credentials emailed.'},
};
Map<String, Object?> _report() => {
  'schema_available': true,
  'summary': {
    'event_count': 1,
    'total_past_due_amount': '90071992547409.93',
    'remaining_past_due_amount': '0.01',
  },
  'rows': [
    {
      'client_name': 'Maria Santos',
      'collector_name': 'Ana Collector',
      'area': 'Cardona',
      'reason_label': 'No cash',
      'event_kind_label': 'Unable to pay',
      'event_count': 1,
      'total_past_due_amount': '90071992547409.93',
      'remaining_past_due_amount': '0.01',
    },
  ],
};
