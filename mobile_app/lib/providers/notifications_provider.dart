import 'package:chaqmoq_mobile/models/app_models.dart';
import 'package:chaqmoq_mobile/services/api_client.dart';
import 'package:chaqmoq_mobile/services/api_services.dart';
import 'package:flutter/foundation.dart';

class NotificationsProvider extends ChangeNotifier {
  NotificationsProvider({required NotificationsService notificationsService})
    : _notificationsService = notificationsService;

  final NotificationsService _notificationsService;

  List<NotificationModel> _items = <NotificationModel>[];
  int _unreadCount = 0;
  ViewState _state = ViewState.idle;
  String? _errorMessage;

  List<NotificationModel> get items => _items;
  int get unreadCount => _unreadCount;
  ViewState get state => _state;
  String? get errorMessage => _errorMessage;

  Future<void> load({bool force = false}) async {
    if (_state == ViewState.loading) {
      return;
    }
    if (!force && _items.isNotEmpty) {
      return;
    }
    _state = ViewState.loading;
    _errorMessage = null;
    notifyListeners();
    try {
      final payload = await _notificationsService.fetchNotifications();
      _items = payload.$1;
      _unreadCount = payload.$2;
      _state = ViewState.success;
    } catch (error) {
      _state = ViewState.error;
      _errorMessage = _mapError(error);
    } finally {
      notifyListeners();
    }
  }

  Future<void> refresh() => load(force: true);

  void markRead(NotificationModel notification) {
    _items = _items
        .map(
          (item) => item.id == notification.id ? item.copyWith(isRead: true) : item,
        )
        .toList();
    _unreadCount = _items.where((item) => !item.isRead).length;
    notifyListeners();
  }

  Future<void> markAllRead() async {
    await _notificationsService.markAllRead();
    _items = _items.map((item) => item.copyWith(isRead: true)).toList();
    _unreadCount = 0;
    notifyListeners();
  }

  String _mapError(Object error) {
    if (error is ApiException) {
      return error.message;
    }
    return 'Bildirishnomalar yuklanmadi';
  }
}
