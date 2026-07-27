import 'package:chaqmoq_mobile/models/app_models.dart';
import 'package:chaqmoq_mobile/models/game_models.dart';
import 'package:chaqmoq_mobile/services/api_client.dart';
import 'package:chaqmoq_mobile/services/game_service.dart';
import 'package:flutter/foundation.dart';

/// O'yin bo'limi holati: katalog, profil va yon bo'limlar.
///
/// O'yin ichidagi holat (joriy savol, taymer, ball) bu yerda **saqlanmaydi** —
/// u har motorning o'z ekranida yashaydi. Provider faqat o'yindan tashqaridagi,
/// ekranlar orasida bo'lishiladigan narsalarni tutadi.
class GameProvider extends ChangeNotifier {
  GameProvider({required GameService service}) : _service = service;

  final GameService _service;

  GameKatalog _katalog = GameKatalog.bosh;
  ViewState _state = ViewState.idle;
  String? _errorMessage;

  GameLiga? _liga;
  List<GameYangilik> _yangiliklar = const [];
  List<GameTarix> _tarix = const [];
  List<GameMahsulot> _mahsulotlar = const [];

  GameKatalog get katalog => _katalog;
  GameProfil get profil => _katalog.profil;
  List<GameOyin> get oyinlar => _katalog.oyinlar;
  int get orin => _katalog.orin;
  ViewState get state => _state;
  String? get errorMessage => _errorMessage;

  GameLiga? get liga => _liga;
  List<GameYangilik> get yangiliklar => _yangiliklar;
  List<GameTarix> get tarix => _tarix;
  List<GameMahsulot> get mahsulotlar => _mahsulotlar;

  bool get yuklangan => _state == ViewState.success;

  /// Serverdagi motor tavsifi — ilova tanimaydigan o'yin uchun.
  GameMotor? motorTavsifi(String kalit) {
    for (final motor in _katalog.motorlar) {
      if (motor.kalit == kalit) return motor;
    }
    return null;
  }

  Future<void> load({bool force = false}) async {
    if (_state == ViewState.loading) return;
    if (!force && _state == ViewState.success) return;

    _state = ViewState.loading;
    _errorMessage = null;
    notifyListeners();

    try {
      _katalog = await _service.katalog();
      _state = ViewState.success;
    } catch (error) {
      _state = ViewState.error;
      _errorMessage = error is ApiException
          ? error.message
          : 'O‘yinlar ro‘yxati yuklanmadi';
    } finally {
      notifyListeners();
    }
  }

  Future<void> refresh() => load(force: true);

  /// O'yin tugagach chaqiriladi — jon/chaqmoq/XP darhol yangilanadi.
  ///
  /// Katalogni qayta so'raymiz, chunki jon kamayishi bilan boshqa o'yinlarning
  /// «ochiq» holati ham o'zgaradi.
  Future<void> natijaniQabulQil(GameNatija natija) async {
    _katalog = GameKatalog(
      profil: profil.nusxa(
        jon: natija.jon,
        chaqmoq: natija.chaqmoq,
        xp: natija.xp,
        liga: natija.liga,
        streakKun: natija.streakKun,
      ),
      orin: _katalog.orin,
      oyinlar: _katalog.oyinlar,
      motorlar: _katalog.motorlar,
    );
    notifyListeners();
    await refresh();
  }

  // ─── Yon bo'limlar ──────────────────────────────────────────

  Future<GameBoshlanish> oyinBoshla(
    GameOyin oyin, {
    int? raqibId,
    bool robot = false,
  }) {
    return _service.oyinBoshla(oyin.id, raqibId: raqibId, robot: robot);
  }

  // ─── Raqib qidirish ─────────────────────────────────────────

  Future<({String holat, GameBoshlanish? oyin, int qolganSoniya})> navbatHolati(
    int navbatId,
  ) => _service.navbatHolati(navbatId);

  Future<GameBoshlanish> navbatRobotga(int navbatId) =>
      _service.navbatRobotga(navbatId);

  Future<void> navbatBekor(int navbatId) => _service.navbatBekor(navbatId);

  // ─── Tariflar va murojaatlar ────────────────────────────────

  Future<GameTariflar> tariflar() => _service.tariflar();

  Future<({String xabar, String telegramUsername, String telegramMatn})>
      tarifSotibOl(int tarifId, {required String usul}) async {
    final natija = await _service.tarifSotibOl(tarifId, usul: usul);
    // Naqd so'rovda tarif hali yoqilmaydi, lekin Click'da darhol yoqilishi
    // mumkin — katalogni yangilab qo'yamiz.
    await refresh();
    return natija;
  }

  Future<List<GameMurojaat>> murojaatlar() => _service.murojaatlar();

  Future<String> murojaatYubor({
    required String tur,
    required String matn,
    int? oyinId,
    String? aloqa,
  }) => _service.murojaatYubor(
    tur: tur, matn: matn, oyinId: oyinId, aloqa: aloqa,
  );

  Future<GameJavobNatijasi> javobYubor({
    required GameBoshlanish oyin,
    required int tartib,
    required String tanlangan,
    required int sarflanganMs,
  }) {
    return _service.javobYubor(
      oyin: oyin,
      tartib: tartib,
      tanlangan: tanlangan,
      sarflanganMs: sarflanganMs,
    );
  }

  Future<GameNatija> yakunla(GameBoshlanish oyin) => _service.yakunla(oyin);

  Future<void> ligaYukla({String doira = 'markaz'}) async {
    _liga = await _service.liga(doira: doira);
    notifyListeners();
  }

  Future<void> yangiliklarYukla() async {
    _yangiliklar = await _service.yangiliklar();
    notifyListeners();
  }

  Future<void> tarixYukla() async {
    _tarix = await _service.tarix();
    notifyListeners();
  }

  Future<void> dokonYukla() async {
    final natija = await _service.dokon();
    _mahsulotlar = natija.mahsulotlar;
    _yangiChaqmoq(natija.chaqmoq);
  }

  Future<String> sotibOl(GameMahsulot mahsulot) async {
    final natija = await _service.sotibOl(mahsulot.id);
    _katalog = GameKatalog(
      profil: profil.nusxa(chaqmoq: natija.chaqmoq, jon: natija.jon),
      orin: _katalog.orin,
      oyinlar: _katalog.oyinlar,
      motorlar: _katalog.motorlar,
    );
    notifyListeners();
    // Jon qo'shilgan bo'lishi mumkin — qulflangan o'yinlar ochilgandir.
    await refresh();
    return natija.xabar;
  }

  void _yangiChaqmoq(double chaqmoq) {
    _katalog = GameKatalog(
      profil: profil.nusxa(chaqmoq: chaqmoq),
      orin: _katalog.orin,
      oyinlar: _katalog.oyinlar,
      motorlar: _katalog.motorlar,
    );
    notifyListeners();
  }

  /// Chiqishda tozalanadi — keyingi foydalanuvchi boshqasining ballini ko'rmasin.
  void tozala() {
    _katalog = GameKatalog.bosh;
    _state = ViewState.idle;
    _errorMessage = null;
    _liga = null;
    _yangiliklar = const [];
    _tarix = const [];
    _mahsulotlar = const [];
    notifyListeners();
  }
}
