import 'package:flutter/material.dart';
import 'package:gilbic_mobile/src/core/auth/user_session.dart';
import 'package:gilbic_mobile/src/core/device/device_identity.dart';
import 'package:gilbic_mobile/src/core/management/tax_evidence_repository.dart';
import 'package:gilbic_mobile/src/core/management/tax_liability_repository.dart';
import 'package:gilbic_mobile/src/features/management/management_tax_evidence_page.dart';
import 'package:gilbic_mobile/src/features/management/management_tax_liability_page.dart';

class ManagementTaxAccountingPage extends StatelessWidget {
  const ManagementTaxAccountingPage({
    required this.session,
    required this.deviceIdentityProvider,
    this.evidenceRepository,
    this.liabilityRepository,
    super.key,
  });

  final UserSession session;
  final DeviceIdentityProvider deviceIdentityProvider;
  final TaxEvidenceRepository? evidenceRepository;
  final TaxLiabilityRepository? liabilityRepository;

  @override
  Widget build(BuildContext context) => Scaffold(
    appBar: AppBar(title: const Text('Tax Accounting')),
    body: SafeArea(
      child: ListView(
        padding: const EdgeInsets.all(16),
        children: <Widget>[
          const Card(
            child: Padding(
              padding: EdgeInsets.all(14),
              child: Text(
                'Use retained current tax evidence only. SPINA never invents a legal rate or tax base, and automatic source posting remains disabled.',
              ),
            ),
          ),
          const SizedBox(height: 10),
          Card(
            child: ListTile(
              key: const Key('tax-evidence-workspace'),
              leading: const Icon(Icons.fact_check_outlined),
              title: const Text('Tax evidence'),
              subtitle: const Text(
                'Review approved rules, DST sources and exact percentage-tax cash allocations.',
              ),
              trailing: const Icon(Icons.chevron_right),
              onTap: () => Navigator.of(context).push<void>(
                MaterialPageRoute<void>(
                  builder: (context) => ManagementTaxEvidencePage(
                    session: session,
                    deviceIdentityProvider: deviceIdentityProvider,
                    repository: evidenceRepository,
                  ),
                ),
              ),
            ),
          ),
          const SizedBox(height: 10),
          Card(
            child: ListTile(
              key: const Key('tax-liability-workspace'),
              leading: const Icon(Icons.account_balance_outlined),
              title: const Text('Tax liabilities'),
              subtitle: const Text(
                'Prepare and post exact evidence-backed tax liabilities through the protected General Journal.',
              ),
              trailing: const Icon(Icons.chevron_right),
              onTap: () => Navigator.of(context).push<void>(
                MaterialPageRoute<void>(
                  builder: (context) => ManagementTaxLiabilityPage(
                    session: session,
                    deviceIdentityProvider: deviceIdentityProvider,
                    repository: liabilityRepository,
                  ),
                ),
              ),
            ),
          ),
          const SizedBox(height: 10),
          const Card(
            child: Padding(
              padding: EdgeInsets.all(14),
              child: Text(
                'Tax returns/payments, settlements, corrections, amendments and Tax Recoverable realization remain separate protected workflows and are not performed on these screens.',
              ),
            ),
          ),
        ],
      ),
    ),
  );
}
