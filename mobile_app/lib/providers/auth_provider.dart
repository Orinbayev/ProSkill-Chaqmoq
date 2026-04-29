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

  AuthSession? get session => _session;
  UserModel? get user => _session?.user;
  bool get isAuthenticated => _session != null;
  bool get isOfflineMode => _session?.isOffline ?? false;
  ViewState get state => _state;
  bool get isInitializing => _isInitializing;
  String? get errorMessage => _errorMessage;
  String? get inlineErrorMessage =>
      _errorPresentation == AuthErrorPresentation.inline ? _errorMessage : null;
  String? get bannerErrorMessage =>
      _errorPresentation == AuthErrorPresentation.banner ? _errorMessage : null;
  bool get hasInlineError => inlineErrorMessage != null;
  bool get hasBannerError => bannerErrorMessage != null;

  Future<void> restoreSession() async {
    _isInitializing = true;
    _errorMessage = null;
    _errorPresentation = null;
    notifyListeners();

    _session = await _authRepository.restoreSession();

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
    notifyListeners();

    try {
      _session = await _authRepository.login(
        login: login,
        phoneNumber: phoneNumber,
        password: password,
      );
      _state = ViewState.success;
      return true;
    } on AuthException catch (error) {
      _state = ViewState.error;
      _errorMessage = error.message;
      _errorPresentation = error.presentation;
      return false;
    } catch (error) {
      _state = ViewState.error;
      _errorMessage = _mapError(error);
      _errorPresentation = AuthErrorPresentation.banner;
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
    _state = ViewState.idle;
    notifyListeners();
  }

  Future<void> handleUnauthorized() async {
    _session = null;
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

  String _mapError(Object error) {
    return 'Kutilmagan xatolik yuz berdi';
  }
}
