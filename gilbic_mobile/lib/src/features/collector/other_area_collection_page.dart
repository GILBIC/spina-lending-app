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
  bool _searching = false;
  bool _searched = false;
  int _searchGeneration = 0;

  static const String _allAreas = 'All areas';
  static const String _allLoans = 'All loans';

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

  List<OtherAreaClient> get _visibleResults {
    final query = _searchController.text.trim().toLowerCase();
    final filtered = _results.where((client) {
      if (_selectedArea != _allAreas && client.entry.area != _selectedArea) {
        return false;
      }
      if (_selectedLoanType != _allLoans &&
          client.entry.loanType != _selectedLoanType) {
        return false;
      }
      return true;
    }).toList(growable: false);

    filtered.sort((left, right) {
      final leftName = left.entry.clientName.toLowerCase();
      final rightName = right.entry.clientName.toLowerCase();
      final leftCode = left.clientCode.toLowerCase();
      final rightCode = right.clientCode.toLowerCase();
      final leftExact = leftName == query || leftCode == query;
      final rightExact = rightName == query || rightCode == query;
      if (leftExact != rightExact) {
        return leftExact ? -1 : 1;
      }
      final leftStarts = leftName.startsWith(query) || leftCode.startsWith(query);
      final rightStarts = rightName.startsWith(query) || rightCode.startsWith(query);
      if (leftStarts != rightStarts) {
        return leftStarts ? -1 : 1;
      }
      final nameOrder = leftName.compareTo(rightName);
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
  }

  @override
  void dispose() {
    _searchDebounce?.cancel();
    _searchController.dispose();
    super.dispose();
  }

  void _onSearchChanged(String value) {
    _searchDebounce?.cancel();
    final query = value.trim();
    if (query.length < 2) {
      _searchGeneration += 1;
      setState(() {
        _results = const <OtherAreaClient>[];
        _searched = false;
        _searching = false;
        _errorMessage = null;
        _selectedArea = _allAreas;
        _selectedLoanType = _allLoans;
      });
      return;
    }
    _searchDebounce = Timer(const Duration(milliseconds: 350), _search);
  }

  void _clearSearch() {
    _searchDebounce?.cancel();
    _searchController.clear();
    _searchGeneration += 1;
    setState(() {
      _results = const <OtherAreaClient>[];
      _searched = false;
      _searching = false;
      _errorMessage = null;
      _selectedArea = _allAreas;
      _selectedLoanType = _allLoans;
    });
  }

  Future<void> _search({bool showValidation = false}) async {
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

    final generation = ++_searchGeneration;
    setState(() {
      _searching = true;
      _errorMessage = null;
    });
    try {
      final results = await _repository.search(widget.session, query);
      if (!mounted || generation != _searchGeneration) {
        return;
      }
      setState(() {
        _results = results;
        _searched = true;
        _selectedArea = _allAreas;
        _selectedLoanType = _allLoans;
      });
    } on SpinaApiException catch (error) {
      if (!mounted || generation != _searchGeneration) {
        return;
      }
      setState(() {
        _errorMessage = error.message;
        _searched = true;
        _results = const <OtherAreaClient>[];
      });
    } on Object {
      if (!mounted || generation != _searchGeneration) {
        return;
      }
      setState(() {
        _errorMessage = _isManagement
            ? 'Clients could not be searched for direct payment entry.'
            : 'Other-area clients could not be searched.';
        _searched = true;
        _results = const <OtherAreaClient>[];
      });
    } finally {
      if (mounted && generation == _searchGeneration) {
        setState(() => _searching = false);
      }
    }
  }

  String? _blockedReason(OtherAreaClient client) {
    final entry = client.entry;
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
      return 'Refresh this search before recording the payment.';
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
              : 'Record another collector’s client?',
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
                  'Your name will remain the recorder. The assigned collector and '
                  'linked client will be notified after the payment is posted.',
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
      await _search(showValidation: true);
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: Text(_isManagement ? 'Direct Payment Entry' : 'Other Area Payment'),
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
                        : 'Use this only when a client pays a collector outside the client’s assigned area.',
                    style: Theme.of(context).textTheme.bodyMedium,
                  ),
                  const SizedBox(height: 12),
                  TextField(
                    key: const Key('other-area-search'),
                    controller: _searchController,
                    textInputAction: TextInputAction.search,
                    autocorrect: false,
                    onChanged: _onSearchChanged,
                    onSubmitted: (_) => _search(showValidation: true),
                    decoration: InputDecoration(
                      labelText: 'Find by name, code, phone, or area',
                      helperText: 'Results appear automatically after 2 characters.',
                      prefixIcon: const Icon(Icons.person_search),
                      suffixIcon: Row(
                        mainAxisSize: MainAxisSize.min,
                        children: [
                          if (_searchController.text.isNotEmpty)
                            IconButton(
                              tooltip: 'Clear search',
                              onPressed: _clearSearch,
                              icon: const Icon(Icons.clear),
                            ),
                          IconButton(
                            tooltip: 'Search now',
                            onPressed: _searching
                                ? null
                                : () => _search(showValidation: true),
                            icon: _searching
                                ? const SizedBox(
                                    width: 18,
                                    height: 18,
                                    child: CircularProgressIndicator(
                                      strokeWidth: 2,
                                    ),
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
                      style: Theme.of(context).textTheme.labelLarge,
                    ),
                    const SizedBox(height: 8),
                    Row(
                      children: [
                        Expanded(
                          child: DropdownButtonFormField<String>(
                            value: _areas.contains(_selectedArea)
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
                            value: _loanTypes.contains(_selectedLoanType)
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
    if (_searching && !_searched) {
      return const Center(child: CircularProgressIndicator());
    }
    if (!_searched) {
      return Center(
        child: Padding(
          padding: const EdgeInsets.all(24),
          child: Text(
            _isManagement
                ? 'Start typing the client name, code, phone, or area.'
                : 'Start typing. Your own assigned clients remain in Daily Route.',
            textAlign: TextAlign.center,
          ),
        ),
      );
    }
    if (_results.isEmpty) {
      return Center(
        child: Padding(
          padding: const EdgeInsets.all(24),
          child: Text(
            _isManagement
                ? 'No active client matched the search.'
                : 'No active other-area client matched the search.',
            textAlign: TextAlign.center,
          ),
        ),
      );
    }

    final visibleResults = _visibleResults;
    if (visibleResults.isEmpty) {
      return const Center(
        child: Padding(
          padding: EdgeInsets.all(24),
          child: Text(
            'No client matches the selected area and loan filters.',
            textAlign: TextAlign.center,
          ),
        ),
      );
    }

    return ListView.separated(
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
                    onPressed: blocked == null ? () => _openPayment(client) : null,
                    icon: const Icon(Icons.payments_outlined),
                    label: Text(
                      _isManagement ? 'Record direct payment' : 'Record payment',
                    ),
                  ),
                ),
              ],
            ),
          ),
        );
      },
    );
  }
}

bool _isSevenBySevenLoan(String value) {
  final normalized = value.toLowerCase().replaceAll(' ', '');
  return normalized.contains('7x7') || normalized.contains('7×7');
}

String _money(double value) => '₱${value.toStringAsFixed(2)}';
