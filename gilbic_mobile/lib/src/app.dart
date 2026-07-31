import 'package:flutter/material.dart';
import 'package:gilbic_mobile/src/core/auth/auth_repository.dart';
import 'package:gilbic_mobile/src/core/auth/session_store.dart';
import 'package:gilbic_mobile/src/core/auth/user_session.dart';
import 'package:gilbic_mobile/src/core/collector/collector_route_cache.dart';
import 'package:gilbic_mobile/src/core/collector/collector_route_loader.dart';
import 'package:gilbic_mobile/src/core/collector/collector_route_repository.dart';
import 'package:gilbic_mobile/src/core/network/spina_api.dart';
import 'package:gilbic_mobile/src/features/auth/login_page.dart';
import 'package:gilbic_mobile/src/features/dashboard/role_dashboard.dart';

class GilbicApp extends StatefulWidget {
  const GilbicApp({
    this.sessionStore,
    this.authRepository,
    this.collectorRouteRepository,
    this.collectorRouteCache,
    this.collectorRouteLoader,
    super.key,
  });

  final SessionStore? sessionStore;
  final AuthRepository? authRepository;
  final CollectorRouteRepository? collectorRouteRepository;
  final CollectorRouteCache? collectorRouteCache;
  final CollectorRouteLoader? collectorRouteLoader;

  @override
  State<GilbicApp> createState() => _GilbicAppState();
}

class _GilbicAppState extends State<GilbicApp> {
  late final SessionStore _sessionStore;
  late final AuthRepository _authRepository;
  late final CollectorRouteLoader _collectorRouteLoader;
  CollectorRouteCache? _collectorRouteCache;
  UserSession? _session;
  bool _loading = true;

  @override
  void initState() {
    super.initState();
    _sessionStore = widget.sessionStore ?? SecureSessionStore();
    _authRepository = widget.authRepository ?? SpinaAuthRepository();

    final suppliedLoader = widget.collectorRouteLoader;
    if (suppliedLoader != null) {
      _collectorRouteLoader = suppliedLoader;
      _collectorRouteCache = widget.collectorRouteCache;
    } else {
      final cache = widget.collectorRouteCache ?? SqlCipherCollectorRouteCache();
      _collectorRouteCache = cache;
      _collectorRouteLoader = CachedCollectorRouteLoader(
        remote: widget.collectorRouteRepository ??
            SpinaCollectorRouteRepository(),
        cache: cache,
      );
    }
    _restoreSession();
  }

  Future<void> _restoreSession() async {
    UserSession? session;
    try {
      session = await _sessionStore.read();
    } on Exception {
      await _sessionStore.clear();
    }
    if (!mounted) {
      return;
    }
    setState(() {
      _session = session;
      _loading = false;
    });
  }

  Future<String?> _signIn(String username, String password) async {
    try {
      final session = await _authRepository.signIn(
        username: username,
        password: password,
      );
      await _sessionStore.write(session);
      if (!mounted) {
        return null;
      }
      setState(() => _session = session);
      return null;
    } on SpinaApiException catch (error) {
      return error.message;
    } on Exception {
      return 'Gilbic could not complete the login request.';
    }
  }

  Future<void> _signOut() async {
    final session = _session;
    if (session != null) {
      await _authRepository.signOut(session);
      try {
        await _collectorRouteCache?.clearForUser(session.userId);
      } on Object {
        // Session removal must continue even if the local cache is unavailable.
      }
    }
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
              : RoleDashboard(
                  session: _session!,
                  onSignOut: _signOut,
                  collectorRouteLoader: _collectorRouteLoader,
                ),
    );
  }
}
