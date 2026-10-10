import 'dart:async';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:gilbic_mobile/src/core/clients/client_photo_repository.dart';
import 'package:gilbic_mobile/src/features/office/office_widgets.dart';
import 'package:gilbic_mobile/src/features/shared/client_photo_card.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';
import 'client_photo_card_test.dart' show content, metadata, settle;
import 'client_photo_repository_test.dart'
    show photoClient, photoId, photoPng, photoStaff;

Future<void> openEditor(
  WidgetTester tester,
  ClientPhotoRepository repository, {
  OfficePhotoPicker? picker,
  ValueNotifier<String>? client,
}) async {
  Widget editor(String clientId) => ClientPhotoCard(
    session: photoStaff,
    clientId: clientId,
    clientName: clientId == photoClient ? 'Maria Santos' : 'Juan Reyes',
    deviceId: 'device',
    repository: repository,
    allowUpload: true,
    picker: picker ?? (_) async => OfficePhoto(photoPng, 'image/png'),
  );
  await tester.pumpWidget(
    MaterialApp(
      home: Builder(
        builder: (context) => Scaffold(
          body: TextButton(
            child: const Text('Open selected client photo'),
            onPressed: () => Navigator.of(context).push<void>(
              MaterialPageRoute(
                builder: (_) => Scaffold(
                  appBar: AppBar(title: const Text('Client photo editor')),
                  body: SingleChildScrollView(
                    child: client == null
                        ? editor(photoClient)
                        : ValueListenableBuilder<String>(
                            valueListenable: client,
                            builder: (_, id, _) => editor(id),
                          ),
                  ),
                ),
              ),
            ),
          ),
        ),
      ),
    ),
  );
  await tester.tap(find.text('Open selected client photo'));
  await settle(tester);
  await tester.tap(find.text('Add photo'));
  await settle(tester);
  await tester.tap(find.text('Gallery'));
}

void main() {
  testWidgets(
    'Back retains pending and uncertain upload until identical retry succeeds',
    (tester) async {
      final delayed = Completer<http.Response>();
      final posts = <http.Request>[];
      final repository = ClientPhotoRepository(
        client: MockClient((request) async {
          if (request.method == 'POST') {
            posts.add(request);
            return posts.length == 1
                ? delayed.future
                : metadata(missing: false);
          }
          return request.url.path.endsWith('/content') ? content() : metadata();
        }),
      );
      await openEditor(tester, repository);
      await settle(tester);
      await tester.tap(find.text('Save photo'));
      await tester.pump();
      await tester.pageBack();
      await tester.pump();
      await tester.pump(const Duration(milliseconds: 350));
      expect(find.text('Client photo editor'), findsOneWidget);
      expect(find.byKey(const Key('client-photo-preview')), findsOneWidget);
      delayed.completeError(http.ClientException('response lost'));
      await settle(tester);
      await tester.binding.handlePopRoute();
      await settle(tester);
      expect(find.text('Retry same upload'), findsOneWidget);
      await tester.tap(find.text('Retry same upload'));
      await settle(tester);
      expect(posts, hasLength(2));
      expect(posts[0].url, posts[1].url);
      expect(posts[1].url.queryParameters['expected_version'], '0');
      expect(posts[0].bodyBytes, photoPng);
      expect(posts[1].bodyBytes, photoPng);
      expect(find.text('Photo saved.'), findsOneWidget);
      await tester.pageBack();
      await settle(tester);
      expect(find.text('Open selected client photo'), findsOneWidget);
      expect(find.byType(ClientPhotoCard), findsNothing);
    },
  );

  testWidgets('Back asks before discarding a private preview', (tester) async {
    final repository = ClientPhotoRepository(
      client: MockClient((_) async => metadata()),
    );
    await openEditor(tester, repository);
    await settle(tester);
    await tester.pageBack();
    await settle(tester);
    expect(find.text('Discard photo change?'), findsOneWidget);
    await tester.tap(find.text('Keep editing'));
    await settle(tester);
    expect(find.byKey(const Key('client-photo-preview')), findsOneWidget);
    await tester.binding.handlePopRoute();
    await settle(tester);
    await tester.tap(find.text('Discard photo'));
    await settle(tester);
    expect(find.text('Open selected client photo'), findsOneWidget);
    expect(find.byType(ClientPhotoCard), findsNothing);
  });

  testWidgets(
    'Back cannot dispose an active picker but can leave after cancellation',
    (tester) async {
      final picked = Completer<OfficePhoto?>();
      final repository = ClientPhotoRepository(
        client: MockClient((_) async => metadata()),
      );
      await openEditor(tester, repository, picker: (_) => picked.future);
      await tester.pump();
      await tester.binding.handlePopRoute();
      await tester.pump(const Duration(milliseconds: 350));
      expect(find.text('Client photo editor'), findsOneWidget);
      picked.complete(null);
      await settle(tester);
      await tester.pageBack();
      await settle(tester);
      expect(find.byType(ClientPhotoCard), findsNothing);
    },
  );

  testWidgets('late discard confirmation cannot pop a replacement client', (
    tester,
  ) async {
    final client = ValueNotifier(photoClient);
    addTearDown(client.dispose);
    final repository = ClientPhotoRepository(
      client: MockClient(
        (request) async => metadata(
          client: request.url.path.contains(photoId) ? photoId : photoClient,
        ),
      ),
    );
    await openEditor(tester, repository, client: client);
    await settle(tester);
    await tester.pageBack();
    await settle(tester);
    expect(find.text('Discard photo change?'), findsOneWidget);
    client.value = photoId;
    await settle(tester);
    await tester.tap(find.text('Discard photo'));
    await settle(tester);
    expect(find.text('Juan Reyes'), findsOneWidget);
    expect(find.byKey(const Key('client-photo-preview')), findsNothing);
    await tester.pageBack();
    await settle(tester);
    expect(find.byType(ClientPhotoCard), findsNothing);
  });

  for (final status in [401, 403, 426]) {
    testWidgets(
      'upload denial $status clears private state and releases Back',
      (tester) async {
        final repository = ClientPhotoRepository(
          client: MockClient(
            (request) async => request.method == 'POST'
                ? http.Response('{}', status)
                : metadata(),
          ),
        );
        await openEditor(tester, repository);
        await settle(tester);
        await tester.tap(find.text('Save photo'));
        await settle(tester);
        expect(find.byKey(const Key('client-photo-preview')), findsNothing);
        await tester.pageBack();
        await settle(tester);
        expect(find.byType(ClientPhotoCard), findsNothing);
      },
    );
  }
}
