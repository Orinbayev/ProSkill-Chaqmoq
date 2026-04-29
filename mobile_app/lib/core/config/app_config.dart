import 'package:flutter/foundation.dart';

class AppConfig {
  const AppConfig._();

  static const String _rawEnvironment = String.fromEnvironment(
    'CHAQMOQ_ENV',
    defaultValue: '',
  );

  static const String _overrideBaseUrl = String.fromEnvironment(
    'CHAQMOQ_BASE_URL',
    defaultValue: '',
  );

  static const String _devBaseUrl = String.fromEnvironment(
    'CHAQMOQ_DEV_BASE_URL',
    defaultValue: '',
  );

  static const String _stagingBaseUrl = String.fromEnvironment(
    'CHAQMOQ_STAGING_BASE_URL',
    defaultValue: '',
  );

  static const String _productionBaseUrl = String.fromEnvironment(
    'CHAQMOQ_PROD_BASE_URL',
    defaultValue: 'https://chaqmoqapp.uz',
  );

  static const String defaultCenterSlug = String.fromEnvironment(
    'CHAQMOQ_CENTER_SLUG',
    defaultValue: '',
  );

  static String get environmentName {
    final normalized = _rawEnvironment.trim().toLowerCase();
    switch (normalized) {
      case 'dev':
      case 'development':
        return 'dev';
      case 'staging':
        return 'staging';
      case 'prod':
      case 'production':
        return 'production';
      default:
        return kReleaseMode ? 'production' : 'dev';
    }
  }

  static String get _resolvedDevBaseUrl {
    final configured = _devBaseUrl.trim();
    if (configured.isNotEmpty) {
      return configured;
    }
    if (kIsWeb) {
      return 'http://127.0.0.1:8000';
    }
    return 'http://10.0.2.2:8000';
  }

  static String get baseUrl {
    final resolvedBaseUrl = _overrideBaseUrl.trim().isNotEmpty
        ? _overrideBaseUrl.trim()
        : switch (environmentName) {
            'dev' => _resolvedDevBaseUrl,
            'staging' =>
              _stagingBaseUrl.trim().isNotEmpty
                  ? _stagingBaseUrl
                  : _productionBaseUrl,
            _ => _productionBaseUrl,
          };

    if (resolvedBaseUrl.endsWith('/')) {
      return resolvedBaseUrl.substring(0, resolvedBaseUrl.length - 1);
    }
    return resolvedBaseUrl;
  }

  static const Duration connectTimeout = Duration(seconds: 15);
  static const Duration receiveTimeout = Duration(seconds: 20);
  static const Duration sendTimeout = Duration(seconds: 20);

  static const String appName = 'ChaqmoqApp Mobile';
  static const String loginPath = '/api/mobile/auth/login/';
  static const String authStatusPath = '/api/mobile/auth/status/';
  static const String parentDashboardPath = '/api/mobile/dashboard/';
  static const String attendancePath = '/api/mobile/attendance/';
  static const String paymentsPath = '/api/mobile/payments/';
  static const String progressPath = '/api/mobile/progress/';
  static const String profilePath = '/api/mobile/profile/';
  static const String parentProfilePath = '/api/mobile/parent/profile/';
  static const String parentProfileAvatarPath =
      '/api/mobile/parent/profile/avatar/';
  static const String parentNotificationPreferencesPath =
      '/api/mobile/parent/notification-preferences/';
  static const String changePasswordPath = '/api/mobile/auth/change-password/';
  static const String addChildPath = '/api/mobile/parent/children/add/';
  static const String selectChildPath = '/api/mobile/parent/select-child/';
  static const String notificationsPath = '/api/mobile/notifications/';
}
