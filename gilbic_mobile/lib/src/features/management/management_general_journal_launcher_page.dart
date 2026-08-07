import 'package:flutter/material.dart';
import 'package:gilbic_mobile/src/core/auth/user_session.dart';
import 'package:gilbic_mobile/src/core/device/device_identity.dart';
import 'package:gilbic_mobile/src/core/management/financial_accounting_repository.dart';
import 'package:gilbic_mobile/src/core/network/spina_api.dart';
import 'package:gilbic_mobile/src/features/management/management_general_journal_page.dart';

class ManagementGeneralJournalLauncherPage extends StatefulWidget {
  const ManagementGeneralJournalLauncherPage({
    required this.session,
    required this.deviceIdentityProvider,
    super.key,
  });

  final UserSession session;
  final DeviceIdentityProvider deviceIdentityProvider;

  @override
  State<ManagementGeneralJournalLauncherPage> createState() =>
      _ManagementGeneralJournalLauncherPageState();
}

class _ManagementGeneralJournalLauncherPageState
    extends State<ManagementGeneralJournalLauncherPage> {
  String? _error;
  Widget? _page;

  @override
  void initState() {
    super.initState();
    _load();
  }

  Future<void> _load() async {
    setState(() => _error = null);
    try {
      final identity = await widget.deviceIdentityProvider.load();
      final overview = await SpinaFinancialAccountingRepository().loadOverview(
        widget.session,
        deviceId: identity.installationId,
      );
      if (mounted) {
        setState(() {
          _page = ManagementGeneralJournalPage(
            session: widget.session,
            deviceIdentityProvider: widget.deviceIdentityProvider,
            accounts: overview.accounts,
            periods: overview.fiscalPeriods,
          );
        });
      }
    } on SpinaApiException catch (error) {
      if (mounted) {
        setState(() => _error = error.message);
      }
    } on Object {
      if (mounted) {
        setState(() => _error = 'General Journal accounting context could not be loaded.');
      }
    }
  }

  @override
  Widget build(BuildContext context) {
    final page = _page;
    if (page != null) {
      return page;
    }
    return Scaffold(
      appBar: AppBar(title: const Text('General Journal')),
      body: Center(
        child: _error == null
            ? const CircularProgressIndicator()
            : Padding(
                padding: const EdgeInsets.all(24),
                child: Column(
                  mainAxisSize: MainAxisSize.min,
                  children: [
                    Icon(
                      Icons.error_outline,
                      size: 48,
                      color: Theme.of(context).colorScheme.error,
                    ),
                    const SizedBox(height: 12),
                    Text(_error!, textAlign: TextAlign.center),
                    const SizedBox(height: 16),
                    FilledButton.icon(
                      onPressed: _load,
                      icon: const Icon(Icons.refresh),
                      label: const Text('Try again'),
                    ),
                  ],
                ),
              ),
      ),
    );
  }
}
