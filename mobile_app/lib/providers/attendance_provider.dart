import 'package:chaqmoq_mobile/models/app_models.dart';
import 'package:chaqmoq_mobile/services/api_client.dart';
import 'package:chaqmoq_mobile/services/api_services.dart';
import 'package:flutter/foundation.dart';

class AttendanceProvider extends ChangeNotifier {
  AttendanceProvider({required AttendanceService attendanceService})
    : _attendanceService = attendanceService;

  final AttendanceService _attendanceService;

  DateTime _selectedDate = DateTime.now();
  GroupModel? _selectedGroup;
  AttendanceSheetModel? _sheet;
  ViewState _state = ViewState.idle;
  ViewState _submitState = ViewState.idle;
  String? _errorMessage;

  DateTime get selectedDate => _selectedDate;
  GroupModel? get selectedGroup => _selectedGroup;
  AttendanceSheetModel? get sheet => _sheet;
  ViewState get state => _state;
  ViewState get submitState => _submitState;
  String? get errorMessage => _errorMessage;

  Future<void> loadSheet(GroupModel group, {DateTime? date}) async {
    _selectedGroup = group;
    _selectedDate = date ?? _selectedDate;
    _state = ViewState.loading;
    _errorMessage = null;
    notifyListeners();
    try {
      _sheet = await _attendanceService.fetchAttendanceSheet(
        groupId: group.id,
        groupName: group.name,
        date: _selectedDate,
      );
      _state = ViewState.success;
    } catch (error) {
      _state = ViewState.error;
      _errorMessage = _mapError(error);
    } finally {
      notifyListeners();
    }
  }

  Future<void> changeDate(DateTime date) async {
    _selectedDate = date;
    notifyListeners();
    if (_selectedGroup != null) {
      await loadSheet(_selectedGroup!, date: date);
    }
  }

  void updateStatus(int studentId, String status) {
    final current = _sheet;
    if (current == null) {
      return;
    }
    _sheet = AttendanceSheetModel(
      groupId: current.groupId,
      groupName: current.groupName,
      date: current.date,
      readOnly: current.readOnly,
      items: current.items
          .map(
            (item) => item.studentId == studentId
                ? item.copyWith(status: status)
                : item,
          )
          .toList(),
    );
    notifyListeners();
  }

  Future<void> submit() async {
    if (_sheet == null || _selectedGroup == null) {
      return;
    }
    _submitState = ViewState.loading;
    _errorMessage = null;
    notifyListeners();
    try {
      await _attendanceService.submitAttendance(
        groupId: _selectedGroup!.id,
        date: _selectedDate,
        items: _sheet!.items,
      );
      _submitState = ViewState.success;
    } catch (error) {
      _submitState = ViewState.error;
      _errorMessage = _mapError(error);
    } finally {
      notifyListeners();
    }
  }

  String _mapError(Object error) {
    if (error is ApiException) {
      return error.message;
    }
    return 'Davomat saqlanmadi';
  }
}
