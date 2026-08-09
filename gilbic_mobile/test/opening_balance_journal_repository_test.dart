import 'dart:convert';

import 'package:flutter_test/flutter_test.dart';
import 'package:gilbic_mobile/src/core/auth/app_role.dart';
import 'package:gilbic_mobile/src/core/auth/user_session.dart';
import 'package:gilbic_mobile/src/core/management/opening_balance_journal.dart';
import 'package:gilbic_mobile/src/core/management/opening_balance_journal_repository.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';

void main() {
  test('preserves exact cent strings beyond IEEE-754 safe integer range', () async {
    const exact = '90071992547409.93';
    late http.Request captured;
    final repository = SpinaOpeningBalanceJournalRepository(
      client: MockClient((request) async {
        captured = request;
        return http.Response(
          jsonEncode(<String, Object?>{
            'success': true,
            'data': <String, Object?>{
              'journal_draft': _payload(total: exact),
            },
          }),
          200,
          headers: const <String, String>{'content-type': 'application/json'},
        );
      }),
    );

    final result = await repository.post(
      _session,
      deviceId: 'management-device',
      workbookId: 'workbook-1',
      journalEntryId: 'journal-1',
      totalDebit: exact,
      totalCredit: exact,
    );
    final body = jsonDecode(captured.body) as Map<String, dynamic>;

    expect(body['total_debit'], exact);
    expect(body['total_credit'], exact);
    expect(body['total_debit'], isA<String>());
    expect(body['total_credit'], isA<String>());
    expect(result.totalDebitExact, exact);
    expect(result.totalCreditExact, exact);
  });

  test('payload parser retains exact decimal text for stale confirmation', () {
    const exact = '90071992547409.93';
    final status = OpeningBalanceJournalDraftStatus.fromPayload(
      _payload(total: exact),
    );

    expect(status.totalDebitExact, exact);
    expect(status.totalCreditExact, exact);
    expect(status.canPost, isTrue);
  });
}

Map<String, Object?> _payload({required String total}) => <String, Object?>{
      'workbook_id': 'workbook-1',
      'cutover_date': '2026-08-08',
      'workbook_status': 'review_ready',
      'journal_entry_id': 'journal-1',
      'journal_status': 'draft',
      'entry_number': null,
      'journal_line_count': 2,
      'total_debit': total,
      'total_credit': total,
      'draft_prepared': true,
      'preparation_ready': false,
      'preparation_blocker': 'Protected opening-balance journal draft is already prepared.',
      'opening_balance_posting_enabled': true,
      'automatic_source_posting_enabled': false,
      'posting_ready': true,
      'posting_blocker': null,
      'posted_by_user_id': null,
      'posted_at': null,
      'notice': 'Protected opening-balance posting test.',
    };

const UserSession _session = UserSession(
  userId: 'management-1',
  username: 'manager',
  displayName: 'Management',
  role: AppRole.management,
  rawRole: 'Management',
  accessToken: 'management-token',
  permissions: <String>['accounting.opening_balance.post'],
);
