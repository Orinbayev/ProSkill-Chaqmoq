import 'package:chaqmoq_mobile/core/config/app_config.dart';
import 'package:chaqmoq_mobile/models/app_models.dart';
import 'package:chaqmoq_mobile/services/api_client.dart';
import 'package:google_sign_in/google_sign_in.dart';

/// Markazsiz o'yinchi uchun Google orqali kirish.
///
/// Ilova Google'dan **ID token** oladi va uni serverga yuboradi. Tekshiruv
/// serverda bo'ladi — ilovaga ishonilmaydi.
///
/// Google client ID'lar `AppConfig` orqali `--dart-define` bilan beriladi.
/// Ular bo'sh bo'lsa [mavjud] `false` qaytaradi va ilova Google tugmasini
/// ko'rsatmaydi.
class GameAuthService {
  GameAuthService(this._api);

  static const _asos = '/api/mobile/game';

  final ApiClient _api;

  /// Google sozlanganmi (client ID berilganmi).
  static bool get mavjud => AppConfig.googleServerClientId.isNotEmpty;

  GoogleSignIn _googleSignIn() {
    return GoogleSignIn(
      scopes: const ['email', 'profile'],
      // iOS uchun o'z client ID, server tekshiruvi uchun esa serverClientId.
      clientId: AppConfig.googleIosClientId.isEmpty
          ? null
          : AppConfig.googleIosClientId,
      serverClientId: AppConfig.googleServerClientId.isEmpty
          ? null
          : AppConfig.googleServerClientId,
    );
  }

  /// Google oynasini ochadi va serverga token yuboradi.
  ///
  /// Foydalanuvchi bekor qilsa `null` qaytaradi.
  Future<GameAuthNatijasi?> googleBilanKirish() async {
    final google = _googleSignIn();

    // Avvalgi sessiya qolib ketmasin — har safar hisob tanlash oynasi chiqsin.
    await google.signOut();

    final hisob = await google.signIn();
    if (hisob == null) return null; // Foydalanuvchi bekor qildi.

    final auth = await hisob.authentication;
    final idToken = auth.idToken;
    if (idToken == null || idToken.isEmpty) {
      throw ApiException(
        'Google javobida token yo‘q. Sozlamalarni tekshiring.',
        code: 'token_yoq',
      );
    }

    final javob = await _api.post(
      '$_asos/auth/google/',
      data: {'id_token': idToken},
    );

    return GameAuthNatijasi(
      accessToken: jsonString(javob['access_token']),
      yangi: javob['yangi'] == true,
      profil: GameOyinchiProfil.fromJson(jsonMap(javob['profil'])),
    );
  }

  Future<void> chiqish() async {
    try {
      await _googleSignIn().signOut();
    } catch (_) {
      // Google seansini tozalash muvaffaqiyatsiz bo'lsa ham chiqish davom etadi.
    }
  }

  /// Ro'yxatdan o'tgandan keyingi ma'lumot.
  Future<GameOyinchiProfil> profilniToldir({
    required String ism,
    required String familya,
    required int yosh,
  }) async {
    final javob = await _api.post(
      '$_asos/auth/profile/',
      data: {'ism': ism, 'familya': familya, 'yosh': yosh},
    );
    return GameOyinchiProfil.fromJson(jsonMap(javob['profil']));
  }

  Future<GameOyinchiProfil> profilniOl() async {
    final javob = await _api.get('$_asos/me/');
    return GameOyinchiProfil.fromJson(jsonMap(javob['profil']));
  }
}

class GameAuthNatijasi {
  const GameAuthNatijasi({
    required this.accessToken,
    required this.yangi,
    required this.profil,
  });

  final String accessToken;

  /// Hisob endi yaratildimi (birinchi marta kirdimi).
  final bool yangi;
  final GameOyinchiProfil profil;
}

/// Mustaqil o'yinchi profili — markaz paneli maydonlarisiz.
class GameOyinchiProfil {
  const GameOyinchiProfil({
    required this.id,
    required this.email,
    required this.ism,
    required this.familya,
    required this.yosh,
    required this.toliq,
    required this.gameOnly,
  });

  factory GameOyinchiProfil.fromJson(Map<String, dynamic> json) {
    return GameOyinchiProfil(
      id: jsonInt(json['id']),
      email: jsonString(json['email']),
      ism: jsonString(json['ism']),
      familya: jsonString(json['familya']),
      yosh: json['yosh'] == null ? null : jsonInt(json['yosh']),
      toliq: json['toliq'] == true,
      gameOnly: json['game_only'] == true,
    );
  }

  static const bosh = GameOyinchiProfil(
    id: 0,
    email: '',
    ism: '',
    familya: '',
    yosh: null,
    toliq: false,
    gameOnly: false,
  );

  final int id;
  final String email;
  final String ism;
  final String familya;
  final int? yosh;

  /// Ism/familya/yosh to'ldirilganmi.
  final bool toliq;
  final bool gameOnly;

  String get toliqIsm => [ism, familya].where((q) => q.isNotEmpty).join(' ');
}
