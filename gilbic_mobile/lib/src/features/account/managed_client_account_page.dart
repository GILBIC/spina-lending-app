import 'package:flutter/material.dart';
import 'package:gilbic_mobile/src/core/auth/app_role.dart';
import 'package:gilbic_mobile/src/core/auth/user_session.dart';
import 'package:gilbic_mobile/src/core/device/device_identity.dart';
import 'package:gilbic_mobile/src/core/management/staff_operations_repository.dart';
import 'package:gilbic_mobile/src/core/network/staff_operations_client.dart';

class ManagedClientAccountPage extends StatefulWidget {
  const ManagedClientAccountPage({
    required this.session,
    required this.deviceIdentityProvider,
    this.repository,
    super.key,
  });
  final UserSession session;
  final DeviceIdentityProvider deviceIdentityProvider;
  final StaffOperationsRepository? repository;
  @override
  State<ManagedClientAccountPage> createState() =>
      _ManagedClientAccountPageState();
}

class _ManagedClientAccountPageState extends State<ManagedClientAccountPage>
    with WidgetsBindingObserver {
  late final _repository =
      widget.repository ??
      StaffOperationsRepository(
        deviceIdentityProvider: widget.deviceIdentityProvider,
      );
  final _query = TextEditingController(), _email = TextEditingController();
  List<Map<String, dynamic>> _candidates = [];
  Map<String, dynamic>? _selected;
  ManagedClientCredentials? _credentials;
  String? _error;
  bool _busy = false,
      _searched = false,
      _uncertain = false,
      _reloaded = false,
      _reveal = false;
  bool get _allowed =>
      widget.session.role == AppRole.management &&
      widget.session.hasPermission('account.manage');
  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addObserver(this);
  }

  @override
  void didChangeAppLifecycleState(AppLifecycleState state) {
    if (state != AppLifecycleState.resumed && mounted) {
      setState(() {
        _reveal = false;
      });
    }
  }

  @override
  void dispose() {
    WidgetsBinding.instance.removeObserver(this);
    _credentials = null;
    _candidates = [];
    _selected = null;
    _query.dispose();
    _email.dispose();
    if (widget.repository == null) _repository.close();
    super.dispose();
  }

  Future<void> _search() async {
    if (_busy || !_allowed) return;
    final query = _query.text.trim();
    setState(() {
      _candidates = [];
      _selected = null;
      _credentials = null;
      _error = null;
      _searched = false;
      _reloaded = false;
      _reveal = false;
    });
    if (query.length < 2) {
      setState(() {
        _error = 'Enter at least two characters.';
      });
      return;
    }
    setState(() {
      _busy = true;
    });
    try {
      final candidates = await _repository.candidates(widget.session, query);
      if (mounted) {
        setState(() {
          _candidates = candidates;
          _searched = true;
          _reloaded = true;
        });
      }
    } catch (error) {
      if (mounted) {
        setState(() {
          _error = staffError(error);
          if (staffAccessRejected(error)) {
            _query.clear();
            _email.clear();
          }
        });
      }
    } finally {
      if (mounted) {
        setState(() {
          _busy = false;
        });
      }
    }
  }

  Future<bool> _confirm(String title, String message) async =>
      await showDialog<bool>(
        context: context,
        builder: (c) => AlertDialog(
          title: Text(title),
          content: Text(message),
          actions: [
            TextButton(
              onPressed: () => Navigator.pop(c, false),
              child: const Text('Cancel'),
            ),
            FilledButton(
              onPressed: () => Navigator.pop(c, true),
              child: const Text('Confirm'),
            ),
          ],
        ),
      ) ==
      true;
  Future<void> _create() async {
    final client = _selected;
    if (_busy || _uncertain || !_allowed || client == null) return;
    final email = _email.text.trim().toLowerCase();
    if (!RegExp(r'^[^\s@]+@[^\s@]+\.[^\s@]+$').hasMatch(email) ||
        email.length > 320) {
      setState(() {
        _error = 'Enter the borrower’s valid email address.';
      });
      return;
    }
    setState(() {
      _busy = true;
      _error = null;
      _credentials = null;
      _reveal = false;
    });
    var sent = false;
    try {
      if (!await _confirm(
        'Create Client account?',
        '${requiredStaffText(client, 'full_name')}\n$email\nGenerate credentials for this existing active borrower?',
      )) {
        return;
      }
      if (!mounted) return;
      sent = true;
      final credentials = await _repository.createAccount(
        widget.session,
        requiredStaffText(client, 'id'),
        email,
      );
      if (!mounted) return;
      setState(() {
        _credentials = credentials;
        _selected = null;
        _candidates = [];
        _searched = false;
        _email.clear();
      });
    } catch (error) {
      if (!mounted) return;
      setState(() {
        _error = staffError(error);
        _credentials = null;
        _selected = null;
        _candidates = [];
        if (sent) {
          _uncertain = true;
          _reloaded = false;
        }
        if (staffAccessRejected(error)) {
          _query.clear();
          _email.clear();
        }
      });
    } finally {
      if (mounted) {
        setState(() {
          _busy = false;
        });
      }
    }
  }

  @override
  Widget build(BuildContext context) {
    final credentials = _credentials;
    return Scaffold(
      appBar: AppBar(title: const Text('Create Client account')),
      body: SafeArea(
        child: !_allowed
            ? const Center(
                child: Text('Management account permission is required.'),
              )
            : ListView(
                padding: const EdgeInsets.all(16),
                children: [
                  const Text(
                    'Create managed access for an existing active borrower who has no linked account. New applicants use the office onboarding workflow.',
                  ),
                  TextField(
                    key: const Key('managed-client-search'),
                    controller: _query,
                    enabled: !_busy,
                    maxLength: 200,
                    decoration: const InputDecoration(
                      labelText: 'Borrower name or code',
                    ),
                    onSubmitted: (_) => _search(),
                  ),
                  FilledButton(
                    key: const Key('managed-client-search-submit'),
                    onPressed: _busy ? null : _search,
                    child: const Text('Search borrowers'),
                  ),
                  if (_busy) const LinearProgressIndicator(),
                  if (_error != null)
                    Text(
                      _error!,
                      style: TextStyle(
                        color: Theme.of(context).colorScheme.error,
                      ),
                    ),
                  if (_uncertain)
                    Card(
                      child: Padding(
                        padding: const EdgeInsets.all(12),
                        child: Column(
                          crossAxisAlignment: CrossAxisAlignment.start,
                          children: [
                            const Text(
                              'Account creation was not confirmed. It may have completed. Check the borrower account and credential email, then search again. Do not repeat the request automatically.',
                            ),
                            TextButton(
                              key: const Key('managed-client-reconciled'),
                              onPressed: !_busy && _reloaded
                                  ? () async {
                                      if (await _confirm(
                                        'Continue after checking?',
                                        'Confirm you checked the existing account and email and refreshed the borrower search. A new request is only appropriate for a borrower who still has no account.',
                                      )) {
                                        if (mounted) {
                                          setState(() {
                                            _uncertain = false;
                                          });
                                        }
                                      }
                                    }
                                  : null,
                              child: const Text(
                                'I checked the account and email',
                              ),
                            ),
                          ],
                        ),
                      ),
                    ),
                  if (_searched && _candidates.isEmpty)
                    const Text('No active unlinked borrower record matched.'),
                  for (final client in _candidates)
                    Card(
                      child: ListTile(
                        key: Key(
                          'managed-candidate-${requiredStaffText(client, 'id')}',
                        ),
                        title: Text(requiredStaffText(client, 'full_name')),
                        subtitle: Text(
                          '${client['client_code']?.toString() ?? ''} · ${client['area']?.toString() ?? ''}',
                        ),
                        selected: _selected?['id'] == client['id'],
                        trailing: const Icon(Icons.person_add_alt),
                        onTap: _busy || _uncertain
                            ? null
                            : () => setState(() {
                                _selected = client;
                                _email.clear();
                              }),
                      ),
                    ),
                  if (_candidates.length >= 50)
                    const Text(
                      'Showing the first 50 matches. Refine your search.',
                    ),
                  if (_selected != null) ...[
                    const SizedBox(height: 12),
                    Text(
                      'Selected: ${requiredStaffText(_selected!, 'full_name')}',
                    ),
                    TextField(
                      key: const Key('managed-client-email'),
                      controller: _email,
                      enabled: !_busy,
                      keyboardType: TextInputType.emailAddress,
                      autocorrect: false,
                      decoration: const InputDecoration(
                        labelText: 'Borrower email',
                      ),
                    ),
                    FilledButton(
                      key: const Key('managed-client-create'),
                      onPressed: _busy || _uncertain ? null : _create,
                      child: const Text('Create account'),
                    ),
                  ],
                  if (credentials != null)
                    Card(
                      child: Padding(
                        padding: const EdgeInsets.all(16),
                        child: Column(
                          crossAxisAlignment: CrossAxisAlignment.start,
                          children: [
                            Text(
                              'Client account created',
                              style: Theme.of(context).textTheme.titleLarge,
                            ),
                            SelectableText('Username: ${credentials.username}'),
                            const Text('One-time password'),
                            if (_reveal)
                              SelectableText(credentials.password)
                            else
                              const Text('••••••••'),
                            TextButton(
                              onPressed: () => setState(() {
                                _reveal = !_reveal;
                              }),
                              child: Text(
                                _reveal ? 'Hide password' : 'Reveal password',
                              ),
                            ),
                            Text(
                              credentials.deliverySent
                                  ? 'Credential email sent'
                                  : 'Credential email not sent',
                            ),
                            Text(credentials.deliveryDetail),
                            const Text(
                              'Provide the credentials privately. This page does not save a readable password; leaving or searching clears it.',
                            ),
                            TextButton(
                              onPressed: () => setState(() {
                                _credentials = null;
                                _reveal = false;
                              }),
                              child: const Text('Clear credentials'),
                            ),
                          ],
                        ),
                      ),
                    ),
                ],
              ),
      ),
    );
  }
}
