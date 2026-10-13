import 'package:gilbic_mobile/src/features/office/office_intake_authority.dart';
import 'package:gilbic_mobile/src/core/office/office_operation.dart';
import 'package:flutter/material.dart';
import 'package:gilbic_mobile/src/core/auth/user_session.dart';
import 'package:gilbic_mobile/src/core/device/device_identity.dart';
import 'package:gilbic_mobile/src/core/network/spina_api.dart';
import 'package:gilbic_mobile/src/core/office/office_repository.dart';
import 'package:gilbic_mobile/src/features/office/office_application_page.dart';
import 'package:gilbic_mobile/src/features/office/office_cif_page.dart';
import 'package:gilbic_mobile/src/features/office/office_first_loan_page.dart';
import 'package:gilbic_mobile/src/features/office/office_finder_page.dart';
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
  late OfficeRepository repository;
  OfficeOperation _localIntakeCreate = OfficeOperation();
  late OfficeOperation _intakeCreate;

  void _replaceCreate(OfficeOperation operation) {
    _intakeCreate.removeListener(_createChanged);
    _intakeCreate = operation;
    _intakeCreate.addListener(_createChanged);
  }

  @override
  void didChangeDependencies() {
    super.didChangeDependencies();
    final authority = OfficeIntakeAuthority.maybeOf(context);
    if (authority == null) {
      return; // Standalone previews/tests own their local lifetime.
    }
    if (authority.authorizationScopeKey !=
        widget.session.authorizationScopeKey) {
      operation.invalidate();
      denyAccess();
      _dismissPrivateRoutes();
      return;
    }
    if (!identical(_intakeCreate, authority.operation)) {
      _replaceCreate(authority.operation);
    }
    if (_intakeCreate.denied) denyAccess();
  }

  void _createChanged() {
    if (!mounted) return;
    if (_intakeCreate.denied) {
      operation.invalidate();
      denyAccess();
      _dismissPrivateRoutes();
    } else {
      setState(() {});
    }
  }

  void _dismissPrivateRoutes() {
    final route = ModalRoute.of(context);
    final navigator = Navigator.of(context);
    WidgetsBinding.instance.addPostFrameCallback((_) {
      if (mounted && route != null && route.isActive && !route.isCurrent) {
        navigator.popUntil((candidate) => candidate == route);
      }
    });
  }

  @override
  void didUpdateWidget(OfficeWorkspacePage oldWidget) {
    super.didUpdateWidget(oldWidget);
    final scopeChanged =
        oldWidget.session.authorizationScopeKey !=
        widget.session.authorizationScopeKey;
    if (scopeChanged ||
        oldWidget.deviceIdentityProvider != widget.deviceIdentityProvider ||
        oldWidget.repository != widget.repository) {
      operation.invalidate();
      clearPrivate();
      if (scopeChanged) {
        _localIntakeCreate.dispose();
        _localIntakeCreate = OfficeOperation();
        _replaceCreate(_localIntakeCreate);
        operation.denied = false;
        operation.blocked = false;
      }
      repository = widget.repository ?? OfficeRepository();
      _dismissPrivateRoutes();
    }
  }

  @override
  void initState() {
    super.initState();
    _intakeCreate = _localIntakeCreate;
    repository = widget.repository ?? OfficeRepository();
    _intakeCreate.addListener(_createChanged);
  }

  @override
  void clearPrivate() => fields.clear();
  @override
  void dispose() {
    _intakeCreate.removeListener(_createChanged);
    _localIntakeCreate.dispose();
    fields.dispose();
    super.dispose();
  }

  Future<void> _open(String stage) async {
    final session = widget.session;
    final result = await operation.run(() async {
      final identity = OfficeIdentity(
        session,
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
      'find' => OfficeFinderPage(
        actor: identity,
        repository: repository,
        createOperation: _intakeCreate,
      ),
      'new' => OfficeIntakePage(
        actor: identity,
        repository: repository,
        createOperation: _intakeCreate,
      ),
      'intake' => OfficeIntakePage(
        actor: identity,
        repository: repository,
        reference: fields.text('intake-reference'),
        createOperation: _intakeCreate,
      ),
      'cif' => OfficeCifPage(
        actor: identity,
        repository: repository,
        clientId: selected!['client_id'],
        intakeReference: selected['application_reference'],
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
                'Find an intake or application',
                operation.busy ? null : () => _open('find'),
                primary: true,
              ),
              if (_intakeCreate.busy || _intakeCreate.blocked)
                const Padding(
                  padding: EdgeInsets.only(bottom: 12),
                  child: Text(
                    'An office intake attempt is unresolved. New intake is locked. Open the intake form or find saved records to review the outcome; a different record cannot resolve this attempt.',
                  ),
                ),
              officeButton(
                'New office intake',
                operation.busy ? null : () => _open('new'),
              ),
              ExpansionTile(
                title: const Text('Open by reference'),
                maintainState: true,
                children: [
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
              ),
            ],
    );
  }
}
