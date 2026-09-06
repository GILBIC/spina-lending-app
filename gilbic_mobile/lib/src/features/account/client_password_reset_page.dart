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
          children: const [
            Text(
              'Client password reset',
              style: TextStyle(fontSize: 22, fontWeight: FontWeight.w600),
            ),
            SizedBox(height: 8),
            Text('Search Client accounts by name, username, or email.'),
          ],
        ),
      ),
    );
  }
}
