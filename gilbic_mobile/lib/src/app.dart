import 'dart:async';

import 'package:flutter/material.dart';
import 'package:gilbic_mobile/src/core/auth/auth_repository.dart';
import 'package:gilbic_mobile/src/core/auth/session_store.dart';
import 'package:gilbic_mobile/src/core/auth/user_session.dart';
import 'package:gilbic_mobile/src/core/collector/collector_route_cache.dart';
import 'package:gilbic_mobile/src/core/collector/collector_route_loader.dart';
import 'package:gilbic_mobile/src/core/collector/collector_route_repository.dart';
import 'package:gilbic_mobile/src/core/device/device_identity.dart';
import 'package:gilbic_mobile/src/core/network/spina_api.dart';
import 'package:gilbic_mobile/src/core/payments/collection_device_sequence.dart';
import 'package:gilbic_mobile/src/core/payments/payment_submission_repository.dart';
import 'package:gilbic_mobile/src/features/auth/login_page.dart';
import 'package:gilbic_mobile/src/features/dashboard/enhanced_role_dashboard.dart';

class GilbicApp extends StatefulWidget {
  const GilbicApp({
    this.sessionStore,
    this.authRepository,
    this.collectorRouteRepository,
    this.collectorRouteCache,
    this.collectorRouteLoader,
    this.paymentSubmissionRepository,
    this.deviceIdentityProvider,
    this.collectionDeviceSequence,
    super.key,
  });

  final SessionStore? sessionStore;
  final AuthRepository? authRepository;
  final CollectorRouteRepository? collectorRouteRepository;
  final CollectorRouteCache? collectorRouteCache;
  final CollectorRouteLoader? collectorRouteLoader;
  final PaymentSubmissionRepository? paymentSubmissionRepository;
  final DeviceIdentityProvider? deviceIdentityProvider;
  final CollectionDeviceSequence? collectionDeviceSequence;

  @override
  State<GilbicApp> createState() => _GilbicAppState();
}

class _GilbicAppState extends State<GilbicApp> with WidgetsBindingObserver {
  static const Duration _refreshLeadTime = Duration(minutes: 2);
  static const Duration _refreshRetryDelay = Duration(seconds: 30);

  late final SessionStore _sessionStore;
  late final AuthRepository _authRepository;
  late final CollectorRouteLoader _collectorRouteLoader;
  late final PaymentSubmissionRepository _paymentSubmissionRepository;
  late final DeviceIdentityProvider _deviceIdentityProvider;
  late final CollectionDeviceSequence _collectionDeviceSequence;
  CollectorRouteCache? _collectorRouteCache;
  UserSession? _session;
  Timer? _sessionRefreshTimer;
  bool _loading = true;
  bool _refreshingSession = false;

  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addObserver(this);
    _sessionStore = widget.sessionStore ?? SecureSessionStore();
    _authRepository = widget.authRepository ?? SpinaAuthRepository();
    _paymentSubmissionRepository = widget.paymentSubmissionRepository ??
        SpinaPaymentSubmissionRepository();
    _deviceIdentityProvider =
        widget.deviceIdentityProvider ?? DeviceIdentityProvider();
    _collectionDeviceSequence = widget.collectionDeviceSequence ??
        SecureCollectionDeviceSequence();

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

  @override
  void dispose() {
    WidgetsBinding.instance.removeObserver(this);
    _sessionRefreshTimer?.cancel();
    super.dispose();
  }

  @override
  void didChangeAppLifecycleState(AppLifecycleState state) {
    if (state == AppLifecycleState.resumed) {
      unawaited(_revalidateSessionOnResume());
    }
  }

  Future<void> _restoreSession() async {
    UserSession? session;
    try {
      session = await _sessionStore.read();
      if (session != null) {
        if (session.isExpired) {
          session = await _refreshStoredSession(session);
        } else {
          session = await _validateStoredSession(session);
        }
      }
    } on Exception {
      if (session != null) {
        try {
          await _collectorRouteCache?.clearForUser(session.userId);
        } on Object {
          // Invalid-session cleanup must continue if local cache storage fails.
        }
        session.clearRefreshOverride();
      }
      await _sessionStore.clear();
      session = null;
    }
    if (!mounted) {
      return;
    }
    setState(() {
      _session = session;
      _loading = false;
    });
    _scheduleSessionRefresh(session);
  }

  Future<UserSession> _refreshStoredSession(UserSession current) async {
    final refresher = _authRepository;
    if (refresher is! SessionRefreshRepository) {
      throw const SpinaApiException(
        'Your login session expired. Sign in again.',
        statusCode: 401,
      );
    }
    final refreshed =
        await (refresher as SessionRefreshRepository).refresh(current);
    current.applyRefresh(refreshed);
    await _sessionStore.write(refreshed);
    return refreshed;
  }

  Future<UserSession> _validateStoredSession(UserSession current) async {
    final validator = _authRepository;
    if (validator is! SessionValidationRepository) {
      return current;
    }
    try {
      final validated =
          await (validator as SessionValidationRepository).validate(current);
      current.applyRefresh(validated);
      await _sessionStore.write(validated);
      return validated;
    } on SpinaApiException catch (error) {
      if (_isTerminalSessionError(error)) {
        rethrow;
      }
      return current;
    } on Exception {
      return current;
    }
  }

  Future<String?> _signIn(String username, String password) async {
    try {
      final session = await _authRepository.signIn(
        username: username,
        password: password,
      );
      session.clearRefreshOverride();
      await _sessionStore.write(session);
      if (!mounted) {
        return null;
      }
      setState(() => _session = session);
      _scheduleSessionRefresh(session);
      return null;
    } on SpinaApiException catch (error) {
      return error.message;
    } on Exception {
      return 'Gilbic could not complete the login request.';
    }
  }

  ClientRegistrationRepository? get _clientRegistrationRepository {
    final repository = _authRepository;
    return repository is ClientRegistrationRepository
        ? repository as ClientRegistrationRepository
        : null;
  }

  Future<void> _signOut() async {
    _sessionRefreshTimer?.cancel();
    final session = _session;
    if (session != null) {
      await _authRepository.signOut(session);
      await _invalidateLocalSession(session);
      return;
    }
    await _sessionStore.clear();
  }

  Future<void> _invalidateLocalSession(UserSession session) async {
    _sessionRefreshTimer?.cancel();
    try {
      await _collectorRouteCache?.clearForUser(session.userId);
    } on Object {
      // Session removal must continue even if the local cache is unavailable.
    }
    session.clearRefreshOverride();
    await _sessionStore.clear();
    if (!mounted) {
      return;
    }
    setState(() => _session = null);
  }

  bool _isTerminalSessionError(SpinaApiException error) {
    return error.statusCode == 401 || error.statusCode == 403;
  }

  void _scheduleSessionRefresh(UserSession? session) {
    _sessionRefreshTimer?.cancel();
    final refresher = _authRepository;
    final refreshToken = session?.refreshToken?.trim() ?? '';
    final expiry = session?.expiresAt;
    if (session == null ||
        refresher is! SessionRefreshRepository ||
        refreshToken.isEmpty ||
        expiry == null) {
      return;
    }

    final refreshAt = expiry.subtract(_refreshLeadTime);
    final delay = refreshAt.difference(DateTime.now().toUtc());
    _sessionRefreshTimer = Timer(
      delay.isNegative ? Duration.zero : delay,
      () => unawaited(_refreshSessionIfNeeded(force: true)),
    );
  }

  Future<void> _revalidateSessionOnResume() async {
    final current = _session;
    if (current == null) {
      return;
    }

    final expiry = current.expiresAt;
    final needsRefresh = expiry == null ||
        !expiry.isAfter(DateTime.now().toUtc().add(_refreshLeadTime));
    final refreshToken = current.refreshToken?.trim() ?? '';
    if (needsRefresh &&
        _authRepository is SessionRefreshRepository &&
        refreshToken.isNotEmpty) {
      await _refreshSessionIfNeeded(force: true);
      return;
    }
    if (current.isExpired) {
      await _invalidateLocalSession(current);
      return;
    }
    await _validateCurrentSession();
  }

  Future<void> _validateCurrentSession() async {
    if (_refreshingSession) {
      return;
    }
    final current = _session;
    final validator = _authRepository;
    if (current == null || validator is! SessionValidationRepository) {
      return;
    }

    _refreshingSession = true;
    try {
      final validated =
          await (validator as SessionValidationRepository).validate(current);
      current.applyRefresh(validated);
      await _sessionStore.write(validated);
      if (!mounted) {
        return;
      }
      setState(() => _session = validated);
      _scheduleSessionRefresh(validated);
    } on SpinaApiException catch (error) {
      if (_isTerminalSessionError(error)) {
        await _invalidateLocalSession(current);
      }
    } on Exception {
      // A temporary network failure must not destroy a still-valid local session.
    } finally {
      _refreshingSession = false;
    }
  }

  Future<void> _refreshSessionIfNeeded({bool force = false}) async {
    if (_refreshingSession) {
      return;
    }
    final current = _session;
    final refresher = _authRepository;
    final refreshToken = current?.refreshToken?.trim() ?? '';
    if (current == null ||
        refresher is! SessionRefreshRepository ||
        refreshToken.isEmpty) {
      return;
    }

    final expiry = current.expiresAt;
    final needsRefresh = expiry == null ||
        !expiry.isAfter(DateTime.now().toUtc().add(_refreshLeadTime));
    if (!force && !needsRefresh) {
      _scheduleSessionRefresh(current);
      return;
    }

    _refreshingSession = true;
    try {
      final refreshed =
          await (refresher as SessionRefreshRepository).refresh(current);
      current.applyRefresh(refreshed);
      await _sessionStore.write(refreshed);
      if (!mounted) {
        return;
      }
      setState(() => _session = refreshed);
      _scheduleSessionRefresh(refreshed);
    } on SpinaApiException catch (error) {
      if (_isTerminalSessionError(error) || current.isExpired) {
        await _invalidateLocalSession(current);
      } else {
        _scheduleRefreshRetry();
      }
    } on Exception {
      if (current.isExpired) {
        await _invalidateLocalSession(current);
      } else {
        _scheduleRefreshRetry();
      }
    } finally {
      _refreshingSession = false;
    }
  }

  void _scheduleRefreshRetry() {
    _sessionRefreshTimer?.cancel();
    _sessionRefreshTimer = Timer(
      _refreshRetryDelay,
      () => unawaited(_refreshSessionIfNeeded(force: true)),
    );
  }

  String _authorizationScopeKey(UserSession? session) {
    if (session == null) {
      return 'signed-out';
    }
    final permissions = List<String>.of(session.permissions)..sort();
    return '${session.userId}|${session.rawRole.toLowerCase()}|${permissions.join('|')}';
  }

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      key: ValueKey<String>(_authorizationScopeKey(_session)),
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
              ? LoginPage(
                  onSignIn: _signIn,
                  clientRegistrationRepository: _clientRegistrationRepository,
                )
              : EnhancedRoleDashboard(
                  session: _session!,
                  onSignOut: _signOut,
                  collectorRouteLoader: _collectorRouteLoader,
                  paymentSubmissionRepository: _paymentSubmissionRepository,
                  deviceIdentityProvider: _deviceIdentityProvider,
                  collectionDeviceSequence: _collectionDeviceSequence,
                ),
    );
  }
}
