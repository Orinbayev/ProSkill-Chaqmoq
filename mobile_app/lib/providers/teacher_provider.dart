import 'package:chaqmoq_mobile/models/app_models.dart';
import 'package:chaqmoq_mobile/models/teacher_models.dart';
import 'package:chaqmoq_mobile/services/teacher_service.dart';
import 'package:flutter/material.dart';

class TeacherProvider extends ChangeNotifier {
  TeacherProvider({required this.service});

  final TeacherService service;

  // ── Groups ──
  List<TeacherGroupModel> groups = [];
  ViewState groupsState = ViewState.idle;
  String groupsError = '';

  Future<void> loadGroups() async {
    if (groupsState == ViewState.loading) return;
    groupsState = ViewState.loading;
    notifyListeners();
    try {
      groups = await service.getGroups();
      groupsState = ViewState.success;
    } catch (e) {
      groupsError = e.toString();
      groupsState = ViewState.error;
    }
    notifyListeners();
  }

  // ── Attendance ──
  TeacherAttendanceDay? attendance;
  ViewState attendanceState = ViewState.idle;
  String attendanceError = '';
  int? _attendanceGroupId;
  DateTime? _attendanceDate;

  Future<void> loadAttendance(int groupId, {DateTime? date}) async {
    final d = date ?? DateTime.now();
    if (_attendanceGroupId == groupId &&
        _attendanceDate?.day == d.day &&
        _attendanceDate?.month == d.month &&
        _attendanceDate?.year == d.year &&
        attendanceState == ViewState.success) return;
    attendanceState = ViewState.loading;
    _attendanceGroupId = groupId;
    _attendanceDate = d;
    notifyListeners();
    try {
      attendance = await service.getGroupStudents(groupId, date: d);
      attendanceState = ViewState.success;
    } catch (e) {
      attendanceError = e.toString();
      attendanceState = ViewState.error;
    }
    notifyListeners();
  }

  Future<void> toggleAttendance(int studentId, bool newPresent) async {
    if (attendance == null) return;
    final groupId = attendance!.group.id;
    final date = attendance!.date;

    // Optimistic update
    final updated = attendance!.students.map((s) {
      if (s.id != studentId) return s;
      return s.copyWith(attendanceStatus: newPresent ? 'present' : 'absent');
    }).toList();
    attendance = TeacherAttendanceDay(
      group: attendance!.group,
      date: attendance!.date,
      students: updated,
    );
    notifyListeners();

    try {
      await service.markAttendance(
        groupId: groupId,
        studentId: studentId,
        present: newPresent,
        date: date,
      );
    } catch (_) {
      // Revert on failure
      await loadAttendance(groupId, date: date);
    }
  }

  // ── Income ──
  TeacherIncomeModel? income;
  ViewState incomeState = ViewState.idle;
  String incomeError = '';
  int _incomeYear = 0;
  int _incomeMonth = 0;

  Future<void> loadIncome({int? year, int? month}) async {
    final now = DateTime.now();
    final y = year ?? now.year;
    final m = month ?? now.month;
    if (_incomeYear == y && _incomeMonth == m && incomeState == ViewState.success) return;
    incomeState = ViewState.loading;
    _incomeYear = y;
    _incomeMonth = m;
    notifyListeners();
    try {
      income = await service.getIncome(year: y, month: m);
      incomeState = ViewState.success;
    } catch (e) {
      incomeError = e.toString();
      incomeState = ViewState.error;
    }
    notifyListeners();
  }

  Future<void> forceReloadIncome({int? year, int? month}) async {
    _incomeYear = 0;
    _incomeMonth = 0;
    await loadIncome(year: year, month: month);
  }
}
