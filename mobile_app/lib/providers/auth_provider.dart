import 'dart:async';

import 'package:chaqmoq_mobile/models/app_models.dart';
import 'package:chaqmoq_mobile/repositories/auth_repository.dart';
import 'package:flutter/foundation.dart';

class AuthProvider extends ChangeNotifier {
  AuthProvider({required AuthRepository authRepository})
    : _authRepository = authRepository;

  final AuthRepository _authRepository;

  AuthSession? _session;
  ViewState _state = ViewState.idle;
  String? _errorMessage;
  AuthErrorPresentation? _errorPresentation;
  bool _isInitializing = true;

  // Race-shield: increments on every successful auth state mutation.
  // restoreSession() captures this at start; if it changes mid-call, the
  // restore result is dropped (a login completed in the meantime).
  int _sessionEpoch = 0;

  // Brief window after login where we ignore stale 401 errors that may come
  // from in-flight requests configured with the previous (or empty) token.
  bool _ignoreUnauthorized = false;
  Timer? _ignoreUnauthorizedTimer;

  // Just-logged-in flag: powers a transient success splash before the gate
  // switches to the home shell.
  bool _justAuthenticated = false;
  Timer? _justAuthenticatedTimer;

  AuthSession? get session => _session;
  UserModel? get user => _session?.user;
  bool get isAuthenticated => _session != null;
  bool get isOfflineMode => _session?.isOffline ?? false;
  ViewState get state => _state;
  bool get isInitializing => _isInitializing;
  bool get justAuthenticated => _justAuthenticated;
  String? get errorMessage => _errorMessage;
  String? get inlineErrorMessage =>
      _errorPresentation == AuthErrorPresentation.inline ? _errorMessage : null;
  String? get bannerErrorMessage =>
      _errorPresentation == AuthErrorPresentation.banner ? _errorMessage : null;
  bool get hasInlineError => inlineErrorMessage != null;
  bool get hasBannerError => bannerErrorMessage != null;

  Future<void> restoreSession() async {
    final epochAtStart = _sessionEpoch;
    _isInitializing = true;
    _errorMessage = null;
    _errorPresentation = null;
    notifyListeners();

    final result = await _authRepository.restoreSession();

    // If a login completed while we were restoring, the user's freshly
    // established session must NOT be overwritten by a null/expired result.
    if (epochAtStart != _sessionEpoch) {
      _isInitializing = false;
      notifyListeners();
      return;
    }

    _session = result;
    _isInitializing = false;
    notifyListeners();
  }

  Future<bool> login({
    String? login,
    String? phoneNumber,
    required String password,
  }) async {
    _state = ViewState.loading;
    _errorMessage = null;
    _errorPresentation = null;
    // Suppress stale 401s that may arrive from older in-flight requests.
    _armIgnoreUnauthorized();
    notifyListeners();

    try {
      final newSession = await _authRepository.login(
        login: login,
        phoneNumber: phoneNumber,
        password: password,
      );
      _session = newSession;
      _sessionEpoch += 1;
      _state = ViewState.success;
      _flashJustAuthenticated();
      return true;
    } on AuthException catch (error) {
      _state = ViewState.error;
      _errorMessage = error.message;
      _errorPresentation = error.presentation;
      _disarmIgnoreUnauthorized();
      return false;
    } catch (error) {
      _state = ViewState.error;
      _errorMessage = _mapError(error);
      _errorPresentation = AuthErrorPresentation.banner;
      _disarmIgnoreUnauthorized();
      return false;
    } finally {
      notifyListeners();
    }
  }

  Future<void> logout() async {
    _state = ViewState.loading;
    notifyListeners();
    await _authRepository.logout();
    _session = null;
    _sessionEpoch += 1;
    _state = ViewState.idle;
    notifyListeners();
  }

  Future<void> handleUnauthorized() async {
    // Right after a successful login, swallow any stale 401 from prior
    // in-flight requests so they don't bounce the user back to the login
    // screen.
    if (_ignoreUnauthorized) {
      return;
    }
    _session = null;
    _sessionEpoch += 1;
    _state = ViewState.error;
    _errorMessage = 'Sessiya yakunlandi. Qayta tizimga kiring.';
    _errorPresentation = AuthErrorPresentation.banner;
    notifyListeners();
  }

  void clearError() {
    if (_errorMessage == null && _errorPresentation == null) {
      return;
    }
    _errorMessage = null;
    _errorPresentation = null;
    if (_state == ViewState.error) {
      _state = ViewState.idle;
    }
    notifyListeners();
  }

  void updateUser(UserModel user) {
    if (_session == null) {
      return;
    }
    _session = _session!.copyWith(user: user);
    notifyListeners();
  }

  void _armIgnoreUnauthorized() {
    _ignoreUnauthorized = true;
    _ignoreUnauthorizedTimer?.cancel();
    // After 4s the protection auto-disarms, so genuine session expirations
    // are still propagated to the user.
    _ignoreUnauthorizedTimer = Timer(const Duration(seconds: 4), () {
      _ignoreUnauthorized = false;
    });
  }

  void _disarmIgnoreUnauthorized() {
    _ignoreUnauthorized = false;
    _ignoreUnauthorizedTimer?.cancel();
    _ignoreUnauthorizedTimer = null;
  }

  void _flashJustAuthenticated() {
    _justAuthenticated = true;
    _justAuthenticatedTimer?.cancel();
    _justAuthenticatedTimer = Timer(const Duration(milliseconds: 900), () {
      _justAuthenticated = false;
      notifyListeners();
    });
  }

  @override
  void dispose() {
    _ignoreUnauthorizedTimer?.cancel();
    _justAuthenticatedTimer?.cancel();
    super.dispose();
  }

  String _mapError(Object error) {
    return 'Kutilmagan xatolik yuz berdi';
  }
}
