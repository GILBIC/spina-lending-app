import 'package:flutter/material.dart';
import 'package:gilbic_mobile/src/core/auth/auth_repository.dart';
import 'package:gilbic_mobile/src/core/auth/client_registration.dart';
import 'package:gilbic_mobile/src/core/network/spina_api.dart';

class ClientRegistrationPage extends StatefulWidget {
  const ClientRegistrationPage({
    required this.repository,
    super.key,
  });

  final ClientRegistrationRepository repository;

  @override
  State<ClientRegistrationPage> createState() =>
      _ClientRegistrationPageState();
}

class _ClientRegistrationPageState extends State<ClientRegistrationPage> {
  final _formKey = GlobalKey<FormState>();
  final _fullNameController = TextEditingController();
  final _clientCodeController = TextEditingController();
  final _phoneController = TextEditingController();
  final _emailController = TextEditingController();
  final _usernameController = TextEditingController();
  final _passwordController = TextEditingController();
  final _confirmPasswordController = TextEditingController();

  bool _submitting = false;
  bool _showPassword = false;
  String? _errorMessage;
  ClientRegistrationResult? _result;

  @override
  void dispose() {
    _fullNameController.dispose();
    _clientCodeController.dispose();
    _phoneController.dispose();
    _emailController.dispose();
    _usernameController.dispose();
    _passwordController.dispose();
    _confirmPasswordController.dispose();
    super.dispose();
  }

  Future<void> _submit() async {
    if (_submitting || !_formKey.currentState!.validate()) {
      return;
    }
    setState(() {
      _submitting = true;
      _errorMessage = null;
    });

    try {
      final result = await widget.repository.registerClient(
        ClientRegistrationDraft(
          fullName: _fullNameController.text,
          clientCode: _clientCodeController.text,
          phoneNumber: _phoneController.text,
          email: _emailController.text,
          username: _usernameController.text,
          password: _passwordController.text,
        ),
      );
      if (!mounted) {
        return;
      }
      setState(() => _result = result);
    } on SpinaApiException catch (error) {
      if (mounted) {
        setState(() => _errorMessage = error.message);
      }
    } on Object {
      if (mounted) {
        setState(
          () => _errorMessage =
              'Registration could not be completed. Try again.',
        );
      }
    } finally {
      if (mounted) {
        setState(() => _submitting = false);
      }
    }
  }

  String? _required(String? value, String label) {
    if ((value ?? '').trim().isEmpty) {
      return '$label is required.';
    }
    return null;
  }

  @override
  Widget build(BuildContext context) {
    final result = _result;
    return Scaffold(
      appBar: AppBar(title: const Text('Create client account')),
      body: SafeArea(
        child: Center(
          child: SingleChildScrollView(
            padding: const EdgeInsets.all(20),
            child: ConstrainedBox(
              constraints: const BoxConstraints(maxWidth: 560),
              child: result == null
                  ? _buildForm(context)
                  : _buildSuccess(context, result),
            ),
          ),
        ),
      ),
    );
  }

  Widget _buildSuccess(
    BuildContext context,
    ClientRegistrationResult result,
  ) {
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(24),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            Icon(
              Icons.pending_actions,
              size: 64,
              color: Theme.of(context).colorScheme.primary,
            ),
            const SizedBox(height: 16),
            Text(
              'Registration submitted',
              style: Theme.of(context).textTheme.headlineSmall,
              textAlign: TextAlign.center,
            ),
            const SizedBox(height: 12),
            Text(
              result.message,
              key: const Key('registration-success-message'),
              textAlign: TextAlign.center,
            ),
            if (result.requiresEmailConfirmation) ...[
              const SizedBox(height: 12),
              const Text(
                'Check your email and confirm the address. You can sign in after both email confirmation and Management approval are complete.',
                textAlign: TextAlign.center,
              ),
            ],
            const SizedBox(height: 24),
            FilledButton.icon(
              onPressed: () => Navigator.of(context).pop(),
              icon: const Icon(Icons.login),
              label: const Text('Back to sign in'),
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildForm(BuildContext context) {
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(20),
        child: Form(
          key: _formKey,
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: [
              Text(
                'Client portal registration',
                style: Theme.of(context).textTheme.headlineSmall,
              ),
              const SizedBox(height: 8),
              const Text(
                'Use the client code from your SPINA borrower record. Management will verify and link the account before access is activated.',
              ),
              const SizedBox(height: 20),
              TextFormField(
                key: const Key('registration-full-name'),
                controller: _fullNameController,
                enabled: !_submitting,
                textCapitalization: TextCapitalization.words,
                textInputAction: TextInputAction.next,
                validator: (value) => _required(value, 'Full name'),
                decoration: const InputDecoration(
                  labelText: 'Full name',
                  prefixIcon: Icon(Icons.badge_outlined),
                  border: OutlineInputBorder(),
                ),
              ),
              const SizedBox(height: 14),
              TextFormField(
                key: const Key('registration-client-code'),
                controller: _clientCodeController,
                enabled: !_submitting,
                autocorrect: false,
                textCapitalization: TextCapitalization.characters,
                textInputAction: TextInputAction.next,
                validator: (value) => _required(value, 'Client code'),
                decoration: const InputDecoration(
                  labelText: 'SPINA client code',
                  helperText: 'Example: TEST-LEDGER-20260802',
                  prefixIcon: Icon(Icons.numbers),
                  border: OutlineInputBorder(),
                ),
              ),
              const SizedBox(height: 14),
              TextFormField(
                key: const Key('registration-phone'),
                controller: _phoneController,
                enabled: !_submitting,
                keyboardType: TextInputType.phone,
                textInputAction: TextInputAction.next,
                decoration: const InputDecoration(
                  labelText: 'Mobile number (optional)',
                  prefixIcon: Icon(Icons.phone_outlined),
                  border: OutlineInputBorder(),
                ),
              ),
              const SizedBox(height: 14),
              TextFormField(
                key: const Key('registration-email'),
                controller: _emailController,
                enabled: !_submitting,
                keyboardType: TextInputType.emailAddress,
                autocorrect: false,
                textInputAction: TextInputAction.next,
                validator: (value) {
                  final requiredError = _required(value, 'Email');
                  if (requiredError != null) {
                    return requiredError;
                  }
                  if (!(value ?? '').contains('@')) {
                    return 'Enter a valid email address.';
                  }
                  return null;
                },
                decoration: const InputDecoration(
                  labelText: 'Email',
                  prefixIcon: Icon(Icons.email_outlined),
                  border: OutlineInputBorder(),
                ),
              ),
              const SizedBox(height: 14),
              TextFormField(
                key: const Key('registration-username'),
                controller: _usernameController,
                enabled: !_submitting,
                autocorrect: false,
                textInputAction: TextInputAction.next,
                validator: (value) {
                  final text = (value ?? '').trim();
                  if (text.length < 3) {
                    return 'Username must contain at least 3 characters.';
                  }
                  if (text.contains(RegExp(r'\s'))) {
                    return 'Username cannot contain spaces.';
                  }
                  return null;
                },
                decoration: const InputDecoration(
                  labelText: 'Username',
                  prefixIcon: Icon(Icons.person_outline),
                  border: OutlineInputBorder(),
                ),
              ),
              const SizedBox(height: 14),
              TextFormField(
                key: const Key('registration-password'),
                controller: _passwordController,
                enabled: !_submitting,
                obscureText: !_showPassword,
                textInputAction: TextInputAction.next,
                validator: (value) => (value ?? '').length < 8
                    ? 'Password must contain at least 8 characters.'
                    : null,
                decoration: InputDecoration(
                  labelText: 'Password',
                  prefixIcon: const Icon(Icons.lock_outline),
                  border: const OutlineInputBorder(),
                  suffixIcon: IconButton(
                    tooltip: _showPassword
                        ? 'Hide passwords'
                        : 'Show passwords',
                    onPressed: _submitting
                        ? null
                        : () => setState(
                              () => _showPassword = !_showPassword,
                            ),
                    icon: Icon(
                      _showPassword ? Icons.visibility_off : Icons.visibility,
                    ),
                  ),
                ),
              ),
              const SizedBox(height: 14),
              TextFormField(
                key: const Key('registration-confirm-password'),
                controller: _confirmPasswordController,
                enabled: !_submitting,
                obscureText: !_showPassword,
                textInputAction: TextInputAction.done,
                onFieldSubmitted: (_) => _submit(),
                validator: (value) => value != _passwordController.text
                    ? 'Passwords do not match.'
                    : null,
                decoration: const InputDecoration(
                  labelText: 'Confirm password',
                  prefixIcon: Icon(Icons.lock_reset),
                  border: OutlineInputBorder(),
                ),
              ),
              if (_errorMessage != null) ...[
                const SizedBox(height: 14),
                Text(
                  _errorMessage!,
                  key: const Key('registration-error'),
                  style: TextStyle(
                    color: Theme.of(context).colorScheme.error,
                  ),
                  textAlign: TextAlign.center,
                ),
              ],
              const SizedBox(height: 20),
              FilledButton.icon(
                key: const Key('submit-client-registration'),
                onPressed: _submitting ? null : _submit,
                icon: _submitting
                    ? const SizedBox.square(
                        dimension: 18,
                        child: CircularProgressIndicator(strokeWidth: 2),
                      )
                    : const Icon(Icons.person_add_alt_1),
                label: Text(
                  _submitting ? 'Submitting...' : 'Submit registration',
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }
}
