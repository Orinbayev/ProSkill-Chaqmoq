import 'package:chaqmoq_mobile/models/app_models.dart';
import 'package:chaqmoq_mobile/services/api_client.dart';
import 'package:chaqmoq_mobile/services/api_services.dart';
import 'package:flutter/foundation.dart';

class AuthProvider extends ChangeNotifier {
  AuthProvider({required AuthService authService}) : _authService = authService;

  final AuthService _authService;

  AuthSession? _session;
  bool _isInitializing = true;
  bool _isBusy = false;
  String? _errorMessage;
  String _lastUsedSlug = '';

  AuthSession? get session => _session;
  AppUser? get user => _session?.user;
  bool get isInitializing => _isInitializing;
  bool get isBusy => _isBusy;
  bool get isAuthenticated => _session != null;
  String? get errorMessage => _errorMessage;
  String get lastUsedSlug => _session?.slug ?? _lastUsedSlug;

  String _messageFromError(Object error) {
    if (error is ApiException) {
      return error.message;
    }
    return 'Kutilmagan xatolik yuz berdi';
  }

  Future<void> restoreSession() async {
    _isInitializing = true;
    _errorMessage = null;
    notifyListeners();

    _lastUsedSlug = await _authService.readStoredSlug() ?? '';
    _session = await _authService.restoreSession();

    _isInitializing = false;
    notifyListeners();
  }

  Future<bool> login({
    required String slug,
    required String identifier,
    required String password,
  }) async {
    _isBusy = true;
    _errorMessage = null;
    notifyListeners();

    try {
      _session = await _authService.login(
        slug: slug,
        identifier: identifier,
        password: password,
      );
      _lastUsedSlug = _session?.slug ?? '';
      return true;
    } catch (error) {
      _errorMessage = _messageFromError(error);
      return false;
    } finally {
      _isBusy = false;
      notifyListeners();
    }
  }

  Future<void> logout() async {
    _isBusy = true;
    notifyListeners();

    await _authService.logout();
    _session = null;

    _isBusy = false;
    notifyListeners();
  }

  Future<void> switchTenant(String slug) async {
    if (_session == null) {
      return;
    }
    await _authService.switchTenant(slug: slug, token: _session!.accessToken);
    _session = _session!.copyWith(slug: slug);
    _lastUsedSlug = slug;
    notifyListeners();
  }

  void replaceUser(AppUser user) {
    if (_session == null) {
      return;
    }
    _session = _session!.copyWith(user: user);
    notifyListeners();
  }
}
