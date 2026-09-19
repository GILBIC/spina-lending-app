import 'dart:async';
import 'package:flutter_test/flutter_test.dart';
import 'package:gilbic_mobile/src/core/network/spina_api.dart';
import 'package:gilbic_mobile/src/core/office/office_operation.dart';

void main() {
  test('mandatory upgrade is a terminal office rejection', () async {
    final state = OfficeOperation();
    await state.run(
      () async =>
          throw const SpinaApiException('Upgrade required', statusCode: 426),
    );
    expect(state.denied, isTrue);
    expect(state.canWrite, isFalse);
    state.dispose();
  });
  test(
    'uncertain write is sticky until successful authoritative reconciliation',
    () async {
      final state = OfficeOperation();
      var writes = 0;
      await state.run(() async {
        writes++;
        throw const SpinaApiException('Uncertain', code: 'network_unavailable');
      }, mutation: true);
      expect(state.blocked, isTrue);
      await state.run(() async {
        writes++;
        return 1;
      }, mutation: true);
      expect(writes, 1);
      await state.run(
        () async => throw const SpinaApiException('Offline'),
        reconcile: true,
      );
      expect(state.blocked, isTrue);
      await state.run(() async => 1, reconcile: true);
      expect(state.blocked, isFalse);
      state.dispose();
    },
  );
  test('late response cannot repopulate replaced private selection', () async {
    final state = OfficeOperation();
    final pending = Completer<String>();
    final result = state.run(() => pending.future);
    state.invalidate();
    pending.complete('Private record');
    expect(await result, isNull);
    state.dispose();
  });
  test(
    'access denial latches and blocks another write even after invalidation',
    () async {
      final state = OfficeOperation();
      await state.run(
        () async => throw const SpinaApiException('Revoked', statusCode: 403),
      );
      expect(state.denied, isTrue);
      state.invalidate();
      var called = false;
      await state.run(() async {
        called = true;
        return 1;
      }, mutation: true);
      expect(called, isFalse);
      state.dispose();
    },
  );
  test(
    'validation error allows correction but duplicate taps cannot issue two writes',
    () async {
      final state = OfficeOperation();
      await state.run(
        () async =>
            throw const SpinaApiException('Check amount', statusCode: 422),
        mutation: true,
      );
      expect(state.blocked, isFalse);
      final pending = Completer<int>();
      final first = state.run(() => pending.future, mutation: true);
      expect(await state.run(() async => 2, mutation: true), isNull);
      pending.complete(1);
      expect(await first, 1);
      state.dispose();
    },
  );
}
