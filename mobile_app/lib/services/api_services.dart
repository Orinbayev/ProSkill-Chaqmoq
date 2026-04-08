import 'dart:io';

import 'package:chaqmoq_mobile/models/app_models.dart';
import 'package:chaqmoq_mobile/services/api_client.dart';
import 'package:chaqmoq_mobile/services/storage_service.dart';

class AuthService {
  AuthService({
    required ApiClient apiClient,
    required SecureStorageService storageService,
  }) : _apiClient = apiClient,
       _storageService = storageService;

  final ApiClient _apiClient;
  final SecureStorageService _storageService;

  Future<String?> readStoredSlug() => _storageService.readSlug();

  Future<AuthSession?> restoreSession() async {
    final token = await _storageService.readToken();
    final slug = await _storageService.readSlug();

    if (token == null || slug == null || token.isEmpty || slug.isEmpty) {
      return null;
    }

    _apiClient.configure(slug: slug, accessToken: token);

    try {
      final payload = await _apiClient.get('auth/status/');
      if (payload['authenticated'] != true) {
        await _storageService.clearToken();
        return null;
      }

      return AuthSession(
        accessToken: token,
        slug: slug,
        user: AppUser.fromJson(jsonMap(payload['user'])),
      );
    } catch (_) {
      await _storageService.clearToken();
      return null;
    }
  }

  Future<AuthSession> login({
    required String slug,
    required String identifier,
    required String password,
  }) async {
    final requestedSlug = slug.trim();
    if (requestedSlug.isEmpty) {
      throw ApiException('Markaz slugi kiritilmagan');
    }

    final payload = await _apiClient.postGlobal(
      'auth/login/',
      data: {
        'slug': requestedSlug,
        'username': identifier.trim(),
        'password': password,
        'device_name': 'Chaqmoq Mobile',
        'device_platform': Platform.operatingSystem,
      },
    );

    final token = jsonString(payload['access_token']);
    final user = AppUser.fromJson(jsonMap(payload['user']));
    var resolvedSlug = user.center?.slug.trim() ?? requestedSlug;

    if (resolvedSlug.isEmpty && user.isSuperuser) {
      resolvedSlug = requestedSlug;
    }

    if (!user.isSuperuser &&
        user.center != null &&
        user.center!.slug.isNotEmpty &&
        user.center!.slug.trim().toLowerCase() != requestedSlug.toLowerCase()) {
      throw ApiException(
        'Bu foydalanuvchi $requestedSlug markaziga tegishli emas',
      );
    }

    if (resolvedSlug.isEmpty) {
      throw ApiException(
        'Bu foydalanuvchi uchun markaz topilmadi. Administrator bilan bog\'laning.',
      );
    }

    await _storageService.saveToken(token);
    await _storageService.saveSlug(resolvedSlug);
    _apiClient.configure(slug: resolvedSlug, accessToken: token);

    return AuthSession(accessToken: token, slug: resolvedSlug, user: user);
  }

  Future<void> switchTenant({
    required String slug,
    required String token,
  }) async {
    await _storageService.saveSlug(slug.trim());
    _apiClient.configure(slug: slug.trim(), accessToken: token);
  }

  Future<void> logout() async {
    try {
      await _apiClient.post('auth/logout/');
    } catch (_) {}
    await _storageService.clearToken();
    _apiClient.clearSession();
  }
}

class DashboardService {
  DashboardService({required ApiClient apiClient}) : _apiClient = apiClient;

  final ApiClient _apiClient;

  Future<RoleHomeModel> fetchRoleHome() async {
    final payload = await _apiClient.get('home/');
    return RoleHomeModel.fromJson(payload);
  }

  Future<SuperadminHomeModel> fetchSuperadminHome() async {
    final payload = await _apiClient.get('superadmin/home/');
    return SuperadminHomeModel.fromJson(payload);
  }

  Future<Map<String, dynamic>> fetchDirectorDashboard() =>
      _apiClient.get('dashboard/director/');

  Future<Map<String, dynamic>> fetchTeacherHome() =>
      _apiClient.get('teacher/home/');
}

class StudentService {
  StudentService({required ApiClient apiClient}) : _apiClient = apiClient;

  final ApiClient _apiClient;

  Future<List<StudentModel>> fetchStudents({String? query}) async {
    final payload = await _apiClient.get(
      'students/',
      queryParameters: {'q': query},
    );
    return jsonMapList(payload['items']).map(StudentModel.fromJson).toList();
  }

  Future<StudentModel> createStudent(Map<String, dynamic> data) async {
    final payload = await _apiClient.post('students/', data: data);
    return StudentModel.fromJson(jsonMap(payload['student']));
  }
}

class TeacherService {
  TeacherService({required ApiClient apiClient}) : _apiClient = apiClient;

  final ApiClient _apiClient;

  Future<List<TeacherModel>> fetchTeachers({String? query}) async {
    final payload = await _apiClient.get(
      'teachers/',
      queryParameters: {'q': query},
    );
    return jsonMapList(payload['items']).map(TeacherModel.fromJson).toList();
  }

  Future<TeacherModel> createTeacher(Map<String, dynamic> data) async {
    final payload = await _apiClient.post('teachers/', data: data);
    return TeacherModel.fromJson(jsonMap(payload['teacher']));
  }
}

class GroupService {
  GroupService({required ApiClient apiClient}) : _apiClient = apiClient;

  final ApiClient _apiClient;

  Future<List<GroupModel>> fetchGroups() async {
    final payload = await _apiClient.get('groups/');
    return jsonMapList(payload['items']).map(GroupModel.fromJson).toList();
  }
}

class AttendanceService {
  AttendanceService({required ApiClient apiClient}) : _apiClient = apiClient;

  final ApiClient _apiClient;

  Future<AttendanceSheetData> fetchAttendanceSheet({
    required int groupId,
    required DateTime date,
  }) async {
    final payload = await _apiClient.get(
      'attendance/',
      queryParameters: {
        'group_id': groupId.toString(),
        'date': date.toIso8601String().split('T').first,
      },
    );
    return AttendanceSheetData.fromJson(payload);
  }

  Future<AttendanceSheetData> submitAttendance({
    required int groupId,
    required DateTime date,
    required List<Map<String, dynamic>> items,
  }) async {
    final payload = await _apiClient.post(
      'attendance/',
      data: {
        'group_id': groupId,
        'date': date.toIso8601String().split('T').first,
        'items': items,
      },
    );
    return AttendanceSheetData.fromJson(payload);
  }
}

class PaymentService {
  PaymentService({required ApiClient apiClient}) : _apiClient = apiClient;

  final ApiClient _apiClient;

  Future<(List<PaymentModel>, int)> fetchPayments({String? query}) async {
    final payload = await _apiClient.get(
      'payments/',
      queryParameters: {'q': query},
    );
    final items = jsonMapList(
      payload['items'],
    ).map(PaymentModel.fromJson).toList();
    final total = jsonInt(jsonMap(payload['summary'])['total_amount']);
    return (items, total);
  }

  Future<PaymentModel> createPayment({
    required int enrollmentId,
    required int cashAmount,
    required int cardAmount,
    required DateTime month,
    String note = '',
  }) async {
    final payload = await _apiClient.post(
      'payments/',
      data: {
        'enrollment_id': enrollmentId,
        'cash_amount': cashAmount,
        'card_amount': cardAmount,
        'month': month.toIso8601String().split('T').first,
        'note': note,
      },
    );
    return PaymentModel.fromJson(jsonMap(payload['payment']));
  }
}

class NotificationsService {
  NotificationsService({required ApiClient apiClient}) : _apiClient = apiClient;

  final ApiClient _apiClient;

  Future<(List<AppNotification>, int)> fetchNotifications() async {
    final payload = await _apiClient.get('notifications/');
    final items = jsonMapList(
      payload['items'],
    ).map(AppNotification.fromJson).toList();
    return (items, jsonInt(payload['unread_count']));
  }

  Future<int> markAllRead() async {
    final payload = await _apiClient.post('notifications/read-all/');
    return jsonInt(payload['updated_count']);
  }
}

class ProfileService {
  ProfileService({required ApiClient apiClient}) : _apiClient = apiClient;

  final ApiClient _apiClient;

  Future<AppUser> updateProfile(Map<String, dynamic> data) async {
    final payload = await _apiClient.patch('profile/', data: data);
    return AppUser.fromJson(jsonMap(payload['user']));
  }
}
