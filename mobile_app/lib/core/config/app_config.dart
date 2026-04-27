class AppConfig {
  const AppConfig._();

  // Local real-phone testing:
  // Build with:
  // --dart-define=CHAQMOQ_BASE_URL=http://YOUR_MAC_IP:8000
  // --dart-define=CHAQMOQ_CENTER_SLUG=test
  // Find YOUR_MAC_IP on macOS with: ipconfig getifaddr en0
  static const String _rawBaseUrl = String.fromEnvironment(
    'CHAQMOQ_BASE_URL',
    defaultValue: 'http://192.168.1.153:8000',
  );

  static const String defaultCenterSlug = String.fromEnvironment(
    'CHAQMOQ_CENTER_SLUG',
    defaultValue: 'test',
  );

  static String get baseUrl {
    if (_rawBaseUrl.endsWith('/')) {
      return _rawBaseUrl.substring(0, _rawBaseUrl.length - 1);
    }
    return _rawBaseUrl;
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
  static const String changePasswordPath = '/api/mobile/auth/change-password/';
  static const String addChildPath = '/api/mobile/parent/children/add/';
  static const String notificationsPath = '/api/mobile/notifications/';
}
