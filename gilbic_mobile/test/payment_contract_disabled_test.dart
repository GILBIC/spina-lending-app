import 'dart:io';

import 'package:flutter_test/flutter_test.dart';

void main() {
  test('approved online collection form is wired without an offline outbox', () {
    final appSource = File('lib/src/app.dart').readAsStringSync();
    final routeSource = File(
      'lib/src/features/collector/collector_route_page.dart',
    ).readAsStringSync();
    final entrySource = File(
      'lib/src/features/collector/collection_entry_page.dart',
    ).readAsStringSync();

    expect(appSource, contains('SpinaPaymentSubmissionRepository'));
    expect(routeSource, contains('CollectionEntryPage'));
    expect(routeSource, contains('Offline route copies are read-only'));
    expect(entrySource, contains('Retry same entry'));
    expect(entrySource, contains('7x7 mobile collection is disabled'));
    expect(appSource, isNot(contains('PendingCollectionOutbox')));
    expect(entrySource, isNot(contains('automaticRetry')));
  });
}
