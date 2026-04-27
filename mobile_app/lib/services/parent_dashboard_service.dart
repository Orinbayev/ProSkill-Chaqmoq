import 'package:chaqmoq_mobile/core/config/app_config.dart';
import 'package:chaqmoq_mobile/models/app_models.dart';
import 'package:chaqmoq_mobile/models/parent_models.dart';
import 'package:chaqmoq_mobile/services/api_client.dart';

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
  }) async {
    final queryParameters = <String, dynamic>{};
    if (childId != null) {
      queryParameters['child_id'] = childId;
    }
    if (month != null) {
      queryParameters['month'] =
          '${month.year.toString().padLeft(4, '0')}-${month.month.toString().padLeft(2, '0')}';
    }
    final payload = await _apiClient.get(
      AppConfig.attendancePath,
      queryParameters: queryParameters.isEmpty ? null : queryParameters,
    );
    return ParentAttendanceModel.fromJson(payload);
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

  Future<ParentProgressModel> fetchProgress({int? childId}) async {
    final payload = await _apiClient.get(
      AppConfig.progressPath,
      queryParameters: childId == null
          ? null
          : <String, dynamic>{'child_id': childId},
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
      '/api/mobile/parent/select-child/',
      data: <String, dynamic>{'child_id': childId},
    );
    return ParentChildModel.fromJson(
      (payload['selected_child'] as Map?)?.cast<String, dynamic>() ??
          const <String, dynamic>{},
    );
  }
}
