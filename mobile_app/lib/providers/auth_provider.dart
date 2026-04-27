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
  bool _isInitializing = true;

  AuthSession? get session => _session;
  UserModel? get user => _session?.user;
  bool get isAuthenticated => _session != null;
  ViewState get state => _state;
  bool get isInitializing => _isInitializing;
  String? get errorMessage => _errorMessage;

  Future<void> restoreSession() async {
    _isInitializing = true;
    _errorMessage = null;
    notifyListeners();

    _session = await _authRepository.restoreSession();

    _isInitializing = false;
    notifyListeners();
  }

  Future<bool> login({required String login, required String password}) async {
    _state = ViewState.loading;
    _errorMessage = null;
    notifyListeners();

    try {
      _session = await _authRepository.login(login: login, password: password);
      _state = ViewState.success;
      return true;
    } catch (error) {
      _state = ViewState.error;
      _errorMessage = _mapError(error);
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
    if (error is AuthException) {
      return error.message;
    }
    return 'Serverda xatolik yuz berdi';
  }
}
