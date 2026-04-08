import 'package:chaqmoq_mobile/models/app_models.dart';
import 'package:chaqmoq_mobile/services/api_client.dart';
import 'package:chaqmoq_mobile/services/api_services.dart';
import 'package:flutter/foundation.dart';

class TeachersProvider extends ChangeNotifier {
  TeachersProvider({required TeacherService teacherService})
    : _teacherService = teacherService;

  final TeacherService _teacherService;

  List<TeacherModel> items = [];
  bool isLoading = false;
  bool isSaving = false;
  String? errorMessage;

  void reset() {
    items = [];
    isLoading = false;
    isSaving = false;
    errorMessage = null;
    notifyListeners();
  }

  Future<void> ensureLoaded() async {
    if (items.isEmpty && !isLoading) {
      await load();
    }
  }

  Future<void> load({String? query}) async {
    isLoading = true;
    errorMessage = null;
    notifyListeners();

    try {
      items = await _teacherService.fetchTeachers(query: query);
    } catch (error) {
      errorMessage = error is ApiException
          ? error.message
          : 'O\'qituvchilar ro\'yxatini yuklab bo\'lmadi';
    } finally {
      isLoading = false;
      notifyListeners();
    }
  }

  Future<TeacherModel?> create(Map<String, dynamic> data) async {
    isSaving = true;
    errorMessage = null;
    notifyListeners();

    try {
      final teacher = await _teacherService.createTeacher(data);
      items = [teacher, ...items];
      return teacher;
    } catch (error) {
      errorMessage = error is ApiException
          ? error.message
          : 'O\'qituvchini yaratib bo\'lmadi';
      return null;
    } finally {
      isSaving = false;
      notifyListeners();
    }
  }
}
