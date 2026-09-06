import 'package:flutter/material.dart';
import 'package:gilbic_mobile/src/theme/spina_theme.dart';

class LoginPage extends StatefulWidget {
  const LoginPage({
    required this.onSignIn,
    this.noticeMessage,
    super.key,
  });

  final Future<String?> Function(String username, String password) onSignIn;
  final String? noticeMessage;

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

  @override
  Widget build(BuildContext context) {
    final noticeMessage = widget.noticeMessage?.trim();
    return Scaffold(
      body: DecoratedBox(
        decoration: const BoxDecoration(
          gradient: LinearGradient(
            begin: Alignment.topCenter,
            end: Alignment.bottomCenter,
            colors: [Color(0xFFFFFBFD), Color(0xFFFFF3F8)],
          ),
        ),
        child: SafeArea(
          child: Center(
            child: SingleChildScrollView(
              padding: const EdgeInsets.fromLTRB(20, 18, 20, 18),
              child: ConstrainedBox(
                constraints: const BoxConstraints(maxWidth: 480),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.stretch,
                  children: [
                    const _SpinaBrandHeader(),
                    const SizedBox(height: 14),
                    Card(
                      child: Padding(
                        padding: const EdgeInsets.fromLTRB(22, 20, 22, 20),
                        child: AutofillGroup(
                          child: Column(
                            crossAxisAlignment: CrossAxisAlignment.stretch,
                            children: [
                              Text(
                                'Welcome back',
                                style: Theme.of(context).textTheme.headlineSmall,
                              ),
                              if (noticeMessage != null &&
                                  noticeMessage.isNotEmpty) ...[
                                const SizedBox(height: 14),
                                Semantics(
                                  liveRegion: true,
                                  child: Container(
                                    key: const Key('session-notice'),
                                    padding: const EdgeInsets.all(14),
                                    decoration: BoxDecoration(
                                      color: SpinaTheme.brandPinkSoft,
                                      borderRadius: BorderRadius.circular(16),
                                      border: Border.all(
                                        color: const Color(0xFFEFC7D8),
                                      ),
                                    ),
                                    child: Row(
                                      crossAxisAlignment:
                                          CrossAxisAlignment.start,
                                      children: [
                                        const Icon(
                                          Icons.info_outline_rounded,
                                          color: SpinaTheme.brandPinkDark,
                                        ),
                                        const SizedBox(width: 10),
                                        Expanded(child: Text(noticeMessage)),
                                      ],
                                    ),
                                  ),
                                ),
                              ],
                              const SizedBox(height: 16),
                              TextField(
                                key: const Key('username-field'),
                                controller: _usernameController,
                                enabled: !_submitting,
                                autofillHints: const <String>[
                                  AutofillHints.username,
                                ],
                                textInputAction: TextInputAction.next,
                                autocorrect: false,
                                decoration: const InputDecoration(
                                  labelText: 'Username',
                                  hintText: 'Enter your username',
                                  prefixIcon:
                                      Icon(Icons.person_outline_rounded),
                                ),
                              ),
                              const SizedBox(height: 12),
                              TextField(
                                key: const Key('password-field'),
                                controller: _passwordController,
                                enabled: !_submitting,
                                autofillHints: const <String>[
                                  AutofillHints.password,
                                ],
                                obscureText: !_showPassword,
                                textInputAction: TextInputAction.done,
                                onSubmitted: (_) => _submit(),
                                decoration: InputDecoration(
                                  labelText: 'Password',
                                  hintText: 'Enter your password',
                                  prefixIcon:
                                      const Icon(Icons.lock_outline_rounded),
                                  suffixIcon: IconButton(
                                    tooltip: _showPassword
                                        ? 'Hide password'
                                        : 'Show password',
                                    onPressed: _submitting
                                        ? null
                                        : () {
                                            setState(
                                              () => _showPassword =
                                                  !_showPassword,
                                            );
                                          },
                                    icon: Icon(
                                      _showPassword
                                          ? Icons.visibility_off_outlined
                                          : Icons.visibility_outlined,
                                    ),
                                  ),
                                ),
                              ),
                              if (_errorMessage != null) ...[
                                const SizedBox(height: 12),
                                Container(
                                  key: const Key('login-error'),
                                  padding: const EdgeInsets.all(12),
                                  decoration: BoxDecoration(
                                    color: Theme.of(context)
                                        .colorScheme
                                        .errorContainer,
                                    borderRadius: BorderRadius.circular(14),
                                  ),
                                  child: Row(
                                    crossAxisAlignment:
                                        CrossAxisAlignment.start,
                                    children: [
                                      Icon(
                                        Icons.error_outline_rounded,
                                        color: Theme.of(context)
                                            .colorScheme
                                            .onErrorContainer,
                                      ),
                                      const SizedBox(width: 9),
                                      Expanded(
                                        child: Text(
                                          _errorMessage!,
                                          style: TextStyle(
                                            color: Theme.of(context)
                                                .colorScheme
                                                .onErrorContainer,
                                          ),
                                        ),
                                      ),
                                    ],
                                  ),
                                ),
                              ],
                              const SizedBox(height: 16),
                              FilledButton.icon(
                                key: const Key('sign-in-button'),
                                onPressed: _submitting ? null : _submit,
                                icon: _submitting
                                    ? const SizedBox.square(
                                        dimension: 18,
                                        child: CircularProgressIndicator(
                                          strokeWidth: 2,
                                          color: Colors.white,
                                        ),
                                      )
                                    : const Icon(Icons.arrow_forward_rounded),
                                label: Text(
                                  _submitting ? 'Signing in...' : 'Sign in',
                                ),
                              ),
                            ],
                          ),
                        ),
                      ),
                    ),
                  ],
                ),
              ),
            ),
          ),
        ),
      ),
    );
  }
}

class _SpinaBrandHeader extends StatelessWidget {
  const _SpinaBrandHeader();

  @override
  Widget build(BuildContext context) {
    return Column(
      children: [
        Container(
          width: 56,
          height: 56,
          decoration: BoxDecoration(
            color: Colors.white,
            borderRadius: BorderRadius.circular(18),
            border: Border.all(color: const Color(0xFFF0D6E1)),
            boxShadow: [
              BoxShadow(
                color: Colors.black.withValues(alpha: 0.05),
                blurRadius: 20,
                offset: const Offset(0, 6),
              ),
            ],
          ),
          alignment: Alignment.center,
          child: const Text(
            'S',
            style: TextStyle(
              color: SpinaTheme.brandPinkDark,
              fontSize: 27,
              fontWeight: FontWeight.w900,
              letterSpacing: -1,
            ),
          ),
        ),
        const SizedBox(height: 8),
        Text(
          'SPINA',
          style: Theme.of(context).textTheme.headlineMedium?.copyWith(
                color: SpinaTheme.brandPinkDark,
                letterSpacing: 1.4,
              ),
        ),
      ],
    );
  }
}