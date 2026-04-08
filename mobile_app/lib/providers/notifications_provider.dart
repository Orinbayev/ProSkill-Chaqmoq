import 'package:chaqmoq_mobile/models/app_models.dart';
import 'package:chaqmoq_mobile/services/api_client.dart';
import 'package:chaqmoq_mobile/services/api_services.dart';
import 'package:flutter/foundation.dart';

class NotificationsProvider extends ChangeNotifier {
  NotificationsProvider({required NotificationsService notificationsService})
    : _notificationsService = notificationsService;

  final NotificationsService _notificationsService;

  List<AppNotification> items = [];
  int unreadCount = 0;
  bool isLoading = false;
  bool isSaving = false;
  String? errorMessage;

  void reset() {
    items = [];
    unreadCount = 0;
    isLoading = false;
    isSaving = false;
    errorMessage = null;
    notifyListeners();
  }

  Future<void> load() async {
    isLoading = true;
    errorMessage = null;
    notifyListeners();

    try {
      final result = await _notificationsService.fetchNotifications();
      items = result.$1;
      unreadCount = result.$2;
    } catch (error) {
      errorMessage = error is ApiException
          ? error.message
          : 'Bildirishnomalarni yuklab bo\'lmadi';
    } finally {
      isLoading = false;
      notifyListeners();
    }
  }

  Future<bool> markAllRead() async {
    isSaving = true;
    errorMessage = null;
    notifyListeners();

    try {
      await _notificationsService.markAllRead();
      items = [
        for (final item in items)
          AppNotification(
            id: item.id,
            title: item.title,
            message: item.message,
            type: item.type,
            isRead: true,
            createdAt: item.createdAt,
          ),
      ];
      unreadCount = 0;
      return true;
    } catch (error) {
      errorMessage = error is ApiException
          ? error.message
          : 'Bildirishnomalarni belgilab bo\'lmadi';
      return false;
    } finally {
      isSaving = false;
      notifyListeners();
    }
  }
}
