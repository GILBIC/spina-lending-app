import 'dart:async';
import 'dart:convert';
import 'dart:typed_data';

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:gilbic_mobile/src/core/auth/app_role.dart';
import 'package:gilbic_mobile/src/core/auth/user_session.dart';
import 'package:gilbic_mobile/src/core/config/api_config.dart';
import 'package:gilbic_mobile/src/core/device/device_identity.dart';
import 'package:gilbic_mobile/src/core/media/image_recovery_controller.dart';
import 'package:gilbic_mobile/src/features/shared/image_recovery_scope.dart';
import 'package:image_picker/image_picker.dart';

class _Store implements ImageRecoveryStore {
  String? value;
  @override
  Future<String?> read() async => value;
  @override
  Future<void> write(String value) async {
    this.value = value;
  }

  @override
  Future<void> delete() async {
    value = null;
  }
}

class _IdentityProvider extends DeviceIdentityProvider {
  _IdentityProvider(this.responses);
  final List<Future<DeviceIdentity>> responses;
  @override
  Future<DeviceIdentity> load() => responses.removeAt(0);
}

const _identity = DeviceIdentity(
  installationId: 'installation-42',
  platform: 'android',
  appVersion: 'test',
);
const _photoContext = ImagePickContext(
  purpose: 'proof',
  target: 'loan-42',
  label: 'Loan 42 payment proof',
);
final _photo = XFile('/test/new-photo.jpg');

UserSession _session({
  String userId = 'actor-a',
  List<String> permissions = const ['z.permission', 'a.permission'],
}) => UserSession(
  userId: userId,
  username: userId,
  displayName: userId,
  role: AppRole.management,
  rawRole: 'Management',
  accessToken: 'unused-test-token',
  roles: const ['management', 'collector'],
  permissions: permissions,
);

Widget _host({
  required ImageRecoveryController controller,
  required DeviceIdentityProvider identity,
  required UserSession? session,
  bool restored = true,
}) => MaterialApp(
  home: ImageRecoveryHost(
    controller: controller,
    session: session,
    sessionRestored: restored,
    deviceIdentityProvider: identity,
    child: const Scaffold(body: Text('Authorized content')),
  ),
);

String _pendingJournal() => jsonEncode({
  'version': 1,
  'owner': jsonEncode([
    ApiConfig.baseUrl,
    'installation-42',
    jsonEncode([
      'actor-a',
      'management',
      ['collector', 'management'],
      ['a.permission', 'z.permission'],
    ]),
  ]),
  'purpose': 'proof',
  'target': 'loan-42',
  'label': 'Loan 42 payment proof',
  'createdAt': DateTime.now().toUtc().toIso8601String(),
  'path': null,
});

void main() {
  testWidgets('already resumed host rechecks pending result after binding', (
    tester,
  ) async {
    tester.binding.handleAppLifecycleStateChanged(AppLifecycleState.resumed);
    final store = _Store()..value = _pendingJournal();
    var reads = 0;
    final file = XFile.fromData(
      Uint8List.fromList([0xff, 0xd8, 0xff]),
      path: '/test/late.jpg',
    );
    final controller = ImageRecoveryController(
      store: store,
      enabled: true,
      retrieveLostData: () async => ++reads == 1
          ? LostDataResponse.empty()
          : LostDataResponse(type: RetrieveType.image, files: [file]),
    );
    final identity = _IdentityProvider([Future.value(_identity)]);
    await tester.pumpWidget(
      _host(controller: controller, identity: identity, session: _session()),
    );
    await tester.pumpAndSettle();
    expect(controller.recoveredFor(_photoContext)?.path, '/test/late.jpg');
    expect(controller.pending, isNull);
    expect(reads, 2);
  });

  testWidgets(
    'resume rechecks pending photo and shows interrupted selection while empty',
    (tester) async {
      tester.binding.handleAppLifecycleStateChanged(AppLifecycleState.inactive);
      final store = _Store()..value = _pendingJournal();
      var response = LostDataResponse.empty();
      final controller = ImageRecoveryController(
        store: store,
        enabled: true,
        retrieveLostData: () async => response,
      );
      final identity = _IdentityProvider([Future.value(_identity)]);
      await tester.pumpWidget(
        _host(controller: controller, identity: identity, session: _session()),
      );
      await tester.pumpAndSettle();
      expect(
        find.textContaining('Photo selection was interrupted.'),
        findsOneWidget,
      );
      final file = XFile.fromData(
        Uint8List.fromList([0xff, 0xd8, 0xff]),
        path: '/test/late.jpg',
      );
      response = LostDataResponse(type: RetrieveType.image, files: [file]);
      tester.binding.handleAppLifecycleStateChanged(AppLifecycleState.resumed);
      await tester.pumpAndSettle();
      expect(controller.recoveredFor(_photoContext)?.path, '/test/late.jpg');
      expect(find.textContaining('Photo recovered for'), findsOneWidget);
      expect(
        find.textContaining('Photo selection was interrupted.'),
        findsNothing,
      );
    },
  );

  testWidgets('session loading does not consume Android recovery data', (
    tester,
  ) async {
    final store = _Store()..value = 'unread journal';
    var retrievals = 0;
    final controller = ImageRecoveryController(
      store: store,
      enabled: true,
      retrieveLostData: () async {
        retrievals++;
        return LostDataResponse.empty();
      },
    );
    final identity = _IdentityProvider([Future.value(_identity)]);
    await tester.pumpWidget(
      _host(
        controller: controller,
        identity: identity,
        session: null,
        restored: false,
      ),
    );
    await tester.pump();
    expect(retrievals, 0);
    expect(store.value, 'unread journal');
    expect(controller.ready, isFalse);
    await tester.pumpWidget(
      _host(controller: controller, identity: identity, session: _session()),
    );
    await tester.pumpAndSettle();
    expect(retrievals, 1);
    expect(controller.ready, isTrue);
    expect(await controller.pick(_photoContext, () async => _photo), _photo);
  });

  testWidgets(
    'journal owner binds verified roles permissions endpoint and device',
    (tester) async {
      final store = _Store();
      final controller = ImageRecoveryController(
        store: store,
        enabled: true,
        retrieveLostData: () async => LostDataResponse.empty(),
      );
      final identity = _IdentityProvider([Future.value(_identity)]);
      await tester.pumpWidget(
        _host(controller: controller, identity: identity, session: _session()),
      );
      await tester.pumpAndSettle();
      String? atLaunch;
      await controller.pick(_photoContext, () async {
        atLaunch = store.value;
        return null;
      });
      final journal = jsonDecode(atLaunch!) as Map<String, dynamic>;
      final owner = jsonDecode(journal['owner'] as String) as List<dynamic>;
      expect(owner[0], ApiConfig.baseUrl);
      expect(owner[1], 'installation-42');
      expect(jsonDecode(owner[2] as String), [
        'actor-a',
        'management',
        ['collector', 'management'],
        ['a.permission', 'z.permission'],
      ]);
      expect(
        (journal['owner'] as String).contains('unused-test-token'),
        isFalse,
      );
    },
  );

  testWidgets(
    'scope change suspends old picker before device identity resolves',
    (tester) async {
      final store = _Store();
      final controller = ImageRecoveryController(
        store: store,
        enabled: true,
        retrieveLostData: () async => LostDataResponse.empty(),
      );
      final delayedIdentity = Completer<DeviceIdentity>();
      final identity = _IdentityProvider([
        Future.value(_identity),
        delayedIdentity.future,
      ]);
      await tester.pumpWidget(
        _host(controller: controller, identity: identity, session: _session()),
      );
      await tester.pumpAndSettle();
      final selected = Completer<XFile?>();
      final started = Completer<void>();
      final inFlight = controller.pick(_photoContext, () {
        started.complete();
        return selected.future;
      });
      await started.future;
      await tester.pumpWidget(
        _host(
          controller: controller,
          identity: identity,
          session: _session(permissions: const ['a.permission']),
        ),
      );
      expect(controller.ready, isFalse);
      expect(find.text('Authorized content'), findsNothing);
      selected.complete(_photo);
      expect(await inFlight, isNull);
      delayedIdentity.complete(_identity);
      await tester.pumpAndSettle();
      expect(controller.ready, isTrue);
      expect(await controller.pick(_photoContext, () async => _photo), _photo);
    },
  );

  testWidgets('stale device failure cannot clear a newer authorized owner', (
    tester,
  ) async {
    final store = _Store();
    final controller = ImageRecoveryController(
      store: store,
      enabled: true,
      retrieveLostData: () async => LostDataResponse.empty(),
    );
    final failedIdentity = Completer<DeviceIdentity>();
    final identity = _IdentityProvider([
      failedIdentity.future,
      Future.value(_identity),
    ]);
    await tester.pumpWidget(
      _host(controller: controller, identity: identity, session: _session()),
    );
    await tester.pumpWidget(
      _host(
        controller: controller,
        identity: identity,
        session: _session(userId: 'actor-b'),
      ),
    );
    await tester.pumpAndSettle();
    expect(controller.ready, isTrue);
    failedIdentity.completeError(StateError('Old device lookup failed'));
    await tester.pumpAndSettle();
    String? journalAtLaunch;
    expect(
      await controller.pick(_photoContext, () async {
        journalAtLaunch = store.value;
        return _photo;
      }),
      _photo,
    );
    final journal = jsonDecode(journalAtLaunch!) as Map<String, dynamic>;
    final owner = jsonDecode(journal['owner'] as String) as List<dynamic>;
    expect((jsonDecode(owner[2] as String) as List<dynamic>).first, 'actor-b');
  });
}
