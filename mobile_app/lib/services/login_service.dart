import 'package:chaqmoq_mobile/core/config/app_config.dart';
import 'package:chaqmoq_mobile/models/login_models.dart';
import 'package:chaqmoq_mobile/services/api_client.dart';
import 'package:flutter/foundation.dart';

class LoginService {
  const LoginService({required ApiClient apiClient}) : _apiClient = apiClient;

  final ApiClient _apiClient;

  Future<LoginResponse> login(LoginRequest request) async {
    if (kDebugMode) {
      debugPrint(
        '[Chaqmoq Auth] env=${AppConfig.environmentName} '
        'POST ${AppConfig.baseUrl}${AppConfig.loginPath} ${request.toDebugJson()}',
      );
    }
    final payload = await _apiClient.post(
      AppConfig.loginPath,
      data: request.toJson(),
    );
    return LoginResponse.fromJson(payload);
  }
}
