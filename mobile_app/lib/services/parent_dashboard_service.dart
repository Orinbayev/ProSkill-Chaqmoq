import 'package:chaqmoq_mobile/core/config/app_config.dart';
import 'package:chaqmoq_mobile/models/app_models.dart';
import 'package:chaqmoq_mobile/models/parent_models.dart';
import 'package:chaqmoq_mobile/services/api_client.dart';
import 'package:dio/dio.dart';
import 'package:image_picker/image_picker.dart';

class ParentDashboardService {
  const ParentDashboardService(this._apiClient);

  final ApiClient _apiClient;

  Future<ParentDashboardModel> fetchDashboard({int? childId}) async {
    final payload = await _apiClient.get(
      AppConfig.parentDashboardPath,
      queryParameters: childId == null
          ? null
          : <String, dynamic>{'child_id': childId},
    );
    return ParentDashboardModel.fromJson(payload);
  }

  Future<ParentAttendanceModel> fetchAttendance({
    int? childId,
    DateTime? month,
    DateTime? from,
    DateTime? to,
    int? groupId,
  }) async {
    final queryParameters = <String, dynamic>{};
    if (childId != null) {
      queryParameters['child_id'] = childId;
    }
    if (month != null) {
      queryParameters['month'] =
          '${month.year.toString().padLeft(4, '0')}-${month.month.toString().padLeft(2, '0')}';
    }
    if (from != null) {
      queryParameters['from'] = _formatIsoDate(from);
    }
    if (to != null) {
      queryParameters['to'] = _formatIsoDate(to);
    }
    if (groupId != null) {
      queryParameters['group_id'] = groupId;
    }
    final payload = await _apiClient.get(
      AppConfig.attendancePath,
      queryParameters: queryParameters.isEmpty ? null : queryParameters,
    );
    return ParentAttendanceModel.fromJson(payload);
  }

  static String _formatIsoDate(DateTime date) {
    final y = date.year.toString().padLeft(4, '0');
    final m = date.month.toString().padLeft(2, '0');
    final d = date.day.toString().padLeft(2, '0');
    return '$y-$m-$d';
  }

  Future<ParentPaymentsModel> fetchPayments({int? childId}) async {
    final payload = await _apiClient.get(
      AppConfig.paymentsPath,
      queryParameters: childId == null
          ? null
          : <String, dynamic>{'child_id': childId},
    );
    return ParentPaymentsModel.fromJson(payload);
  }

  Future<ParentProgressModel> fetchProgress({
    int? childId,
    String? period,
  }) async {
    final queryParameters = <String, dynamic>{};
    if (childId != null) {
      queryParameters['child_id'] = childId;
    }
    if ((period ?? '').trim().isNotEmpty) {
      queryParameters['period'] = period!.trim();
    }
    final payload = await _apiClient.get(
      AppConfig.progressPath,
      queryParameters: queryParameters.isEmpty ? null : queryParameters,
    );
    return ParentProgressModel.fromJson(payload);
  }

  Future<ParentProfileModel> fetchProfile() async {
    final payload = await _apiClient.get(AppConfig.parentProfilePath);
    return ParentProfileModel.fromJson(payload);
  }

  Future<ParentProfileModel> updateProfile({
    required String fullName,
    required String phone,
    required String email,
  }) async {
    final payload = await _apiClient.patch(
      AppConfig.parentProfilePath,
      data: <String, dynamic>{
        'full_name': fullName,
        'phone': phone,
        'email': email,
      },
    );
    return ParentProfileModel.fromJson(payload);
  }

  Future<ParentProfileModel> updateProfileAvatar({
    XFile? image,
    bool clear = false,
  }) async {
    if (image == null && !clear) {
      throw ApiException('Profil rasmi tanlanmadi');
    }
    final payload = await _apiClient.post(
      AppConfig.parentProfileAvatarPath,
      data: FormData.fromMap(<String, dynamic>{
        if (clear) 'clear': 'true',
        if (image != null)
          'avatar': await MultipartFile.fromFile(
            image.path,
            filename: image.name,
          ),
      }),
    );
    return ParentProfileModel.fromJson(payload);
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

  Future<ParentChildModel> addChild(String childCode) async {
    final payload = await _apiClient.post(
      AppConfig.addChildPath,
      data: <String, dynamic>{'child_code': childCode},
    );
    final childPayload = jsonMap(payload['child']);
    if (childPayload.isEmpty) {
      throw ApiException('Farzand qo‘shish funksiyasi tez orada ulanadi');
    }
    return ParentChildModel.fromJson(childPayload);
  }

  Future<ParentChildModel> selectChild(int childId) async {
    final payload = await _apiClient.post(
      AppConfig.selectChildPath,
      data: <String, dynamic>{'child_id': childId},
    );
    return ParentChildModel.fromJson(
      (payload['selected_child'] as Map?)?.cast<String, dynamic>() ??
          const <String, dynamic>{},
    );
  }

  Future<Map<String, bool>> fetchNotificationPreferences() async {
    final payload = await _apiClient.get(
      AppConfig.parentNotificationPreferencesPath,
    );
    final settings = jsonMap(payload['settings']);
    return <String, bool>{
      'attendance': jsonBool(settings['attendance']),
      'payments': jsonBool(settings['payments']),
      'progress': jsonBool(settings['progress']),
      'general': jsonBool(settings['general']),
    };
  }

  Future<Map<String, bool>> updateNotificationPreferences({
    required bool attendance,
    required bool payments,
    required bool progress,
    required bool general,
  }) async {
    final payload = await _apiClient.patch(
      AppConfig.parentNotificationPreferencesPath,
      data: <String, dynamic>{
        'attendance': attendance,
        'payments': payments,
        'progress': progress,
        'general': general,
      },
    );
    final settings = jsonMap(payload['settings']);
    return <String, bool>{
      'attendance': jsonBool(settings['attendance']),
      'payments': jsonBool(settings['payments']),
      'progress': jsonBool(settings['progress']),
      'general': jsonBool(settings['general']),
    };
  }
}
