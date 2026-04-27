import 'package:chaqmoq_mobile/core/config/app_config.dart';
import 'package:chaqmoq_mobile/models/app_models.dart';
import 'package:chaqmoq_mobile/models/login_models.dart';
import 'package:chaqmoq_mobile/services/api_client.dart';
import 'package:chaqmoq_mobile/services/login_service.dart';
import 'package:chaqmoq_mobile/services/storage_service.dart';

class AuthException implements Exception {
  const AuthException(this.message);

  final String message;

  @override
  String toString() => message;
}

class AuthRepository {
  AuthRepository({
    required ApiClient apiClient,
    required LoginService loginService,
    required StorageService storageService,
  }) : _apiClient = apiClient,
       _loginService = loginService,
       _storageService = storageService;

  final ApiClient _apiClient;
  final LoginService _loginService;
  final StorageService _storageService;

  Future<AuthSession?> restoreSession() async {
    final token = await _storageService.readToken();
    final slug = await _storageService.readSlug();
    final cachedUser = await _storageService.readUser();

    if (slug == null || slug.isEmpty) {
      return null;
    }

    _apiClient.configure(accessToken: token, slug: slug);

    try {
      final payload = await _apiClient.get(AppConfig.authStatusPath);
      final authenticated = payload['authenticated'] == null
          ? true
          : jsonBool(payload['authenticated']);
      if (!authenticated) {
        await _storageService.clearAuth();
        return null;
      }

      final userPayload = jsonMap(payload['user']);
      final user = userPayload.isEmpty
          ? cachedUser
          : UserModel.fromJson(userPayload);

      if (user == null) {
        await _storageService.clearAuth();
        return null;
      }

      final session = AuthSession(
        accessToken: token ?? '',
        slug: user.center?.slug.isNotEmpty == true ? user.center!.slug : slug,
        user: user,
      );
      await _storageService.saveSession(session);
      _apiClient.configure(
        accessToken: session.accessToken,
        slug: session.slug,
      );
      return session;
    } catch (_) {
      await _storageService.clearAuth();
      return null;
    }
  }

  Future<AuthSession> login({
    required String login,
    required String password,
  }) async {
    try {
      final response = await _loginService.login(
        LoginRequest(
          login: login.trim(),
          password: password,
          centerSlug: AppConfig.defaultCenterSlug,
        ),
      );
      final user = response.user;
      final session = AuthSession(
        accessToken: response.accessToken,
        slug: user.center?.slug.isNotEmpty == true
            ? user.center!.slug
            : AppConfig.defaultCenterSlug,
        user: user,
      );
      await _storageService.saveSession(session);
      _apiClient.configure(
        accessToken: session.accessToken,
        slug: session.slug,
      );
      return session;
    } on ApiException catch (error) {
      throw AuthException(_friendlyLoginError(error));
    } catch (_) {
      throw const AuthException('Serverga ulanib bo‘lmadi');
    }
  }

  Future<void> logout() async {
    try {
      await _postFirst(const ['/api/mobile/auth/logout/', '/api/auth/logout/']);
    } catch (_) {}

    await _storageService.clearAuth();
    _apiClient.clearSession();
  }

  Future<Map<String, dynamic>> _postFirst(List<String> paths) async {
    Object? lastError;
    for (final path in paths) {
      try {
        return await _apiClient.post(path);
      } catch (error) {
        lastError = error;
      }
    }
    if (lastError is ApiException) {
      throw lastError;
    }
    throw ApiException('So‘rov bajarilmadi');
  }

  String _friendlyLoginError(ApiException error) {
    final status = error.statusCode;
    final code = error.code;
    if (code == 'invalid_credentials' || status == 401) {
      return 'Login yoki parol noto‘g‘ri';
    }
    if (code == 'center_not_found') {
      return 'O‘quv markazi topilmadi';
    }
    if (code == 'center_mismatch') {
      return 'Bu akkaunt tanlangan o‘quv markaziga tegishli emas';
    }
    if (code == 'role_required' ||
        code == 'center_required' ||
        code == 'permission_denied') {
      return 'Bu akkaunt mobil ilovaga ruxsat etilmagan';
    }
    if (status == 403) {
      return 'Bu akkaunt mobil ilovaga ruxsat etilmagan';
    }
    if (status == 404) {
      return 'Login endpoint topilmadi';
    }
    if (status != null && status >= 500) {
      return 'Serverda xatolik yuz berdi';
    }
    if (status == null || status == 408 || status == 429) {
      return 'Serverga ulanib bo‘lmadi';
    }
    return 'Serverda xatolik yuz berdi';
  }
}
