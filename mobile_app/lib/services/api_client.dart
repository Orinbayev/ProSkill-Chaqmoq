import 'dart:async';
import 'dart:convert';
import 'dart:io';

import 'package:chaqmoq_mobile/core/config/app_config.dart';
import 'package:chaqmoq_mobile/services/storage_service.dart';
import 'package:dio/dio.dart';
import 'package:flutter/foundation.dart';

class ApiException implements Exception {
  ApiException(this.message, {this.statusCode, this.code});

  final String message;
  final int? statusCode;
  final String? code;

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
          _debugLog(
            '--> ${options.method} ${options.uri} ${_safeDebugBody(options.data)}',
          );
          handler.next(options);
        },
        onResponse: (response, handler) {
          _debugLog(
            '<-- ${response.statusCode} ${response.requestOptions.uri} '
            '${_safeDebugBody(response.data)}',
          );
          handler.next(response);
        },
        onError: (error, handler) {
          _debugLog(
            '<-- ERROR ${error.response?.statusCode ?? error.type} '
            '${error.requestOptions.uri} ${_safeDebugBody(error.response?.data)}',
          );
          handler.next(error);
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

  void configure({String? accessToken, String? slug}) {
    _accessToken = accessToken;
    _slug = slug;
  }

  void clearSession() {
    _accessToken = null;
    _slug = null;
  }

  Future<void> warmup() async {
    try {
      await _dio.get<dynamic>(
        AppConfig.healthPath,
        options: Options(
          receiveTimeout: const Duration(seconds: 60),
          sendTimeout: const Duration(seconds: 30),
        ),
      );
    } catch (_) {
      // Best-effort: ignore failures so cold-start doesn't block app launch.
    }
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
    final parsedMessage = _extractErrorMessage(data);
    final parsedCode = _extractErrorCode(data);

    if (data is Map) {
      final payload = data.map((key, value) => MapEntry(key.toString(), value));
      final message = parsedMessage;
      if (message != null && message.isNotEmpty) {
        return ApiException(
          message,
          statusCode: error.response?.statusCode,
          code: parsedCode ?? payload['code']?.toString(),
        );
      }
    }

    if (error.type == DioExceptionType.connectionError) {
      final isOffline = _looksLikeOffline(error.error);
      return ApiException(
        isOffline
            ? 'Internet aloqasini tekshiring'
            : 'Serverga ulanib bo‘lmadi',
        statusCode: error.response?.statusCode,
        code: isOffline ? 'network_offline' : 'network',
      );
    }

    if (error.type == DioExceptionType.connectionTimeout ||
        error.type == DioExceptionType.receiveTimeout ||
        error.type == DioExceptionType.sendTimeout) {
      return ApiException(
        'Server javobi kutilganidan uzoq davom etdi',
        statusCode: error.response?.statusCode,
        code: 'timeout',
      );
    }

    final statusCode = error.response?.statusCode;
    if (statusCode == 401) {
      return ApiException(
        'Sessiya yakunlandi. Qayta tizimga kiring.',
        statusCode: statusCode,
        code: 'unauthorized',
      );
    }
    if (statusCode == 403) {
      return ApiException(
        'Bu amal uchun ruxsat yetarli emas',
        statusCode: statusCode,
        code: 'forbidden',
      );
    }
    if (statusCode == 404) {
      return ApiException(
        'So‘ralgan ma’lumot topilmadi',
        statusCode: statusCode,
        code: 'not_found',
      );
    }
    if (statusCode == 429) {
      return ApiException(
        'Juda ko‘p so‘rov yuborildi. Birozdan keyin qayta urinib ko‘ring.',
        statusCode: statusCode,
        code: 'rate_limited',
      );
    }
    if (statusCode != null && statusCode >= 500) {
      return ApiException(
        'Server hozircha javob bermayapti',
        statusCode: statusCode,
        code: 'server_unavailable',
      );
    }

    return ApiException(
      error.message ?? 'So\'rov bajarilmadi',
      statusCode: statusCode,
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
          throw _mapError(error);
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
    final cacheKey = _cacheKeyForGet(path, queryParameters);
    try {
      final response = await _sendWithRetry(
        () => _dio.get<dynamic>(path, queryParameters: queryParameters),
      );
      final payload = _mapBody(response);
      await _storageService.saveApiCache(cacheKey, payload);
      return payload;
    } on ApiException catch (error) {
      final cached = await _storageService.readApiCache(cacheKey);
      if (cached != null && _shouldUseCachedResponse(error)) {
        _debugLog('<-- CACHE ${_buildCacheFingerprint(path, queryParameters)}');
        return cached;
      }
      rethrow;
    }
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

  Future<Map<String, dynamic>> patch(String path, {Object? data}) async {
    final response = await _sendWithRetry(
      () => _dio.patch<dynamic>(path, data: data),
    );
    return _mapBody(response);
  }

  void _debugLog(String message) {
    if (!kDebugMode) {
      return;
    }
    debugPrint(
      '[Chaqmoq API] env=${AppConfig.environmentName} baseUrl=${AppConfig.baseUrl} $message',
    );
  }

  String _cacheKeyForGet(String path, Map<String, dynamic>? queryParameters) {
    final fingerprint = _buildCacheFingerprint(path, queryParameters);
    return 'chaqmoq_api_cache_${base64Url.encode(utf8.encode(fingerprint))}';
  }

  String _buildCacheFingerprint(
    String path,
    Map<String, dynamic>? queryParameters,
  ) {
    if (queryParameters == null || queryParameters.isEmpty) {
      return '${AppConfig.baseUrl}|$path';
    }

    final sortedEntries = queryParameters.entries.toList()
      ..sort((left, right) => left.key.compareTo(right.key));
    final normalizedQuery = sortedEntries
        .map((entry) {
          return '${entry.key}=${entry.value}';
        })
        .join('&');
    return '${AppConfig.baseUrl}|$path?$normalizedQuery';
  }

  bool _shouldUseCachedResponse(ApiException error) {
    final statusCode = error.statusCode ?? 0;
    return error.code == 'network' ||
        error.code == 'network_offline' ||
        error.code == 'timeout' ||
        error.code == 'server_unavailable' ||
        error.code == 'rate_limited' ||
        statusCode >= 500;
  }

  String? _extractErrorMessage(Object? data) {
    if (data is Map) {
      final payload = data.map((key, value) => MapEntry(key.toString(), value));
      for (final key in const [
        'message',
        'error',
        'detail',
        'non_field_errors',
      ]) {
        final message = _stringifyErrorValue(payload[key]);
        if (message != null && message.isNotEmpty) {
          return message;
        }
      }

      for (final entry in payload.entries) {
        final message = _stringifyErrorValue(entry.value);
        if (message != null && message.isNotEmpty) {
          return message;
        }
      }
    }

    return _stringifyErrorValue(data);
  }

  String? _extractErrorCode(Object? data) {
    if (data is! Map) {
      return null;
    }
    final payload = data.map((key, value) => MapEntry(key.toString(), value));
    return payload['code']?.toString();
  }

  String? _stringifyErrorValue(Object? value) {
    if (value == null) {
      return null;
    }
    if (value is String) {
      return value.trim();
    }
    if (value is List) {
      for (final item in value) {
        final normalized = _stringifyErrorValue(item);
        if (normalized != null && normalized.isNotEmpty) {
          return normalized;
        }
      }
      return null;
    }
    if (value is Map) {
      for (final nested in value.values) {
        final normalized = _stringifyErrorValue(nested);
        if (normalized != null && normalized.isNotEmpty) {
          return normalized;
        }
      }
      return null;
    }
    return value.toString().trim();
  }

  bool _looksLikeOffline(Object? error) {
    if (error is SocketException) {
      final message = [
        error.message,
        error.osError?.message,
      ].whereType<String>().join(' ').toLowerCase();
      return message.contains('network is unreachable') ||
          message.contains('no route to host') ||
          message.contains('temporarily unavailable') ||
          message.contains('host lookup') ||
          message.contains('failed host lookup') ||
          message.contains('not known') ||
          message.contains('nodename nor servname');
    }
    return false;
  }

  Object? _safeDebugBody(Object? data) {
    if (data is Map) {
      final redacted = <String, Object?>{};
      for (final entry in data.entries) {
        final key = entry.key.toString();
        final lower = key.toLowerCase();
        if (lower.contains('password') ||
            lower == 'token' ||
            lower == 'access' ||
            lower == 'access_token' ||
            lower == 'refresh') {
          redacted[key] = '***';
        } else {
          redacted[key] = entry.value;
        }
      }
      return redacted;
    }
    return data;
  }
}
