import 'package:chaqmoq_mobile/models/app_models.dart';
import 'package:chaqmoq_mobile/services/api_client.dart';
import 'package:chaqmoq_mobile/services/api_services.dart';
import 'package:flutter/foundation.dart';

class StudentsProvider extends ChangeNotifier {
  StudentsProvider({required StudentService studentService})
    : _studentService = studentService;

  final StudentService _studentService;

  List<StudentModel> items = [];
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
      items = await _studentService.fetchStudents(query: query);
    } catch (error) {
      errorMessage = error is ApiException
          ? error.message
          : 'O\'quvchilar ro\'yxatini yuklab bo\'lmadi';
    } finally {
      isLoading = false;
      notifyListeners();
    }
  }

  Future<StudentModel?> create(Map<String, dynamic> data) async {
    isSaving = true;
    errorMessage = null;
    notifyListeners();

    try {
      final student = await _studentService.createStudent(data);
      items = [student, ...items];
      return student;
    } catch (error) {
      errorMessage = error is ApiException
          ? error.message
          : 'O\'quvchini yaratib bo\'lmadi';
      return null;
    } finally {
      isSaving = false;
      notifyListeners();
    }
  }
}
