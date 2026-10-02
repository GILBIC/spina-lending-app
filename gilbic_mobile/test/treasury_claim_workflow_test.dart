import 'dart:convert';
import 'dart:io';
import 'dart:typed_data';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:gilbic_mobile/src/core/media/image_recovery_controller.dart';
import 'package:gilbic_mobile/src/core/media/private_image_store.dart';
import 'package:gilbic_mobile/src/core/treasury/treasury_repository.dart';
import 'package:gilbic_mobile/src/features/shared/image_recovery_scope.dart';
import 'package:gilbic_mobile/src/features/treasury/treasury_claim_page.dart';
import 'package:http/testing.dart';
import 'package:http/http.dart' as http;
import 'package:image_picker/image_picker.dart';
import 'support/android_role_fixture.dart';
import 'support/treasury_fixture.dart';

class ClaimRecoveryStore implements ImageRecoveryStore {
  String? value;
  @override
  Future<String?> read() async => value;
  @override
  Future<void> write(String next) async {
    value = next;
  }

  @override
  Future<void> delete() async {
    value = null;
  }
}

class ClaimMemoryFiles extends PrivateImageStore {
  final files = <String, XFile>{};
  @override
  Future<XFile> retain(XFile source) async {
    final held = XFile.fromData(
      await source.readAsBytes(),
      path: '${Directory.systemTemp.path}/synthetic-private/${source.name}',
      name: source.name,
      mimeType: source.mimeType,
    );
    files[held.path] = held;
    return held;
  }

  @override
  Future<T> use<T>(XFile file, Future<T> Function(XFile) read) =>
      read(files[file.path] ?? file);
  @override
  Future<bool> owns(XFile file) async => files.containsKey(file.path);
  @override
  Future<void> cleanup({String? keepPath}) async {
    files.removeWhere((key, _) => key != keepPath);
  }
}

class MutableProofFile extends XFile {
  MutableProofFile(this.bytes)
    : super(
        '${Directory.systemTemp.path}/synthetic.pdf',
        mimeType: 'application/pdf',
      );
  Uint8List bytes;
  @override
  Future<Uint8List> readAsBytes() async => Uint8List.fromList(bytes);
  @override
  Future<int> length() async => bytes.length;
}

final proofBytes = base64Decode(
  'iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUBAScY42YAAAAASUVORK5CYII=',
);
List<Map<String, dynamic>> claimBorrowers() => [
  {
    'client_id': user,
    'name': 'Synthetic own borrower',
    'allowed_account_ids': [account],
    'loans': [
      {
        'loan_id': ledger,
        'loan_number': 'Synthetic own loan',
        'loan_type': 'Regular',
        'expected_version': 0,
      },
    ],
  },
];

void main() {
  testWidgets(
    'denied claim form cannot choose a file or start camera recovery',
    (tester) async {
      var denied = false, picks = 0;
      final repo = SpinaTreasuryRepository(
        session: session(),
        deviceId: 'external',
        journal: MemoryTreasuryJournal(),
        images: ClaimMemoryFiles(),
        client: MockClient(
          (r) async => denied
              ? http.Response('{}', 403)
              : jsonResponse(workspace(private: false)),
        ),
      );
      await repo.loadWorkspace();
      final scopedAccount = repo.workspace!.accounts.single;
      denied = true;
      await expectLater(
        repo.loadWorkspace(),
        throwsA(isA<TreasuryAccessChanged>()),
      );
      await pumpAndroidRoleFixture(
        tester,
        home: TreasuryClaimPage(
          repository: repo,
          account: scopedAccount,
          borrowerChoices: claimBorrowers(),
          pickFile: () async {
            picks++;
            return null;
          },
          pickCamera: () async {
            picks++;
            return null;
          },
        ),
        size: const Size(360, 900),
        textScaler: TextScaler.linear(1),
      );
      await tester.pumpAndSettle();
      await tester.scrollUntilVisible(
        find.text('Take proof photo'),
        200,
        scrollable: find.byType(Scrollable).first,
      );
      await tester.ensureVisible(find.text('Take proof photo'));
      await tester.pumpAndSettle();
      expect(
        tester
            .widget<OutlinedButton>(
              find.widgetWithText(OutlinedButton, 'Take proof photo'),
            )
            .onPressed,
        isNull,
      );
      expect(
        tester
            .widget<OutlinedButton>(
              find.widgetWithText(OutlinedButton, 'Choose PDF or image'),
            )
            .onPressed,
        isNull,
      );
      expect(picks, 0);
    },
  );
  for (final matching in [true, false]) {
    testWidgets(
      'camera recovery is ${matching ? 'the same' : 'a different'} exact account/borrower claim; never uploads automatically',
      (tester) async {
        var posts = 0, cameraCalls = 0;
        final images = ClaimMemoryFiles();
        final store = ClaimRecoveryStore()
          ..value = jsonEncode({
            'version': 1,
            'owner': 'synthetic-owner',
            'purpose': 'treasury-claim',
            'target': '$account:${matching ? user : event}',
            'label': 'Payment proof',
            'createdAt': DateTime.now().toUtc().toIso8601String(),
          });
        final recovery = ImageRecoveryController(
          store: store,
          images: images,
          retrieveLostData: () async => LostDataResponse(
            files: [
              XFile.fromData(
                proofBytes,
                path: '/synthetic-camera.png',
                name: 'synthetic.png',
                mimeType: 'image/png',
              ),
            ],
            type: RetrieveType.image,
          ),
          enabled: true,
        );
        await recovery.initialize('synthetic-owner');
        expect(recovery.recovered, isNotNull);
        final expectedName = recovery.recovered!.file.name;
        final repo = SpinaTreasuryRepository(
          session: session(),
          deviceId: 'external',
          journal: MemoryTreasuryJournal(),
          images: images,
          client: MockClient((r) async {
            if (r.method == 'POST') posts++;
            return jsonResponse(workspace(private: false));
          }),
        );
        await repo.loadWorkspace();
        await pumpAndroidRoleFixture(
          tester,
          home: ImageRecoveryScope(
            controller: recovery,
            child: TreasuryClaimPage(
              repository: repo,
              account: repo.workspace!.accounts.single,
              borrowerChoices: claimBorrowers(),
              pickCamera: () async {
                cameraCalls++;
                return null;
              },
            ),
          ),
          size: const Size(320, 900),
          textScaler: TextScaler.linear(2),
        );
        await tester.pumpAndSettle();
        await tester.scrollUntilVisible(
          find.text('Take proof photo'),
          200,
          scrollable: find.byType(Scrollable).first,
        );
        await tester.ensureVisible(find.text('Take proof photo'));
        await tester.pumpAndSettle();
        await tester.tap(find.text('Take proof photo'));
        await tester.pumpAndSettle();
        expect(posts, 0);
        expect(cameraCalls, 0);
        if (matching) {
          expect(find.text('Recover photo?'), findsOneWidget);
          await tester.tap(find.text('Use photo'));
          await tester.pumpAndSettle();
          await tester.scrollUntilVisible(
            find.textContaining('Selected private file:'),
            200,
            scrollable: find.byType(Scrollable).first,
          );
          expect(find.textContaining(expectedName), findsOneWidget);
          expect(recovery.recovered, isNull);
          await tester.scrollUntilVisible(
            find.byType(Image),
            100,
            scrollable: find.byType(Scrollable).first,
          );
          expect(find.byType(Image), findsOneWidget);
        } else {
          expect(
            find.text('A different form has a recovered photo'),
            findsOneWidget,
          );
          expect(find.text('Use photo'), findsNothing);
          await tester.tap(find.text('Keep for later'));
          await tester.pumpAndSettle();
          expect(recovery.recovered, isNotNull);
          expect(find.textContaining('Selected private file:'), findsNothing);
        }
        expect(posts, 0);
        expect(tester.takeException(), isNull);
        await tester.pumpWidget(const SizedBox.shrink());
        recovery.dispose();
        repo.dispose();
      },
    );
  }
  testWidgets(
    'own PDF file remains an unsent draft until explicit reviewed confirmation',
    (tester) async {
      var posts = 0;
      Map<String, dynamic>? sent;
      final reviewedBytes = Uint8List.fromList(
        utf8.encode('%PDF-1.4\nSynthetic reviewed fixture'),
      );
      final picked = MutableProofFile(reviewedBytes);
      Uint8List? uploadedBytes;
      final images = ClaimMemoryFiles();
      final w = workspace(private: false)
        ..['borrower_choices'] = claimBorrowers();
      final repo = SpinaTreasuryRepository(
        session: session(),
        deviceId: 'external',
        journal: MemoryTreasuryJournal(),
        images: images,
        client: MockClient((r) async {
          if (r.method == 'GET') return jsonResponse(w);
          posts++;
          uploadedBytes = r.bodyBytes;
          final m =
              jsonDecode(
                    utf8.decode(
                      base64Decode(r.headers['X-Treasury-Metadata']!),
                    ),
                  )
                  as Map<String, dynamic>;
          sent = m;
          return jsonResponse({
            'contract_version': 1,
            'request_id': m['request_id'],
            'action': 'claim_submit',
            'status': 'saved',
            'target_id': event,
            'version': 1,
            'result': {
              'actor_user_id': user,
              'device_id': device,
              'account_id': account,
              'ledger_context_id': ledger,
              'claim': {
                'id': event,
                'version': 1,
                'account_id': account,
                'client_id': user,
                'current_version': {
                  'account_version': 1,
                  'amount': m['amount'],
                  'reference': m['reference'],
                  'loan_ids': m['loan_ids'],
                  'sha256': null,
                  'byte_count': r.bodyBytes.length,
                  'media_type': 'application/pdf',
                },
              },
            },
          });
        }),
      );
      await repo.loadWorkspace();
      await pumpAndroidRoleFixture(
        tester,
        home: TreasuryClaimPage(
          repository: repo,
          account: repo.workspace!.accounts.single,
          borrowerChoices: claimBorrowers(),
          pickFile: () async => picked,
        ),
        size: const Size(360, 900),
        textScaler: TextScaler.linear(1),
      );
      await tester.pumpAndSettle();
      await tester.tap(find.text('Synthetic own loan'));
      await tester.enterText(
        find.widgetWithText(TextField, 'Amount (PHP)'),
        '90071992547409.91',
      );
      await tester.enterText(
        find.widgetWithText(TextField, 'Transaction reference'),
        'Synthetic provider reference',
      );
      await tester.enterText(
        find.widgetWithText(TextField, 'Actual sent time with timezone'),
        '2026-10-02T00:00:00Z',
      );
      await tester.scrollUntilVisible(
        find.text('Choose PDF or image'),
        200,
        scrollable: find.byType(Scrollable).first,
      );
      await tester.ensureVisible(find.text('Choose PDF or image'));
      await tester.tap(find.text('Choose PDF or image'));
      await tester.pumpAndSettle();
      expect(posts, 0);
      await tester.scrollUntilVisible(
        find.text(
          'I checked the amount, reference, borrower, loans and selected proof.',
        ),
        200,
        scrollable: find.byType(Scrollable).first,
      );
      await tester.tap(
        find.text(
          'I checked the amount, reference, borrower, loans and selected proof.',
        ),
      );
      await tester.pump();
      await tester.ensureVisible(find.text('Review submission'));
      await tester.tap(find.text('Review submission'));
      await tester.pumpAndSettle();
      expect(posts, 0);
      expect(find.text('PHP 90071992547409.91'), findsOneWidget);
      picked.bytes = Uint8List.fromList(
        utf8.encode('%PDF-1.4\nDifferent mutable provider file'),
      );
      await tester.tap(find.text('Submit proof'));
      await tester.pumpAndSettle();
      expect(posts, 1);
      expect(
        uploadedBytes,
        reviewedBytes,
        reason:
            'The exact reviewed snapshot is submitted even if the picker file changes after confirmation opens.',
      );
      expect(sent!['client_id'], user);
      expect(sent!['loan_ids'], [ledger]);
      expect(sent!['amount'], '90071992547409.91');
      // A mismatched server digest cannot turn a submitted claim into success.
      expect(repo.pendingRequestId, isNotNull);
      expect(find.textContaining('unconfirmed'), findsWidgets);
      expect(
        find.textContaining('No official loan payment was recorded.'),
        findsNothing,
      );
    },
  );
}
