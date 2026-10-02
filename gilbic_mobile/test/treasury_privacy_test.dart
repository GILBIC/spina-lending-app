import 'dart:convert';
import 'dart:io';
import 'dart:typed_data';
import 'package:crypto/crypto.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:gilbic_mobile/src/core/media/private_image_store.dart';
import 'package:gilbic_mobile/src/core/treasury/treasury_repository.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';
import 'package:image_picker/image_picker.dart';
import 'support/treasury_fixture.dart';

void main() {
  final bytes = base64Decode(
    'iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUBAScY42YAAAAASUVORK5CYII=',
  );
  Map<String, dynamic> metadata() => {
    'request_id': requestId,
    'account_id': account,
    'account_version': 1,
    'client_id': user,
    'loan_ids': [ledger],
    'amount': '20.01',
    'reference': 'Synthetic receipt',
    'claimed_at': '2026-10-02T02:00:00Z',
    'sender_note': '',
  };
  late Directory temp;
  late PrivateImageStore images;
  setUp(() async {
    temp = await Directory.systemTemp.createTemp('synthetic-treasury-test-');
    images = PrivateImageStore(
      directory: () async => Directory('${temp.path}/private'),
    );
  });
  tearDown(() async {
    await temp.delete(recursive: true);
  });
  Map<String, dynamic> savedUpload({String amount = '20.01'}) => {
    'contract_version': 1,
    'request_id': requestId,
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
          'amount': amount,
          'reference': 'Synthetic receipt',
          'loan_ids': [ledger],
          'sha256': sha256.convert(bytes).toString(),
          'media_type': 'image/png',
          'byte_count': bytes.length,
        },
      },
    },
  };
  test(
    'Client and authorized Collector use same typed claim service, bytes and exact metadata',
    () async {
      final requests = <http.Request>[];
      final journal = MemoryTreasuryJournal();
      final repo = SpinaTreasuryRepository(
        session: session(),
        deviceId: 'external',
        journal: journal,
        images: images,
        client: MockClient((r) async {
          requests.add(r);
          return jsonResponse(
            r.method == 'GET' ? workspace(private: false) : savedUpload(),
          );
        }),
      );
      await repo.loadWorkspace();
      final result = await repo.uploadClaim(
        metadata(),
        XFile.fromData(bytes, name: 'synthetic.png', mimeType: 'image/png'),
      );
      expect(result.status, 'saved');
      final upload = requests.singleWhere((r) => r.method == 'POST');
      expect(upload.url.path, '/api/v1/treasury/claims');
      expect(upload.bodyBytes, bytes);
      expect(
        jsonDecode(
          utf8.decode(base64Decode(upload.headers['X-Treasury-Metadata']!)),
        ),
        metadata(),
      );
      expect(journal.value, isNull);
      expect(await Directory('${temp.path}/private').list().toList(), isEmpty);
    },
  );
  test(
    'upload wrong exact money never reports saved or clears retained attempt',
    () async {
      final journal = MemoryTreasuryJournal();
      final repo = SpinaTreasuryRepository(
        session: session(),
        deviceId: 'external',
        journal: journal,
        images: images,
        client: MockClient(
          (r) async => jsonResponse(
            r.method == 'GET' ? workspace() : savedUpload(amount: '20.02'),
          ),
        ),
      );
      await repo.loadWorkspace();
      await expectLater(
        repo.uploadClaim(
          metadata(),
          XFile.fromData(bytes, name: 'proof.png', mimeType: 'image/png'),
        ),
        throwsA(isA<TreasuryUncertain>()),
      );
      expect(repo.pendingRequestId, requestId);
      expect(journal.value, isNotNull);
    },
  );
  test('changed retained bytes cannot retry unchanged upload', () async {
    var posts = 0;
    final journal = MemoryTreasuryJournal();
    final repo = SpinaTreasuryRepository(
      session: session(),
      deviceId: 'external',
      journal: journal,
      images: images,
      client: MockClient((r) async {
        if (r.method == 'GET') return jsonResponse(workspace());
        posts++;
        throw http.ClientException('Synthetic disconnect');
      }),
    );
    await repo.loadWorkspace();
    await expectLater(
      repo.uploadClaim(
        metadata(),
        XFile.fromData(bytes, name: 'proof.png', mimeType: 'image/png'),
      ),
      throwsA(isA<TreasuryUncertain>()),
    );
    final held = jsonDecode(journal.value!) as Map;
    final path = (held['upload'] as Map)['path'] as String;
    await File(path).writeAsBytes([1, 2, 3]);
    await expectLater(repo.retrySame(), throwsA(isA<TreasuryUncertain>()));
    expect(posts, 1);
    expect(repo.pendingRequestId, requestId);
  });
  test(
    'denied recovery erases submitted private copies and outcome identity',
    () async {
      var deny = false;
      final journal = MemoryTreasuryJournal();
      final repo = SpinaTreasuryRepository(
        session: session(),
        deviceId: 'external',
        journal: journal,
        images: images,
        client: MockClient((r) async {
          if (deny) return http.Response('{"detail":"Denied"}', 403);
          if (r.method == 'GET') return jsonResponse(workspace());
          throw http.ClientException('Synthetic disconnect');
        }),
      );
      await repo.loadWorkspace();
      await expectLater(
        repo.uploadClaim(
          metadata(),
          XFile.fromData(bytes, name: 'proof.png', mimeType: 'image/png'),
        ),
        throwsA(isA<TreasuryUncertain>()),
      );
      deny = true;
      await expectLater(repo.recover(), throwsA(isA<TreasuryAccessChanged>()));
      expect(repo.workspace, isNull);
      expect(repo.pendingRequestId, isNull);
      expect(journal.value, isNull);
      expect(await Directory('${temp.path}/private').list().toList(), isEmpty);
    },
  );
  test(
    'private bytes must match the exact chosen media digest and byte count',
    () async {
      final repo = SpinaTreasuryRepository(
        session: session(),
        deviceId: 'external',
        journal: MemoryTreasuryJournal(),
        client: MockClient(
          (r) async => http.Response.bytes(
            bytes,
            200,
            headers: {'content-type': 'image/png'},
          ),
        ),
      );
      expect(
        await repo.content(
          claimId: event,
          version: 1,
          mediaType: 'image/png',
          digest: sha256.convert(bytes).toString(),
          byteCount: bytes.length,
        ),
        bytes,
      );
      await expectLater(
        repo.content(
          claimId: event,
          version: 2,
          mediaType: 'image/png',
          digest: '0' * 64,
        ),
        throwsFormatException,
      );
    },
  );
  test(
    'PDF PNG JPEG strict media validation rejects fake and oversized file',
    () async {
      expect(
        await treasuryMediaType(
          XFile.fromData(bytes, name: 'test.png', mimeType: 'image/png'),
        ),
        'image/png',
      );
      await expectLater(
        treasuryMediaType(
          XFile.fromData(
            Uint8List.fromList([1, 2, 3]),
            name: 'false.pdf',
            mimeType: 'application/pdf',
          ),
        ),
        throwsFormatException,
      );
      await expectLater(
        treasuryMediaType(
          XFile.fromData(bytes, name: 'wrong.pdf', mimeType: 'application/pdf'),
        ),
        throwsFormatException,
      );
    },
  );
  test(
    'submitted bytes must be app-owned; outside picker files are never replayed',
    () async {
      final original = File('${temp.path}/external.png');
      await original.writeAsBytes(bytes);
      expect(await images.owns(XFile(original.path)), isFalse);
      final retained = await images.retain(
        XFile(original.path, name: 'proof.png', mimeType: 'image/png'),
      );
      expect(await images.owns(retained), isTrue);
      await File(retained.path).delete();
      expect(await images.owns(retained), isFalse);
    },
  );
}
