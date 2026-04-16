import 'package:chaqmoq_mobile/models/app_models.dart';
import 'package:chaqmoq_mobile/services/api_client.dart';
import 'package:chaqmoq_mobile/services/api_services.dart';
import 'package:flutter/foundation.dart';

class TeachersProvider extends ChangeNotifier {
  TeachersProvider({required TeachersService teachersService})
    : _teachersService = teachersService;

  final TeachersService _teachersService;

  List<TeacherModel> _teachers = <TeacherModel>[];
  TeacherModel? _selectedTeacher;
  ViewState _state = ViewState.idle;
  ViewState _detailState = ViewState.idle;
  String? _errorMessage;

  List<TeacherModel> get teachers => _teachers;
  TeacherModel? get selectedTeacher => _selectedTeacher;
  ViewState get state => _state;
  ViewState get detailState => _detailState;
  String? get errorMessage => _errorMessage;

  Future<void> load({bool force = false}) async {
    if (_state == ViewState.loading) {
      return;
    }
    if (!force && _teachers.isNotEmpty) {
      return;
    }
    _state = ViewState.loading;
    _errorMessage = null;
    notifyListeners();
    try {
      _teachers = await _teachersService.fetchTeachers();
      _state = ViewState.success;
    } catch (error) {
      _state = ViewState.error;
      _errorMessage = _mapError(error);
    } finally {
      notifyListeners();
    }
  }

  Future<void> refresh() => load(force: true);

  Future<void> loadDetail(TeacherModel teacher) async {
    _detailState = ViewState.loading;
    notifyListeners();
    try {
      _selectedTeacher = await _teachersService.fetchTeacherDetail(teacher);
      _detailState = ViewState.success;
    } catch (error) {
      _detailState = ViewState.error;
      _errorMessage = _mapError(error);
    } finally {
      notifyListeners();
    }
  }

  String _mapError(Object error) {
    if (error is ApiException) {
      return error.message;
    }
    return 'Ustozlar ma\'lumoti yuklanmadi';
  }
}
