import 'package:flutter/material.dart';
import 'package:gilbic_mobile/src/core/auth/user_session.dart';
import 'package:gilbic_mobile/src/core/device/device_identity.dart';
import 'package:gilbic_mobile/src/core/network/spina_api.dart';
import 'package:gilbic_mobile/src/core/office/office_repository.dart';
import 'package:gilbic_mobile/src/features/office/office_application_page.dart';
import 'package:gilbic_mobile/src/features/office/office_cif_page.dart';
import 'package:gilbic_mobile/src/features/office/office_first_loan_page.dart';
import 'package:gilbic_mobile/src/features/office/office_intake_page.dart';
import 'package:gilbic_mobile/src/features/office/office_widgets.dart';

/// Shared authorized office workflow for Management and Employee.
class OfficeWorkspacePage extends StatefulWidget {
  const OfficeWorkspacePage({
    required this.session,
    required this.deviceIdentityProvider,
    this.repository,
    super.key,
  });
  final UserSession session;
  final DeviceIdentityProvider deviceIdentityProvider;
  final OfficeRepository? repository;
  @override
  State<OfficeWorkspacePage> createState() => _OfficeWorkspacePageState();
}

class _OfficeWorkspacePageState extends OfficeScreenState<OfficeWorkspacePage> {
  final fields = OfficeFields();
  late final OfficeRepository repository;
  @override
  void initState() {
    super.initState();
    repository = widget.repository ?? OfficeRepository();
  }

  @override
  void clearPrivate() => fields.clear();
  @override
  void dispose() {
    fields.dispose();
    super.dispose();
  }

  Future<void> _open(String stage) async {
    final result = await operation.run(() async {
      final identity = OfficeIdentity(
        widget.session,
        (await widget.deviceIdentityProvider.load()).installationId,
      );
      if (!identity.allowed) {
        throw const SpinaApiException(
          'Authorized office access is required.',
          statusCode: 403,
        );
      }
      OfficeRecord? selected;
      if (['cif', 'application', 'loan'].contains(stage)) {
        if (fields.text('intake-reference').isEmpty) {
          throw const SpinaApiException(
            'Enter the office intake reference.',
            statusCode: 422,
          );
        }
        selected = await repository.selectClient(
          identity,
          fields.text('intake-reference'),
        );
      }
      if (stage == 'loan' && fields.text('application-reference').isEmpty) {
        throw const SpinaApiException(
          'Enter the loan application reference.',
          statusCode: 422,
        );
      }
      return (identity, selected);
    });
    if (!mounted || result == null) return;
    final (identity, selected) = result;
    final page = switch (stage) {
      'new' => OfficeIntakePage(actor: identity, repository: repository),
      'intake' => OfficeIntakePage(
        actor: identity,
        repository: repository,
        reference: fields.text('intake-reference'),
      ),
      'cif' => OfficeCifPage(
        actor: identity,
        repository: repository,
        clientId: selected!['client_id'],
      ),
      'application' => OfficeApplicationPage(
        actor: identity,
        repository: repository,
        clientId: selected!['client_id'],
        applicationReference: fields.text('application-reference'),
      ),
      _ => OfficeFirstLoanPage(
        actor: identity,
        repository: repository,
        clientId: selected!['client_id'],
        applicationReference: fields.text('application-reference'),
      ),
    };
    await Navigator.of(
      context,
    ).push<void>(MaterialPageRoute(builder: (_) => page));
    if (mounted && identity.accessDenied) denyAccess();
  }

  @override
  Widget build(BuildContext context) {
    final allowed = OfficeIdentity(widget.session, '').allowed;
    return screen(
      'Office workflow',
      !allowed
          ? [
              const Text(
                'Authorized office access and onboarding review permission are required.',
              ),
            ]
          : [
              const Text(
                'Complete office intake, review the applicant’s saved information, and follow the exact approved first-loan record. Each action uses your current server permissions.',
              ),
              const SizedBox(height: 16),
              officeButton(
                'New office intake',
                operation.busy ? null : () => _open('new'),
                primary: true,
              ),
              officeField(
                fields,
                'intake-reference',
                'Office intake reference',
                enabled: !operation.busy,
              ),
              officeField(
                fields,
                'application-reference',
                'Loan application reference',
                enabled: !operation.busy,
              ),
              officeButton(
                'Office intake and requirements',
                operation.busy ? null : () => _open('intake'),
              ),
              officeButton(
                'CIF review',
                operation.busy ? null : () => _open('cif'),
              ),
              officeButton(
                'Application entry and review',
                operation.busy ? null : () => _open('application'),
              ),
              officeButton(
                'First-loan approval and release',
                operation.busy ? null : () => _open('loan'),
              ),
            ],
    );
  }
}
