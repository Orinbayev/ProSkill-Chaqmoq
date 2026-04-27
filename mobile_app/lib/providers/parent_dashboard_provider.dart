import 'package:chaqmoq_mobile/models/app_models.dart';
import 'package:chaqmoq_mobile/models/parent_models.dart';
import 'package:chaqmoq_mobile/services/api_client.dart';
import 'package:chaqmoq_mobile/services/parent_dashboard_service.dart';
import 'package:flutter/foundation.dart';

class ParentDashboardProvider extends ChangeNotifier {
  ParentDashboardProvider({required ParentDashboardService service})
    : _service = service;

  final ParentDashboardService _service;

  ParentDashboardModel? _data;
  ViewState _state = ViewState.idle;
  String? _errorMessage;
  int? _selectedChildId;

  ParentDashboardModel? get data => _data;
  ViewState get state => _state;
  String? get errorMessage => _errorMessage;
  int? get selectedChildId => _selectedChildId;

  Future<void> load({bool force = false}) async {
    if (_state == ViewState.loading) {
      return;
    }
    if (!force && _data != null) {
      return;
    }
    _state = ViewState.loading;
    _errorMessage = null;
    notifyListeners();

    try {
      _data = await _service.fetchDashboard(childId: _selectedChildId);
      _selectedChildId = _data?.selectedChild.id;
      _state = ViewState.success;
    } catch (error) {
      _state = ViewState.error;
      _errorMessage = _mapError(error);
    } finally {
      notifyListeners();
    }
  }

  Future<void> refresh() => load(force: true);

  Future<void> selectChild(int childId) async {
    _selectedChildId = childId;
    try {
      await _service.selectChild(childId);
    } catch (_) {
      // The dashboard fetch below is the source of truth for the selected child.
    }
    await load(force: true);
  }

  void clear() {
    _data = null;
    _selectedChildId = null;
    _state = ViewState.idle;
    _errorMessage = null;
    notifyListeners();
  }

  String _mapError(Object error) {
    if (error is ApiException) {
      return error.message;
    }
    return 'Dashboard ma’lumotlari yuklanmadi';
  }
}
