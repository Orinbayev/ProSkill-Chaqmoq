import 'package:chaqmoq_mobile/models/app_models.dart';
import 'package:chaqmoq_mobile/services/api_client.dart';
import 'package:chaqmoq_mobile/services/api_services.dart';
import 'package:flutter/foundation.dart';

class DashboardProvider extends ChangeNotifier {
  DashboardProvider({required DashboardService dashboardService})
    : _dashboardService = dashboardService;

  final DashboardService _dashboardService;

  DashboardData _data = DashboardData.empty();
  ViewState _state = ViewState.idle;
  String? _errorMessage;

  DashboardData get data => _data;
  ViewState get state => _state;
  String? get errorMessage => _errorMessage;

  Future<void> load(UserModel user, {bool force = false}) async {
    if (_state == ViewState.loading) {
      return;
    }
    if (!force && _data.metrics.isNotEmpty) {
      return;
    }
    _state = ViewState.loading;
    _errorMessage = null;
    notifyListeners();

    try {
      _data = await _dashboardService.fetchDashboard(user);
      _state = ViewState.success;
    } catch (error) {
      _state = ViewState.error;
      _errorMessage = _mapError(error);
    } finally {
      notifyListeners();
    }
  }

  Future<void> refresh(UserModel user) => load(user, force: true);

  String _mapError(Object error) {
    if (error is ApiException) {
      return error.message;
    }
    return 'Dashboard ma\'lumotlari yuklanmadi';
  }
}
