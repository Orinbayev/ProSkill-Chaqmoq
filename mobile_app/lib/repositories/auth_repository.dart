import 'package:chaqmoq_mobile/core/config/app_config.dart';
import 'package:chaqmoq_mobile/models/app_models.dart';
import 'package:chaqmoq_mobile/models/login_models.dart';
import 'package:chaqmoq_mobile/services/api_client.dart';
import 'package:chaqmoq_mobile/services/login_service.dart';
import 'package:chaqmoq_mobile/services/storage_service.dart';

enum AuthErrorPresentation { inline, banner }

class AuthException implements Exception {
  const AuthException(
    this.message, {
    this.presentation = AuthErrorPresentation.banner,
  });

  final String message;
  final AuthErrorPresentation presentation;

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

    if (slug == null || slug.isEmpty || cachedUser == null) {
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
    } on ApiException catch (error) {
      if (_canRecoverFromOffline(error)) {
        return AuthSession(
          accessToken: token ?? '',
          slug: slug,
          user: cachedUser,
          isOffline: true,
        );
      }
      await _storageService.clearAuth();
      return null;
    } catch (_) {
      return AuthSession(
        accessToken: token ?? '',
        slug: slug,
        user: cachedUser,
        isOffline: true,
      );
    }
  }

  Future<AuthSession> login({
    String? login,
    String? phoneNumber,
    required String password,
  }) async {
    try {
      final normalizedLogin = (login ?? '').trim();
      final normalizedPhoneNumber = (phoneNumber ?? '').trim();
      if (normalizedLogin.isEmpty && normalizedPhoneNumber.isEmpty) {
        throw const AuthException(
          'Email, login yoki telefon raqamini kiriting',
          presentation: AuthErrorPresentation.inline,
        );
      }

      final rememberedSlug = await _storageService.readLastCenterSlug();
      final configuredSlug = AppConfig.defaultCenterSlug.trim().isNotEmpty
          ? AppConfig.defaultCenterSlug.trim()
          : (rememberedSlug ?? '').trim();
      final response = await _loginService.login(
        normalizedPhoneNumber.isNotEmpty
            ? LoginRequest.phone(
                phoneNumber: normalizedPhoneNumber,
                password: password,
                centerSlug: configuredSlug,
              )
            : LoginRequest.login(
                login: normalizedLogin,
                password: password,
                centerSlug: configuredSlug,
              ),
      );
      final user = response.user;
      final session = AuthSession(
        accessToken: response.accessToken,
        slug: user.center?.slug.isNotEmpty == true
            ? user.center!.slug
            : configuredSlug,
        user: user,
      );
      await _storageService.saveSession(session);
      _apiClient.configure(
        accessToken: session.accessToken,
        slug: session.slug,
      );
      return session;
    } on ApiException catch (error) {
      throw _mapLoginError(error);
    } on AuthException {
      rethrow;
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

  AuthException _mapLoginError(ApiException error) {
    final status = error.statusCode;
    final code = error.code;
    final message = error.message.trim();
    if (code == 'user_not_found') {
      return const AuthException(
        'Bunday foydalanuvchi topilmadi',
        presentation: AuthErrorPresentation.inline,
      );
    }
    if (code == 'inactive_user') {
      return const AuthException(
        'Akkaunt faol emas. Administrator bilan bog‘laning.',
        presentation: AuthErrorPresentation.inline,
      );
    }
    if (code == 'invalid_password') {
      return const AuthException(
        'Parol noto‘g‘ri',
        presentation: AuthErrorPresentation.inline,
      );
    }
    if (code == 'invalid_credentials' || status == 400 || status == 401) {
      return const AuthException(
        'Login yoki parol noto‘g‘ri',
        presentation: AuthErrorPresentation.inline,
      );
    }
    if (code == 'center_not_found') {
      return const AuthException('O‘quv markazi topilmadi');
    }
    if (code == 'center_mismatch') {
      return const AuthException(
        'Bu akkaunt tanlangan o‘quv markaziga tegishli emas',
      );
    }
    if (code == 'role_required' ||
        code == 'center_required' ||
        code == 'permission_denied') {
      return const AuthException('Bu akkaunt mobil ilovaga ruxsat etilmagan');
    }
    if (status == 403) {
      return const AuthException('Bu akkaunt mobil ilovaga ruxsat etilmagan');
    }
    if (status == 404) {
      return const AuthException('Login endpoint topilmadi');
    }
    if (code == 'network_offline') {
      return const AuthException('Internet aloqasini tekshiring');
    }
    if (code == 'timeout') {
      return const AuthException('So‘rov vaqti tugadi, qayta urinib ko‘ring');
    }
    if (status != null && status >= 500) {
      return const AuthException('Serverga ulanib bo‘lmadi');
    }
    if (code == 'network' || status == null || status == 408 || status == 429) {
      return const AuthException('Serverga ulanib bo‘lmadi');
    }
    if (message.isNotEmpty) {
      return AuthException(message);
    }
    return const AuthException('Serverga ulanib bo‘lmadi');
  }

  bool _canRecoverFromOffline(ApiException error) {
    final status = error.statusCode ?? 0;
    return error.code == 'network' ||
        error.code == 'network_offline' ||
        error.code == 'timeout' ||
        error.code == 'server_unavailable' ||
        error.code == 'rate_limited' ||
        status >= 500;
  }
}
