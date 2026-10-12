import 'dart:async';
import 'dart:typed_data';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:gilbic_mobile/src/core/auth/app_role.dart';
import 'package:gilbic_mobile/src/core/auth/user_session.dart';
import 'package:gilbic_mobile/src/core/device/device_identity.dart';
import 'package:gilbic_mobile/src/core/documents/client_document_repository.dart';
import 'package:gilbic_mobile/src/core/management/accounting_export_repository.dart';
import 'package:gilbic_mobile/src/core/network/spina_api.dart';
import 'package:gilbic_mobile/src/features/management/accounting_report_download_card.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';

const session = UserSession(
  userId: 'manager',
  username: 'manager',
  displayName: 'Management',
  role: AppRole.management,
  rawRole: 'management',
  accessToken: 'private-token',
  permissions: ['accounting.view'],
);

void main() {
  test('report ZIP request binds session, device and exact range', () async {
    final repository = AccountingExportRepository(
      client: MockClient((request) async {
        expect(
          request.url.path,
          '/api/mobile/v1/management/financial-accounting/export',
        );
        expect(request.url.queryParameters, {
          'start_date': '2026-01-01',
          'end_date': '2026-12-31',
          'include_reporting': 'true',
        });
        expect(request.headers['Authorization'], 'Bearer private-token');
        expect(request.headers['X-Device-Id'], 'device');
        return http.Response.bytes(
          [0x50, 0x4b, 3, 4],
          200,
          headers: {'content-type': 'application/zip'},
        );
      }),
    );
    final file = await repository.download(
      session,
      deviceId: 'device',
      startDate: '2026-01-01',
      endDate: '2026-12-31',
    );
    expect(file.filename, 'spina-accounting-2026-01-01-to-2026-12-31.zip');
  });
  test('invalid dates and HTML cannot become reporting files', () async {
    var calls = 0;
    final repository = AccountingExportRepository(
      client: MockClient((request) async {
        calls++;
        return http.Response(
          '<html>private error</html>',
          200,
          headers: {'content-type': 'text/html'},
        );
      }),
    );
    await expectLater(
      repository.download(
        session,
        deviceId: 'device',
        startDate: '2026-02-30',
        endDate: '2026-03-31',
      ),
      throwsA(isA<SpinaApiException>()),
    );
    expect(calls, 0);
    await expectLater(
      repository.download(
        session,
        deviceId: 'device',
        startDate: '2026-02-01',
        endDate: '2026-03-31',
      ),
      throwsA(isA<SpinaApiException>()),
    );
  });
  for (final code in [401, 403, 426]) {
    testWidgets('revoked download $code stays disabled and cannot save', (
      tester,
    ) async {
      var denied = 0, saved = 0;
      final repository = AccountingExportRepository(
        client: MockClient((_) async => http.Response('private detail', code)),
      );
      await tester.pumpWidget(
        MaterialApp(
          home: Scaffold(
            body: card(
              repository,
              onDenied: (_) {
                denied++;
              },
              save: (_) async {
                saved++;
                return true;
              },
            ),
          ),
        ),
      );
      await tester.tap(find.text('Reporting review download'));
      await tester.pumpAndSettle();
      await tester.tap(find.text('Download reporting package (ZIP)'));
      await tester.pumpAndSettle();
      expect(denied, 1);
      expect(saved, 0);
      expect(find.text('private detail'), findsNothing);
      expect(
        tester.widget<OutlinedButton>(find.byType(OutlinedButton)).onPressed,
        isNull,
      );
    });
  }
  testWidgets(
    'late private package is cleared without saving after scope changes',
    (tester) async {
      final pending = Completer<http.Response>();
      final repository = AccountingExportRepository(
        client: MockClient((_) => pending.future),
      );
      var saved = 0;
      final provider = device();
      Widget view(DateTime end) => MaterialApp(
        home: Scaffold(
          body: card(
            repository,
            provider: provider,
            end: end,
            onDenied: (_) {},
            save: (_) async {
              saved++;
              return true;
            },
          ),
        ),
      );
      await tester.pumpWidget(view(DateTime(2026, 1, 31)));
      await tester.tap(find.text('Reporting review download'));
      await tester.pumpAndSettle();
      await tester.tap(find.text('Download reporting package (ZIP)'));
      await tester.pump();
      await tester.pumpWidget(view(DateTime(2026, 2, 28)));
      final bytes = Uint8List.fromList([0x50, 0x4b, 3, 4]);
      pending.complete(
        http.Response.bytes(
          bytes,
          200,
          headers: {'content-type': 'application/zip'},
        ),
      );
      await tester.pumpAndSettle();
      expect(saved, 0);
      expect(find.text('Reporting package saved.'), findsNothing);
    },
  );
}

DeviceIdentityProvider device() => DeviceIdentityProvider(
  store: MemoryDeviceIdentityStore()..value = 'device',
  platformResolver: () => 'android',
  appVersionResolver: () async => '1.0.0',
);
Widget card(
  AccountingExportRepository repository, {
  DeviceIdentityProvider? provider,
  DateTime? end,
  required void Function(SpinaApiException) onDenied,
  required Future<bool> Function(ClientDocumentFile) save,
}) => AccountingReportDownloadCard(
  session: session,
  deviceIdentityProvider: provider ?? device(),
  startDate: DateTime(2026, 1, 1),
  endDate: end ?? DateTime(2026, 1, 31),
  onAccessDenied: onDenied,
  repository: repository,
  saver: save,
);
