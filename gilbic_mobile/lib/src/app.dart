import 'package:gilbic_mobile/src/core/mirror/mirror_controller.dart';
import 'package:gilbic_mobile/src/core/mirror/mirror_repository.dart';
import 'package:gilbic_mobile/src/features/mirror/mirror_host.dart';
import 'package:gilbic_mobile/src/features/mirror/mirror_viewer_page.dart';
import 'package:gilbic_mobile/src/features/mirror/safe_mirror_surface.dart';
import 'dart:async';

import 'package:flutter/material.dart';
import 'package:gilbic_mobile/src/core/auth/auth_repository.dart';
import 'package:gilbic_mobile/src/core/auth/session_store.dart';
import 'package:gilbic_mobile/src/core/auth/user_session.dart';
import 'package:gilbic_mobile/src/core/media/image_recovery_controller.dart';
import 'package:gilbic_mobile/src/features/shared/image_recovery_scope.dart';
import 'package:gilbic_mobile/src/core/collector/collector_route_cache.dart';
import 'package:gilbic_mobile/src/core/collector/collector_route_cache_factory.dart';
import 'package:gilbic_mobile/src/core/collector/collector_route_loader.dart';
import 'package:gilbic_mobile/src/core/collector/collector_route_repository.dart';
import 'package:gilbic_mobile/src/core/device/device_identity.dart';
import 'package:gilbic_mobile/src/core/employee_operations/employee_operations_service.dart';
import 'package:gilbic_mobile/src/core/loans/client_loan_repository.dart';
import 'package:gilbic_mobile/src/core/network/spina_api.dart';
import 'package:gilbic_mobile/src/core/payments/collection_device_sequence.dart';
import 'package:gilbic_mobile/src/core/payments/payment_submission_repository.dart';
import 'package:gilbic_mobile/src/features/auth/login_page.dart';
import 'package:gilbic_mobile/src/features/dashboard/enhanced_role_dashboard.dart';
import 'package:gilbic_mobile/src/theme/spina_theme.dart';

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
    this.clientLoanRepository,
    this.employeeOperationsService,
    this.imageRecoveryController,
    this.mirrorController,
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
  final ClientLoanRepository? clientLoanRepository;
  final EmployeeOperationsService? employeeOperationsService;
  final ImageRecoveryController? imageRecoveryController;
  final MirrorController? mirrorController;

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
  late final EmployeeOperationsService _employeeOperations;
  late final ImageRecoveryController _imageRecovery;
  late final MirrorController _mirror;
  late final MirrorNavigationObserver _mirrorNavigation;
  final _navigator = GlobalKey<NavigatorState>();
  CollectorRouteCache? _collectorRouteCache;
  UserSession? _session;
  Timer? _sessionRefreshTimer;
  bool _loading = true;
  bool _refreshingSession = false;
  int _sessionGeneration = 0;
  Future<void> _sessionStorageWork = Future<void>.value();
  String? _updateRequiredMessage;
  String? _sessionNotice;

  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addObserver(this);
    _sessionStore = widget.sessionStore ?? SecureSessionStore();
    _imageRecovery =
        widget.imageRecoveryController ?? ImageRecoveryController();
    _authRepository = widget.authRepository ?? SpinaAuthRepository();
    _paymentSubmissionRepository =
        widget.paymentSubmissionRepository ??
        SpinaPaymentSubmissionRepository();
    _deviceIdentityProvider =
        widget.deviceIdentityProvider ?? DeviceIdentityProvider();
    _collectionDeviceSequence =
        widget.collectionDeviceSequence ?? SecureCollectionDeviceSequence();
    _employeeOperations =
        widget.employeeOperationsService ??
        EmployeeOperationsService(
          deviceIdentityProvider: _deviceIdentityProvider,
        );

    _mirror =
        widget.mirrorController ??
        MirrorController(
          SpinaMirrorRepository(
            session: () => _session,
            deviceId: () async {
              final identity = await _deviceIdentityProvider.load();
              if (!_mirror.deviceChanged(identity.installationId)) {
                throw const SpinaApiException(
                  'Device changed. Request consent again.',
                );
              }
              return identity.installationId;
            },
          ),
        );
    _mirrorNavigation = MirrorNavigationObserver(_mirror);
    final suppliedLoader = widget.collectorRouteLoader;
    if (suppliedLoader != null) {
      _collectorRouteLoader = suppliedLoader;
      _collectorRouteCache = widget.collectorRouteCache;
    } else {
      final cache =
          widget.collectorRouteCache ?? createDefaultCollectorRouteCache();
      _collectorRouteCache = cache;
      _collectorRouteLoader = CachedCollectorRouteLoader(
        remote:
            widget.collectorRouteRepository ?? SpinaCollectorRouteRepository(),
        cache: cache,
      );
    }
    _restoreSession();
  }

  @override
  void dispose() {
    _sessionGeneration++;
    _mirror.attach(null);
    if (widget.mirrorController == null) _mirror.dispose();
    WidgetsBinding.instance.removeObserver(this);
    _sessionRefreshTimer?.cancel();
    _employeeOperations.attach(null);
    if (widget.employeeOperationsService == null) _employeeOperations.dispose();
    if (widget.imageRecoveryController == null) _imageRecovery.dispose();
    super.dispose();
  }

  @override
  void didChangeAppLifecycleState(AppLifecycleState state) {
    _mirror.foreground(state == AppLifecycleState.resumed);
    _employeeOperations.foreground(state == AppLifecycleState.resumed);
    if (state == AppLifecycleState.resumed) {
      unawaited(_revalidateSessionOnResume());
    }
  }

  Future<void> _restoreSession() async {
    final generation = _sessionGeneration;
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
        // Validation may fail temporarily after the stored token has expired.
        // Only a still-valid session may enter the offline fallback shell.
        if (session.isExpired) {
          throw const SpinaApiException(_expiredSessionNotice, statusCode: 401);
        }
      }
    } on SpinaApiException catch (error) {
      if (!_isCurrentGeneration(generation)) return;
      if (session != null) {
        try {
          await _collectorRouteCache?.clearForUser(session.userId);
        } on Object {
          // Invalid-session cleanup must continue if local cache storage fails.
        }
        session.clearRefreshOverride();
      }
      await _persistSession(null, generation);
      if (error.statusCode == 426) {
        updateRequiredMessage = error.message;
      } else {
        sessionNotice = _sessionNoticeForError(error);
      }
      session = null;
    } on Exception {
      if (!_isCurrentGeneration(generation)) return;
      if (session != null) {
        try {
          await _collectorRouteCache?.clearForUser(session.userId);
        } on Object {
          // Invalid-session cleanup must continue if local cache storage fails.
        }
        session.clearRefreshOverride();
      }
      await _persistSession(null, generation);
      sessionNotice =
          'SPINA could not restore your secure login session. Sign in again.';
      session = null;
    }
    if (!_isCurrentGeneration(generation)) {
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
    final generation = _sessionGeneration;
    final refresher = _authRepository;
    if (refresher is! SessionRefreshRepository) {
      throw const SpinaApiException(_expiredSessionNotice, statusCode: 401);
    }
    final refreshed = await (refresher as SessionRefreshRepository).refresh(
      current,
    );
    if (!_isCurrentGeneration(generation)) return current;
    await _persistSession(refreshed, generation);
    if (!_isCurrentGeneration(generation)) return current;
    current.applyRefresh(refreshed);
    return refreshed;
  }

  Future<UserSession> _validateStoredSession(UserSession current) async {
    final generation = _sessionGeneration;
    final validator = _authRepository;
    if (validator is! SessionValidationRepository) {
      return current;
    }
    try {
      final validated = await (validator as SessionValidationRepository)
          .validate(current);
      if (!_isCurrentGeneration(generation)) return current;
      await _persistSession(validated, generation);
      if (!_isCurrentGeneration(generation)) return current;
      current.applyRefresh(validated);
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
    final generation = ++_sessionGeneration;
    _refreshingSession = false;
    if (mounted && _sessionNotice != null) {
      setState(() => _sessionNotice = null);
    }
    try {
      final session = await _authRepository.signIn(
        username: username,
        password: password,
      );
      if (!_isCurrentGeneration(generation)) return null;
      session.clearRefreshOverride();
      await _persistSession(session, generation);
      if (!_isCurrentGeneration(generation)) {
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
      if (!_isCurrentGeneration(generation)) return null;
      if (error.statusCode == 426) {
        await _showUpdateRequired(null, error.message);
        return null;
      }
      return error.message;
    } on Exception {
      return 'SPINA could not complete the login request.';
    }
  }

  Future<void> _signOut() async {
    final session = _session;
    final cleanup = _invalidateLocalSession(session);
    if (session != null) {
      unawaited(_revokeRemoteSession(session));
    }
    await cleanup;
  }

  Future<void> _revokeRemoteSession(UserSession session) async {
    try {
      await _authRepository
          .signOut(session)
          .timeout(const Duration(seconds: 5));
    } on Object {
      // Local sign-out is complete even if remote revocation is unavailable.
    }
  }

  bool _isCurrentGeneration(int generation) =>
      mounted && generation == _sessionGeneration;

  Future<void> _persistSession(UserSession? session, int generation) {
    final operation = _sessionStorageWork.then((_) async {
      if (!_isCurrentGeneration(generation)) return;
      if (session == null) {
        await _sessionStore.clear();
      } else {
        await _sessionStore.write(session);
      }
    });
    // Keep writes/clears ordered even when secure storage reports an error.
    _sessionStorageWork = operation.catchError((Object _) {});
    return operation;
  }

  Future<void> _invalidateLocalSession(
    UserSession? session, {
    String? notice,
    String? updateRequiredMessage,
  }) async {
    final generation = ++_sessionGeneration;
    _refreshingSession = false;
    _mirror.attach(null);
    _employeeOperations.attach(null);
    _sessionRefreshTimer?.cancel();
    session?.clearRefreshOverride();
    if (mounted) {
      setState(() {
        _session = null;
        _sessionNotice = notice;
        _updateRequiredMessage = updateRequiredMessage;
        _loading = false;
      });
    }
    await _persistSession(null, generation);
    try {
      if (session != null) {
        await _collectorRouteCache?.clearForUser(session.userId);
      }
    } on Object {
      // Session removal must continue even if the local cache is unavailable.
    }
  }

  Future<void> _showUpdateRequired(UserSession? session, String message) async {
    await _invalidateLocalSession(session, updateRequiredMessage: message);
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
        ? 'SPINA could not restore your secure login session. Sign in again.'
        : message;
  }

  void _scheduleSessionRefresh(UserSession? session) {
    _mirror.attach(session);
    _employeeOperations.attach(session);
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
    final needsRefresh =
        expiry == null ||
        !expiry.isAfter(DateTime.now().toUtc().add(_refreshLeadTime));
    final refreshToken = current.refreshToken?.trim() ?? '';
    if (needsRefresh &&
        _authRepository is SessionRefreshRepository &&
        refreshToken.isNotEmpty) {
      await _refreshSessionIfNeeded(force: true);
      return;
    }
    if (current.isExpired) {
      await _invalidateLocalSession(current, notice: _expiredSessionNotice);
      return;
    }
    await _validateCurrentSession();
  }

  Future<void> _validateCurrentSession() async {
    final generation = _sessionGeneration;
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
      final validated = await (validator as SessionValidationRepository)
          .validate(current);
      if (!_isCurrentGeneration(generation)) return;
      await _persistSession(validated, generation);
      if (!_isCurrentGeneration(generation)) {
        return;
      }
      current.applyRefresh(validated);
      setState(() => _session = validated);
      _scheduleSessionRefresh(validated);
    } on SpinaApiException catch (error) {
      if (!_isCurrentGeneration(generation)) return;
      if (error.statusCode == 426) {
        await _showUpdateRequired(current, error.message);
      } else if (_isTerminalSessionError(error)) {
        await _invalidateLocalSession(
          current,
          notice: _sessionNoticeForError(error),
        );
      } else if (current.isExpired) {
        await _invalidateLocalSession(current, notice: _expiredSessionNotice);
      } else {
        // The refresh timer may have fired while validation held the guard.
        _scheduleSessionRefresh(current);
      }
    } on Exception {
      if (!_isCurrentGeneration(generation)) return;
      if (current.isExpired) {
        await _invalidateLocalSession(current, notice: _expiredSessionNotice);
      } else {
        _scheduleSessionRefresh(current);
      }
    } finally {
      if (_isCurrentGeneration(generation)) _refreshingSession = false;
    }
  }

  Future<void> _refreshSessionIfNeeded({bool force = false}) async {
    final generation = _sessionGeneration;
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
    final needsRefresh =
        expiry == null ||
        !expiry.isAfter(DateTime.now().toUtc().add(_refreshLeadTime));
    if (!force && !needsRefresh) {
      _scheduleSessionRefresh(current);
      return;
    }

    _refreshingSession = true;
    try {
      final refreshed = await (refresher as SessionRefreshRepository).refresh(
        current,
      );
      if (!_isCurrentGeneration(generation)) return;
      await _persistSession(refreshed, generation);
      if (!_isCurrentGeneration(generation)) {
        return;
      }
      current.applyRefresh(refreshed);
      setState(() => _session = refreshed);
      _scheduleSessionRefresh(refreshed);
    } on SpinaApiException catch (error) {
      if (!_isCurrentGeneration(generation)) return;
      if (error.statusCode == 426) {
        await _showUpdateRequired(current, error.message);
      } else if (_isTerminalSessionError(error)) {
        await _invalidateLocalSession(
          current,
          notice: _sessionNoticeForError(error),
        );
      } else if (current.isExpired) {
        await _invalidateLocalSession(current, notice: _expiredSessionNotice);
      } else {
        _scheduleRefreshRetry();
      }
    } on Exception {
      if (!_isCurrentGeneration(generation)) return;
      if (current.isExpired) {
        await _invalidateLocalSession(current, notice: _expiredSessionNotice);
      } else {
        _scheduleRefreshRetry();
      }
    } finally {
      if (_isCurrentGeneration(generation)) _refreshingSession = false;
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
    final roles = List<String>.of(session.roles)..sort();
    return '${session.userId}|${session.rawRole.toLowerCase()}|${roles.join('|')}|${permissions.join('|')}';
  }

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      key: ValueKey<String>(_authorizationScopeKey(_session)),
      navigatorKey: _navigator,
      navigatorObservers: [_mirrorNavigation],
      title: 'SPINA',
      debugShowCheckedModeBanner: false,
      theme: SpinaTheme.light,
      builder: (context, child) => MirrorHost(
        controller: _mirror,
        onOpenViewer: () => _navigator.currentState?.push(
          MaterialPageRoute<void>(
            builder: (_) => MirrorViewerPage(controller: _mirror),
          ),
        ),
        child: ImageRecoveryHost(
          controller: _imageRecovery,
          session: _session,
          sessionRestored: !_loading,
          deviceIdentityProvider: _deviceIdentityProvider,
          child: EmployeeOperationsScope(
            service: _employeeOperations,
            child: child!,
          ),
        ),
      ),
      home: _loading
          ? const Scaffold(body: Center(child: CircularProgressIndicator()))
          : _updateRequiredMessage != null
          ? _UpdateRequiredPage(message: _updateRequiredMessage!)
          : _session == null
          ? LoginPage(onSignIn: _signIn, noticeMessage: _sessionNotice)
          : EnhancedRoleDashboard(
              session: _session!,
              onSignOut: _signOut,
              collectorRouteLoader: _collectorRouteLoader,
              paymentSubmissionRepository: _paymentSubmissionRepository,
              deviceIdentityProvider: _deviceIdentityProvider,
              collectionDeviceSequence: _collectionDeviceSequence,
              clientLoanRepository: widget.clientLoanRepository,
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
              child: Card(
                child: Padding(
                  padding: const EdgeInsets.all(28),
                  child: Column(
                    mainAxisSize: MainAxisSize.min,
                    children: <Widget>[
                      Container(
                        width: 72,
                        height: 72,
                        decoration: BoxDecoration(
                          color: SpinaTheme.brandPinkSoft,
                          borderRadius: BorderRadius.circular(24),
                        ),
                        child: const Icon(
                          Icons.system_update_alt_rounded,
                          size: 36,
                          color: SpinaTheme.brandPinkDark,
                        ),
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
                        'Install the latest SPINA build, then reopen the app.',
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
    );
  }
}
