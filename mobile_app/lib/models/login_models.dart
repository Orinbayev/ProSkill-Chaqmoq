import 'package:chaqmoq_mobile/models/app_models.dart';

class LoginRequest {
  const LoginRequest.login({
    required this.login,
    required this.password,
    this.centerSlug = '',
  }) : phoneNumber = null;

  const LoginRequest.phone({
    required this.phoneNumber,
    required this.password,
    this.centerSlug = '',
  }) : login = null;

  final String? login;
  final String? phoneNumber;
  final String password;
  final String centerSlug;

  Map<String, dynamic> toJson() {
    final normalizedLogin = login?.trim() ?? '';
    final normalizedPhoneNumber = phoneNumber?.trim() ?? '';
    return {
      if (normalizedLogin.isNotEmpty) 'login': normalizedLogin,
      if (normalizedPhoneNumber.isNotEmpty)
        'phone_number': normalizedPhoneNumber,
      'password': password,
      if (centerSlug.trim().isNotEmpty) 'center_slug': centerSlug.trim(),
    };
  }

  Map<String, dynamic> toDebugJson() {
    final payload = toJson();
    payload['password'] = '********';
    return payload;
  }
}

class LoginResponse {
  const LoginResponse({required this.accessToken, required this.user});

  final String accessToken;
  final UserModel user;

  factory LoginResponse.fromJson(Map<String, dynamic> json) {
    return LoginResponse(
      accessToken: jsonString(json['access_token']).isNotEmpty
          ? jsonString(json['access_token'])
          : jsonString(json['access']),
      user: UserModel.fromJson(jsonMap(json['user'])),
    );
  }
}
