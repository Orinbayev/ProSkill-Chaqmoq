import 'package:chaqmoq_mobile/core/config/app_config.dart';
import 'package:chaqmoq_mobile/services/storage_service.dart';
import 'package:dio/dio.dart';

class ApiException implements Exception {
  ApiException(this.message, {this.statusCode});

  final String message;
  final int? statusCode;

  @override
  String toString() => message;
}

class ApiClient {
  ApiClient({required SecureStorageService storageService})
    : _storageService = storageService,
      _dio = Dio(
        BaseOptions(
          baseUrl: AppConfig.baseUrl,
          connectTimeout: AppConfig.connectTimeout,
          receiveTimeout: AppConfig.receiveTimeout,
          contentType: Headers.jsonContentType,
          responseType: ResponseType.json,
        ),
      );

  final SecureStorageService _storageService;
  final Dio _dio;

  String? _slug;
  String? _accessToken;

  void configure({required String slug, String? accessToken}) {
    _slug = slug.trim();
    _accessToken = accessToken;
  }

  Future<void> persistSlug(String slug) => _storageService.saveSlug(slug);

  void clearSession() {
    _accessToken = null;
  }

  String get currentSlug => _slug ?? '';

  String _tenantPath(String endpoint) {
    if (_slug == null || _slug!.isEmpty) {
      throw ApiException('Markaz slugi sozlanmagan');
    }

    final clean = endpoint.startsWith('/') ? endpoint.substring(1) : endpoint;
    return '/${_slug!}/api/mobile/$clean';
  }

  String _globalPath(String endpoint) {
    final clean = endpoint.startsWith('/') ? endpoint.substring(1) : endpoint;
    return '/api/mobile/$clean';
  }

  Options _buildOptions() {
    final headers = <String, dynamic>{};
    if (_accessToken != null && _accessToken!.isNotEmpty) {
      headers['Authorization'] = 'Bearer $_accessToken';
    }
    return Options(headers: headers);
  }

  Map<String, dynamic> _decode(Response<dynamic> response) {
    final data = response.data;
    if (data is Map) {
      return Map<String, dynamic>.from(data);
    }
    return <String, dynamic>{'data': data};
  }

  Never _throwFromDio(DioException error) {
    final responseData = error.response?.data;
    if (responseData is Map) {
      final payload = Map<String, dynamic>.from(responseData);
      throw ApiException(
        payload['error']?.toString() ??
            payload['message']?.toString() ??
            'So\'rov bajarilmadi',
        statusCode: error.response?.statusCode,
      );
    }

    throw ApiException(
      error.message ?? 'Tarmoq so\'rovi bajarilmadi',
      statusCode: error.response?.statusCode,
    );
  }

  Map<String, dynamic> _cleanQuery(Map<String, dynamic>? values) {
    if (values == null) {
      return const {};
    }
    return Map<String, dynamic>.fromEntries(
      values.entries.where(
        (entry) => entry.value != null && '${entry.value}'.isNotEmpty,
      ),
    );
  }

  Future<Map<String, dynamic>> get(
    String endpoint, {
    Map<String, dynamic>? queryParameters,
  }) async {
    try {
      final response = await _dio.get<dynamic>(
        _tenantPath(endpoint),
        queryParameters: _cleanQuery(queryParameters),
        options: _buildOptions(),
      );
      return _decode(response);
    } on DioException catch (error) {
      _throwFromDio(error);
    }
  }

  Future<Map<String, dynamic>> post(
    String endpoint, {
    Map<String, dynamic>? data,
  }) async {
    try {
      final response = await _dio.post<dynamic>(
        _tenantPath(endpoint),
        data: data,
        options: _buildOptions(),
      );
      return _decode(response);
    } on DioException catch (error) {
      _throwFromDio(error);
    }
  }

  Future<Map<String, dynamic>> postGlobal(
    String endpoint, {
    Map<String, dynamic>? data,
  }) async {
    try {
      final response = await _dio.post<dynamic>(
        _globalPath(endpoint),
        data: data,
        options: _buildOptions(),
      );
      return _decode(response);
    } on DioException catch (error) {
      _throwFromDio(error);
    }
  }

  Future<Map<String, dynamic>> patch(
    String endpoint, {
    Map<String, dynamic>? data,
  }) async {
    try {
      final response = await _dio.patch<dynamic>(
        _tenantPath(endpoint),
        data: data,
        options: _buildOptions(),
      );
      return _decode(response);
    } on DioException catch (error) {
      _throwFromDio(error);
    }
  }
}
