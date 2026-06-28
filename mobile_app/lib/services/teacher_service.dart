import 'package:chaqmoq_mobile/models/app_models.dart';
import 'package:chaqmoq_mobile/models/teacher_models.dart';
import 'package:chaqmoq_mobile/services/api_client.dart';
import 'package:dio/dio.dart';
import 'package:image_picker/image_picker.dart';

class TeacherService {
  const TeacherService({required this.apiClient});

  final ApiClient apiClient;

  Future<List<TeacherGroupModel>> getGroups() async {
    final data = await apiClient.get('/api/mobile/teacher/groups/');
    final list = data['groups'] as List? ?? [];
    return list.map((e) => TeacherGroupModel.fromJson(e as Map<String, dynamic>)).toList();
  }

  Future<TeacherAttendanceDay> getGroupStudents(int groupId, {DateTime? date}) async {
    final dateStr = (date ?? DateTime.now()).toIso8601String().substring(0, 10);
    final data = await apiClient.get(
      '/api/mobile/teacher/groups/$groupId/students/',
      queryParameters: {'date': dateStr},
    );
    final group = TeacherGroupModel.fromJson(data['group'] as Map<String, dynamic>);
    final students = (data['students'] as List? ?? [])
        .map((e) => TeacherStudentModel.fromJson(e as Map<String, dynamic>))
        .toList();
    return TeacherAttendanceDay(
      group: group,
      date: DateTime.parse(jsonString(data['date'])),
      students: students,
    );
  }

  Future<bool> markAttendance({
    required int groupId,
    required int studentId,
    required bool present,
    DateTime? date,
  }) async {
    final dateStr = (date ?? DateTime.now()).toIso8601String().substring(0, 10);
    final data = await apiClient.post(
      '/api/mobile/teacher/attendance/mark/',
      data: {'group_id': groupId, 'student_id': studentId, 'present': present, 'date': dateStr},
    );
    return jsonBool(data['present']);
  }

  Future<TeacherIncomeModel> getIncome({int? year, int? month}) async {
    final now = DateTime.now();
    final data = await apiClient.get(
      '/api/mobile/teacher/income/',
      queryParameters: {
        'year': '${year ?? now.year}',
        'month': '${month ?? now.month}',
      },
    );
    return TeacherIncomeModel.fromJson(data);
  }

  Future<UserModel> updateProfile({
    String? ism,
    String? familya,
    String? phone,
  }) async {
    final data = await apiClient.patch(
      '/api/mobile/profile/',
      data: {
        if (ism != null) 'ism': ism,
        if (familya != null) 'familya': familya,
        if (phone != null) 'phone': phone,
      },
    );
    return UserModel.fromJson(data['user'] as Map<String, dynamic>);
  }

  Future<UserModel> uploadAvatar(XFile image) async {
    final data = await apiClient.post(
      '/api/mobile/profile/avatar/',
      data: FormData.fromMap(<String, dynamic>{
        'avatar': await MultipartFile.fromFile(image.path, filename: image.name),
      }),
    );
    return UserModel.fromJson(data['user'] as Map<String, dynamic>);
  }

  Future<UserModel> removeAvatar() async {
    final data = await apiClient.post(
      '/api/mobile/profile/avatar/',
      data: FormData.fromMap(<String, dynamic>{'clear': 'true'}),
    );
    return UserModel.fromJson(data['user'] as Map<String, dynamic>);
  }

  Future<void> changePassword({
    required String currentPassword,
    required String newPassword,
    required String confirmPassword,
  }) async {
    await apiClient.post(
      '/api/mobile/auth/change-password/',
      data: {
        'current_password': currentPassword,
        'new_password': newPassword,
        'confirm_password': confirmPassword,
      },
    );
  }
}
