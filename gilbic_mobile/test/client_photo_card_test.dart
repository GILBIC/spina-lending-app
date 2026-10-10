import 'dart:async';
import 'dart:convert';
import 'dart:typed_data';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:gilbic_mobile/src/core/auth/app_role.dart';
import 'package:gilbic_mobile/src/core/auth/user_session.dart';
import 'package:gilbic_mobile/src/core/clients/client_photo_repository.dart';
import 'package:gilbic_mobile/src/core/media/image_recovery_controller.dart';
import 'package:gilbic_mobile/src/features/office/office_widgets.dart';
import 'package:gilbic_mobile/src/features/shared/client_photo_card.dart';
import 'package:gilbic_mobile/src/features/shared/image_recovery_scope.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';
import 'package:image_picker/image_picker.dart';
import 'support/memory_private_image_store.dart';
import 'client_photo_repository_test.dart'
    show photoClient, photoId, photoStaff, photoPng, photoEnvelope;

Widget host(
  ClientPhotoRepository repository, {
  String clientId = photoClient,
  UserSession session = photoStaff,
  bool allowUpload = true,
  OfficePhotoPicker? picker,
}) => MaterialApp(
  home: Scaffold(
    body: SingleChildScrollView(
      child: Column(
        children: [
          ClientPhotoCard(
            session: session,
            deviceId: 'device',
            clientId: clientId,
            clientName: clientId == photoClient ? 'Maria Santos' : 'Juan Reyes',
            repository: repository,
            allowUpload: allowUpload,
            picker: picker ?? (_) async => OfficePhoto(photoPng, 'image/png'),
          ),
          TextButton(onPressed: () {}, child: const Text('Continue loan')),
        ],
      ),
    ),
  ),
);
http.Response metadata({
  String client = photoClient,
  bool missing = true,
  bool canUpload = true,
}) => http.Response(
  jsonEncode(
    photoEnvelope(client: client, missing: missing, canUpload: canUpload),
  ),
  200,
);
http.Response content() => http.Response.bytes(
  Uint8List.fromList(photoPng),
  200,
  headers: {'content-type': 'image/png'},
);

Future<void> settle(WidgetTester tester) async {
  // Native image decoding completes outside Flutter's fake clock. Advance both
  // queues until idle instead of racing decoding against one fixed delay.
  for (var attempt = 0; attempt < 100; attempt++) {
    await tester.pump(const Duration(milliseconds: 16));
    await tester.runAsync(
      () => Future<void>.delayed(const Duration(milliseconds: 10)),
    );
    if (!tester.binding.hasScheduledFrame) break;
  }
  await tester.pumpAndSettle();
}

void main() {
  testWidgets('client photo recovery never enters the global image cache', (
    tester,
  ) async {
    final recovery = ImageRecoveryController(
      enabled: true,
      images: MemoryPrivateImageStore(),
      store: _PhotoRecoveryStore(
        jsonEncode({
          'version': 1,
          'owner': 'staff-device',
          'purpose': 'client_photo',
          'target': photoClient,
          'label': 'Client photo for Maria Santos',
          'createdAt': DateTime.now().toUtc().toIso8601String(),
          'path': null,
        }),
      ),
      retrieveLostData: () async => LostDataResponse(
        type: RetrieveType.image,
        files: [
          XFile.fromData(
            Uint8List.fromList(photoPng),
            path: 'C:/recovery/client-photo.png',
            mimeType: 'image/png',
          ),
        ],
      ),
    );
    await recovery.initialize('staff-device');
    addTearDown(recovery.dispose);
    final cache = PaintingBinding.instance.imageCache;
    final baseline = cache.currentSize;
    final repository = ClientPhotoRepository(
      client: MockClient((_) async => metadata()),
    );
    await tester.pumpWidget(
      MaterialApp(
        home: ImageRecoveryScope(
          controller: recovery,
          child: Scaffold(
            body: ClientPhotoCard(
              session: photoStaff,
              deviceId: 'device',
              clientId: photoClient,
              clientName: 'Maria Santos',
              repository: repository,
              allowUpload: true,
            ),
          ),
        ),
      ),
    );
    await settle(tester);
    await tester.tap(find.text('Add photo'));
    await settle(tester);
    await tester.tap(find.text('Gallery'));
    await tester.pump();
    await tester.pump(const Duration(milliseconds: 300));
    await tester.runAsync(
      () => Future<void>.delayed(const Duration(milliseconds: 80)),
    );
    await tester.pump();
    expect(find.text('Recover photo?'), findsOneWidget);
    expect(cache.currentSize, baseline);
    expect(find.byType(Image), findsNothing);
    await tester.tap(find.text('Use photo'));
    await tester.pump();
    await settle(tester);
    expect(find.byKey(const Key('client-photo-preview')), findsOneWidget);
    expect(cache.currentSize, baseline);
    await tester.pumpWidget(const SizedBox());
    await settle(tester);
    expect(cache.currentSize, baseline);
    expect(recovery.recovered, isNull);
  });
  testWidgets(
    'missing photo keeps loan actions available and offers office upload',
    (tester) async {
      final repository = ClientPhotoRepository(
        client: MockClient((_) async => metadata()),
      );
      await tester.pumpWidget(host(repository));
      await settle(tester);
      expect(find.text('No client photo'), findsOneWidget);
      expect(find.text('Add photo'), findsOneWidget);
      expect(
        tester
            .widget<TextButton>(
              find.widgetWithText(TextButton, 'Continue loan'),
            )
            .onPressed,
        isNotNull,
      );
    },
  );

  testWidgets(
    'gallery and camera preview beside selected name before explicit save',
    (tester) async {
      final sent = <http.Request>[];
      final sources = <ImageSource>[];
      final repository = ClientPhotoRepository(
        client: MockClient((request) async {
          sent.add(request);
          return request.url.path.endsWith('/content')
              ? content()
              : metadata(missing: request.method != 'POST');
        }),
      );
      await tester.pumpWidget(
        host(
          repository,
          picker: (source) async {
            sources.add(source);
            return OfficePhoto(photoPng, 'image/png');
          },
        ),
      );
      await settle(tester);
      await tester.tap(find.text('Add photo'));
      await settle(tester);
      await tester.tap(find.text('Gallery'));
      await settle(tester);
      expect(find.byKey(const Key('client-photo-preview')), findsOneWidget);
      expect(find.text('Maria Santos'), findsOneWidget);
      expect(sent.where((r) => r.method == 'POST'), isEmpty);
      await tester.tap(find.text('Camera'));
      await settle(tester);
      expect(sources, [ImageSource.gallery, ImageSource.camera]);
      await tester.tap(find.text('Save photo'));
      await settle(tester);
      expect(sent.where((r) => r.method == 'POST'), hasLength(1));
      expect(find.text('Photo saved.'), findsOneWidget);
      expect(find.text('Change photo'), findsOneWidget);
    },
  );

  testWidgets(
    'uncertain upload retains original bytes and request identity for retry',
    (tester) async {
      final posts = <http.Request>[];
      final repository = ClientPhotoRepository(
        client: MockClient((request) async {
          if (request.method == 'POST') {
            posts.add(request);
            if (posts.length == 1) throw http.ClientException('response lost');
            return metadata(missing: false);
          }
          return request.url.path.endsWith('/content') ? content() : metadata();
        }),
      );
      await tester.pumpWidget(host(repository));
      await settle(tester);
      await tester.tap(find.text('Add photo'));
      await settle(tester);
      await tester.tap(find.text('Gallery'));
      await settle(tester);
      await tester.tap(find.text('Save photo'));
      await settle(tester);
      expect(find.text('Retry same upload'), findsOneWidget);
      expect(
        tester
            .widget<OutlinedButton>(
              find.widgetWithText(OutlinedButton, 'Gallery'),
            )
            .onPressed,
        isNull,
      );
      await tester.tap(find.text('Retry same upload'));
      await settle(tester);
      expect(posts, hasLength(2));
      expect(posts[0].bodyBytes, photoPng);
      expect(posts[1].bodyBytes, photoPng);
      expect(posts[0].url, posts[1].url);
      expect(posts[1].url.queryParameters['expected_version'], '0');
      expect(find.text('Photo saved.'), findsOneWidget);
    },
  );

  testWidgets(
    'conflict requires reloading current photo before another replacement',
    (tester) async {
      final repository = ClientPhotoRepository(
        client: MockClient(
          (request) async =>
              request.method == 'POST' ? http.Response('{}', 409) : metadata(),
        ),
      );
      await tester.pumpWidget(host(repository));
      await settle(tester);
      await tester.tap(find.text('Add photo'));
      await settle(tester);
      await tester.tap(find.text('Gallery'));
      await settle(tester);
      await tester.tap(find.text('Save photo'));
      await settle(tester);
      expect(find.text('Retry same upload'), findsNothing);
      expect(find.byKey(const Key('client-photo-preview')), findsNothing);
      expect(find.text('Add photo'), findsNothing);
      await tester.tap(find.text('Reload photo'));
      await settle(tester);
      expect(find.text('Add photo'), findsOneWidget);
    },
  );

  testWidgets('late private content cannot appear after client switch', (
    tester,
  ) async {
    final delayed = Completer<http.Response>();
    final repository = ClientPhotoRepository(
      client: MockClient((request) async {
        if (request.url.path.endsWith('/content')) return delayed.future;
        return metadata(
          client: request.url.path.contains(photoClient)
              ? photoClient
              : photoId,
          missing: !request.url.path.contains(photoClient),
        );
      }),
    );
    await tester.pumpWidget(host(repository));
    await tester.pump();
    await tester.pump();
    await tester.pumpWidget(host(repository, clientId: photoId));
    await settle(tester);
    delayed.complete(content());
    await settle(tester);
    expect(find.text('Juan Reyes'), findsOneWidget);
    expect(find.byType(RawImage), findsNothing);
    expect(find.text('No client photo'), findsOneWidget);
  });

  testWidgets('late picker cannot attach old selection to a new session', (
    tester,
  ) async {
    final picked = Completer<OfficePhoto?>();
    final repository = ClientPhotoRepository(
      client: MockClient((_) async => metadata()),
    );
    await tester.pumpWidget(host(repository, picker: (_) => picked.future));
    await settle(tester);
    await tester.tap(find.text('Add photo'));
    await settle(tester);
    await tester.tap(find.text('Gallery'));
    await tester.pump();
    const next = UserSession(
      userId: 'next',
      username: 'next',
      displayName: 'Next',
      role: AppRole.employee,
      rawRole: 'employee',
      accessToken: 'next-token',
      permissions: ['client_onboarding.requirement.review'],
    );
    await tester.pumpWidget(host(repository, session: next));
    await settle(tester);
    picked.complete(OfficePhoto(photoPng, 'image/png'));
    await settle(tester);
    expect(find.byKey(const Key('client-photo-preview')), findsNothing);
    expect(find.text('Save photo'), findsNothing);
  });

  testWidgets('collector reads photo without gaining upload controls', (
    tester,
  ) async {
    const collector = UserSession(
      userId: 'collector',
      username: 'collector',
      displayName: 'Collector',
      role: AppRole.collector,
      rawRole: 'collector',
      accessToken: 'collector-token',
    );
    final repository = ClientPhotoRepository(
      client: MockClient(
        (request) async => request.url.path.endsWith('/content')
            ? content()
            : metadata(missing: false),
      ),
    );
    await tester.pumpWidget(host(repository, session: collector));
    await settle(tester);
    expect(find.byType(RawImage), findsOneWidget);
    expect(find.text('Change photo'), findsNothing);
    expect(find.text('Add photo'), findsNothing);
    expect(find.text('Save photo'), findsNothing);
  });

  testWidgets('access denial clears prior photo and any upload controls', (
    tester,
  ) async {
    var denied = false;
    final repository = ClientPhotoRepository(
      client: MockClient(
        (request) async => denied
            ? http.Response('{}', 403)
            : request.url.path.endsWith('/content')
            ? content()
            : metadata(missing: false),
      ),
    );
    await tester.pumpWidget(host(repository));
    await settle(tester);
    expect(find.byType(RawImage), findsOneWidget);
    denied = true;
    await tester.tap(find.text('Reload photo'));
    await settle(tester);
    expect(find.byType(RawImage), findsNothing);
    expect(find.text('Change photo'), findsNothing);
    expect(find.text('Add photo'), findsNothing);
  });
}

class _PhotoRecoveryStore implements ImageRecoveryStore {
  _PhotoRecoveryStore(this.value);
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
