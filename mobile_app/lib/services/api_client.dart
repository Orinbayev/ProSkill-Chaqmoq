import 'dart:async';

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
  ApiClient({required StorageService storageService})
    : _storageService = storageService,
      _dio = Dio(
        BaseOptions(
          baseUrl: AppConfig.baseUrl,
          connectTimeout: AppConfig.connectTimeout,
          receiveTimeout: AppConfig.receiveTimeout,
          sendTimeout: AppConfig.sendTimeout,
          responseType: ResponseType.json,
          contentType: Headers.jsonContentType,
          headers: const {'Accept': 'application/json'},
        ),
      ) {
    _dio.interceptors.add(
      InterceptorsWrapper(
        onRequest: (options, handler) async {
          if (_accessToken?.isNotEmpty == true) {
            options.headers['Authorization'] = 'Bearer $_accessToken';
          }
          if (_slug?.isNotEmpty == true) {
            options.headers['X-Center-Slug'] = _slug;
          }
          handler.next(options);
        },
      ),
    );
  }

  final Dio _dio;
  final StorageService _storageService;

  String? _accessToken;
  String? _slug;
  Future<void> Function()? _unauthorizedHandler;
  bool _isHandlingUnauthorized = false;

  void configure({
    String? accessToken,
    String? slug,
  }) {
    _accessToken = accessToken;
    _slug = slug;
  }

  void clearSession() {
    _accessToken = null;
    _slug = null;
  }

  void setUnauthorizedHandler(Future<void> Function() handler) {
    _unauthorizedHandler = handler;
  }

  Future<void> _handleUnauthorized() async {
    if (_isHandlingUnauthorized) {
      return;
    }
    _isHandlingUnauthorized = true;
    try {
      clearSession();
      await _storageService.clearAuth();
      await _unauthorizedHandler?.call();
    } finally {
      _isHandlingUnauthorized = false;
    }
  }

  bool _shouldRetry(DioException error) {
    if (error.type == DioExceptionType.connectionTimeout ||
        error.type == DioExceptionType.receiveTimeout ||
        error.type == DioExceptionType.sendTimeout ||
        error.type == DioExceptionType.connectionError) {
      return true;
    }

    final statusCode = error.response?.statusCode ?? 0;
    return statusCode == 429 || statusCode >= 500;
  }

  ApiException _mapError(DioException error) {
    final data = error.response?.data;
    if (data is Map) {
      final payload = data.map(
        (key, value) => MapEntry(key.toString(), value),
      );
      final message =
          payload['message']?.toString() ??
          payload['error']?.toString() ??
          payload['detail']?.toString() ??
          payload['non_field_errors']?.toString();
      if (message != null && message.isNotEmpty) {
        return ApiException(message, statusCode: error.response?.statusCode);
      }
    }

    if (error.type == DioExceptionType.connectionError ||
        error.type == DioExceptionType.connectionTimeout) {
      return ApiException('Server bilan aloqa o\'rnatilmadi');
    }

    return ApiException(
      error.message ?? 'So\'rov bajarilmadi',
      statusCode: error.response?.statusCode,
    );
  }

  Future<Response<dynamic>> _sendWithRetry(
    Future<Response<dynamic>> Function() action,
  ) async {
    var attempt = 0;
    while (true) {
      try {
        return await action();
      } on DioException catch (error) {
        if (error.response?.statusCode == 401) {
          await _handleUnauthorized();
          throw ApiException(
            'Sessiya yakunlandi. Qayta tizimga kiring.',
            statusCode: 401,
          );
        }

        if (attempt >= 2 || !_shouldRetry(error)) {
          throw _mapError(error);
        }

        final wait = Duration(milliseconds: 300 * (1 << attempt));
        await Future<void>.delayed(wait);
        attempt += 1;
      }
    }
  }

  Map<String, dynamic> _mapBody(Response<dynamic> response) {
    final data = response.data;
    if (data is Map<String, dynamic>) {
      return data;
    }
    if (data is Map) {
      return data.map((key, value) => MapEntry(key.toString(), value));
    }
    if (data is List) {
      return <String, dynamic>{'items': data};
    }
    return <String, dynamic>{'data': data};
  }

  Future<Map<String, dynamic>> get(
    String path, {
    Map<String, dynamic>? queryParameters,
  }) async {
    final response = await _sendWithRetry(
      () => _dio.get<dynamic>(
        path,
        queryParameters: queryParameters,
      ),
    );
    return _mapBody(response);
  }

  Future<Map<String, dynamic>> post(
    String path, {
    Object? data,
    Map<String, dynamic>? queryParameters,
  }) async {
    final response = await _sendWithRetry(
      () => _dio.post<dynamic>(
        path,
        data: data,
        queryParameters: queryParameters,
      ),
    );
    return _mapBody(response);
  }

  Future<Map<String, dynamic>> patch(
    String path, {
    Object? data,
  }) async {
    final response = await _sendWithRetry(
      () => _dio.patch<dynamic>(path, data: data),
    );
    return _mapBody(response);
  }
}
