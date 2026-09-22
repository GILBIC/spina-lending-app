import 'dart:async';
import 'dart:convert';
import 'dart:io';

import 'package:flutter/services.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:gilbic_mobile/src/core/media/image_recovery_controller.dart';
import 'package:image_picker/image_picker.dart';

const proof = ImagePickContext(
  purpose: 'client_payment_proof',
  target: 'loan-42',
  label: 'Loan 42 payment proof',
);
const anotherLoan = ImagePickContext(
  purpose: 'client_payment_proof',
  target: 'loan-99',
  label: 'Loan 99 payment proof',
);
const anotherPurpose = ImagePickContext(
  purpose: 'cash_handover',
  target: 'loan-42',
  label: 'Loan 42 cash handover',
);
final now = DateTime.utc(2026, 9, 22, 10);

class MemoryRecoveryStore implements ImageRecoveryStore {
  String? value;
  bool failWrites = false;
  bool failDeletes = false;
  Future<void> Function()? beforeDelete;

  @override
  Future<String?> read() async => value;

  @override
  Future<void> write(String value) async {
    if (failWrites) throw StateError('Test storage unavailable');
    this.value = value;
  }

  @override
  Future<void> delete() async {
    if (failDeletes) throw StateError('Test deletion unavailable');
    await beforeDelete?.call();
    value = null;
  }
}

String journal({
  String owner = 'client-a|scope-1|endpoint-1|device-1',
  String? path,
  DateTime? created,
}) => jsonEncode({
  'version': 1,
  'owner': owner,
  'purpose': 'client_payment_proof',
  'target': 'loan-42',
  'label': 'Loan 42 payment proof',
  'createdAt': (created ?? now).toIso8601String(),
  'path': path,
});

void main() {
  const owner = 'client-a|scope-1|endpoint-1|device-1';
  late Directory temp;
  late XFile photo;
  late MemoryRecoveryStore store;

  setUp(() async {
    temp = await Directory.systemTemp.createTemp('spina-picker-test-');
    final file = File('${temp.path}/selected.jpg');
    await file.writeAsBytes([0xff, 0xd8, 0xff, 1]);
    photo = XFile(file.path);
    store = MemoryRecoveryStore();
  });
  tearDown(() => temp.delete(recursive: true));

  ImageRecoveryController controller({
    Future<LostDataResponse> Function()? lost,
    bool enabled = true,
  }) => ImageRecoveryController(
    store: store,
    retrieveLostData: lost ?? () async => LostDataResponse.empty(),
    enabled: enabled,
    now: () => now,
  );

  test(
    'journals context before Android picker can leave the process',
    () async {
      final recovery = controller();
      await recovery.initialize(owner);
      String? durableAtLaunch;
      final selected = await recovery.pick(proof, () async {
        durableAtLaunch = store.value;
        return photo;
      });
      expect(jsonDecode(durableAtLaunch!), {
        'version': 1,
        'owner': owner,
        'purpose': 'client_payment_proof',
        'target': 'loan-42',
        'label': 'Loan 42 payment proof',
        'createdAt': '2026-09-22T10:00:00.000Z',
        'path': null,
      });
      expect(selected?.path, photo.path);
      expect(store.value, isNull);
      expect(recovery.busy, isFalse);
    },
  );

  test(
    'restores only the matching purpose and target after process death',
    () async {
      store.value = journal();
      final recovery = controller(
        lost: () async =>
            LostDataResponse(type: RetrieveType.image, files: [photo]),
      );
      await recovery.initialize(owner);
      expect(recovery.recoveredFor(proof)?.path, photo.path);
      expect(recovery.recoveredFor(anotherLoan), isNull);
      expect(recovery.recoveredFor(anotherPurpose), isNull);
      expect(await recovery.takeRecovered(anotherLoan), isNull);
      expect(recovery.recovered?.context.label, 'Loan 42 payment proof');
      expect(await recovery.takeRecovered(proof), photo);
      expect(recovery.recovered, isNull);
      expect(store.value, isNull);
    },
  );

  test(
    'keeps recovered path through a second restart until explicitly used',
    () async {
      store.value = journal();
      final first = controller(
        lost: () async => LostDataResponse(
          type: RetrieveType.image,
          file: photo,
          files: [photo],
        ),
      );
      await first.initialize(owner);
      final second = controller();
      await second.initialize(owner);
      expect(second.recoveredFor(proof)?.path, photo.path);
      expect(await second.takeRecovered(proof), isNotNull);
      final third = controller();
      await third.initialize(owner);
      expect(third.recovered, isNull);
    },
  );

  test(
    'suspension immediately invalidates an in-flight picker before identity resolves',
    () async {
      final recovery = controller();
      await recovery.initialize(owner);
      final started = Completer<void>();
      final result = Completer<XFile?>();
      final selected = recovery.pick(proof, () {
        started.complete();
        return result.future;
      });
      await started.future;
      final durable = store.value;
      recovery.suspend();
      expect(recovery.ready, isFalse);
      expect(store.value, durable);
      result.complete(photo);
      expect(await selected, isNull);
      await recovery.initialize(owner);
      expect(recovery.ready, isTrue);
      expect(await recovery.pick(proof, () async => photo), photo);
    },
  );

  test(
    'suspension preserves recovery until an authoritative owner is known',
    () async {
      store.value = journal(path: photo.path);
      var retrievals = 0;
      final recovery = controller(
        lost: () async {
          retrievals++;
          return LostDataResponse.empty();
        },
      );
      await recovery.initialize(owner);
      final durable = store.value;
      recovery.suspend();
      expect(recovery.recovered, isNull);
      expect(recovery.ready, isFalse);
      expect(store.value, durable);
      expect(retrievals, 1);
      await recovery.initialize(owner);
      expect(recovery.recoveredFor(proof)?.path, photo.path);
      expect(retrievals, 1);
    },
  );

  test('expires recovery at consumption without another restart', () async {
    var clock = now;
    store.value = journal(path: photo.path);
    final recovery = ImageRecoveryController(
      store: store,
      enabled: true,
      retrieveLostData: () async => LostDataResponse.empty(),
      now: () => clock,
    );
    await recovery.initialize(owner);
    expect(recovery.recoveredFor(proof), isNotNull);
    clock = now.add(const Duration(hours: 24));
    expect(await recovery.takeRecovered(proof), isNull);
    expect(recovery.recovered, isNull);
    expect(store.value, isNull);
    expect(recovery.error, isNotNull);
    expect(await File(photo.path).exists(), isTrue);
    expect(await recovery.pick(proof, () async => photo), photo);
  });

  for (final changedOwner in [
    null,
    'client-b|scope-1|endpoint-1|device-1',
    'client-a|scope-2|endpoint-1|device-1',
    'client-a|scope-1|endpoint-2|device-1',
    'client-a|scope-1|endpoint-1|device-2',
  ]) {
    test(
      'does not recover across authorization boundary $changedOwner',
      () async {
        store.value = journal();
        final recovery = controller(
          lost: () async =>
              LostDataResponse(type: RetrieveType.image, files: [photo]),
        );
        await recovery.initialize(changedOwner);
        expect(recovery.recovered, isNull);
        expect(store.value, isNull);
        expect(await File(photo.path).exists(), isTrue);
      },
    );
  }

  test(
    'consumes global lost-data cache only once while owner switches',
    () async {
      var retrievals = 0;
      store.value = journal();
      final recovery = controller(
        lost: () async {
          retrievals++;
          return LostDataResponse(type: RetrieveType.image, files: [photo]);
        },
      );
      await Future.wait([
        recovery.initialize(owner),
        recovery.initialize(owner),
      ]);
      expect(recovery.recoveredFor(proof), isNotNull);
      await recovery.initialize(null);
      await recovery.initialize(owner);
      expect(retrievals, 1);
      expect(recovery.recovered, isNull);
      expect(store.value, isNull);
    },
  );

  test(
    'discard preserves the image file but removes recovery metadata',
    () async {
      store.value = journal(path: photo.path);
      final recovery = controller();
      await recovery.initialize(owner);
      await recovery.discard();
      expect(recovery.recovered, isNull);
      expect(store.value, isNull);
      expect(await File(photo.path).exists(), isTrue);
    },
  );

  test('does not overwrite an unreviewed recovered image', () async {
    store.value = journal(path: photo.path);
    final recovery = controller();
    await recovery.initialize(owner);
    var launches = 0;
    await expectLater(
      recovery.pick(anotherLoan, () async {
        launches++;
        return null;
      }),
      throwsStateError,
    );
    expect(launches, 0);
    expect(recovery.recoveredFor(proof)?.path, photo.path);
  });

  test('blocks unjournaled picker launch when secure storage fails', () async {
    final recovery = controller();
    await recovery.initialize(owner);
    store.failWrites = true;
    var launches = 0;
    await expectLater(
      recovery.pick(proof, () async {
        launches++;
        return photo;
      }),
      throwsStateError,
    );
    expect(launches, 0);
    expect(recovery.error, isNotNull);
    expect(recovery.busy, isFalse);
  });

  test(
    'does not hand out recovery before its journal can be cleared',
    () async {
      store.value = journal(path: photo.path);
      final recovery = controller();
      await recovery.initialize(owner);
      store.failDeletes = true;
      await expectLater(recovery.takeRecovered(proof), throwsStateError);
      expect(recovery.recoveredFor(proof)?.path, photo.path);
    },
  );

  test(
    'cancellation clears pending metadata without inventing recovery',
    () async {
      final recovery = controller();
      await recovery.initialize(owner);
      expect(await recovery.pick(proof, () async => null), isNull);
      expect(store.value, isNull);
      expect(recovery.recovered, isNull);
    },
  );

  test('picker failure clears pending metadata and allows a retry', () async {
    final recovery = controller();
    await recovery.initialize(owner);
    await expectLater(
      recovery.pick(proof, () async {
        throw PlatformException(code: 'camera_denied');
      }),
      throwsA(isA<PlatformException>()),
    );
    expect(store.value, isNull);
    expect(await recovery.pick(proof, () async => photo), photo);
  });

  test('blocks concurrent pickers and drops result after logout', () async {
    final recovery = controller();
    await recovery.initialize(owner);
    final started = Completer<void>();
    final result = Completer<XFile?>();
    final first = recovery.pick(proof, () {
      started.complete();
      return result.future;
    });
    await started.future;
    await expectLater(
      recovery.pick(anotherLoan, () async => photo),
      throwsStateError,
    );
    await recovery.initialize(null);
    result.complete(photo);
    expect(await first, isNull);
    expect(recovery.recovered, isNull);
    expect(store.value, isNull);
  });

  test('scope switch during startup prevents stale file exposure', () async {
    store.value = journal();
    final entered = Completer<void>();
    final lost = Completer<LostDataResponse>();
    final recovery = controller(
      lost: () {
        entered.complete();
        return lost.future;
      },
    );
    final initializing = recovery.initialize(owner);
    await entered.future;
    final switched = recovery.initialize('client-b');
    lost.complete(LostDataResponse(type: RetrieveType.image, files: [photo]));
    await Future.wait([initializing, switched]);
    expect(recovery.recovered, isNull);
    expect(store.value, isNull);
  });

  test(
    'scope switch during picker cleanup does not return the old account image',
    () async {
      final recovery = controller();
      await recovery.initialize(owner);
      final deleting = Completer<void>();
      final release = Completer<void>();
      store.beforeDelete = () async {
        if (!deleting.isCompleted) deleting.complete();
        await release.future;
      };
      final selected = recovery.pick(proof, () async => photo);
      await deleting.future;
      final switched = recovery.initialize('client-b');
      release.complete();
      expect(await selected, isNull);
      await switched;
    },
  );

  test(
    'clears stale pending journal when picker was cancelled during restart',
    () async {
      store.value = journal();
      final recovery = controller();
      await recovery.initialize(owner);
      expect(recovery.recovered, isNull);
      expect(store.value, isNull);
      expect(recovery.ready, isTrue);
    },
  );

  for (final invalid in [
    'expired',
    'malformed',
    'relative_path',
    'missing',
    'empty',
  ]) {
    test('fails closed for $invalid recovery metadata', () async {
      store.value = switch (invalid) {
        'expired' => journal(
          path: photo.path,
          created: now.subtract(const Duration(hours: 25)),
        ),
        'malformed' => '{"owner":true}',
        'relative_path' => journal(path: '../secret.jpg'),
        'missing' => journal(path: '${temp.path}/absent.jpg'),
        _ => journal(path: '${temp.path}/empty.jpg'),
      };
      if (invalid == 'empty') {
        await File('${temp.path}/empty.jpg').writeAsBytes([]);
      }
      final recovery = controller();
      await recovery.initialize(owner);
      expect(recovery.recovered, isNull);
      expect(store.value, isNull);
      expect(recovery.ready, isTrue);
    });
  }

  for (final invalid in ['exception', 'multiple', 'video']) {
    test(
      'does not recover $invalid plugin response as a single image',
      () async {
        store.value = journal();
        final recovery = controller(
          lost: () async => switch (invalid) {
            'exception' => LostDataResponse(
              exception: PlatformException(code: 'failed'),
            ),
            'multiple' => LostDataResponse(
              type: RetrieveType.image,
              files: [photo, photo],
            ),
            _ => LostDataResponse(type: RetrieveType.video, files: [photo]),
          },
        );
        await recovery.initialize(owner);
        expect(recovery.recovered, isNull);
        expect(store.value, isNull);
      },
    );
  }

  test(
    'other platforms avoid Android cache and journal but still pick',
    () async {
      store.failWrites = true;
      store.failDeletes = true;
      final recovery = controller(
        enabled: false,
        lost: () async {
          fail('Android lost-data method called on another platform');
        },
      );
      await recovery.initialize(owner);
      expect(await recovery.pick(proof, () async => photo), photo);
      expect(recovery.ready, isTrue);
    },
  );
}
