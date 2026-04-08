import 'package:chaqmoq_mobile/models/app_models.dart';
import 'package:chaqmoq_mobile/services/api_client.dart';
import 'package:chaqmoq_mobile/services/api_services.dart';
import 'package:flutter/foundation.dart';

class GroupsProvider extends ChangeNotifier {
  GroupsProvider({required GroupService groupService})
    : _groupService = groupService;

  final GroupService _groupService;

  List<GroupModel> items = [];
  bool isLoading = false;
  String? errorMessage;

  void reset() {
    items = [];
    isLoading = false;
    errorMessage = null;
    notifyListeners();
  }

  Future<void> ensureLoaded() async {
    if (items.isEmpty && !isLoading) {
      await load();
    }
  }

  Future<void> load() async {
    isLoading = true;
    errorMessage = null;
    notifyListeners();

    try {
      items = await _groupService.fetchGroups();
    } catch (error) {
      errorMessage = error is ApiException
          ? error.message
          : 'Guruhlarni yuklab bo\'lmadi';
    } finally {
      isLoading = false;
      notifyListeners();
    }
  }
}
