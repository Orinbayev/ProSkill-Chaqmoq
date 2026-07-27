import 'package:chaqmoq_mobile/models/game_models.dart';
import 'package:chaqmoq_mobile/services/api_client.dart';

/// Chaqmoq Game backendi bilan aloqa.
///
/// Endpointlar `game/mobile_urls.py` bilan bir xil tartibda yozilgan —
/// ikkalasini yonma-yon o'qish oson bo'lsin.
class GameService {
  GameService(this._api);

  static const _asos = '/api/mobile/game';

  final ApiClient _api;

  // ─── Katalog ────────────────────────────────────────────────

  Future<GameKatalog> katalog() async {
    final javob = await _api.get('$_asos/catalog/');
    return GameKatalog.fromJson(javob);
  }

  /// O'yinni boshlaydi.
  ///
  /// Duel motorida server avval **jonli raqib** qidiradi: javobda
  /// `tur: "kutish"` kelsa, [navbatHolati] bilan poll qilish kerak.
  /// `robot: true` bersak — qidirmasdan darhol robot bilan o'ynaladi.
  Future<GameBoshlanish> oyinBoshla(
    int oyinId, {
    int? raqibId,
    bool robot = false,
  }) async {
    final javob = await _api.post(
      '$_asos/play/$oyinId/start/',
      data: <String, dynamic>{
        if (raqibId != null) 'raqib_id': raqibId,
        if (robot) 'robot': true,
      },
    );
    return GameBoshlanish.fromJson(javob);
  }

  /// Serverning javobi "raqib qidirilmoqda" ekanini aytadi.
  static bool kutishKerak(Map<String, dynamic> javob) =>
      GameBoshlanish.kutishmi(javob);

  // ─── Raqib qidirish navbati ─────────────────────────────────

  /// Navbat holati: `kutmoqda` | `topildi` | `vaqt_tugadi`.
  Future<({String holat, GameBoshlanish? oyin, int qolganSoniya})> navbatHolati(
    int navbatId,
  ) async {
    final javob = await _api.get('$_asos/queue/$navbatId/');
    final holat = (javob['holat'] ?? '').toString();
    return (
      holat: holat,
      oyin: holat == 'topildi' ? GameBoshlanish.fromJson(javob) : null,
      qolganSoniya: (javob['qolgan_soniya'] as num? ?? 0).toInt(),
    );
  }

  /// Raqib topilmadi — robot bilan davom etamiz.
  Future<GameBoshlanish> navbatRobotga(int navbatId) async {
    final javob = await _api.post('$_asos/queue/$navbatId/robot/');
    return GameBoshlanish.fromJson(javob);
  }

  Future<void> navbatBekor(int navbatId) async {
    await _api.post('$_asos/queue/$navbatId/cancel/');
  }

  // ─── O'ynash (duel va yakka sessiya bitta interfeys ostida) ──

  Future<GameJavobNatijasi> javobYubor({
    required GameBoshlanish oyin,
    required int tartib,
    required String tanlangan,
    required int sarflanganMs,
  }) async {
    final yol = oyin.duel
        ? '$_asos/duel/${oyin.duelId}/answer/'
        : '$_asos/play/session/${oyin.sessiyaId}/answer/';

    final javob = await _api.post(
      yol,
      data: {
        'tartib': tartib,
        'tanlangan': tanlangan,
        'sarflangan_ms': sarflanganMs,
      },
    );
    return GameJavobNatijasi.fromJson(javob);
  }

  Future<GameNatija> yakunla(GameBoshlanish oyin) async {
    final yol = oyin.duel
        ? '$_asos/duel/${oyin.duelId}/finish/'
        : '$_asos/play/session/${oyin.sessiyaId}/finish/';

    final javob = await _api.post(yol);
    return GameNatija.fromJson(javob, oyinNomi: oyin.oyinNomi);
  }

  // ─── Yon bo'limlar ──────────────────────────────────────────

  Future<GameLiga> liga({String doira = 'markaz'}) async {
    final javob = await _api.get('$_asos/league/', queryParameters: {'doira': doira});
    return GameLiga.fromJson(javob);
  }

  Future<List<GameYangilik>> yangiliklar() async {
    final javob = await _api.get('$_asos/news/');
    return (javob['yangiliklar'] as List? ?? const [])
        .map((e) => GameYangilik.fromJson(Map<String, dynamic>.from(e as Map)))
        .toList();
  }

  Future<({double chaqmoq, List<GameMahsulot> mahsulotlar})> dokon() async {
    final javob = await _api.get('$_asos/shop/');
    return (
      chaqmoq: (javob['chaqmoq'] as num? ?? 0).toDouble(),
      mahsulotlar: (javob['mahsulotlar'] as List? ?? const [])
          .map((e) => GameMahsulot.fromJson(Map<String, dynamic>.from(e as Map)))
          .toList(),
    );
  }

  Future<({double chaqmoq, int jon, String xabar})> sotibOl(int mahsulotId) async {
    final javob = await _api.post('$_asos/shop/$mahsulotId/buy/');
    return (
      chaqmoq: (javob['chaqmoq'] as num? ?? 0).toDouble(),
      jon: (javob['jon'] as num? ?? 0).toInt(),
      xabar: (javob['xabar'] ?? 'Sotib olindi').toString(),
    );
  }

  // ─── Tariflar ───────────────────────────────────────────────

  Future<GameTariflar> tariflar() async {
    final javob = await _api.get('$_asos/tariffs/');
    return GameTariflar.fromJson(javob);
  }

  /// Tarif sotib olish so'rovi. `usul`: "click" yoki "naqd".
  ///
  /// Ikkala usulda ham so'rov yaratiladi va admin bilan Telegram orqali
  /// bog'lanish uchun havola qaytariladi.
  Future<({String xabar, String telegramUsername, String telegramMatn})>
      tarifSotibOl(int tarifId, {required String usul}) async {
    final javob = await _api.post(
      '$_asos/tariffs/$tarifId/buy/',
      data: {'usul': usul},
    );
    final telegram = javob['telegram'];
    final map = telegram is Map
        ? telegram.map((k, v) => MapEntry(k.toString(), v))
        : <String, dynamic>{};
    return (
      xabar: (javob['xabar'] ?? 'So‘rov yuborildi').toString(),
      telegramUsername: (map['username'] ?? '').toString(),
      telegramMatn: (map['matn'] ?? '').toString(),
    );
  }

  // ─── Shikoyat va takliflar ──────────────────────────────────

  Future<List<GameMurojaat>> murojaatlar() async {
    final javob = await _api.get('$_asos/feedback/');
    return (javob['murojaatlar'] as List? ?? const [])
        .map((e) => GameMurojaat.fromJson(Map<String, dynamic>.from(e as Map)))
        .toList();
  }

  Future<String> murojaatYubor({
    required String tur,
    required String matn,
    int? oyinId,
    String? aloqa,
  }) async {
    final javob = await _api.post(
      '$_asos/feedback/send/',
      data: <String, dynamic>{
        'tur': tur,
        'matn': matn,
        if (oyinId != null) 'mode_id': oyinId,
        if (aloqa != null && aloqa.isNotEmpty) 'aloqa': aloqa,
      },
    );
    return (javob['xabar'] ?? 'Yuborildi').toString();
  }

  /// Duel va yakka o'yin tarixini bitta ro'yxatga qo'shib beradi.
  Future<List<GameTarix>> tarix() async {
    final javoblar = await Future.wait([
      _api.get('$_asos/duel/history/'),
      _api.get('$_asos/play/history/'),
    ]);

    final natija = <GameTarix>[
      ...(javoblar[0]['duellar'] as List? ?? const [])
          .map((e) => GameTarix.duelJson(Map<String, dynamic>.from(e as Map))),
      ...(javoblar[1]['sessiyalar'] as List? ?? const [])
          .map((e) => GameTarix.sessiyaJson(Map<String, dynamic>.from(e as Map))),
    ];

    // Sanasi yo'qlar (kutilmagan holat) oxiriga tushadi.
    natija.sort((a, b) {
      final chap = a.sana;
      final ong = b.sana;
      if (chap == null && ong == null) return 0;
      if (chap == null) return 1;
      if (ong == null) return -1;
      return ong.compareTo(chap);
    });
    return natija;
  }
}
