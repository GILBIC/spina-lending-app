import 'package:flutter/material.dart';
import 'package:gilbic_mobile/src/core/auth/user_session.dart';
import 'package:gilbic_mobile/src/core/device/device_identity.dart';
import 'package:gilbic_mobile/src/core/management/additional_tax_repository.dart';
import 'package:gilbic_mobile/src/core/management/tax_evidence_repository.dart';
import 'package:gilbic_mobile/src/core/management/tax_adjustment_repository.dart';
import 'package:gilbic_mobile/src/core/management/tax_liability_repository.dart';
import 'package:gilbic_mobile/src/core/management/tax_settlement_repository.dart';
import 'package:gilbic_mobile/src/core/management/tax_recoverable_repository.dart';
import 'package:gilbic_mobile/src/features/management/management_tax_adjustment_page.dart';
import 'package:gilbic_mobile/src/features/management/management_additional_tax_page.dart';
import 'package:gilbic_mobile/src/features/management/management_tax_evidence_page.dart';
import 'package:gilbic_mobile/src/features/management/management_tax_liability_page.dart';
import 'package:gilbic_mobile/src/features/management/management_tax_settlement_page.dart';
import 'package:gilbic_mobile/src/features/management/management_tax_recoverable_page.dart';

class ManagementTaxAccountingPage extends StatelessWidget {
  const ManagementTaxAccountingPage({
    required this.session,
    required this.deviceIdentityProvider,
    this.evidenceRepository,
    this.liabilityRepository,
    this.settlementRepository,
    this.adjustmentRepository,
    this.additionalTaxRepository,
    this.taxRecoverableRepository,
    super.key,
  });

  final UserSession session;
  final DeviceIdentityProvider deviceIdentityProvider;
  final TaxEvidenceRepository? evidenceRepository;
  final TaxLiabilityRepository? liabilityRepository;
  final TaxSettlementRepository? settlementRepository;
  final TaxAdjustmentRepository? adjustmentRepository;
  final AdditionalTaxRepository? additionalTaxRepository;
  final TaxRecoverableRepository? taxRecoverableRepository;

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
          Card(
            child: ListTile(
              key: const Key('tax-settlement-workspace'),
              leading: const Icon(Icons.receipt_long_outlined),
              title: const Text('Tax returns & settlements'),
              subtitle: const Text(
                'Compose returns from exact posted liabilities, retain full-payment evidence, then prepare and post separately.',
              ),
              trailing: const Icon(Icons.chevron_right),
              onTap: () => Navigator.of(context).push<void>(
                MaterialPageRoute<void>(
                  builder: (context) => ManagementTaxSettlementPage(
                    session: session,
                    deviceIdentityProvider: deviceIdentityProvider,
                    repository: settlementRepository,
                  ),
                ),
              ),
            ),
          ),
          const SizedBox(height: 10),
          Card(
            child: ListTile(
              key: const Key('tax-adjustment-workspace'),
              leading: const Icon(Icons.rule_folder_outlined),
              title: const Text('Tax corrections'),
              subtitle: const Text(
                'Use server-derived stale/current evidence pairs for protected reversals or Tax Recoverable corrections.',
              ),
              trailing: const Icon(Icons.chevron_right),
              onTap: () => Navigator.of(context).push<void>(
                MaterialPageRoute<void>(
                  builder: (context) => ManagementTaxAdjustmentPage(
                    session: session,
                    deviceIdentityProvider: deviceIdentityProvider,
                    repository: adjustmentRepository,
                  ),
                ),
              ),
            ),
          ),
          const SizedBox(height: 10),
          Card(
            child: ListTile(
              key: const Key('additional-tax-workspace'),
              leading: const Icon(Icons.trending_up),
              title: const Text('Additional tax'),
              subtitle: const Text(
                'Retain upward-amendment evidence, post the additional liability, then settle the exact required payment.',
              ),
              trailing: const Icon(Icons.chevron_right),
              onTap: () => Navigator.of(context).push<void>(
                MaterialPageRoute<void>(
                  builder: (context) => ManagementAdditionalTaxPage(
                    session: session,
                    deviceIdentityProvider: deviceIdentityProvider,
                    repository: additionalTaxRepository,
                  ),
                ),
              ),
            ),
          ),
          const SizedBox(height: 10),
          Card(
            child: ListTile(
              key: const Key('tax-recoverable-workspace'),
              leading: const Icon(Icons.account_balance_wallet_outlined),
              title: const Text('Tax Recoverable'),
              subtitle: const Text(
                'Realize one exact posted 1130 balance by protected cash refund or same-tax-type credit application.',
              ),
              trailing: const Icon(Icons.chevron_right),
              onTap: () => Navigator.of(context).push<void>(
                MaterialPageRoute<void>(
                  builder: (context) => ManagementTaxRecoverablePage(
                    session: session,
                    deviceIdentityProvider: deviceIdentityProvider,
                    repository: taxRecoverableRepository,
                  ),
                ),
              ),
            ),
          ),
        ],
      ),
    ),
  );
}
