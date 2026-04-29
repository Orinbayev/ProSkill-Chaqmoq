import 'dart:convert';

import 'package:chaqmoq_mobile/services/storage_service.dart';
import 'package:flutter/material.dart';

enum AppLanguage { uzbek, russian, english }

enum AppThemePreference { system, light, dark }

class NotificationPreferenceSettings {
  const NotificationPreferenceSettings({
    this.attendance = true,
    this.payments = true,
    this.progress = true,
    this.general = true,
  });

  final bool attendance;
  final bool payments;
  final bool progress;
  final bool general;

  NotificationPreferenceSettings copyWith({
    bool? attendance,
    bool? payments,
    bool? progress,
    bool? general,
  }) {
    return NotificationPreferenceSettings(
      attendance: attendance ?? this.attendance,
      payments: payments ?? this.payments,
      progress: progress ?? this.progress,
      general: general ?? this.general,
    );
  }

  Map<String, dynamic> toJson() => <String, dynamic>{
    'attendance': attendance,
    'payments': payments,
    'progress': progress,
    'general': general,
  };

  factory NotificationPreferenceSettings.fromJson(Map<String, dynamic> json) {
    return NotificationPreferenceSettings(
      attendance: json['attendance'] != false,
      payments: json['payments'] != false,
      progress: (json['progress'] ?? json['grades']) != false,
      general: json['general'] != false,
    );
  }
}

class AppPreferencesProvider extends ChangeNotifier {
  AppPreferencesProvider({required StorageService storageService})
    : _storageService = storageService;

  final StorageService _storageService;

  AppLanguage _language = AppLanguage.uzbek;
  AppThemePreference _themePreference = AppThemePreference.system;
  NotificationPreferenceSettings _notificationSettings =
      const NotificationPreferenceSettings();
  bool _isLoaded = false;

  AppLanguage get language => _language;
  AppThemePreference get themePreference => _themePreference;
  NotificationPreferenceSettings get notificationSettings =>
      _notificationSettings;
  bool get isLoaded => _isLoaded;

  String get languageLabel {
    switch (_language) {
      case AppLanguage.uzbek:
        return 'O‘zbekcha';
      case AppLanguage.russian:
        return 'Русский';
      case AppLanguage.english:
        return 'English';
    }
  }

  String get themeLabel {
    switch (_themePreference) {
      case AppThemePreference.system:
        return 'Tizim bo‘yicha';
      case AppThemePreference.light:
        return 'Yorug‘';
      case AppThemePreference.dark:
        return 'Qorong‘i';
    }
  }

  ThemeMode get themeMode {
    switch (_themePreference) {
      case AppThemePreference.system:
        return ThemeMode.system;
      case AppThemePreference.light:
        return ThemeMode.light;
      case AppThemePreference.dark:
        return ThemeMode.dark;
    }
  }

  Future<void> load() async {
    final languageCode = await _storageService.readLanguage();
    final themeCode = await _storageService.readThemeMode();
    final rawNotificationSettings = await _storageService
        .readNotificationSettings();

    _language = _languageFromCode(languageCode);
    _themePreference = _themeFromCode(themeCode);
    if (rawNotificationSettings != null && rawNotificationSettings.isNotEmpty) {
      try {
        _notificationSettings = NotificationPreferenceSettings.fromJson(
          jsonDecode(rawNotificationSettings) as Map<String, dynamic>,
        );
      } catch (_) {
        _notificationSettings = const NotificationPreferenceSettings();
      }
    }
    _isLoaded = true;
    notifyListeners();
  }

  Future<void> setLanguage(AppLanguage language) async {
    _language = language;
    await _storageService.saveLanguage(_languageCode(language));
    notifyListeners();
  }

  Future<void> setThemePreference(AppThemePreference preference) async {
    _themePreference = preference;
    await _storageService.saveThemeMode(_themeCode(preference));
    notifyListeners();
  }

  Future<void> saveNotificationSettings(
    NotificationPreferenceSettings settings,
  ) async {
    _notificationSettings = settings;
    await _storageService.saveNotificationSettings(
      jsonEncode(settings.toJson()),
    );
    notifyListeners();
  }

  AppLanguage _languageFromCode(String value) {
    switch (value.toLowerCase()) {
      case 'ru':
        return AppLanguage.russian;
      case 'en':
        return AppLanguage.english;
      default:
        return AppLanguage.uzbek;
    }
  }

  AppThemePreference _themeFromCode(String value) {
    switch (value.toLowerCase()) {
      case 'light':
        return AppThemePreference.light;
      case 'dark':
        return AppThemePreference.dark;
      default:
        return AppThemePreference.system;
    }
  }

  String _languageCode(AppLanguage value) {
    switch (value) {
      case AppLanguage.uzbek:
        return 'UZ';
      case AppLanguage.russian:
        return 'RU';
      case AppLanguage.english:
        return 'EN';
    }
  }

  String _themeCode(AppThemePreference value) {
    switch (value) {
      case AppThemePreference.system:
        return 'system';
      case AppThemePreference.light:
        return 'light';
      case AppThemePreference.dark:
        return 'dark';
    }
  }
}
