class AppConfig {
  const AppConfig._();

  static const String appEnv = String.fromEnvironment(
    'APP_ENV',
    defaultValue: 'prod',
  );

  static const String _apiBaseUrl = String.fromEnvironment(
    'API_BASE_URL',
    defaultValue: 'https://chaqmoqapp.uz',
  );

  static const String defaultCenterSlug = String.fromEnvironment(
    'CENTER_SLUG',
    defaultValue: 'proskill',
  );

  // ─── Google orqali ro'yxatdan o'tish ────────────────────────
  //
  // Google Cloud Console'dan olinadi. Bo'sh bo'lsa ilovada Google tugmasi
  // ko'rsatilmaydi — o'rniga «hozircha mavjud emas» xabari chiqadi.
  //
  //   GOOGLE_SERVER_CLIENT_ID — Web (server) client ID. Server ID tokenni
  //                             shu ID bo'yicha tekshiradi. **Majburiy.**
  //   GOOGLE_IOS_CLIENT_ID    — iOS client ID (faqat iOS uchun).
  static const String googleServerClientId = String.fromEnvironment(
    'GOOGLE_SERVER_CLIENT_ID',
    defaultValue: '',
  );

  static const String googleIosClientId = String.fromEnvironment(
    'GOOGLE_IOS_CLIENT_ID',
    defaultValue: '',
  );

  static String get environmentName {
    final normalized = appEnv.trim().toLowerCase();

    if (normalized == 'dev' || normalized == 'development') {
      return 'dev';
    }

    return 'prod';
  }

  static String get baseUrl {
    final url = _apiBaseUrl.trim().isNotEmpty
        ? _apiBaseUrl.trim()
        : 'https://chaqmoqapp.uz';

    if (url.endsWith('/')) {
      return url.substring(0, url.length - 1);
    }

    return url;
  }

  static const Duration connectTimeout = Duration(seconds: 12);
  static const Duration receiveTimeout = Duration(seconds: 20);
  static const Duration sendTimeout = Duration(seconds: 15);

  static const String healthPath = '/api/mobile/health/';

  static const String appName = 'ChaqmoqApp Mobile';

  static const String loginPath = '/api/mobile/auth/login/';
  static const String authStatusPath = '/api/mobile/auth/status/';
  static const String changePasswordPath = '/api/mobile/auth/change-password/';

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
  static const String addChildPath = '/api/mobile/parent/children/add/';
  static const String selectChildPath = '/api/mobile/parent/select-child/';
  static const String notificationsPath = '/api/mobile/notifications/';
}