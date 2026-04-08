import 'package:chaqmoq_mobile/models/app_models.dart';
import 'package:chaqmoq_mobile/services/api_client.dart';
import 'package:chaqmoq_mobile/services/api_services.dart';
import 'package:flutter/foundation.dart';

class ProfileProvider extends ChangeNotifier {
  ProfileProvider({required ProfileService profileService})
    : _profileService = profileService;

  final ProfileService _profileService;

  bool isSaving = false;
  String? errorMessage;

  void reset() {
    isSaving = false;
    errorMessage = null;
    notifyListeners();
  }

  Future<AppUser?> save(Map<String, dynamic> data) async {
    isSaving = true;
    errorMessage = null;
    notifyListeners();

    try {
      return await _profileService.updateProfile(data);
    } catch (error) {
      errorMessage = error is ApiException
          ? error.message
          : 'Profilni yangilab bo\'lmadi';
      return null;
    } finally {
      isSaving = false;
      notifyListeners();
    }
  }
}
