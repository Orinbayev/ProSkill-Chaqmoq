import 'package:chaqmoq_mobile/models/app_models.dart';

class LoginRequest {
  const LoginRequest({
    required this.login,
    required this.password,
    this.centerSlug = '',
  });

  final String login;
  final String password;
  final String centerSlug;

  Map<String, dynamic> toJson() {
    return {
      'login': login,
      'password': password,
      if (centerSlug.trim().isNotEmpty) 'center_slug': centerSlug.trim(),
    };
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
