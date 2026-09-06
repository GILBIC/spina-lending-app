import 'package:flutter/material.dart';
import 'package:gilbic_mobile/src/core/auth/user_session.dart';
import 'package:gilbic_mobile/src/core/device/device_identity.dart';

class ClientPasswordResetPage extends StatelessWidget {
  const ClientPasswordResetPage({
    required this.session,
    required this.deviceIdentityProvider,
    super.key,
  });

  final UserSession session;
  final DeviceIdentityProvider deviceIdentityProvider;

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
            const TextField(
              key: Key('client-password-search'),
              decoration: InputDecoration(
                labelText: 'Client',
                hintText: 'Name, username, or email',
              ),
            ),
            const SizedBox(height: 12),
            Align(
              alignment: Alignment.centerLeft,
              child: FilledButton.icon(
                key: const Key('client-password-search-submit'),
                onPressed: () {},
                icon: const Icon(Icons.search),
                label: const Text('Search'),
              ),
            ),
          ],
        ),
      ),
    );
  }
}
