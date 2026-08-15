import 'dart:math';

import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:gilbic_mobile/src/core/auth/user_session.dart';
import 'package:gilbic_mobile/src/core/device/device_identity.dart';
import 'package:gilbic_mobile/src/core/loans/client_loan.dart';
import 'package:gilbic_mobile/src/core/loans/client_loan_repository.dart';
import 'package:gilbic_mobile/src/core/network/spina_api.dart';
import 'package:gilbic_mobile/src/core/payments/client_gcash.dart';
import 'package:gilbic_mobile/src/core/payments/client_gcash_repository.dart';
import 'package:gilbic_mobile/src/theme/spina_theme.dart';
import 'package:url_launcher/url_launcher.dart';

class ClientGcashPaymentPage extends StatefulWidget {
  const ClientGcashPaymentPage({
    required this.session,
    required this.deviceIdentityProvider,
    this.gcashRepository,
    this.loanRepository,
    super.key,
  });

  final UserSession session;
  final DeviceIdentityProvider deviceIdentityProvider;
  final ClientGcashRepository? gcashRepository;
  final ClientLoanRepository? loanRepository;

  @override
  State<ClientGcashPaymentPage> createState() => _ClientGcashPaymentPageState();
}

class _ClientGcashPaymentPageState extends State<ClientGcashPaymentPage> {
  late final ClientGcashRepository _gcashRepository;
  late final ClientLoanRepository _loanRepository;
  final Map<String, TextEditingController> _amountControllers =
      <String, TextEditingController>{};
  final Set<String> _selectedLoanIds = <String>{};

  ClientGcashCapability? _capability;
  ClientLoanPortfolio? _portfolio;
  ClientGcashIntent? _intent;
  String? _deviceId;
  String? _errorMessage;
  bool _loading = true;
  bool _submitting = false;

  @override
  void initState() {
    super.initState();
    _gcashRepository = widget.gcashRepository ?? SpinaClientGcashRepository();
    _loanRepository = widget.loanRepository ?? SpinaClientLoanRepository();
    _load();
  }

  @override
  void dispose() {
    for (final controller in _amountControllers.values) {
      controller.dispose();
    }
    super.dispose();
  }

  Future<void> _load() async {
    if (mounted) {
      setState(() {
        _loading = true;
        _errorMessage = null;
      });
    }
    try {
      final identity = await widget.deviceIdentityProvider.load();
      final capability = await _gcashRepository.loadCapability(
        widget.session,
        deviceId: identity.installationId,
      );
      final portfolio = await _loanRepository.loadPortfolio(
        widget.session,
        deviceId: identity.installationId,
      );
      if (!mounted) {
        return;
      }
      _configureLoans(portfolio.activeLoans);
      setState(() {
        _deviceId = identity.installationId;
        _capability = capability;
        _portfolio = portfolio;
      });
    } on SpinaApiException catch (error) {
      if (mounted) {
        setState(() => _errorMessage = error.message);
      }
    } on Object {
      if (mounted) {
        setState(() => _errorMessage = 'GCash payment could not be loaded.');
      }
    } finally {
      if (mounted) {
        setState(() => _loading = false);
      }
    }
  }

  void _configureLoans(List<ClientLoan> loans) {
    final keepIds = loans.map((loan) => loan.loanId).toSet();
    for (final entry in _amountControllers.entries.toList()) {
      if (!keepIds.contains(entry.key)) {
        entry.value.dispose();
        _amountControllers.remove(entry.key);
        _selectedLoanIds.remove(entry.key);
      }
    }
    for (final loan in loans) {
      final suggested = min(loan.dailyAmount, loan.remainingBalance);
      _amountControllers.putIfAbsent(
        loan.loanId,
        () => TextEditingController(text: suggested.toStringAsFixed(2)),
      );
      if (loans.length == 1) {
        _selectedLoanIds.add(loan.loanId);
      }
    }
  }

  List<ClientGcashAllocation> _allocations() {
    final portfolio = _portfolio;
    if (portfolio == null) {
      return const <ClientGcashAllocation>[];
    }
    final allocations = <ClientGcashAllocation>[];
    for (final loan in portfolio.activeLoans) {
      if (!_selectedLoanIds.contains(loan.loanId)) {
        continue;
      }
      final raw = _amountControllers[loan.loanId]?.text.replaceAll(',', '').trim();
      final amount = double.tryParse(raw ?? '') ?? 0;
      if (amount > 0) {
        allocations.add(ClientGcashAllocation(loanId: loan.loanId, amount: amount));
      }
    }
    return allocations;
  }

  double get _total => _allocations().fold<double>(
        0,
        (total, allocation) => total + allocation.amount,
      );

  Future<void> _createPayment() async {
    final capability = _capability;
    final deviceId = _deviceId;
    final allocations = _allocations();
    if (_submitting || capability == null || deviceId == null) {
      return;
    }
    if (!capability.paymentAvailable) {
      _showMessage(capability.message);
      return;
    }
    if (allocations.isEmpty || _total <= 0) {
      _showMessage('Select at least one loan and enter an amount above zero.');
      return;
    }

    setState(() {
      _submitting = true;
      _errorMessage = null;
    });
    try {
      final intent = await _gcashRepository.createIntent(
        widget.session,
        deviceId: deviceId,
        idempotencyKey: _newIdempotencyKey(),
        allocations: allocations,
      );
      if (!mounted) {
        return;
      }
      setState(() => _intent = intent);
      await _openCheckoutIfAvailable(intent);
    } on SpinaApiException catch (error) {
      if (mounted) {
        setState(() => _errorMessage = error.message);
      }
    } on Object {
      if (mounted) {
        setState(() => _errorMessage = 'GCash checkout could not be started.');
      }
    } finally {
      if (mounted) {
        setState(() => _submitting = false);
      }
    }
  }

  Future<void> _openCheckoutIfAvailable(ClientGcashIntent intent) async {
    final urlText = intent.checkoutUrl?.trim() ?? '';
    if (urlText.isEmpty) {
      return;
    }
    final uri = Uri.tryParse(urlText);
    if (uri == null || !uri.hasScheme) {
      _showMessage('The payment provider returned an invalid checkout link.');
      return;
    }
    final launched = await launchUrl(
      uri,
      mode: LaunchMode.inAppBrowserView,
    );
    if (!launched && mounted) {
      _showMessage('GCash checkout could not be opened on this device.');
    }
  }

  Future<void> _refreshIntent() async {
    final intent = _intent;
    final deviceId = _deviceId;
    if (intent == null || deviceId == null || _submitting) {
      return;
    }
    setState(() => _submitting = true);
    try {
      final refreshed = await _gcashRepository.loadIntent(
        widget.session,
        deviceId: deviceId,
        intentId: intent.intentId,
      );
      if (mounted) {
        setState(() => _intent = refreshed);
      }
    } on SpinaApiException catch (error) {
      if (mounted) {
        setState(() => _errorMessage = error.message);
      }
    } finally {
      if (mounted) {
        setState(() => _submitting = false);
      }
    }
  }

  String _newIdempotencyKey() {
    final random = Random.secure();
    final suffix = List<int>.generate(4, (_) => random.nextInt(1 << 32))
        .map((part) => part.toRadixString(16).padLeft(8, '0'))
        .join();
    return 'mobile-${widget.session.userId}-${DateTime.now().toUtc().microsecondsSinceEpoch}-$suffix';
  }

  void _showMessage(String message) {
    if (!mounted) {
      return;
    }
    ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text(message)));
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('Pay with GCash'),
        actions: [
          IconButton(
            tooltip: 'Refresh',
            onPressed: _loading || _submitting ? null : _load,
            icon: const Icon(Icons.refresh_rounded),
          ),
        ],
      ),
      body: SafeArea(child: _buildBody(context)),
    );
  }

  Widget _buildBody(BuildContext context) {
    if (_loading && _capability == null) {
      return const Center(child: CircularProgressIndicator());
    }
    final capability = _capability;
    final portfolio = _portfolio;
    if (capability == null || portfolio == null) {
      return _ErrorState(
        message: _errorMessage ?? 'GCash payment could not be loaded.',
        onRetry: _load,
      );
    }

    return ListView(
      padding: const EdgeInsets.fromLTRB(16, 14, 16, 28),
      children: [
        _ProviderStatusCard(capability: capability),
        if (_errorMessage != null) ...[
          const SizedBox(height: 10),
          Container(
            padding: const EdgeInsets.all(12),
            decoration: BoxDecoration(
              color: Theme.of(context).colorScheme.errorContainer,
              borderRadius: BorderRadius.circular(14),
            ),
            child: Text(_errorMessage!),
          ),
        ],
        const SizedBox(height: 14),
        Text(
          portfolio.clientName,
          style: Theme.of(context).textTheme.titleLarge,
        ),
        const SizedBox(height: 4),
        Text(
          'Choose the active loan(s) you want to pay. SPINA validates every amount again on the backend.',
          style: Theme.of(context).textTheme.bodySmall,
        ),
        const SizedBox(height: 12),
        if (portfolio.activeLoans.isEmpty)
          const Card(
            child: Padding(
              padding: EdgeInsets.all(20),
              child: Text('There are no active loans available for payment.'),
            ),
          )
        else
          for (final loan in portfolio.activeLoans) ...[
            _LoanPaymentSelector(
              loan: loan,
              selected: _selectedLoanIds.contains(loan.loanId),
              controller: _amountControllers[loan.loanId]!,
              enabled: capability.paymentAvailable && !_submitting,
              onChanged: (selected) {
                setState(() {
                  if (selected) {
                    _selectedLoanIds.add(loan.loanId);
                  } else {
                    _selectedLoanIds.remove(loan.loanId);
                  }
                });
              },
              onAmountChanged: (_) => setState(() {}),
            ),
            const SizedBox(height: 9),
          ],
        const SizedBox(height: 8),
        Container(
          padding: const EdgeInsets.all(16),
          decoration: BoxDecoration(
            color: SpinaTheme.brandPinkSoft,
            borderRadius: BorderRadius.circular(18),
          ),
          child: Row(
            children: [
              const Expanded(
                child: Text(
                  'GCash total',
                  style: TextStyle(fontWeight: FontWeight.w800),
                ),
              ),
              Text(
                _money(_total),
                style: Theme.of(context).textTheme.headlineSmall?.copyWith(
                      color: SpinaTheme.brandPinkDark,
                      fontWeight: FontWeight.w900,
                    ),
              ),
            ],
          ),
        ),
        const SizedBox(height: 12),
        FilledButton.icon(
          key: const Key('client-gcash-start-payment'),
          onPressed: capability.paymentAvailable && !_submitting
              ? _createPayment
              : null,
          icon: _submitting
              ? const SizedBox.square(
                  dimension: 18,
                  child: CircularProgressIndicator(
                    strokeWidth: 2,
                    color: Colors.white,
                  ),
                )
              : const Icon(Icons.account_balance_wallet_outlined),
          label: Text(
            capability.paymentAvailable
                ? (_submitting ? 'Preparing GCash...' : 'Continue to GCash')
                : 'GCash provider not connected',
          ),
        ),
        const SizedBox(height: 9),
        Text(
          capability.officialPaymentRule,
          style: Theme.of(context).textTheme.bodySmall,
          textAlign: TextAlign.center,
        ),
        if (_intent != null) ...[
          const SizedBox(height: 18),
          _IntentStatusCard(
            intent: _intent!,
            loading: _submitting,
            onOpenCheckout: () => _openCheckoutIfAvailable(_intent!),
            onRefresh: _refreshIntent,
          ),
        ],
      ],
    );
  }
}

class _ProviderStatusCard extends StatelessWidget {
  const _ProviderStatusCard({required this.capability});

  final ClientGcashCapability capability;

  @override
  Widget build(BuildContext context) {
    final connected = capability.paymentAvailable;
    return Container(
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        gradient: const LinearGradient(
          colors: <Color>[Color(0xFFFFFBFD), Color(0xFFFFEEF5)],
        ),
        borderRadius: BorderRadius.circular(20),
        border: Border.all(color: const Color(0xFFF0D6E1)),
      ),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Container(
            width: 46,
            height: 46,
            decoration: BoxDecoration(
              color: Colors.white,
              borderRadius: BorderRadius.circular(15),
            ),
            child: const Icon(
              Icons.account_balance_wallet_rounded,
              color: SpinaTheme.brandPinkDark,
            ),
          ),
          const SizedBox(width: 12),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Row(
                  children: [
                    Expanded(
                      child: Text(
                        'Direct GCash payment',
                        style: Theme.of(context).textTheme.titleMedium,
                      ),
                    ),
                    Container(
                      padding: const EdgeInsets.symmetric(
                        horizontal: 8,
                        vertical: 4,
                      ),
                      decoration: BoxDecoration(
                        color: connected
                            ? const Color(0xFFE8F6EF)
                            : const Color(0xFFF2EDF0),
                        borderRadius: BorderRadius.circular(999),
                      ),
                      child: Text(
                        capability.isSandbox
                            ? 'SANDBOX'
                            : connected
                                ? 'READY'
                                : 'NOT CONNECTED',
                        style: TextStyle(
                          color: connected
                              ? SpinaTheme.success
                              : SpinaTheme.inkMuted,
                          fontWeight: FontWeight.w800,
                          fontSize: 10,
                        ),
                      ),
                    ),
                  ],
                ),
                const SizedBox(height: 5),
                Text(capability.message),
                if (!connected) ...[
                  const SizedBox(height: 7),
                  Text(
                    'The screen and backend adapter are ready. Business-provider credentials will be connected on the server later; they are never stored in the mobile app.',
                    style: Theme.of(context).textTheme.bodySmall,
                  ),
                ],
              ],
            ),
          ),
        ],
      ),
    );
  }
}

class _LoanPaymentSelector extends StatelessWidget {
  const _LoanPaymentSelector({
    required this.loan,
    required this.selected,
    required this.controller,
    required this.enabled,
    required this.onChanged,
    required this.onAmountChanged,
  });

  final ClientLoan loan;
  final bool selected;
  final TextEditingController controller;
  final bool enabled;
  final ValueChanged<bool> onChanged;
  final ValueChanged<String> onAmountChanged;

  @override
  Widget build(BuildContext context) {
    return Card(
      child: Padding(
        padding: const EdgeInsets.fromLTRB(12, 10, 12, 12),
        child: Column(
          children: [
            Row(
              children: [
                Checkbox(
                  value: selected,
                  onChanged: enabled
                      ? (value) => onChanged(value ?? false)
                      : null,
                ),
                Expanded(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text(
                        loan.loanTypeName,
                        style: const TextStyle(fontWeight: FontWeight.w900),
                      ),
                      Text(
                        '${loan.loanNumber} • balance ${_money(loan.remainingBalance)}',
                        style: Theme.of(context).textTheme.bodySmall,
                      ),
                    ],
                  ),
                ),
                Text(
                  'Daily ${_money(loan.dailyAmount)}',
                  style: const TextStyle(fontWeight: FontWeight.w700),
                ),
              ],
            ),
            if (selected) ...[
              const SizedBox(height: 8),
              TextField(
                key: Key('client-gcash-amount-${loan.loanId}'),
                controller: controller,
                enabled: enabled,
                keyboardType: const TextInputType.numberWithOptions(decimal: true),
                inputFormatters: <TextInputFormatter>[
                  FilteringTextInputFormatter.allow(RegExp(r'[0-9.,]')),
                ],
                onChanged: onAmountChanged,
                decoration: InputDecoration(
                  labelText: 'Amount for ${loan.loanTypeName}',
                  prefixText: '₱ ',
                  helperText: 'Maximum ${_money(loan.remainingBalance)}',
                ),
              ),
            ],
          ],
        ),
      ),
    );
  }
}

class _IntentStatusCard extends StatelessWidget {
  const _IntentStatusCard({
    required this.intent,
    required this.loading,
    required this.onOpenCheckout,
    required this.onRefresh,
  });

  final ClientGcashIntent intent;
  final bool loading;
  final VoidCallback onOpenCheckout;
  final VoidCallback onRefresh;

  @override
  Widget build(BuildContext context) {
    final official = intent.officialPaymentPosted;
    final verified = intent.isVerified;
    final pending = intent.isPending;
    final title = official
        ? 'Payment posted by SPINA'
        : verified
            ? 'GCash verified — SPINA posting pending'
            : pending
                ? 'Waiting for GCash verification'
                : 'GCash status: ${intent.status}';
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            Row(
              children: [
                Icon(
                  official
                      ? Icons.verified_rounded
                      : Icons.hourglass_top_rounded,
                  color: official ? SpinaTheme.success : SpinaTheme.brandPinkDark,
                ),
                const SizedBox(width: 9),
                Expanded(
                  child: Text(
                    title,
                    style: Theme.of(context).textTheme.titleMedium,
                  ),
                ),
              ],
            ),
            const SizedBox(height: 7),
            Text('Amount: ${_money(intent.amount)}'),
            if (intent.providerReference != null)
              Text('Provider reference: ${intent.providerReference}'),
            if (intent.expiresAt != null)
              Text('Checkout expires: ${intent.expiresAt!.toLocal()}'),
            if (!official) ...[
              const SizedBox(height: 8),
              const Text(
                'Do not treat this as an official loan payment yet. Your balance changes only after SPINA receives and verifies the provider settlement through the protected backend flow.',
              ),
            ],
            if (intent.qrValue != null && intent.qrValue!.isNotEmpty) ...[
              const SizedBox(height: 10),
              OutlinedButton.icon(
                onPressed: () async {
                  await Clipboard.setData(ClipboardData(text: intent.qrValue!));
                },
                icon: const Icon(Icons.copy_rounded),
                label: const Text('Copy GCash QR/payment code'),
              ),
            ],
            if (intent.checkoutUrl != null && intent.checkoutUrl!.isNotEmpty) ...[
              const SizedBox(height: 8),
              OutlinedButton.icon(
                onPressed: loading ? null : onOpenCheckout,
                icon: const Icon(Icons.open_in_new_rounded),
                label: const Text('Open GCash checkout again'),
              ),
            ],
            const SizedBox(height: 8),
            FilledButton.tonalIcon(
              onPressed: loading ? null : onRefresh,
              icon: const Icon(Icons.refresh_rounded),
              label: const Text('Refresh payment status'),
            ),
          ],
        ),
      ),
    );
  }
}

class _ErrorState extends StatelessWidget {
  const _ErrorState({required this.message, required this.onRetry});

  final String message;
  final VoidCallback onRetry;

  @override
  Widget build(BuildContext context) {
    return Center(
      child: Padding(
        padding: const EdgeInsets.all(24),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            const Icon(Icons.account_balance_wallet_outlined, size: 48),
            const SizedBox(height: 12),
            Text(message, textAlign: TextAlign.center),
            const SizedBox(height: 16),
            FilledButton.icon(
              onPressed: onRetry,
              icon: const Icon(Icons.refresh_rounded),
              label: const Text('Try again'),
            ),
          ],
        ),
      ),
    );
  }
}

String _money(double value) => '₱${value.toStringAsFixed(2)}';
