import 'dart:io';

import 'package:flutter_test/flutter_test.dart';

void main() {
  test('Android Client statement uses the protected mobile endpoint and exact money text', () {
    final model = File('lib/src/core/statements/client_statement.dart');
    final repository = File('lib/src/core/statements/client_statement_repository.dart');
    final page = File('lib/src/features/client/client_statement_page.dart');
    final paymentsPage = File('lib/src/features/client/client_payments_page.dart');

    expect(model.existsSync(), isTrue);
    expect(repository.existsSync(), isTrue);
    expect(page.existsSync(), isTrue);

    final modelSource = model.readAsStringSync();
    final repositorySource = repository.readAsStringSync();
    final pageSource = page.readAsStringSync();
    final paymentsSource = paymentsPage.readAsStringSync();

    expect(repositorySource, contains('/api/mobile/v1/client/statement'));
    expect(modelSource, contains('final String principal;'));
    expect(modelSource, contains('final String remainingBalance;'));
    expect(modelSource, contains('final String amount;'));
    expect(modelSource, contains('final String? officialBalance;'));
    expect(pageSource, contains('Statement of Account'));
    expect(pageSource, isNot(contains('double.tryParse')));
    expect(pageSource, isNot(contains('toStringAsFixed')));
    expect(paymentsSource, contains("Key('open-client-statement')"));
    expect(paymentsSource, contains('ClientStatementPage'));
  });
}
