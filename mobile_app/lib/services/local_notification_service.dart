import 'package:flutter/foundation.dart';
import 'package:flutter_local_notifications/flutter_local_notifications.dart';
import 'package:flutter_timezone/flutter_timezone.dart';
import 'package:timezone/data/latest.dart' as tz_data;
import 'package:timezone/timezone.dart' as tz;

class LocalNotificationException implements Exception {
  const LocalNotificationException(this.message);

  final String message;

  @override
  String toString() => message;
}

class LocalNotificationService {
  LocalNotificationService()
    : _plugin = FlutterLocalNotificationsPlugin();

  final FlutterLocalNotificationsPlugin _plugin;
  bool _initialized = false;

  static const String _channelId = 'chaqmoq_parent_reminders';
  static const String _channelName = 'Ota-ona eslatmalari';
  static const String _channelDescription =
      'To‘lov va muhim ota-ona eslatmalari';

  Future<void> initialize() async {
    if (_initialized) {
      return;
    }

    tz_data.initializeTimeZones();
    if (!kIsWeb) {
      try {
        final timezoneInfo = await FlutterTimezone.getLocalTimezone();
        tz.setLocalLocation(tz.getLocation(timezoneInfo.identifier));
      } catch (_) {
        tz.setLocalLocation(tz.getLocation('Asia/Samarkand'));
      }
    }

    const android = AndroidInitializationSettings('@mipmap/ic_launcher');
    const darwin = DarwinInitializationSettings(
      requestAlertPermission: false,
      requestBadgePermission: false,
      requestSoundPermission: false,
    );

    await _plugin.initialize(
      settings: const InitializationSettings(android: android, iOS: darwin),
    );
    _initialized = true;
  }

  Future<bool> ensurePermissions() async {
    await initialize();

    bool granted = true;
    final androidImplementation = _plugin
        .resolvePlatformSpecificImplementation<
          AndroidFlutterLocalNotificationsPlugin
        >();
    if (androidImplementation != null) {
      final enabled = await androidImplementation.areNotificationsEnabled();
      if (enabled != true) {
        granted =
            await androidImplementation.requestNotificationsPermission() ??
            false;
      }
    }

    final iosImplementation = _plugin.resolvePlatformSpecificImplementation<
      IOSFlutterLocalNotificationsPlugin
    >();
    if (iosImplementation != null) {
      final iosGranted = await iosImplementation.requestPermissions(
        alert: true,
        badge: true,
        sound: true,
      );
      granted = granted && (iosGranted ?? false);
    }

    final macImplementation = _plugin.resolvePlatformSpecificImplementation<
      MacOSFlutterLocalNotificationsPlugin
    >();
    if (macImplementation != null) {
      final macGranted = await macImplementation.requestPermissions(
        alert: true,
        badge: true,
        sound: true,
      );
      granted = granted && (macGranted ?? false);
    }

    return granted;
  }

  Future<int> schedulePaymentReminder({
    required DateTime scheduledAt,
    required String title,
    required String body,
    String? payload,
  }) async {
    final granted = await ensurePermissions();
    if (!granted) {
      throw const LocalNotificationException(
        'Bildirishnoma ruxsati berilmadi',
      );
    }

    final scheduled = tz.TZDateTime.from(scheduledAt, tz.local);
    if (scheduled.isBefore(tz.TZDateTime.now(tz.local))) {
      throw const LocalNotificationException(
        'O‘tib ketgan vaqt uchun eslatma qo‘yib bo‘lmaydi',
      );
    }

    final id = scheduled.millisecondsSinceEpoch.remainder(2147483646);
    const androidDetails = AndroidNotificationDetails(
      _channelId,
      _channelName,
      channelDescription: _channelDescription,
      importance: Importance.max,
      priority: Priority.high,
    );
    const darwinDetails = DarwinNotificationDetails();

    await _plugin.zonedSchedule(
      id: id,
      title: title,
      body: body,
      scheduledDate: scheduled,
      notificationDetails: const NotificationDetails(
        android: androidDetails,
        iOS: darwinDetails,
      ),
      androidScheduleMode: AndroidScheduleMode.inexactAllowWhileIdle,
      payload: payload,
    );
    return id;
  }
}
