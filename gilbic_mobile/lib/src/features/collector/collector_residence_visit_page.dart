import 'package:flutter/material.dart';
import 'package:gilbic_mobile/src/core/auth/app_role.dart';
import 'package:gilbic_mobile/src/core/auth/user_session.dart';
import 'package:gilbic_mobile/src/core/collector/collector_residence_visit_repository.dart';
import 'package:gilbic_mobile/src/core/device/device_identity.dart';
import 'package:gilbic_mobile/src/core/network/spina_api.dart';
import 'package:gilbic_mobile/src/core/network/staff_operations_client.dart';

class CollectorResidenceVisitPage extends StatefulWidget {
  const CollectorResidenceVisitPage({
    required this.session,
    required this.deviceIdentityProvider,
    this.repository,
    super.key,
  });
  final UserSession session;
  final DeviceIdentityProvider deviceIdentityProvider;
  final CollectorResidenceVisitRepository? repository;
  @override
  State<CollectorResidenceVisitPage> createState() =>
      _CollectorResidenceVisitPageState();
}

class _CollectorResidenceVisitPageState
    extends State<CollectorResidenceVisitPage> {
  final _reference = TextEditingController(),
      _note = TextEditingController(),
      _evidence = TextEditingController();
  late final _repository =
      widget.repository ??
      CollectorResidenceVisitRepository(
        StaffOperationsClient(
          deviceIdentityProvider: widget.deviceIdentityProvider,
        ),
      );
  ResidenceVisitCase? _case;
  String? _result, _message;
  bool _busy = false, _blocked = false, _denied = false, _editing = false;
  bool get _allowed =>
      widget.session.hasRole(AppRole.collector) &&
      widget.session.hasPermission('client_onboarding.visit.record');

  @override
  void dispose() {
    _reference.dispose();
    _note.dispose();
    _evidence.dispose();
    if (widget.repository == null) _repository.client.close();
    super.dispose();
  }

  Future<void> _load({String? reference}) async {
    if (_busy || !_allowed || _denied) return;
    final selected = reference ?? _reference.text;
    setState(() {
      _busy = true;
      _case = null;
      _editing = false;
      _message = null;
      _result = null;
    });
    _note.clear();
    _evidence.clear();
    try {
      final record = await _repository.load(widget.session, selected);
      if (!mounted) return;
      setState(() {
        _case = record;
        _reference.text = record.reference;
        _blocked = false;
        _editing = record.visitStatus == 'pending';
      });
    } on Object catch (error) {
      if (mounted) {
        setState(() {
          _message = staffError(error);
          _blocked = true;
          _denied = staffAccessRejected(error);
        });
      }
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  Future<void> _submit() async {
    final record = _case;
    if (_busy ||
        _blocked ||
        _denied ||
        !_allowed ||
        record == null ||
        _result == null) {
      return;
    }
    final result = _result!;
    final note = _note.text.trim().replaceAll(RegExp(r'\s+'), ' ');
    final evidence = _evidence.text.trim();
    setState(() {
      _busy = true;
      _message = null;
    });
    try {
      await _repository.record(
        widget.session,
        record,
        result: result,
        note: note,
        evidenceReference: evidence,
      );
      // Verify the saved case before showing completion; never resubmit here.
      final saved = await _repository.load(widget.session, record.reference);
      if (saved.applicantId != record.applicantId ||
          saved.visitStatus != result ||
          (saved.note ?? '') != note ||
          (saved.evidenceReference ?? '') != evidence) {
        throw const SpinaApiException(
          'The reloaded case does not confirm the submitted visit. Reload the intake case.',
        );
      }
      if (!mounted) return;
      setState(() {
        _case = saved;
        _editing = false;
        _result = null;
        _message = 'Residence visit recorded. It does not approve a loan.';
      });
      _note.clear();
      _evidence.clear();
    } on Object catch (error) {
      if (!mounted) return;
      setState(() {
        _denied = staffAccessRejected(error);
        _blocked =
            error is! SpinaApiException ||
            ![400, 422].contains(error.statusCode);
        _message = _blocked && !_denied
            ? 'The visit outcome is uncertain. Reload this intake case before recording another decision.'
            : staffError(error);
        if (_denied) {
          _case = null;
          _note.clear();
          _evidence.clear();
          _reference.clear();
        }
      });
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    final record = _case;
    final locked = _busy || _blocked || _denied;
    return PopScope(
      canPop: !_busy,
      child: Scaffold(
        appBar: AppBar(title: const Text('Residence visit')),
        body: ListView(
          padding: const EdgeInsets.all(16),
          children: [
            if (!_allowed || _denied)
              const Text(
                'Collector residence-visit access is unavailable. Sign in again or contact Management.',
              )
            else ...[
              const Text(
                'Use the office intake reference to record the observed residence visit. This does not approve a loan or verify other documents.',
              ),
              const SizedBox(height: 16),
              TextField(
                key: const Key('visit-reference'),
                controller: _reference,
                enabled: !_busy && !_blocked,
                decoration: const InputDecoration(
                  labelText: 'Office intake reference',
                ),
                onChanged: (_) {
                  if (record != null) {
                    setState(() {
                      _case = null;
                      _editing = false;
                    });
                  }
                },
              ),
              OutlinedButton(
                key: const Key('visit-load'),
                onPressed: _busy || _blocked ? null : _load,
                child: const Text('Load intake case'),
              ),
              if (_busy) const LinearProgressIndicator(),
              if (record != null) ...[
                const SizedBox(height: 16),
                Text(
                  record.name,
                  style: Theme.of(context).textTheme.titleLarge,
                ),
                Text(record.phone),
                Text(record.address),
                Text('Recorded visit: ${_label(record.visitStatus)}'),
                if (record.note?.isNotEmpty == true)
                  Text('Visit note: ${record.note}'),
                if (record.evidenceReference?.isNotEmpty == true)
                  Text('Evidence reference: ${record.evidenceReference}'),
                if (_editing) ...[
                  const SizedBox(height: 16),
                  DropdownButtonFormField<String>(
                    key: const Key('visit-result'),
                    initialValue: _result,
                    decoration: const InputDecoration(
                      labelText: 'Observed visit result',
                    ),
                    items: const [
                      DropdownMenuItem(value: 'passed', child: Text('Passed')),
                      DropdownMenuItem(value: 'failed', child: Text('Failed')),
                    ],
                    onChanged: locked
                        ? null
                        : (value) => setState(() => _result = value),
                  ),
                  TextField(
                    key: const Key('visit-note'),
                    controller: _note,
                    enabled: !locked,
                    maxLength: 500,
                    maxLines: 3,
                    decoration: const InputDecoration(
                      labelText: 'Visit note (optional)',
                    ),
                  ),
                  TextField(
                    key: const Key('visit-evidence'),
                    controller: _evidence,
                    enabled: !locked,
                    maxLength: 500,
                    decoration: const InputDecoration(
                      labelText: 'External evidence reference (optional)',
                    ),
                  ),
                  FilledButton(
                    key: const Key('visit-submit'),
                    onPressed: locked || _result == null ? null : _submit,
                    child: const Text('Record residence visit'),
                  ),
                ] else if (!_blocked)
                  TextButton(
                    onPressed: _busy
                        ? null
                        : () => setState(() {
                            _editing = true;
                            _result = null;
                          }),
                    child: const Text('Record updated visit'),
                  ),
              ],
              if (_blocked)
                OutlinedButton(
                  key: const Key('visit-reload'),
                  onPressed: _busy
                      ? null
                      : () => _load(
                          reference: record?.reference ?? _reference.text,
                        ),
                  child: const Text('Reload authoritative intake case'),
                ),
            ],
            if (_message != null)
              Padding(
                padding: const EdgeInsets.symmetric(vertical: 12),
                child: Text(_message!),
              ),
          ],
        ),
      ),
    );
  }
}

String _label(String value) =>
    {'passed': 'Passed', 'failed': 'Failed', 'pending': 'Pending'}[value] ??
    value;
