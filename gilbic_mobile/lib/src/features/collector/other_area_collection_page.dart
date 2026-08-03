import 'package:flutter/material.dart';
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

  List<OtherAreaClient> _results = const <OtherAreaClient>[];
  String? _errorMessage;
  bool _searching = false;
  bool _searched = false;

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
    _searchController.dispose();
    super.dispose();
  }

  Future<void> _search() async {
    final query = _searchController.text.trim();
    if (query.length < 2 || _searching) {
      setState(() {
        _errorMessage = 'Enter at least two letters, a client code, phone, or area.';
      });
      return;
    }

    setState(() {
      _searching = true;
      _errorMessage = null;
    });
    try {
      final results = await _repository.search(widget.session, query);
      if (!mounted) {
        return;
      }
      setState(() {
        _results = results;
        _searched = true;
      });
    } on SpinaApiException catch (error) {
      if (!mounted) {
        return;
      }
      setState(() {
        _errorMessage = error.message;
        _searched = true;
        _results = const <OtherAreaClient>[];
      });
    } on Object {
      if (!mounted) {
        return;
      }
      setState(() {
        _errorMessage = 'Other-area clients could not be searched.';
        _searched = true;
        _results = const <OtherAreaClient>[];
      });
    } finally {
      if (mounted) {
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
        title: const Text('Record another collector’s client?'),
        content: Text(
          '${client.entry.clientName} is assigned to '
          '${client.assignedCollectorName}.\n\n'
          'Your name will remain the recorder. The assigned collector and linked '
          'client will be notified after the payment is posted.',
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
      await _search();
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('Other Area Payment')),
      body: SafeArea(
        child: Column(
          children: [
            Padding(
              padding: const EdgeInsets.fromLTRB(16, 16, 16, 8),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(
                    'Use this only when a client pays a collector outside the client’s assigned area.',
                    style: Theme.of(context).textTheme.bodyMedium,
                  ),
                  const SizedBox(height: 12),
                  TextField(
                    key: const Key('other-area-search'),
                    controller: _searchController,
                    enabled: !_searching,
                    textInputAction: TextInputAction.search,
                    onSubmitted: (_) => _search(),
                    decoration: InputDecoration(
                      labelText: 'Client name, code, phone, or area',
                      prefixIcon: const Icon(Icons.person_search),
                      suffixIcon: IconButton(
                        tooltip: 'Search',
                        onPressed: _searching ? null : _search,
                        icon: _searching
                            ? const SizedBox(
                                width: 18,
                                height: 18,
                                child: CircularProgressIndicator(strokeWidth: 2),
                              )
                            : const Icon(Icons.search),
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
      return const Center(
        child: Padding(
          padding: EdgeInsets.all(24),
          child: Text(
            'Search first. Your own assigned clients remain in Daily Route.',
            textAlign: TextAlign.center,
          ),
        ),
      );
    }
    if (_results.isEmpty) {
      return const Center(
        child: Padding(
          padding: EdgeInsets.all(24),
          child: Text(
            'No active other-area client matched the search.',
            textAlign: TextAlign.center,
          ),
        ),
      );
    }

    return ListView.separated(
      padding: const EdgeInsets.fromLTRB(12, 4, 12, 20),
      itemCount: _results.length,
      separatorBuilder: (_, __) => const SizedBox(height: 8),
      itemBuilder: (context, index) {
        final client = _results[index];
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
                  blocked ?? entry.collectionMessage,
                  style: Theme.of(context).textTheme.bodySmall,
                ),
                const SizedBox(height: 10),
                SizedBox(
                  width: double.infinity,
                  child: FilledButton.icon(
                    key: Key('record-other-area-${entry.loanId}'),
                    onPressed: blocked == null ? () => _openPayment(client) : null,
                    icon: const Icon(Icons.payments_outlined),
                    label: const Text('Record payment'),
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
