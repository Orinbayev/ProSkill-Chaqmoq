import 'dart:convert';

import 'package:chaqmoq_mobile/models/app_models.dart';
import 'package:flutter_secure_storage/flutter_secure_storage.dart';

class StorageService {
  StorageService()
    : _storage = const FlutterSecureStorage(
        aOptions: AndroidOptions(encryptedSharedPreferences: true),
        iOptions: IOSOptions(accessibility: KeychainAccessibility.first_unlock),
      );

  final FlutterSecureStorage _storage;

  static const String _tokenKey = 'chaqmoq_access_token';
  static const String _slugKey = 'chaqmoq_center_slug';
  static const String _userKey = 'chaqmoq_user';
  static const String _lastCenterSlugKey = 'chaqmoq_last_center_slug';
  static const String _languageKey = 'chaqmoq_language';
  static const String _themeKey = 'chaqmoq_theme_mode';
  static const String _notificationSettingsKey =
      'chaqmoq_notification_settings';
  static const String _cacheIndexKey = 'chaqmoq_cache_index';

  Future<void> saveToken(String token) =>
      _storage.write(key: _tokenKey, value: token);

  Future<String?> readToken() => _storage.read(key: _tokenKey);

  Future<void> saveSlug(String slug) =>
      _storage.write(key: _slugKey, value: slug);

  Future<String?> readSlug() => _storage.read(key: _slugKey);

  Future<void> saveLastCenterSlug(String slug) =>
      _storage.write(key: _lastCenterSlugKey, value: slug);

  Future<String?> readLastCenterSlug() =>
      _storage.read(key: _lastCenterSlugKey);

  Future<void> saveUser(UserModel user) {
    return _storage.write(key: _userKey, value: jsonEncode(user.toJson()));
  }

  Future<UserModel?> readUser() async {
    final raw = await _storage.read(key: _userKey);
    if (raw == null || raw.isEmpty) {
      return null;
    }
    try {
      return UserModel.fromJson(jsonDecode(raw) as Map<String, dynamic>);
    } catch (_) {
      return null;
    }
  }

  Future<void> saveLanguage(String languageCode) {
    return _storage.write(key: _languageKey, value: languageCode);
  }

  Future<String> readLanguage() async {
    return (await _storage.read(key: _languageKey)) ?? 'UZ';
  }

  Future<void> saveThemeMode(String themeMode) {
    return _storage.write(key: _themeKey, value: themeMode);
  }

  Future<String> readThemeMode() async {
    return (await _storage.read(key: _themeKey)) ?? 'system';
  }

  Future<void> saveNotificationSettings(String payload) {
    return _storage.write(key: _notificationSettingsKey, value: payload);
  }

  Future<String?> readNotificationSettings() {
    return _storage.read(key: _notificationSettingsKey);
  }

  Future<void> saveSession(AuthSession session) async {
    await saveToken(session.accessToken);
    await saveSlug(session.slug);
    await saveLastCenterSlug(session.slug);
    await saveUser(session.user);
  }

  Future<void> clearAuth() async {
    await clearCachedResponses();
    await _storage.delete(key: _tokenKey);
    await _storage.delete(key: _slugKey);
    await _storage.delete(key: _userKey);
  }

  Future<void> saveApiCache(
    String cacheKey,
    Map<String, dynamic> payload,
  ) async {
    await _storage.write(key: cacheKey, value: jsonEncode(payload));
    final index = await _readCacheIndex();
    if (!index.contains(cacheKey)) {
      index.add(cacheKey);
      await _storage.write(key: _cacheIndexKey, value: jsonEncode(index));
    }
  }

  Future<Map<String, dynamic>?> readApiCache(String cacheKey) async {
    final raw = await _storage.read(key: cacheKey);
    if (raw == null || raw.isEmpty) {
      return null;
    }
    try {
      return (jsonDecode(raw) as Map<Object?, Object?>).map(
        (key, value) => MapEntry(key.toString(), value),
      );
    } catch (_) {
      return null;
    }
  }

  Future<void> clearCachedResponses() async {
    final index = await _readCacheIndex();
    for (final cacheKey in index) {
      await _storage.delete(key: cacheKey);
    }
    await _storage.delete(key: _cacheIndexKey);
  }

  Future<List<String>> _readCacheIndex() async {
    final raw = await _storage.read(key: _cacheIndexKey);
    if (raw == null || raw.isEmpty) {
      return <String>[];
    }
    try {
      return (jsonDecode(raw) as List<Object?>)
          .map((value) => value.toString())
          .where((value) => value.isNotEmpty)
          .toSet()
          .toList();
    } catch (_) {
      return <String>[];
    }
  }
}
