import 'package:flutter/material.dart';
import 'package:gilbic_mobile/src/core/auth/app_role.dart';
import 'package:gilbic_mobile/src/core/auth/session_store.dart';
import 'package:gilbic_mobile/src/core/auth/user_session.dart';
import 'package:gilbic_mobile/src/features/auth/login_page.dart';
import 'package:gilbic_mobile/src/features/dashboard/role_dashboard.dart';

class GilbicApp extends StatefulWidget {
  const GilbicApp({
    this.sessionStore,
    super.key,
  });

  final SessionStore? sessionStore;

  @override
  State<GilbicApp> createState() => _GilbicAppState();
}

class _GilbicAppState extends State<GilbicApp> {
  late final SessionStore _sessionStore;
  UserSession? _session;
  bool _loading = true;

  @override
  void initState() {
    super.initState();
    _sessionStore = widget.sessionStore ?? MemorySessionStore();
    _restoreSession();
  }

  Future<void> _restoreSession() async {
    final session = await _sessionStore.read();
    if (!mounted) {
      return;
    }
    setState(() {
      _session = session;
      _loading = false;
    });
  }

  Future<void> _signIn(String displayName, AppRole role) async {
    final session = UserSession(
      userId: 'development-user',
      displayName: displayName,
      role: role,
      accessToken: 'development-token',
    );
    await _sessionStore.write(session);
    if (!mounted) {
      return;
    }
    setState(() => _session = session);
  }

  Future<void> _signOut() async {
    await _sessionStore.clear();
    if (!mounted) {
      return;
    }
    setState(() => _session = null);
  }

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      title: 'Gilbic',
      debugShowCheckedModeBanner: false,
      theme: ThemeData(
        colorScheme: ColorScheme.fromSeed(seedColor: const Color(0xFF9C416D)),
        useMaterial3: true,
        inputDecorationTheme: const InputDecorationTheme(filled: true),
      ),
      home: _loading
          ? const Scaffold(body: Center(child: CircularProgressIndicator()))
          : _session == null
              ? LoginPage(onSignIn: _signIn)
              : RoleDashboard(session: _session!, onSignOut: _signOut),
    );
  }
}
