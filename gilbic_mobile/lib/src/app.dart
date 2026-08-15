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
  static const String _expiredSessionNotice =
      'Your login session expired or is no longer valid. Sign in again.';
  static const String _revokedSessionNotice =
      'This account or device is no longer authorized for this session. '
      'Sign in again or contact Management.';

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
  String? _updateRequiredMessage;
  String? _sessionNotice;

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
    String? updateRequiredMessage;
    String? sessionNotice;
    try {
      session = await _sessionStore.read();
      if (session != null) {
        if (session.isExpired) {
          session = await _refreshStoredSession(session);
        } else {
          session = await _validateStoredSession(session);
        }
      }
    } on SpinaApiException catch (error) {
      if (session != null) {
        try {
          await _collectorRouteCache?.clearForUser(session.userId);
        } on Object {
          // Invalid-session cleanup must continue if local cache storage fails.
        }
        session.clearRefreshOverride();
      }
      await _sessionStore.clear();
      if (error.statusCode == 426) {
        updateRequiredMessage = error.message;
      } else {
        sessionNotice = _sessionNoticeForError(error);
      }
      session = null;
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
      sessionNotice =
          'Gilbic could not restore your secure login session. Sign in again.';
      session = null;
    }
    if (!mounted) {
      return;
    }
    setState(() {
      _session = session;
      _updateRequiredMessage = updateRequiredMessage;
      _sessionNotice = sessionNotice;
      _loading = false;
    });
    _scheduleSessionRefresh(session);
  }

  Future<UserSession> _refreshStoredSession(UserSession current) async {
    final refresher = _authRepository;
    if (refresher is! SessionRefreshRepository) {
      throw const SpinaApiException(
        _expiredSessionNotice,
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
      if (_isTerminalSessionError(error) || error.statusCode == 426) {
        rethrow;
      }
      return current;
    } on Exception {
      return current;
    }
  }

  Future<String?> _signIn(String username, String password) async {
    if (mounted && _sessionNotice != null) {
      setState(() => _sessionNotice = null);
    }
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
      setState(() {
        _session = session;
        _updateRequiredMessage = null;
        _sessionNotice = null;
      });
      _scheduleSessionRefresh(session);
      return null;
    } on SpinaApiException catch (error) {
      if (error.statusCode == 426) {
        await _showUpdateRequired(null, error.message);
        return null;
      }
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

  Future<void> _invalidateLocalSession(
    UserSession session, {
    String? notice,
  }) async {
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
    setState(() {
      _session = null;
      _sessionNotice = notice;
    });
  }

  Future<void> _showUpdateRequired(
    UserSession? session,
    String message,
  ) async {
    _sessionRefreshTimer?.cancel();
    if (session != null) {
      try {
        await _collectorRouteCache?.clearForUser(session.userId);
      } on Object {
        // Update enforcement must not depend on local cache cleanup succeeding.
      }
      session.clearRefreshOverride();
    }
    await _sessionStore.clear();
    if (!mounted) {
      return;
    }
    setState(() {
      _session = null;
      _sessionNotice = null;
      _updateRequiredMessage = message;
      _loading = false;
    });
  }

  bool _isTerminalSessionError(SpinaApiException error) {
    return error.statusCode == 401 || error.statusCode == 403;
  }

  String _sessionNoticeForError(SpinaApiException error) {
    if (error.statusCode == 401) {
      return _expiredSessionNotice;
    }
    if (error.statusCode == 403) {
      return _revokedSessionNotice;
    }
    final message = error.message.trim();
    return message.isEmpty
        ? 'Gilbic could not restore your secure login session. Sign in again.'
        : message;
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
      await _invalidateLocalSession(
        current,
        notice: _expiredSessionNotice,
      );
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
      if (error.statusCode == 426) {
        await _showUpdateRequired(current, error.message);
      } else if (_isTerminalSessionError(error)) {
        await _invalidateLocalSession(
          current,
          notice: _sessionNoticeForError(error),
        );
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
      if (error.statusCode == 426) {
        await _showUpdateRequired(current, error.message);
      } else if (_isTerminalSessionError(error)) {
        await _invalidateLocalSession(
          current,
          notice: _sessionNoticeForError(error),
        );
      } else if (current.isExpired) {
        await _invalidateLocalSession(
          current,
          notice: _expiredSessionNotice,
        );
      } else {
        _scheduleRefreshRetry();
      }
    } on Exception {
      if (current.isExpired) {
        await _invalidateLocalSession(
          current,
          notice: _expiredSessionNotice,
        );
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
          : _updateRequiredMessage != null
              ? _UpdateRequiredPage(message: _updateRequiredMessage!)
              : _session == null
                  ? LoginPage(
                      onSignIn: _signIn,
                      noticeMessage: _sessionNotice,
                      clientRegistrationRepository:
                          _clientRegistrationRepository,
                    )
                  : EnhancedRoleDashboard(
                      session: _session!,
                      onSignOut: _signOut,
                      collectorRouteLoader: _collectorRouteLoader,
                      paymentSubmissionRepository:
                          _paymentSubmissionRepository,
                      deviceIdentityProvider: _deviceIdentityProvider,
                      collectionDeviceSequence: _collectionDeviceSequence,
                    ),
    );
  }
}

class _UpdateRequiredPage extends StatelessWidget {
  const _UpdateRequiredPage({required this.message});

  final String message;

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      key: const Key('app-update-required'),
      body: SafeArea(
        child: Center(
          child: ConstrainedBox(
            constraints: const BoxConstraints(maxWidth: 520),
            child: Padding(
              padding: const EdgeInsets.all(24),
              child: Column(
                mainAxisSize: MainAxisSize.min,
                children: <Widget>[
                  Icon(
                    Icons.system_update_alt,
                    size: 56,
                    color: Theme.of(context).colorScheme.primary,
                  ),
                  const SizedBox(height: 20),
                  Text(
                    'Update required',
                    style: Theme.of(context).textTheme.headlineSmall,
                    textAlign: TextAlign.center,
                  ),
                  const SizedBox(height: 12),
                  Text(message, textAlign: TextAlign.center),
                  const SizedBox(height: 12),
                  Text(
                    'Install the latest Gilbic build, then reopen the app.',
                    style: Theme.of(context).textTheme.bodySmall,
                    textAlign: TextAlign.center,
                  ),
                ],
              ),
            ),
          ),
        ),
      ),
    );
  }
}
