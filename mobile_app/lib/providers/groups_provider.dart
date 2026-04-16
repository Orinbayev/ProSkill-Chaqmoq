import 'package:chaqmoq_mobile/models/app_models.dart';
import 'package:chaqmoq_mobile/services/api_client.dart';
import 'package:chaqmoq_mobile/services/api_services.dart';
import 'package:flutter/foundation.dart';

class GroupsProvider extends ChangeNotifier {
  GroupsProvider({required GroupsService groupsService})
    : _groupsService = groupsService;

  final GroupsService _groupsService;

  List<GroupModel> _groups = <GroupModel>[];
  List<StudentModel> _groupStudents = <StudentModel>[];
  ViewState _state = ViewState.idle;
  ViewState _detailState = ViewState.idle;
  String? _errorMessage;

  List<GroupModel> get groups => _groups;
  List<StudentModel> get groupStudents => _groupStudents;
  ViewState get state => _state;
  ViewState get detailState => _detailState;
  String? get errorMessage => _errorMessage;

  Future<void> load(String role, {bool force = false}) async {
    if (_state == ViewState.loading) {
      return;
    }
    if (!force && _groups.isNotEmpty) {
      return;
    }
    _state = ViewState.loading;
    _errorMessage = null;
    notifyListeners();
    try {
      _groups = await _groupsService.fetchGroups(role);
      _state = ViewState.success;
    } catch (error) {
      _state = ViewState.error;
      _errorMessage = _mapError(error);
    } finally {
      notifyListeners();
    }
  }

  Future<void> refresh(String role) => load(role, force: true);

  Future<void> loadGroupStudents(int groupId) async {
    _detailState = ViewState.loading;
    notifyListeners();
    try {
      _groupStudents = await _groupsService.fetchGroupStudents(groupId);
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
    return 'Guruhlar ma\'lumoti yuklanmadi';
  }
}
