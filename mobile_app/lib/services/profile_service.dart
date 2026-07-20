import 'package:chaqmoq_mobile/core/config/app_config.dart';
import 'package:chaqmoq_mobile/models/app_models.dart';
import 'package:chaqmoq_mobile/services/api_client.dart';
import 'package:dio/dio.dart';
import 'package:image_picker/image_picker.dart';

/// Barcha rollar uchun yagona profil API.
///
/// Backend:
/// - GET/PATCH `/api/mobile/profile/`
/// - POST `/api/mobile/profile/avatar/`
/// - POST `/api/mobile/auth/change-password/`
class ProfileService {
  ProfileService(this._apiClient);

  final ApiClient _apiClient;

  Future<UserModel> fetchProfile() async {
    final data = await _apiClient.get(AppConfig.profilePath);
    final userJson = data['user'] as Map<String, dynamic>? ?? data;
    return UserModel.fromJson(userJson);
  }

  Future<UserModel> updateProfile({
    String? ism,
    String? familya,
    String? phone,
  }) async {
    final data = await _apiClient.patch(
      AppConfig.profilePath,
      data: <String, dynamic>{
        if (ism != null) 'ism': ism,
        if (familya != null) 'familya': familya,
        if (phone != null) 'phone': phone,
      },
    );
    return UserModel.fromJson(data['user'] as Map<String, dynamic>);
  }

  Future<UserModel> uploadAvatar(XFile image) async {
    final data = await _apiClient.post(
      '${AppConfig.profilePath}avatar/',
      data: FormData.fromMap(<String, dynamic>{
        'avatar': await MultipartFile.fromFile(
          image.path,
          filename: image.name,
        ),
      }),
    );
    return UserModel.fromJson(data['user'] as Map<String, dynamic>);
  }

  Future<UserModel> removeAvatar() async {
    final data = await _apiClient.post(
      '${AppConfig.profilePath}avatar/',
      data: FormData.fromMap(<String, dynamic>{'clear': 'true'}),
    );
    return UserModel.fromJson(data['user'] as Map<String, dynamic>);
  }

  Future<void> changePassword({
    required String currentPassword,
    required String newPassword,
    required String confirmPassword,
  }) async {
    await _apiClient.post(
      AppConfig.changePasswordPath,
      data: <String, dynamic>{
        'current_password': currentPassword,
        'new_password': newPassword,
        'confirm_password': confirmPassword,
      },
    );
  }
}
