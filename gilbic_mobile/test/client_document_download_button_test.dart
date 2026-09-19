import 'dart:typed_data';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:gilbic_mobile/src/core/documents/client_document_repository.dart';
import 'package:gilbic_mobile/src/core/network/spina_api.dart';
import 'package:gilbic_mobile/src/features/client/client_document_download_button.dart';

void main() {
  testWidgets('protected error cannot reach platform saver', (tester) async {
    var saves = 0;
    await tester.pumpWidget(
      MaterialApp(
        home: Scaffold(
          body: ClientDocumentDownloadButton(
            label: 'Download',
            load: () async => throw const SpinaApiException(
              'Document unavailable',
              statusCode: 404,
            ),
            saver: (_) async {
              saves++;
              return true;
            },
          ),
        ),
      ),
    );
    await tester.tap(find.text('Download'));
    await tester.pumpAndSettle();
    expect(saves, 0);
    expect(find.text('Document unavailable'), findsOneWidget);
  });
  testWidgets('cancelled save does not claim success and can retry', (
    tester,
  ) async {
    var saves = 0;
    await tester.pumpWidget(
      MaterialApp(
        home: Scaffold(
          body: ClientDocumentDownloadButton(
            label: 'Download',
            load: () async => ClientDocumentFile(
              filename: 'record.pdf',
              bytes: Uint8List.fromList([1, 2, 3]),
            ),
            saver: (file) async {
              saves++;
              expect(file.filename, 'record.pdf');
              return false;
            },
          ),
        ),
      ),
    );
    await tester.tap(find.text('Download'));
    await tester.pumpAndSettle();
    expect(saves, 1);
    expect(find.text('Document saved.'), findsNothing);
    await tester.tap(find.text('Download'));
    await tester.pumpAndSettle();
    expect(saves, 2);
  });
}
