import 'package:flutter/material.dart';
import 'package:gilbic_mobile/src/core/auth/app_role.dart';
import 'package:gilbic_mobile/src/core/auth/user_session.dart';
import 'package:gilbic_mobile/src/core/device/device_identity.dart';
import 'package:gilbic_mobile/src/core/management/accounting_readiness_repository.dart';
import 'package:gilbic_mobile/src/core/network/spina_api.dart';

const postedLedgerScopeNotice =
    'Report scope: posted ledger only. Arithmetic balance does not establish accounting readiness or complete source coverage.';

class AccountingReadinessCard extends StatefulWidget {
  const AccountingReadinessCard({
    required this.session,
    required this.deviceIdentityProvider,
    this.repository,
    this.periodId,
    this.showBook = true,
    super.key,
  });
  final UserSession session;
  final DeviceIdentityProvider deviceIdentityProvider;
  final AccountingReadinessRepository? repository;
  final String? periodId;
  final bool showBook;

  @override
  State<AccountingReadinessCard> createState() =>
      _AccountingReadinessCardState();
}

class _AccountingReadinessCardState extends State<AccountingReadinessCard> {
  late AccountingReadinessRepository _repository;
  AccountingBookIdentity? _book;
  AccountingSourceCoverage? _coverage;
  String? _error;
  int _generation = 0;
  late String _sessionScope;

  String get _scope =>
      '${widget.session.userId}:${widget.session.accessToken}:${widget.session.permissions.join(',')}:${widget.session.workspaceRoles.join(',')}';

  @override
  void initState() {
    super.initState();
    _repository = widget.repository ?? SpinaAccountingReadinessRepository();
    _sessionScope = _scope;
    _load();
  }

  @override
  void didUpdateWidget(covariant AccountingReadinessCard oldWidget) {
    super.didUpdateWidget(oldWidget);
    if (_scope != _sessionScope ||
        oldWidget.periodId != widget.periodId ||
        oldWidget.showBook != widget.showBook ||
        oldWidget.deviceIdentityProvider != widget.deviceIdentityProvider ||
        oldWidget.repository != widget.repository) {
      _sessionScope = _scope;
      if (oldWidget.repository != widget.repository) {
        _repository = widget.repository ?? SpinaAccountingReadinessRepository();
      }
      _load();
    }
  }

  bool _active(int generation, String scope) =>
      mounted && generation == _generation && scope == _scope;

  Future<void> _load() async {
    final generation = ++_generation;
    final scope = _scope;
    final session = widget.session;
    final periodId = widget.periodId;
    setState(() {
      _book = null;
      _coverage = null;
      _error = null;
    });
    if (!session.hasRole(AppRole.management) ||
        !session.hasPermission('accounting.view')) {
      setState(
        () => _error =
            'Accounting access is unavailable. Refresh your session and permissions.',
      );
      return;
    }
    try {
      final identity = await widget.deviceIdentityProvider.load();
      if (!_active(generation, scope)) return;
      final book = widget.showBook
          ? await _repository.loadBook(
              session,
              deviceId: identity.installationId,
            )
          : null;
      if (!_active(generation, scope)) return;
      final coverage = periodId != null
          ? await _repository.loadSourceCoverage(
              session,
              deviceId: identity.installationId,
              periodId: periodId,
            )
          : null;
      if (!_active(generation, scope)) return;
      setState(() {
        _book = book;
        _coverage = coverage;
      });
    } on Object catch (error) {
      if (!_active(generation, scope)) return;
      setState(() {
        _error =
            error is SpinaApiException &&
                [401, 403, 426].contains(error.statusCode)
            ? 'Accounting access is unavailable. Refresh your session and permissions.'
            : 'Accounting readiness evidence is unavailable. Refresh before relying on this review.';
      });
    }
  }

  @override
  void dispose() {
    _generation++;
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final book = _book;
    final coverage = _coverage;
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(12),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            const Text(postedLedgerScopeNotice),
            if (_error != null) Text(_error!),
            if (_error == null && widget.showBook) ...[
              const SizedBox(height: 6),
              if (book == null)
                const Text('Loading book identity…')
              else if (!book.configured)
                const Text(
                  'Book identity is unconfigured. Separate owner and corporate accounting has not been established for this ledger.',
                )
              else ...[
                Text(
                  'Immutable book identity: ${book.entityLabel} · ${book.kindLabel}',
                ),
                Text('Book reference: ${book.bookId}'),
              ],
            ],
            if (_error == null && widget.periodId != null) ...[
              const SizedBox(height: 6),
              if (coverage == null)
                const Text('Loading source blockers for this period…')
              else ...[
                Text(
                  'Partial source coverage: ${coverage.sourceFamilies.map((family) => family == 'treasury' ? 'Treasury' : 'Collector').join(', ')}.',
                ),
                const Text(
                  'This check does not certify readiness for other source families.',
                ),
                Text(
                  'Showing ${coverage.blockers.isEmpty ? '0' : '${coverage.offset + 1}–${coverage.offset + coverage.blockers.length}'} of ${coverage.blockerCount} source blockers.',
                ),
                if (coverage.blockerCount > coverage.blockers.length)
                  const Text(
                    'The full blocker inventory is not shown on this page.',
                  ),
                if (coverage.blockerCount == 0)
                  const Text(
                    'No blockers returned for these source families. This does not certify readiness.',
                  ),
                for (final blocker in coverage.blockers)
                  Padding(
                    padding: const EdgeInsets.only(top: 10),
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        if (blocker.restricted)
                          const Text(
                            'Restricted source — Treasury account access required',
                          )
                        else ...[
                          Text(blocker.sourceType.replaceAll('_', ' ')),
                          Text(blocker.reason),
                          Text(
                            '${blocker.effectiveDate} · ${blocker.amount == null ? 'Amount unavailable' : 'PHP ${blocker.amount}'}',
                          ),
                          Text('Source reference: ${blocker.sourceId}'),
                        ],
                      ],
                    ),
                  ),
              ],
            ],
            if (_error != null)
              TextButton(
                onPressed: _load,
                child: const Text('Refresh accounting readiness'),
              ),
          ],
        ),
      ),
    );
  }
}

class AccountingSourceBlockers extends StatefulWidget {
  const AccountingSourceBlockers({
    required this.session,
    required this.deviceIdentityProvider,
    required this.periodId,
    this.repository,
    super.key,
  });
  final UserSession session;
  final DeviceIdentityProvider deviceIdentityProvider;
  final String periodId;
  final AccountingReadinessRepository? repository;

  @override
  State<AccountingSourceBlockers> createState() =>
      _AccountingSourceBlockersState();
}

class _AccountingSourceBlockersState extends State<AccountingSourceBlockers> {
  bool _opened = false;
  @override
  Widget build(BuildContext context) => Column(
    crossAxisAlignment: CrossAxisAlignment.start,
    children: [
      TextButton(
        onPressed: () => setState(() => _opened = !_opened),
        child: Text(
          _opened ? 'Hide source blockers' : 'Review source blockers',
        ),
      ),
      if (_opened)
        AccountingReadinessCard(
          session: widget.session,
          deviceIdentityProvider: widget.deviceIdentityProvider,
          repository: widget.repository,
          periodId: widget.periodId,
          showBook: false,
        ),
    ],
  );
}
