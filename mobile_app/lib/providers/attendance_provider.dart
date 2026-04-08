import 'package:chaqmoq_mobile/models/app_models.dart';
import 'package:chaqmoq_mobile/services/api_client.dart';
import 'package:chaqmoq_mobile/services/api_services.dart';
import 'package:flutter/foundation.dart';

class AttendanceProvider extends ChangeNotifier {
  AttendanceProvider({required AttendanceService attendanceService})
    : _attendanceService = attendanceService;

  final AttendanceService _attendanceService;

  AttendanceSheetData? sheet;
  bool isLoading = false;
  bool isSaving = false;
  String? errorMessage;

  void reset() {
    sheet = null;
    isLoading = false;
    isSaving = false;
    errorMessage = null;
    notifyListeners();
  }

  Future<void> load({required int groupId, required DateTime date}) async {
    isLoading = true;
    errorMessage = null;
    notifyListeners();

    try {
      sheet = await _attendanceService.fetchAttendanceSheet(
        groupId: groupId,
        date: date,
      );
    } catch (error) {
      errorMessage = error is ApiException
          ? error.message
          : 'Davomat ma\'lumotlarini yuklab bo\'lmadi';
    } finally {
      isLoading = false;
      notifyListeners();
    }
  }

  Future<bool> submit({
    required int groupId,
    required DateTime date,
    required List<Map<String, dynamic>> items,
  }) async {
    isSaving = true;
    errorMessage = null;
    notifyListeners();

    try {
      sheet = await _attendanceService.submitAttendance(
        groupId: groupId,
        date: date,
        items: items,
      );
      return true;
    } catch (error) {
      errorMessage = error is ApiException
          ? error.message
          : 'Davomatni saqlab bo\'lmadi';
      return false;
    } finally {
      isSaving = false;
      notifyListeners();
    }
  }
}
