class AppConfig {
  static const String baseUrl = String.fromEnvironment(
    'CHAQMOQ_BASE_URL',
    defaultValue: 'http://127.0.0.1:8001',
  );

  static const Duration connectTimeout = Duration(seconds: 20);
  static const Duration receiveTimeout = Duration(seconds: 20);
}
