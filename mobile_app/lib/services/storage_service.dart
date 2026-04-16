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
  static const String _languageKey = 'chaqmoq_language';

  Future<void> saveToken(String token) => _storage.write(key: _tokenKey, value: token);

  Future<String?> readToken() => _storage.read(key: _tokenKey);

  Future<void> saveSlug(String slug) => _storage.write(key: _slugKey, value: slug);

  Future<String?> readSlug() => _storage.read(key: _slugKey);

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

  Future<void> saveSession(AuthSession session) async {
    await saveToken(session.accessToken);
    await saveSlug(session.slug);
    await saveUser(session.user);
  }

  Future<void> clearAuth() async {
    await _storage.delete(key: _tokenKey);
    await _storage.delete(key: _slugKey);
    await _storage.delete(key: _userKey);
  }
}
