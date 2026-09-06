import 'package:flutter/material.dart';
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
  State<ClientPasswordResetPage> createState() => _ClientPasswordResetPageState();
}

class _ClientPasswordResetPageState extends State<ClientPasswordResetPage> {
  final TextEditingController _searchController = TextEditingController();
  List<_ClientCredentialAccount> _accounts = const <_ClientCredentialAccount>[];
  String? _error;
  bool _searching = false;
  bool _searched = false;

  @override
  void dispose() {
    _searchController.dispose();
    super.dispose();
  }

  Future<void> _search() async {
    final query = _searchController.text.trim().split(RegExp(r'\s+')).join(' ');
    if (query.isEmpty) {
      setState(() {
        _accounts = const <_ClientCredentialAccount>[];
        _searched = false;
        _error = 'Enter a Client name, username, or email.';
      });
      return;
    }

    setState(() {
      _searching = true;
      _searched = false;
      _accounts = const <_ClientCredentialAccount>[];
      _error = null;
    });

    try {
      final identity = await widget.deviceIdentityProvider.load();
      final uri = ApiConfig.endpoint('/api/v1/management/client-accounts').replace(
        queryParameters: <String, String>{'q': query},
      );
      final response = await http.get(
        uri,
        headers: <String, String>{
          'Accept': 'application/json',
          'Authorization': 'Bearer ${widget.session.accessToken}',
          'X-Device-Id': identity.installationId,
        },
      );
      final payload = decodeJsonObject(response.body);
      if (response.statusCode < 200 || response.statusCode >= 300) {
        throw SpinaApiException(
          apiErrorMessage(payload, statusCode: response.statusCode),
          statusCode: response.statusCode,
        );
      }
      final data = stringMap(
        unwrapSpinaData(payload, statusCode: response.statusCode),
      );
      final rawAccounts = data['accounts'];
      if (rawAccounts is! Iterable) {
        throw const SpinaApiException(
          'The SPINA server returned incomplete Client account data.',
        );
      }
      final accounts = rawAccounts
          .map((item) => _ClientCredentialAccount.fromJson(stringMap(item)))
          .toList(growable: false);

      if (!mounted) {
        return;
      }
      setState(() {
        _accounts = accounts;
        _searched = true;
        _searching = false;
      });
    } on SpinaApiException catch (error) {
      if (!mounted) {
        return;
      }
      setState(() {
        _error = error.message;
        _searching = false;
      });
    } on Exception {
      if (!mounted) {
        return;
      }
      setState(() {
        _error = 'Client accounts could not be loaded. Check the connection and try again.';
        _searching = false;
      });
    }
  }

  Future<void> _confirmReset(_ClientCredentialAccount account) async {
    await showDialog<bool>(
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
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      key: const Key('client-password-reset-page'),
      appBar: AppBar(title: const Text('Client password reset')),
      body: SafeArea(
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
              enabled: !_searching,
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
                onPressed: _searching ? null : _search,
                icon: _searching
                    ? const SizedBox.square(
                        dimension: 16,
                        child: CircularProgressIndicator(strokeWidth: 2),
                      )
                    : const Icon(Icons.search),
                label: Text(_searching ? 'Searching…' : 'Search'),
              ),
            ),
            if (_error != null) ...[
              const SizedBox(height: 12),
              Text(
                _error!,
                style: TextStyle(color: Theme.of(context).colorScheme.error),
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
                      onPressed: () => _confirmReset(account),
                      child: const Text('Reset password'),
                    ),
                  ),
                ),
              ),
            ],
          ],
        ),
      ),
    );
  }
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
