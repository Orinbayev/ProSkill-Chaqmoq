import 'package:chaqmoq_mobile/models/app_models.dart';
import 'package:chaqmoq_mobile/services/api_client.dart';
import 'package:chaqmoq_mobile/services/api_services.dart';
import 'package:flutter/foundation.dart';

class StudentsProvider extends ChangeNotifier {
  StudentsProvider({required StudentsService studentsService})
    : _studentsService = studentsService;

  final StudentsService _studentsService;

  List<StudentModel> _students = <StudentModel>[];
  StudentDetailModel? _detail;
  ViewState _state = ViewState.idle;
  ViewState _detailState = ViewState.idle;
  String _filter = 'all';
  String _query = '';
  String? _errorMessage;

  List<StudentModel> get students => _students;
  StudentDetailModel? get detail => _detail;
  ViewState get state => _state;
  ViewState get detailState => _detailState;
  String? get errorMessage => _errorMessage;
  String get filter => _filter;
  String get query => _query;

  List<StudentModel> get filteredStudents {
    final normalizedQuery = _query.trim().toLowerCase();
    return _students.where((student) {
      final matchesQuery =
          normalizedQuery.isEmpty ||
          student.fullName.toLowerCase().contains(normalizedQuery) ||
          student.phone.toLowerCase().contains(normalizedQuery) ||
          student.groupName.toLowerCase().contains(normalizedQuery);

      final matchesFilter = switch (_filter) {
        'active' => student.isActive,
        'inactive' => !student.isActive,
        'debt' => student.balance < 0 || student.status == 'debt',
        _ => true,
      };

      return matchesQuery && matchesFilter;
    }).toList();
  }

  Future<void> load({bool force = false}) async {
    if (_state == ViewState.loading) {
      return;
    }
    if (!force && _students.isNotEmpty) {
      return;
    }
    _state = ViewState.loading;
    _errorMessage = null;
    notifyListeners();

    try {
      _students = await _studentsService.fetchStudents(query: _query);
      _state = ViewState.success;
    } catch (error) {
      _state = ViewState.error;
      _errorMessage = _mapError(error);
    } finally {
      notifyListeners();
    }
  }

  Future<void> refresh() => load(force: true);

  Future<void> loadDetail(StudentModel student) async {
    _detailState = ViewState.loading;
    notifyListeners();
    try {
      _detail = await _studentsService.fetchStudentDetail(student);
      _detailState = ViewState.success;
    } catch (error) {
      _detailState = ViewState.error;
      _errorMessage = _mapError(error);
    } finally {
      notifyListeners();
    }
  }

  void setFilter(String filter) {
    _filter = filter;
    notifyListeners();
  }

  void setQuery(String query) {
    _query = query;
    notifyListeners();
  }

  String _mapError(Object error) {
    if (error is ApiException) {
      return error.message;
    }
    return 'O\'quvchilar ma\'lumotlari yuklanmadi';
  }
}
