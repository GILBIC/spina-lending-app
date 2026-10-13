import 'package:gilbic_mobile/src/core/auth/user_session.dart';
import 'package:gilbic_mobile/src/core/management/accounting_readiness_repository.dart';

/// Deterministic private accounting reads for page integration tests.
class FakeAccountingReadinessRepository
    implements AccountingReadinessRepository {
  FakeAccountingReadinessRepository({this.bookError, this.sourceError});

  final Object? bookError;
  final Object? sourceError;
  int bookReads = 0;
  final List<String> sourcePeriods = [];

  @override
  Future<AccountingBookIdentity> loadBook(
    UserSession session, {
    required String deviceId,
  }) async {
    bookReads++;
    if (bookError case final error?) throw error;
    return AccountingBookIdentity.fromPayload({
      'status': 'unconfigured',
      'book_id': null,
      'kind': null,
      'entity_label': null,
    });
  }

  @override
  Future<AccountingSourceCoverage> loadSourceCoverage(
    UserSession session, {
    required String deviceId,
    required String periodId,
  }) async {
    sourcePeriods.add(periodId);
    if (sourceError case final error?) throw error;
    return AccountingSourceCoverage.fromPayload({
      'comprehensive_source_coverage': false,
      'source_families': ['treasury', 'collector'],
      'limit': 100,
      'offset': 0,
      'blocker_count': 0,
      'blockers': [],
    });
  }
}
