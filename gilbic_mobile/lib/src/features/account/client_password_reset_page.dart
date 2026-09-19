import 'package:flutter/material.dart';
import 'package:gilbic_mobile/src/core/auth/app_role.dart';
import 'package:gilbic_mobile/src/core/auth/user_session.dart';
import 'package:gilbic_mobile/src/core/config/api_config.dart';
import 'package:gilbic_mobile/src/core/device/device_identity.dart';
import 'package:gilbic_mobile/src/core/network/spina_api.dart';
import 'package:http/http.dart' as http;

class ClientPasswordResetPage extends StatefulWidget {
  const ClientPasswordResetPage({
    required this.session,
    required this.deviceIdentityProvider,
    super.key,
  });

  final UserSession session;
  final DeviceIdentityProvider deviceIdentityProvider;

  @override
  State<ClientPasswordResetPage> createState() =>
      _ClientPasswordResetPageState();
}

class _ClientPasswordResetPageState extends State<ClientPasswordResetPage> {
  final TextEditingController _searchController = TextEditingController();
  List<_ClientCredentialAccount> _accounts = const <_ClientCredentialAccount>[];
  _ClientResetResult? _resetResult;
  String? _resettingAccountId;
  String? _error;
  bool _searching = false;
  bool _searched = false;
  bool _confirmingReset = false;
  bool _accessRejected = false;
  bool _revealPassword = false;
  bool _resetUncertain = false;
  bool _uncertainSearchRefreshed = false;
  bool _uncertainAcknowledged = false;
  int _operationGeneration = 0;

  bool get _canAccess =>
      !_accessRejected &&
      (widget.session.role == AppRole.employee ||
          widget.session.role == AppRole.management) &&
      widget.session.hasPermission('client.credential.manage');

  bool get _busy =>
      _searching || _confirmingReset || _resettingAccountId != null;

  bool get _canReset =>
      _canAccess &&
      !_busy &&
      (!_resetUncertain ||
          (_uncertainSearchRefreshed && _uncertainAcknowledged));

  bool _isCurrent(int generation) =>
      mounted && generation == _operationGeneration && _canAccess;

  @override
  void didUpdateWidget(covariant ClientPasswordResetPage oldWidget) {
    super.didUpdateWidget(oldWidget);
    if (oldWidget.session.userId != widget.session.userId ||
        oldWidget.session.role != widget.session.role ||
        oldWidget.session.hasPermission('client.credential.manage') !=
            widget.session.hasPermission('client.credential.manage')) {
      _operationGeneration++;
      _clearPrivateState();
      _searchController.clear();
      _searching = false;
      _confirmingReset = false;
      _resettingAccountId = null;
      _accessRejected = false;
      _error = null;
    }
  }

  void _clearPrivateState() {
    _accounts = const <_ClientCredentialAccount>[];
    _resetResult = null;
    _searched = false;
    _revealPassword = false;
    _resetUncertain = false;
    _uncertainSearchRefreshed = false;
    _uncertainAcknowledged = false;
  }

  void _searchChanged(String _) {
    if (_busy) return;
    setState(() {
      _operationGeneration++;
      _accounts = const <_ClientCredentialAccount>[];
      _resetResult = null;
      _revealPassword = false;
      _searched = false;
      _uncertainSearchRefreshed = false;
      _uncertainAcknowledged = false;
      _error = null;
    });
  }

  bool _isAccessRejection(Object error) =>
      error is SpinaApiException &&
      const <int>{401, 403, 426}.contains(error.statusCode);

  void _rejectAccess(SpinaApiException error) {
    _clearPrivateState();
    _accessRejected = true;
    _error = switch (error.statusCode) {
      401 => 'Your session expired. Sign in again before continuing.',
      426 => 'Install the latest app version, then sign in again.',
      _ =>
        'This account or device is no longer allowed to manage Client credentials.',
    };
  }

  @override
  void dispose() {
    _searchController.dispose();
    super.dispose();
  }

  Future<void> _search() async {
    if (!_canAccess || _busy) return;
    final generation = ++_operationGeneration;
    final query = _searchController.text.trim().split(RegExp(r'\s+')).join(' ');
    if (query.isEmpty) {
      setState(() {
        _accounts = const <_ClientCredentialAccount>[];
        _resetResult = null;
        _searched = false;
        _error = 'Enter a Client name, username, or email.';
      });
      return;
    }

    setState(() {
      _searching = true;
      _searched = false;
      _accounts = const <_ClientCredentialAccount>[];
      _resetResult = null;
      _revealPassword = false;
      _uncertainSearchRefreshed = false;
      _uncertainAcknowledged = false;
      _error = null;
    });

    try {
      final identity = await widget.deviceIdentityProvider.load();
      if (!_isCurrent(generation)) return;
      final uri = ApiConfig.endpoint(
        '/api/v1/management/client-accounts',
      ).replace(queryParameters: <String, String>{'q': query});
      final response = await http.get(
        uri,
        headers: <String, String>{
          'Accept': 'application/json',
          'Authorization': 'Bearer ${widget.session.accessToken}',
          'X-Device-Id': identity.installationId,
        },
      );
      final data = _responseData(response);
      final rawAccounts = data['accounts'];
      if (rawAccounts is! Iterable) {
        throw const SpinaApiException(
          'The SPINA server returned incomplete Client account data.',
        );
      }
      final accounts = rawAccounts
          .map((item) => _ClientCredentialAccount.fromJson(stringMap(item)))
          .toList(growable: false);

      if (!_isCurrent(generation)) {
        return;
      }
      setState(() {
        _accounts = accounts;
        _searched = true;
        _searching = false;
        _uncertainSearchRefreshed = _resetUncertain;
      });
    } on SpinaApiException catch (error) {
      if (!_isCurrent(generation)) {
        return;
      }
      setState(() {
        if (_isAccessRejection(error)) {
          _rejectAccess(error);
        } else {
          _error = error.message;
        }
        _searching = false;
      });
    } on Exception {
      if (!_isCurrent(generation)) {
        return;
      }
      setState(() {
        _error =
            'Client accounts could not be loaded. Check the connection and try again.';
        _searching = false;
      });
    }
  }

  Future<void> _confirmReset(_ClientCredentialAccount account) async {
    if (!_canReset || !_accounts.contains(account)) return;
    final generation = ++_operationGeneration;
    setState(() => _confirmingReset = true);
    final confirmed = await showDialog<bool>(
      context: context,
      builder: (dialogContext) => AlertDialog(
        title: const Text('Reset Client password?'),
        content: Text(
          'SPINA will generate a new password for ${account.fullName}. '
          'The old password cannot be recovered, and the borrower cannot reset it themselves.',
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.of(dialogContext).pop(false),
            child: const Text('Cancel'),
          ),
          FilledButton(
            onPressed: () => Navigator.of(dialogContext).pop(true),
            child: const Text('Reset password'),
          ),
        ],
      ),
    );
    if (!_isCurrent(generation)) return;
    setState(() => _confirmingReset = false);
    if (confirmed != true) {
      return;
    }

    setState(() {
      _resettingAccountId = account.id;
      _resetResult = null;
      _revealPassword = false;
      _error = null;
    });

    var requestWasSent = false;
    try {
      final identity = await widget.deviceIdentityProvider.load();
      if (!_isCurrent(generation)) return;
      requestWasSent = true;
      final response = await http.post(
        ApiConfig.endpoint(
          '/api/v1/management/accounts/${account.id}/password/reset',
        ),
        headers: <String, String>{
          'Accept': 'application/json',
          'Authorization': 'Bearer ${widget.session.accessToken}',
          'X-Device-Id': identity.installationId,
        },
      );
      final data = _responseData(response);
      final returnedAccount = _ClientCredentialAccount.fromJson(
        stringMap(data['account']),
      );
      final credentials = stringMap(data['credentials']);
      final delivery = stringMap(data['delivery']);
      final username = firstNonEmptyString(<Object?>[credentials['username']]);
      final password = firstNonEmptyString(<Object?>[credentials['password']]);
      final deliveryDetail = firstNonEmptyString(<Object?>[delivery['detail']]);
      final deliverySent = delivery['sent'];
      if (returnedAccount.id != account.id ||
          returnedAccount.username != account.username ||
          username == null ||
          username != account.username ||
          password == null ||
          deliveryDetail == null ||
          deliverySent is! bool) {
        throw const SpinaApiException(
          'The SPINA server returned incomplete Client reset data.',
        );
      }

      if (!_isCurrent(generation)) {
        return;
      }
      setState(() {
        _resetResult = _ClientResetResult(
          username: username,
          password: password,
          deliverySent: deliverySent,
          deliveryDetail: deliveryDetail,
        );
        _resettingAccountId = null;
        _resetUncertain = false;
        _uncertainSearchRefreshed = false;
        _uncertainAcknowledged = false;
      });
    } on SpinaApiException catch (error) {
      if (!_isCurrent(generation)) {
        return;
      }
      setState(() {
        final status = error.statusCode;
        if (_isAccessRejection(error)) {
          _rejectAccess(error);
        } else if (requestWasSent &&
            (status == null ||
                status >= 500 ||
                status == 408 ||
                status == 429 ||
                (status >= 200 && status < 300))) {
          _markResetUncertain();
        } else {
          _error = error.message;
        }
        _resettingAccountId = null;
      });
    } on Exception {
      if (!_isCurrent(generation)) {
        return;
      }
      setState(() {
        if (requestWasSent) {
          _markResetUncertain();
        } else {
          _error =
              'The reset could not start. Check this device and try again.';
        }
        _resettingAccountId = null;
      });
    }
  }

  void _markResetUncertain() {
    _resetUncertain = true;
    _uncertainSearchRefreshed = false;
    _uncertainAcknowledged = false;
    _resetResult = null;
    _revealPassword = false;
    _error = null;
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      key: const Key('client-password-reset-page'),
      appBar: AppBar(title: const Text('Client password reset')),
      body: !_canAccess
          ? SafeArea(
              child: Center(
                child: Padding(
                  padding: const EdgeInsets.all(24),
                  child: Column(
                    mainAxisSize: MainAxisSize.min,
                    children: [
                      const Icon(Icons.lock_outline, size: 40),
                      const SizedBox(height: 12),
                      Text(
                        'Access unavailable',
                        style: Theme.of(context).textTheme.titleLarge,
                      ),
                      const SizedBox(height: 8),
                      Text(
                        _error ??
                            'Only authorized Employee and Management accounts can manage Client credentials.',
                        textAlign: TextAlign.center,
                      ),
                    ],
                  ),
                ),
              ),
            )
          : _buildBody(context),
    );
  }

  Widget _buildBody(BuildContext context) {
    return SafeArea(
      child: ListView(
        padding: const EdgeInsets.all(16),
        children: [
          const Text(
            'Client password reset',
            style: TextStyle(fontSize: 22, fontWeight: FontWeight.w600),
          ),
          const SizedBox(height: 8),
          const Text('Search Client accounts by name, username, or email.'),
          const SizedBox(height: 16),
          TextField(
            key: const Key('client-password-search'),
            controller: _searchController,
            enabled: !_busy,
            onChanged: _searchChanged,
            textInputAction: TextInputAction.search,
            onSubmitted: (_) => _search(),
            decoration: const InputDecoration(
              labelText: 'Client',
              hintText: 'Name, username, or email',
            ),
          ),
          const SizedBox(height: 12),
          Align(
            alignment: Alignment.centerLeft,
            child: FilledButton.icon(
              key: const Key('client-password-search-submit'),
              onPressed: _busy ? null : _search,
              icon: _searching
                  ? const SizedBox.square(
                      dimension: 16,
                      child: CircularProgressIndicator(strokeWidth: 2),
                    )
                  : const Icon(Icons.search),
              label: Text(_searching ? 'Searching…' : 'Search'),
            ),
          ),
          if (_resetUncertain) ...[
            const SizedBox(height: 12),
            Card(
              key: const Key('client-password-reset-uncertain'),
              child: Padding(
                padding: const EdgeInsets.all(12),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    const Text(
                      'Reset result not confirmed',
                      style: TextStyle(fontWeight: FontWeight.w700),
                    ),
                    const SizedBox(height: 6),
                    const Text(
                      "The reset may have completed. Check the Client's email or confirm the result with Management. Search again to refresh the account before starting another reset.",
                    ),
                    CheckboxListTile(
                      key: const Key('client-password-reset-acknowledge'),
                      contentPadding: EdgeInsets.zero,
                      title: const Text('I checked the email or reset result.'),
                      value: _uncertainAcknowledged,
                      onChanged: _uncertainSearchRefreshed && !_busy
                          ? (value) => setState(
                              () => _uncertainAcknowledged = value ?? false,
                            )
                          : null,
                    ),
                  ],
                ),
              ),
            ),
          ],
          if (_error != null) ...[
            const SizedBox(height: 12),
            Text(
              _error!,
              style: TextStyle(color: Theme.of(context).colorScheme.error),
            ),
          ],
          if (_resetResult != null) ...[
            const SizedBox(height: 16),
            Card(
              key: const Key('client-password-reset-result'),
              child: Padding(
                padding: const EdgeInsets.all(16),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      'New Client credentials',
                      style: Theme.of(context).textTheme.titleMedium,
                    ),
                    const SizedBox(height: 10),
                    const Text('Username'),
                    Text(_resetResult!.username),
                    const SizedBox(height: 8),
                    const Text('New password'),
                    Text(
                      _revealPassword ? _resetResult!.password : '••••••••••••',
                    ),
                    TextButton.icon(
                      key: const Key('client-password-reset-reveal'),
                      onPressed: () =>
                          setState(() => _revealPassword = !_revealPassword),
                      icon: Icon(
                        _revealPassword
                            ? Icons.visibility_off_outlined
                            : Icons.visibility_outlined,
                      ),
                      label: Text(
                        _revealPassword ? 'Hide password' : 'Reveal password',
                      ),
                    ),
                    const SizedBox(height: 8),
                    Text(
                      _resetResult!.deliverySent
                          ? 'Credential email sent'
                          : 'Credential email not sent',
                    ),
                    Text(_resetResult!.deliveryDetail),
                    const SizedBox(height: 10),
                    const Text(
                      'Copy/share this password now. SPINA does not store or retrieve the old password.',
                    ),
                  ],
                ),
              ),
            ),
          ],
          if (_searched && _accounts.isEmpty) ...[
            const SizedBox(height: 16),
            const Text('No Client accounts found.'),
          ],
          if (_accounts.isNotEmpty) ...[
            const SizedBox(height: 16),
            ..._accounts.map(
              (account) => Card(
                key: Key('client-password-result-${account.id}'),
                child: ListTile(
                  title: Text(account.fullName),
                  subtitle: Text(
                    <String>[
                      account.username,
                      if (account.email != null) account.email!,
                      'Status: ${account.status}',
                    ].join('\n'),
                  ),
                  trailing: TextButton(
                    key: Key('client-password-reset-${account.id}'),
                    onPressed: _canReset ? () => _confirmReset(account) : null,
                    child: _resettingAccountId == account.id
                        ? const SizedBox.square(
                            dimension: 16,
                            child: CircularProgressIndicator(strokeWidth: 2),
                          )
                        : const Text('Reset password'),
                  ),
                ),
              ),
            ),
          ],
        ],
      ),
    );
  }
}

Map<String, dynamic> _responseData(http.Response response) {
  if (response.statusCode < 200 || response.statusCode >= 300) {
    var message = 'The server could not complete the request.';
    try {
      message = apiErrorMessage(
        decodeJsonObject(response.body),
        statusCode: response.statusCode,
      );
    } on Exception {
      // Preserve the rejection status even when its response is not JSON.
    }
    throw SpinaApiException(message, statusCode: response.statusCode);
  }
  return stringMap(
    unwrapSpinaData(
      decodeJsonObject(response.body),
      statusCode: response.statusCode,
    ),
  );
}

class _ClientCredentialAccount {
  const _ClientCredentialAccount({
    required this.id,
    required this.username,
    required this.fullName,
    required this.status,
    this.email,
  });

  factory _ClientCredentialAccount.fromJson(Map<String, dynamic> source) {
    final id = firstNonEmptyString(<Object?>[source['id']]);
    final username = firstNonEmptyString(<Object?>[source['username']]);
    final fullName = firstNonEmptyString(<Object?>[source['full_name']]);
    final status = firstNonEmptyString(<Object?>[source['status']]);
    final roles = stringList(source['roles']);
    if (id == null ||
        username == null ||
        fullName == null ||
        status == null ||
        !roles.contains('client')) {
      throw const SpinaApiException(
        'The SPINA server returned incomplete Client account data.',
      );
    }
    return _ClientCredentialAccount(
      id: id,
      username: username,
      fullName: fullName,
      status: status,
      email: firstNonEmptyString(<Object?>[source['email']]),
    );
  }

  final String id;
  final String username;
  final String fullName;
  final String status;
  final String? email;
}

class _ClientResetResult {
  const _ClientResetResult({
    required this.username,
    required this.password,
    required this.deliverySent,
    required this.deliveryDetail,
  });

  final String username;
  final String password;
  final bool deliverySent;
  final String deliveryDetail;
}
