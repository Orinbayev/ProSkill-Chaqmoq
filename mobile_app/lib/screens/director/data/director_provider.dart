import 'package:flutter/foundation.dart';
import 'package:image_picker/image_picker.dart';

import '../../../models/app_models.dart';
import 'director_data.dart';
import 'director_repository.dart';

enum DirectorLoadState { idle, loading, ready, error }

/// Director paneli holati — overview (dashboard+hisobot) va qarzdorlar.
class DirectorProvider extends ChangeNotifier {
  DirectorProvider(this._repository);

  final DirectorRepository _repository;

  DirectorLoadState _state = DirectorLoadState.idle;
  DirectorData? _data;
  String? _error;

  List<DirectorDebtor> _students = const [];
  DirectorLoadState _studentsState = DirectorLoadState.idle;
  String _studentsQuery = '';
  int _studentsPage = 1;
  bool _studentsHasNext = false;
  bool _loadingMore = false;

  DirectorLoadState get state => _state;
  DirectorData? get data => _data;
  String? get error => _error;
  List<DirectorDebtor> get debtors => _data?.debtors ?? const [];
  List<DirectorDebtor> get students => _students;
  DirectorLoadState get studentsState => _studentsState;
  bool get studentsHasNext => _studentsHasNext;
  bool get loadingMoreStudents => _loadingMore;

  Future<void> load({bool force = false}) async {
    if (_state == DirectorLoadState.loading) return;
    if (_data != null && !force) return;
    _state = DirectorLoadState.loading;
    _error = null;
    notifyListeners();
    try {
      _data = await _repository.loadOverview();
      _state = DirectorLoadState.ready;
    } catch (error) {
      _error = 'Ma\'lumotni yuklab bo\'lmadi. Internetni tekshiring.';
      _state = DirectorLoadState.error;
      if (kDebugMode) debugPrint('DirectorProvider.load error: $error');
    }
    notifyListeners();
  }

  /// Birinchi sahifani yuklaydi (qidiruv o'zgarganda yoki majburan).
  Future<void> loadStudents(String query, {bool force = false}) async {
    final normalized = query.trim();
    if (!force && _studentsState == DirectorLoadState.ready && normalized == _studentsQuery) return;
    _studentsQuery = normalized;
    _studentsPage = 1;
    _studentsState = DirectorLoadState.loading;
    notifyListeners();
    try {
      final result = await _repository.loadStudents(normalized, page: 1);
      if (normalized == _studentsQuery) {
        _students = result.items;
        _studentsHasNext = result.hasNext;
        _studentsState = DirectorLoadState.ready;
      }
    } catch (error) {
      if (normalized == _studentsQuery) _studentsState = DirectorLoadState.error;
      if (kDebugMode) debugPrint('DirectorProvider.loadStudents error: $error');
    }
    notifyListeners();
  }

  /// Keyingi sahifani yuklab, ro'yxatga qo'shadi (infinite scroll).
  Future<void> loadMoreStudents() async {
    if (_loadingMore || !_studentsHasNext || _studentsState != DirectorLoadState.ready) return;
    _loadingMore = true;
    notifyListeners();
    final query = _studentsQuery;
    try {
      final result = await _repository.loadStudents(query, page: _studentsPage + 1);
      if (query == _studentsQuery) {
        _students = [..._students, ...result.items];
        _studentsPage += 1;
        _studentsHasNext = result.hasNext;
      }
    } catch (error) {
      if (kDebugMode) debugPrint('DirectorProvider.loadMoreStudents error: $error');
    }
    _loadingMore = false;
    notifyListeners();
  }

  Future<DirectorStudentDetail> loadStudentDetail(int id) => _repository.loadStudentDetail(id);

  Future<List<DirectorNotification>> loadNotifications({int page = 1}) =>
      _repository.loadNotifications(page: page);

  Future<DirectorReport> loadReport(String month) => _repository.loadReport(month);

  Future<List<AvailableGroup>> loadGroups(String query) => _repository.loadGroups(query);

  Future<void> addStudentToGroup(int studentId, int groupId, {int? price}) =>
      _repository.addStudentToGroup(studentId, groupId, price: price);

  Future<void> removeStudentFromGroup(int studentId, int groupId) =>
      _repository.removeStudentFromGroup(studentId, groupId);

  Future<void> setStudentPrice(int studentId, int enrollmentId, int price) =>
      _repository.setStudentPrice(studentId, enrollmentId, price);

  Future<int?> payStudent(int studentId, int enrollmentId, int amount, String method, {String month = ''}) =>
      _repository.payStudent(studentId, enrollmentId, amount, method, month: month);

  Future<UserModel> updateProfile({String? ism, String? familya, String? phone}) =>
      _repository.updateProfile(ism: ism, familya: familya, phone: phone);

  Future<UserModel> uploadAvatar(XFile image) => _repository.uploadAvatar(image);

  Future<UserModel> removeAvatar() => _repository.removeAvatar();

  Future<void> changePassword({required String current, required String newPass, required String confirm}) =>
      _repository.changePassword(current: current, newPass: newPass, confirm: confirm);


  Future<void> refresh() => load(force: true);
}
