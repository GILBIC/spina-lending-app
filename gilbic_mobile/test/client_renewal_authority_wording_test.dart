import 'dart:io';

import 'package:flutter_test/flutter_test.dart';

void main() {
  final renewalModelSource = File(
    'lib/src/core/renewals/renewal_request.dart',
  ).readAsStringSync();
  final renewalPageSource = File(
    'lib/src/features/client/client_renewal_page.dart',
  ).readAsStringSync();
  final renewalWorkflowSource = File(
    'lib/src/features/client/client_renewal_workflow_page.dart',
  ).readAsStringSync();

  test('Client Android renewal wording preserves Collector then Management sequence', () {
    expect(
      renewalModelSource,
      contains("'Pending Collector recommendation / Management review'"),
    );
    expect(
      renewalPageSource,
      contains(
        'Your assigned Collector must recommend it before Management review.',
      ),
    );
  });

  test('Client Android renewal wording keeps other required signers on their own account', () {
    const signerCopy =
        'Any other required signer must use their own SPINA account.';
    expect(renewalPageSource, contains(signerCopy));
    expect(renewalWorkflowSource, contains(signerCopy));
  });
}
