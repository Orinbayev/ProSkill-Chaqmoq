import 'package:chaqmoq_mobile/models/app_models.dart';
import 'package:chaqmoq_mobile/services/api_client.dart';
import 'package:chaqmoq_mobile/services/api_services.dart';
import 'package:flutter/foundation.dart';

class DashboardProvider extends ChangeNotifier {
  DashboardProvider({required DashboardService dashboardService})
    : _dashboardService = dashboardService;

  final DashboardService _dashboardService;

  bool _isLoading = false;
  String? _errorMessage;
  String? _loadedRole;

  RoleHomeModel? roleHome;
  SuperadminHomeModel? superadminHome;
  Map<String, dynamic>? directorDashboard;
  Map<String, dynamic>? teacherHome;

  bool get isLoading => _isLoading;
  String? get errorMessage => _errorMessage;

  void reset() {
    _isLoading = false;
    _errorMessage = null;
    _loadedRole = null;
    roleHome = null;
    superadminHome = null;
    directorDashboard = null;
    teacherHome = null;
    notifyListeners();
  }

  Future<void> loadForUser(AppUser user, {bool force = false}) async {
    if (_isLoading) {
      return;
    }

    if (!force && _loadedRole == user.effectiveRole && roleHome != null) {
      return;
    }

    _isLoading = true;
    _errorMessage = null;
    notifyListeners();

    try {
      roleHome = await _dashboardService.fetchRoleHome();
      superadminHome = null;
      directorDashboard = null;
      teacherHome = null;

      switch (user.effectiveRole) {
        case 'superadmin':
          superadminHome = await _dashboardService.fetchSuperadminHome();
          break;
        case 'director':
        case 'manager':
          directorDashboard = const <String, dynamic>{};
          break;
        case 'teacher':
          teacherHome = await _dashboardService.fetchTeacherHome();
          break;
      }

      _loadedRole = user.effectiveRole;
    } catch (error) {
      _errorMessage = error is ApiException
          ? error.message
          : 'Asosiy panel ma\'lumotlarini yuklab bo\'lmadi';
    } finally {
      _isLoading = false;
      notifyListeners();
    }
  }
}
