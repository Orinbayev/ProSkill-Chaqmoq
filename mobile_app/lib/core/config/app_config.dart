class AppConfig {
  const AppConfig._();

  static const String _rawBaseUrl = String.fromEnvironment(
    'CHAQMOQ_BASE_URL',
    defaultValue: 'http://127.0.0.1:8000',
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
  static const String loginPath = '/api/auth/login/';
  static const String authStatusPath = '/api/auth/status/';
}
