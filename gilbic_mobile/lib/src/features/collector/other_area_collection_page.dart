import 'dart:async';

import 'package:flutter/material.dart';
import 'package:gilbic_mobile/src/core/auth/app_role.dart';
import 'package:gilbic_mobile/src/core/auth/user_session.dart';
import 'package:gilbic_mobile/src/core/collector/other_area_client.dart';
import 'package:gilbic_mobile/src/core/collector/other_area_client_repository.dart';
import 'package:gilbic_mobile/src/core/device/device_identity.dart';
import 'package:gilbic_mobile/src/core/network/spina_api.dart';
import 'package:gilbic_mobile/src/core/payments/collection_device_sequence.dart';
import 'package:gilbic_mobile/src/core/payments/payment_submission_repository.dart';
import 'package:gilbic_mobile/src/core/time/spina_business_time.dart';
import 'package:gilbic_mobile/src/features/collector/collection_entry_page.dart';

class OtherAreaCollectionPage extends StatefulWidget {
  const OtherAreaCollectionPage({
    required this.session,
    required this.paymentRepository,
    required this.deviceIdentityProvider,
    required this.deviceSequence,
    this.repository,
    super.key,
  });

  final UserSession session;
  final PaymentSubmissionRepository paymentRepository;
  final DeviceIdentityProvider deviceIdentityProvider;
  final CollectionDeviceSequence deviceSequence;
  final OtherAreaClientRepository? repository;

  @override
  State<OtherAreaCollectionPage> createState() =>
      _OtherAreaCollectionPageState();
}

class _OtherAreaCollectionPageState extends State<OtherAreaCollectionPage> {
  late final TextEditingController _searchController;
  late final OtherAreaClientRepository _repository;

  Timer? _searchDebounce;
  List<OtherAreaClient> _results = const <OtherAreaClient>[];
  String? _errorMessage;
  String _selectedArea = _allAreas;
  String _selectedLoanType = _allLoans;
  String _selectedOwner = _allCollectors;
  bool _loading = false;
  bool _hasLoaded = false;
  int _loadGeneration = 0;

  static const String _allAreas = 'All areas';
  static const String _allLoans = 'All loans';
  static const String _allCollectors = 'All assigned collectors';

  bool get _isManagement => widget.session.role == AppRole.management;

  List<String> get _areas {
    final values = _results
        .map((client) => client.entry.area.trim())
        .where((value) => value.isNotEmpty)
        .toSet()
        .toList(growable: false)
      ..sort((left, right) => left.toLowerCase().compareTo(right.toLowerCase()));
    return <String>[_allAreas, ...values];
  }

  List<String> get _loanTypes {
    final values = _results
        .map((client) => client.entry.loanType.trim())
        .where((value) => value.isNotEmpty)
        .toSet()
        .toList(growable: false)
      ..sort((left, right) => left.toLowerCase().compareTo(right.toLowerCase()));
    return <String>[_allLoans, ...values];
  }

  List<String> get _owners {
    final values = _results
        .map((client) => client.assignedCollectorName.trim())
        .where((value) => value.isNotEmpty)
        .toSet()
        .toList(growable: false)
      ..sort((left, right) => left.toLowerCase().compareTo(right.toLowerCase()));
    return <String>[_allCollectors, ...values];
  }

  List<OtherAreaClient> get _visibleResults {
    final query = _searchController.text.trim().toLowerCase();
    final filtered = _results.where((client) {
      final entry = client.entry;
      if (_selectedArea != _allAreas && entry.area != _selectedArea) {
        return false;
      }
      if (_selectedLoanType != _allLoans &&
          entry.loanType != _selectedLoanType) {
        return false;
      }
      if (!_isManagement &&
          _selectedOwner != _allCollectors &&
          client.assignedCollectorName != _selectedOwner) {
        return false;
      }
      if (!_isManagement && query.isNotEmpty) {
        final haystack = <String>[
          entry.clientName,
          client.clientCode,
          client.phoneNumber,
          entry.area,
          entry.loanType,
          client.assignedCollectorName,
        ].join(' ').toLowerCase();
        if (!haystack.contains(query)) {
          return false;
        }
      }
      return true;
    }).toList(growable: false);

    filtered.sort((left, right) {
      if (!_isManagement) {
        final ownerOrder = left.assignedCollectorName
            .toLowerCase()
            .compareTo(right.assignedCollectorName.toLowerCase());
        if (ownerOrder != 0) {
          return ownerOrder;
        }
        final areaOrder = left.entry.area
            .toLowerCase()
            .compareTo(right.entry.area.toLowerCase());
        if (areaOrder != 0) {
          return areaOrder;
        }
      }
      final nameOrder = left.entry.clientName
          .toLowerCase()
          .compareTo(right.entry.clientName.toLowerCase());
      if (nameOrder != 0) {
        return nameOrder;
      }
      return left.entry.loanType
          .toLowerCase()
          .compareTo(right.entry.loanType.toLowerCase());
    });
    return filtered;
  }

  int get _clientCount =>
      _results.map((client) => client.entry.clientId).toSet().length;

  @override
  void initState() {
    super.initState();
    _searchController = TextEditingController();
    _repository = widget.repository ??
        SpinaOtherAreaClientRepository(
          deviceIdentityProvider: widget.deviceIdentityProvider,
        );
    if (!_isManagement) {
      _loadWork();
    }
  }

  @override
  void dispose() {
    _searchDebounce?.cancel();
    _searchController.dispose();
    super.dispose();
  }

  void _onSearchChanged(String value) {
    if (!_isManagement) {
      setState(() {});
      return;
    }
    _searchDebounce?.cancel();
    final query = value.trim();
    if (query.length < 2) {
      _loadGeneration += 1;
      setState(() {
        _results = const <OtherAreaClient>[];
        _hasLoaded = false;
        _loading = false;
        _errorMessage = null;
        _selectedArea = _allAreas;
        _selectedLoanType = _allLoans;
      });
      return;
    }
    _searchDebounce = Timer(const Duration(milliseconds: 350), _searchManagement);
  }

  void _clearSearch() {
    _searchDebounce?.cancel();
    _searchController.clear();
    if (_isManagement) {
      _loadGeneration += 1;
      setState(() {
        _results = const <OtherAreaClient>[];
        _hasLoaded = false;
        _loading = false;
        _errorMessage = null;
        _selectedArea = _allAreas;
        _selectedLoanType = _allLoans;
      });
    } else {
      setState(() {});
    }
  }

  Future<void> _loadWork() async {
    final generation = ++_loadGeneration;
    setState(() {
      _loading = true;
      _errorMessage = null;
    });
    try {
      final results = await _repository.listWork(widget.session, DateTime.now());
      if (!mounted || generation != _loadGeneration) {
        return;
      }
      setState(() {
        _results = results;
        _hasLoaded = true;
        _selectedArea = _areas.contains(_selectedArea) ? _selectedArea : _allAreas;
        _selectedLoanType =
            _loanTypes.contains(_selectedLoanType) ? _selectedLoanType : _allLoans;
        _selectedOwner =
            _owners.contains(_selectedOwner) ? _selectedOwner : _allCollectors;
      });
    } on SpinaApiException catch (error) {
      if (!mounted || generation != _loadGeneration) {
        return;
      }
      setState(() {
        _errorMessage = error.message;
        _hasLoaded = true;
        _results = const <OtherAreaClient>[];
      });
    } on Object {
      if (!mounted || generation != _loadGeneration) {
        return;
      }
      setState(() {
        _errorMessage = 'Other-area work could not be loaded.';
        _hasLoaded = true;
        _results = const <OtherAreaClient>[];
      });
    } finally {
      if (mounted && generation == _loadGeneration) {
        setState(() => _loading = false);
      }
    }
  }

  Future<void> _searchManagement({bool showValidation = false}) async {
    final query = _searchController.text.trim();
    if (query.length < 2) {
      if (showValidation) {
        setState(() {
          _errorMessage =
              'Enter at least two letters, a client code, phone, or area.';
        });
      }
      return;
    }

    final generation = ++_loadGeneration;
    setState(() {
      _loading = true;
      _errorMessage = null;
    });
    try {
      final results = await _repository.search(widget.session, query);
      if (!mounted || generation != _loadGeneration) {
        return;
      }
      setState(() {
        _results = results;
        _hasLoaded = true;
        _selectedArea = _allAreas;
        _selectedLoanType = _allLoans;
      });
    } on SpinaApiException catch (error) {
      if (!mounted || generation != _loadGeneration) {
        return;
      }
      setState(() {
        _errorMessage = error.message;
        _hasLoaded = true;
        _results = const <OtherAreaClient>[];
      });
    } on Object {
      if (!mounted || generation != _loadGeneration) {
        return;
      }
      setState(() {
        _errorMessage = 'Clients could not be searched for direct payment entry.';
        _hasLoaded = true;
        _results = const <OtherAreaClient>[];
      });
    } finally {
      if (mounted && generation == _loadGeneration) {
        setState(() => _loading = false);
      }
    }
  }

  String? _blockedReason(OtherAreaClient client) {
    final entry = client.entry;
    if (entry.processedToday) {
      final recorder = entry.todayCollectorName.trim().isEmpty
          ? 'another collector'
          : entry.todayCollectorName.trim();
      return 'Already recorded today by $recorder.';
    }
    if (!widget.session.permissions.contains('collection.create')) {
      return 'This account does not have collection permission.';
    }
    if (_isSevenBySevenLoan(entry.loanType)) {
      return '7x7 mobile collection remains disabled. Use SPINA desktop.';
    }
    if (!entry.canCollectMobile || !entry.canEnterPayment) {
      return entry.collectionMessage.isNotEmpty
          ? entry.collectionMessage
          : 'Use SPINA desktop for this loan.';
    }
    if (entry.loanId.trim().isEmpty || entry.routeRevision == null) {
      return _isManagement
          ? 'Refresh this search before recording the payment.'
          : 'Refresh Other-Area Work before recording the payment.';
    }
    return null;
  }

  Future<void> _openPayment(OtherAreaClient client) async {
    final blocked = _blockedReason(client);
    if (blocked != null) {
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text(blocked)),
      );
      return;
    }

    final confirmed = await showDialog<bool>(
      context: context,
      builder: (context) => AlertDialog(
        title: Text(
          _isManagement
              ? 'Record direct Management payment?'
              : 'Record delegated-area payment?',
        ),
        content: Text(
          _isManagement
              ? '${client.entry.clientName} is assigned to '
                  '${client.assignedCollectorName}.\n\n'
                  'Management will remain the recorder. The assigned collector and '
                  'linked client will be notified. Collectors cannot edit this '
                  'Management-recorded payment.'
              : '${client.entry.clientName} is assigned to '
                  '${client.assignedCollectorName}.\n\n'
                  'Your active temporary grant will be rechecked by the server when '
                  'you save. Your name remains the recorder and the assigned '
                  'collector will see the official result.',
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.of(context).pop(false),
            child: const Text('Cancel'),
          ),
          FilledButton(
            key: const Key('confirm-other-area-payment'),
            onPressed: () => Navigator.of(context).pop(true),
            child: const Text('Continue'),
          ),
        ],
      ),
    );
    if (confirmed != true || !mounted) {
      return;
    }

    final saved = await Navigator.of(context).push<bool>(
      MaterialPageRoute<bool>(
        builder: (context) => CollectionEntryPage(
          session: widget.session,
          entry: client.entry,
          repository: widget.paymentRepository,
          deviceIdentityProvider: widget.deviceIdentityProvider,
          deviceSequence: widget.deviceSequence,
          collectionDate: DateTime.now(),
        ),
      ),
    );
    if (saved == true && mounted) {
      if (_isManagement) {
        await _searchManagement(showValidation: true);
      } else {
        await _loadWork();
      }
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: Text(_isManagement ? 'Direct Payment Entry' : 'Other-Area Work'),
        actions: [
          if (!_isManagement)
            IconButton(
              key: const Key('refresh-other-area-work'),
              tooltip: 'Refresh approved work',
              onPressed: _loading ? null : _loadWork,
              icon: const Icon(Icons.refresh),
            ),
        ],
      ),
      body: SafeArea(
        child: Column(
          children: [
            Padding(
              padding: const EdgeInsets.fromLTRB(16, 16, 16, 8),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(
                    _isManagement
                        ? 'Search an active client who paid directly to Management. The assigned collector will see a read-only payment update.'
                        : 'Only clients inside your active temporary grants are shown. Permanent assignments stay in Daily Route.',
                    style: Theme.of(context).textTheme.bodyMedium,
                  ),
                  if (!_isManagement) ...[
                    const SizedBox(height: 6),
                    Text(
                      'SPINA business date: ${formatSpinaBusinessDate(DateTime.now())}',
                      key: const Key('other-area-business-date'),
                      style: Theme.of(context).textTheme.labelMedium,
                    ),
                  ],
                  const SizedBox(height: 12),
                  TextField(
                    key: const Key('other-area-search'),
                    controller: _searchController,
                    textInputAction: TextInputAction.search,
                    autocorrect: false,
                    onChanged: _onSearchChanged,
                    onSubmitted: _isManagement
                        ? (_) => _searchManagement(showValidation: true)
                        : null,
                    decoration: InputDecoration(
                      labelText: _isManagement
                          ? 'Find by name, code, phone, or area'
                          : 'Filter today’s approved work',
                      helperText: _isManagement
                          ? 'Results appear automatically after 2 characters.'
                          : 'Filter by client, code, area, loan, or assigned collector.',
                      prefixIcon: const Icon(Icons.person_search),
                      suffixIcon: Row(
                        mainAxisSize: MainAxisSize.min,
                        children: [
                          if (_searchController.text.isNotEmpty)
                            IconButton(
                              tooltip: 'Clear',
                              onPressed: _clearSearch,
                              icon: const Icon(Icons.clear),
                            ),
                          if (_isManagement)
                            IconButton(
                              tooltip: 'Search now',
                              onPressed: _loading
                                  ? null
                                  : () => _searchManagement(showValidation: true),
                              icon: _loading
                                  ? const SizedBox(
                                      width: 18,
                                      height: 18,
                                      child: CircularProgressIndicator(strokeWidth: 2),
                                    )
                                  : const Icon(Icons.search),
                            ),
                        ],
                      ),
                    ),
                  ),
                  if (_errorMessage != null) ...[
                    const SizedBox(height: 8),
                    Text(
                      _errorMessage!,
                      style: TextStyle(
                        color: Theme.of(context).colorScheme.error,
                      ),
                    ),
                  ],
                  if (_results.isNotEmpty) ...[
                    const SizedBox(height: 10),
                    Text(
                      '$_clientCount clients • ${_results.length} active loans',
                      key: const Key('other-area-work-count'),
                      style: Theme.of(context).textTheme.labelLarge,
                    ),
                    const SizedBox(height: 8),
                    if (!_isManagement) ...[
                      DropdownButtonFormField<String>(
                        key: const Key('other-area-owner-filter'),
                        initialValue: _owners.contains(_selectedOwner)
                            ? _selectedOwner
                            : _allCollectors,
                        isExpanded: true,
                        decoration: const InputDecoration(
                          labelText: 'Assigned collector',
                          prefixIcon: Icon(Icons.badge_outlined),
                        ),
                        items: _owners
                            .map(
                              (owner) => DropdownMenuItem<String>(
                                value: owner,
                                child: Text(owner, overflow: TextOverflow.ellipsis),
                              ),
                            )
                            .toList(growable: false),
                        onChanged: (value) {
                          setState(
                            () => _selectedOwner = value ?? _allCollectors,
                          );
                        },
                      ),
                      const SizedBox(height: 8),
                    ],
                    Row(
                      children: [
                        Expanded(
                          child: DropdownButtonFormField<String>(
                            initialValue: _areas.contains(_selectedArea)
                                ? _selectedArea
                                : _allAreas,
                            isExpanded: true,
                            decoration: const InputDecoration(
                              labelText: 'Area',
                              prefixIcon: Icon(Icons.location_on_outlined),
                            ),
                            items: _areas
                                .map(
                                  (area) => DropdownMenuItem<String>(
                                    value: area,
                                    child: Text(
                                      area,
                                      overflow: TextOverflow.ellipsis,
                                    ),
                                  ),
                                )
                                .toList(growable: false),
                            onChanged: (value) {
                              setState(() => _selectedArea = value ?? _allAreas);
                            },
                          ),
                        ),
                        const SizedBox(width: 8),
                        Expanded(
                          child: DropdownButtonFormField<String>(
                            initialValue: _loanTypes.contains(_selectedLoanType)
                                ? _selectedLoanType
                                : _allLoans,
                            isExpanded: true,
                            decoration: const InputDecoration(
                              labelText: 'Loan',
                              prefixIcon: Icon(Icons.account_balance_wallet_outlined),
                            ),
                            items: _loanTypes
                                .map(
                                  (loanType) => DropdownMenuItem<String>(
                                    value: loanType,
                                    child: Text(
                                      loanType,
                                      overflow: TextOverflow.ellipsis,
                                    ),
                                  ),
                                )
                                .toList(growable: false),
                            onChanged: (value) {
                              setState(
                                () => _selectedLoanType = value ?? _allLoans,
                              );
                            },
                          ),
                        ),
                      ],
                    ),
                  ],
                ],
              ),
            ),
            Expanded(child: _buildResults(context)),
          ],
        ),
      ),
    );
  }

  Widget _buildResults(BuildContext context) {
    if (_loading && !_hasLoaded) {
      return const Center(child: CircularProgressIndicator());
    }
    if (!_hasLoaded) {
      return Center(
        child: Padding(
          padding: const EdgeInsets.all(24),
          child: Text(
            _isManagement
                ? 'Start typing the client name, code, phone, or area.'
                : 'Loading today’s approved other-area work…',
            textAlign: TextAlign.center,
          ),
        ),
      );
    }
    if (_results.isEmpty) {
      return RefreshIndicator(
        onRefresh: _isManagement ? () async {} : _loadWork,
        child: ListView(
          physics: const AlwaysScrollableScrollPhysics(),
          children: [
            SizedBox(height: MediaQuery.sizeOf(context).height * 0.2),
            Padding(
              padding: const EdgeInsets.all(24),
              child: Text(
                _isManagement
                    ? 'No active client matched the search.'
                    : 'No active granted work for today. Request access under Temporary Area Access, or refresh after approval.',
                key: _isManagement
                    ? null
                    : const Key('other-area-empty-grant-state'),
                textAlign: TextAlign.center,
              ),
            ),
          ],
        ),
      );
    }

    final visibleResults = _visibleResults;
    if (visibleResults.isEmpty) {
      return const Center(
        child: Padding(
          padding: EdgeInsets.all(24),
          child: Text(
            'No client matches the current filters.',
            textAlign: TextAlign.center,
          ),
        ),
      );
    }

    return RefreshIndicator(
      onRefresh: _isManagement
          ? () => _searchManagement(showValidation: false)
          : _loadWork,
      child: ListView.separated(
        physics: const AlwaysScrollableScrollPhysics(),
        padding: const EdgeInsets.fromLTRB(12, 4, 12, 20),
        itemCount: visibleResults.length,
        separatorBuilder: (_, __) => const SizedBox(height: 8),
        itemBuilder: (context, index) {
          final client = visibleResults[index];
          final entry = client.entry;
          final blocked = _blockedReason(client);
          return Card(
            child: Padding(
              padding: const EdgeInsets.all(14),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Row(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      const Icon(Icons.person_pin_circle_outlined),
                      const SizedBox(width: 10),
                      Expanded(
                        child: Column(
                          crossAxisAlignment: CrossAxisAlignment.start,
                          children: [
                            Text(
                              entry.clientName,
                              style: Theme.of(context).textTheme.titleMedium,
                            ),
                            Text(
                              [client.clientCode, entry.area, entry.loanType]
                                  .where((value) => value.isNotEmpty)
                                  .join(' • '),
                            ),
                          ],
                        ),
                      ),
                    ],
                  ),
                  const Divider(height: 22),
                  Text('Assigned collector: ${client.assignedCollectorName}'),
                  Text('Daily amount: ${_money(entry.dailyAmount)}'),
                  Text('Remaining balance: ${_money(entry.balance)}'),
                  if (client.phoneNumber.isNotEmpty)
                    Text('Phone: ${client.phoneNumber}'),
                  if (entry.processedToday) ...[
                    const SizedBox(height: 10),
                    _TodayResult(entry: entry),
                  ],
                  const SizedBox(height: 8),
                  Text(
                    blocked ??
                        (_isManagement
                            ? 'Direct Management payment. The assigned collector and linked client will be notified.'
                            : entry.collectionMessage),
                    style: Theme.of(context).textTheme.bodySmall,
                  ),
                  const SizedBox(height: 10),
                  SizedBox(
                    width: double.infinity,
                    child: FilledButton.icon(
                      key: Key('record-other-area-${entry.loanId}'),
                      onPressed:
                          blocked == null ? () => _openPayment(client) : null,
                      icon: const Icon(Icons.payments_outlined),
                      label: Text(
                        entry.processedToday
                            ? 'Already recorded today'
                            : (_isManagement
                                ? 'Record direct payment'
                                : 'Record payment'),
                      ),
                    ),
                  ),
                ],
              ),
            ),
          );
        },
      ),
    );
  }
}

class _TodayResult extends StatelessWidget {
  const _TodayResult({required this.entry});

  final dynamic entry;

  @override
  Widget build(BuildContext context) {
    final entryType = entry.todayEntryType.toString().trim().toLowerCase();
    final recorder = entry.todayCollectorName.toString().trim().isEmpty
        ? 'Collector'
        : entry.todayCollectorName.toString().trim();
    final status = entryType == 'pass'
        ? 'Unable to pay'
        : 'Collected ${_money(entry.todayAmount as double)}';
    return Container(
      key: Key('other-area-today-${entry.loanId}'),
      width: double.infinity,
      padding: const EdgeInsets.all(10),
      decoration: BoxDecoration(
        border: Border.all(color: Theme.of(context).colorScheme.outlineVariant),
        borderRadius: BorderRadius.circular(10),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(status, style: Theme.of(context).textTheme.titleSmall),
          Text('Recorded by: $recorder'),
          if (entry.todayIsLocked as bool) const Text('Entry: Locked'),
        ],
      ),
    );
  }
}

bool _isSevenBySevenLoan(String value) {
  final normalized = value.toLowerCase().replaceAll(' ', '');
  return normalized.contains('7x7') || normalized.contains('7×7');
}

String _money(double value) => '₱${value.toStringAsFixed(2)}';
