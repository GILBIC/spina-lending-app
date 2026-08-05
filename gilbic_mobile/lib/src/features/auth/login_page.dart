import 'package:flutter/material.dart';
import 'package:gilbic_mobile/src/core/auth/auth_repository.dart';
import 'package:gilbic_mobile/src/core/config/api_config.dart';
import 'package:gilbic_mobile/src/features/auth/client_registration_page.dart';

class LoginPage extends StatefulWidget {
  const LoginPage({
    required this.onSignIn,
    this.clientRegistrationRepository,
    super.key,
  });

  final Future<String?> Function(String username, String password) onSignIn;
  final ClientRegistrationRepository? clientRegistrationRepository;

  @override
  State<LoginPage> createState() => _LoginPageState();
}

class _LoginPageState extends State<LoginPage> {
  final TextEditingController _usernameController = TextEditingController();
  final TextEditingController _passwordController = TextEditingController();
  bool _submitting = false;
  bool _showPassword = false;
  String? _errorMessage;

  @override
  void dispose() {
    _usernameController.dispose();
    _passwordController.dispose();
    super.dispose();
  }

  Future<void> _submit() async {
    final username = _usernameController.text.trim();
    final password = _passwordController.text;
    if (_submitting) {
      return;
    }
    if (username.isEmpty || password.isEmpty) {
      setState(() => _errorMessage = 'Enter your username and password.');
      return;
    }

    setState(() {
      _submitting = true;
      _errorMessage = null;
    });
    final error = await widget.onSignIn(username, password);
    if (!mounted) {
      return;
    }
    setState(() {
      _submitting = false;
      _errorMessage = error;
    });
  }

  Future<void> _openRegistration() async {
    final repository = widget.clientRegistrationRepository;
    if (repository == null || _submitting) {
      return;
    }
    await Navigator.of(context).push<void>(
      MaterialPageRoute<void>(
        builder: (_) => ClientRegistrationPage(repository: repository),
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      body: SafeArea(
        child: Center(
          child: SingleChildScrollView(
            padding: const EdgeInsets.all(24),
            child: ConstrainedBox(
              constraints: const BoxConstraints(maxWidth: 480),
              child: Card(
                child: Padding(
                  padding: const EdgeInsets.all(24),
                  child: AutofillGroup(
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.stretch,
                      children: [
                        Text(
                          'Gilbic',
                          style: Theme.of(context).textTheme.headlineLarge,
                          textAlign: TextAlign.center,
                        ),
                        const SizedBox(height: 8),
                        Text(
                          'Secure SPINA mobile access',
                          style: Theme.of(context).textTheme.titleMedium,
                          textAlign: TextAlign.center,
                        ),
                        const SizedBox(height: 28),
                        TextField(
                          key: const Key('username-field'),
                          controller: _usernameController,
                          enabled: !_submitting,
                          autofillHints: const <String>[AutofillHints.username],
                          textInputAction: TextInputAction.next,
                          autocorrect: false,
                          decoration: const InputDecoration(
                            labelText: 'Username',
                            prefixIcon: Icon(Icons.person_outline),
                            border: OutlineInputBorder(),
                          ),
                        ),
                        const SizedBox(height: 16),
                        TextField(
                          key: const Key('password-field'),
                          controller: _passwordController,
                          enabled: !_submitting,
                          autofillHints: const <String>[AutofillHints.password],
                          obscureText: !_showPassword,
                          textInputAction: TextInputAction.done,
                          onSubmitted: (_) => _submit(),
                          decoration: InputDecoration(
                            labelText: 'Password',
                            prefixIcon: const Icon(Icons.lock_outline),
                            border: const OutlineInputBorder(),
                            suffixIcon: IconButton(
                              tooltip: _showPassword
                                  ? 'Hide password'
                                  : 'Show password',
                              onPressed: _submitting
                                  ? null
                                  : () {
                                      setState(
                                        () => _showPassword = !_showPassword,
                                      );
                                    },
                              icon: Icon(
                                _showPassword
                                    ? Icons.visibility_off
                                    : Icons.visibility,
                              ),
                            ),
                          ),
                        ),
                        if (_errorMessage != null) ...[
                          const SizedBox(height: 14),
                          Text(
                            _errorMessage!,
                            key: const Key('login-error'),
                            style: TextStyle(
                              color: Theme.of(context).colorScheme.error,
                            ),
                            textAlign: TextAlign.center,
                          ),
                        ],
                        const SizedBox(height: 22),
                        FilledButton.icon(
                          key: const Key('sign-in-button'),
                          onPressed: _submitting ? null : _submit,
                          icon: _submitting
                              ? const SizedBox.square(
                                  dimension: 18,
                                  child: CircularProgressIndicator(
                                    strokeWidth: 2,
                                  ),
                                )
                              : const Icon(Icons.login),
                          label: Text(
                            _submitting ? 'Signing in...' : 'Sign in',
                          ),
                        ),
                        if (widget.clientRegistrationRepository != null) ...[
                          const SizedBox(height: 10),
                          OutlinedButton.icon(
                            key: const Key('create-client-account-button'),
                            onPressed: _submitting ? null : _openRegistration,
                            icon: const Icon(Icons.person_add_alt_1),
                            label: const Text('Create client account'),
                          ),
                        ],
                        const SizedBox(height: 20),
                        Text(
                          'API: ${ApiConfig.baseUrl}\n'
                          'Your role and permissions are assigned by the SPINA server.',
                          style: Theme.of(context).textTheme.bodySmall,
                          textAlign: TextAlign.center,
                        ),
                      ],
                    ),
                  ),
                ),
              ),
            ),
          ),
        ),
      ),
    );
  }
}
