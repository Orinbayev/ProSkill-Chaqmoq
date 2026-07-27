import 'package:flutter/material.dart';

/// Chaqmoq Game modellari — `/api/mobile/game/` javoblarining ko'zgusi.
///
/// Muhim: o'yinlar ro'yxati **kodda emas**, admin panelidagi katalogda.
/// Shu sababli bu yerda hech qanday o'yin nomi qattiq yozilmagan — faqat
/// motor kaliti (`motor`) bo'yicha mos ekran tanlanadi.

int _int(Object? v, [int fallback = 0]) {
  if (v is int) return v;
  if (v is num) return v.toInt();
  if (v is String) return int.tryParse(v) ?? fallback;
  return fallback;
}

double _double(Object? v, [double fallback = 0]) {
  if (v is num) return v.toDouble();
  if (v is String) return double.tryParse(v) ?? fallback;
  return fallback;
}

String _string(Object? v, [String fallback = '']) {
  if (v == null) return fallback;
  return v.toString();
}

String? _stringOrNull(Object? v) {
  if (v == null) return null;
  final text = v.toString().trim();
  return text.isEmpty ? null : text;
}

bool _bool(Object? v, [bool fallback = false]) {
  if (v is bool) return v;
  if (v is num) return v != 0;
  if (v is String) return v.toLowerCase() == 'true';
  return fallback;
}

List<String> _stringList(Object? v) {
  if (v is List) return v.map((e) => e.toString()).toList();
  return const [];
}

Map<String, dynamic> _map(Object? v) {
  if (v is Map) {
    return v.map((key, value) => MapEntry(key.toString(), value));
  }
  return <String, dynamic>{};
}

DateTime? _date(Object? v) {
  final text = _stringOrNull(v);
  if (text == null) return null;
  return DateTime.tryParse(text)?.toLocal();
}

/// `#0EA5E9` ko'rinishidagi rangni `Color`ga o'giradi.
Color rangdanColor(String? hex, Color fallback) {
  final tozalangan = (hex ?? '').replaceAll('#', '').trim();
  if (tozalangan.length != 6) return fallback;
  final qiymat = int.tryParse(tozalangan, radix: 16);
  if (qiymat == null) return fallback;
  return Color(0xFF000000 | qiymat);
}

/// Soniyani "3 soat 20 daqiqa" ko'rinishiga o'giradi.
String qolganVaqt(int soniya) {
  if (soniya <= 0) return 'Ochiq';
  final soat = soniya ~/ 3600;
  final daqiqa = (soniya % 3600) ~/ 60;
  if (soat >= 1) return '$soat soat ${daqiqa}m';
  if (daqiqa >= 1) return '$daqiqa daqiqa';
  return '$soniya soniya';
}

// ═══════════════════════════════════════════════════════════════
// O'YINCHI PROFILI
// ═══════════════════════════════════════════════════════════════

class GameProfil {
  const GameProfil({
    required this.ism,
    required this.avatar,
    required this.xp,
    required this.haftaXp,
    required this.chaqmoq,
    required this.jon,
    required this.maxJon,
    required this.keyingiJonSoniya,
    required this.streakKun,
    required this.liga,
    required this.pro,
    required this.tarif,
    required this.tarifTugaydi,
  });

  factory GameProfil.fromJson(Map<String, dynamic> json) {
    return GameProfil(
      ism: _string(json['ism'], 'O‘yinchi'),
      avatar: _stringOrNull(json['avatar']),
      xp: _int(json['xp']),
      haftaXp: _int(json['hafta_xp']),
      chaqmoq: _double(json['chaqmoq']),
      jon: _int(json['jon']),
      maxJon: _int(json['max_jon'], 3),
      keyingiJonSoniya: _int(json['keyingi_jon_soniya']),
      streakKun: _int(json['streak_kun']),
      liga: _string(json['liga'], 'bronza'),
      pro: _bool(json['pro']),
      tarif: _stringOrNull(json['tarif']),
      tarifTugaydi: _date(json['tarif_tugaydi']),
    );
  }

  static const bosh = GameProfil(
    ism: 'O‘yinchi',
    avatar: null,
    xp: 0,
    haftaXp: 0,
    chaqmoq: 0,
    jon: 0,
    maxJon: 3,
    keyingiJonSoniya: 0,
    streakKun: 0,
    liga: 'bronza',
    pro: false,
    tarif: null,
    tarifTugaydi: null,
  );

  final String ism;
  final String? avatar;
  final int xp;
  final int haftaXp;
  final double chaqmoq;
  final int jon;
  final int maxJon;
  final int keyingiJonSoniya;
  final int streakKun;
  final String liga;
  final bool pro;
  final String? tarif;
  final DateTime? tarifTugaydi;

  String get ligaNomi => switch (liga) {
    'olmos' => 'Olmos',
    'oltin' => 'Oltin',
    'kumush' => 'Kumush',
    _ => 'Bronza',
  };

  GameProfil nusxa({int? jon, double? chaqmoq, int? xp, String? liga, int? streakKun}) {
    return GameProfil(
      ism: ism,
      avatar: avatar,
      xp: xp ?? this.xp,
      haftaXp: haftaXp,
      chaqmoq: chaqmoq ?? this.chaqmoq,
      jon: jon ?? this.jon,
      maxJon: maxJon,
      keyingiJonSoniya: keyingiJonSoniya,
      streakKun: streakKun ?? this.streakKun,
      liga: liga ?? this.liga,
      pro: pro,
      tarif: tarif,
      tarifTugaydi: tarifTugaydi,
    );
  }
}

// ═══════════════════════════════════════════════════════════════
// KATALOG
// ═══════════════════════════════════════════════════════════════

/// Admin panelidagi bitta o'yin. Ilova buni o'zi o'ylab topmaydi — serverdan
/// oladi, shuning uchun yangi o'yin qo'shilishi bilanoq ro'yxatda paydo bo'ladi.
class GameOyin {
  const GameOyin({
    required this.id,
    required this.slug,
    required this.nom,
    required this.izoh,
    required this.yoriqnoma,
    required this.motor,
    required this.motorNomi,
    required this.ikonka,
    required this.rangHex,
    required this.rasm,
    required this.savollarSoni,
    required this.savolSoniya,
    required this.jonNarxi,
    required this.xpMukofot,
    required this.sozlamalar,
    required this.javobOchiq,
    required this.duelOqimi,
    required this.faqatPro,
    required this.mavjudSavol,
    required this.ochiq,
    required this.qulf,
    required this.qulfSoniya,
  });

  factory GameOyin.fromJson(Map<String, dynamic> json) {
    return GameOyin(
      id: _int(json['id']),
      slug: _string(json['slug']),
      nom: _string(json['nom'], 'O‘yin'),
      izoh: _string(json['izoh']),
      yoriqnoma: _string(json['yoriqnoma']),
      motor: _string(json['motor']),
      motorNomi: _string(json['motor_nomi']),
      ikonka: _string(json['ikonka'], '🎮'),
      rangHex: _string(json['rang'], '#0EA5E9'),
      rasm: _stringOrNull(json['rasm']),
      savollarSoni: _int(json['savollar_soni'], 10),
      savolSoniya: _int(json['savol_soniya']),
      jonNarxi: _int(json['jon_narxi'], 1),
      xpMukofot: _int(json['xp_mukofot']),
      sozlamalar: _map(json['sozlamalar']),
      javobOchiq: _bool(json['javob_ochiq']),
      duelOqimi: _bool(json['duel_oqimi']),
      faqatPro: _bool(json['faqat_pro']),
      mavjudSavol: _int(json['mavjud_savol']),
      ochiq: _bool(json['ochiq'], true),
      qulf: _string(json['qulf']),
      qulfSoniya: _int(json['qulf_soniya']),
    );
  }

  final int id;
  final String slug;
  final String nom;
  final String izoh;
  final String yoriqnoma;
  final String motor;
  final String motorNomi;
  final String ikonka;
  final String rangHex;
  final String? rasm;
  final int savollarSoni;
  final int savolSoniya;
  final int jonNarxi;
  final int xpMukofot;
  final Map<String, dynamic> sozlamalar;
  final bool javobOchiq;
  final bool duelOqimi;
  final bool faqatPro;
  final int mavjudSavol;
  final bool ochiq;
  final String qulf;

  /// O'yin qayta ochilishiga qancha qolgani (soniya). 0 = ochiq.
  final int qulfSoniya;

  Color rang(Color fallback) => rangdanColor(rangHex, fallback);

  int sozlamaInt(String kalit, int fallback) => _int(sozlamalar[kalit], fallback);

  /// Qulf sababi — tugma ostida o'quvchiga tushuntiriladi.
  String? get qulfMatni => switch (qulf) {
    'pro_kerak' => 'Tarif kerak',
    'jon_yoq' => 'Jon tugadi',
    'oyin_qulflangan' => qolganVaqt(qulfSoniya),
    'savol_yetarli_emas' => 'Savollar yetarli emas',
    'motor_nomalum' => 'Ilovani yangilang',
    _ => null,
  };
}

/// Server bilgan motorlar — ilova tanimaydigan motor uchun hech bo'lmasa
/// nomi va qoidasini ko'rsatish uchun.
class GameMotor {
  const GameMotor({
    required this.kalit,
    required this.nom,
    required this.izoh,
    required this.yoriqnoma,
  });

  factory GameMotor.fromJson(Map<String, dynamic> json) {
    return GameMotor(
      kalit: _string(json['kalit']),
      nom: _string(json['nom']),
      izoh: _string(json['izoh']),
      yoriqnoma: _string(json['yoriqnoma']),
    );
  }

  final String kalit;
  final String nom;
  final String izoh;
  final String yoriqnoma;
}

class GameKatalog {
  const GameKatalog({
    required this.profil,
    required this.orin,
    required this.oyinlar,
    required this.motorlar,
  });

  factory GameKatalog.fromJson(Map<String, dynamic> json) {
    return GameKatalog(
      profil: GameProfil.fromJson(_map(json['profil'])),
      orin: _int(json['orin']),
      oyinlar: (json['oyinlar'] as List? ?? const [])
          .map((e) => GameOyin.fromJson(_map(e)))
          .toList(),
      motorlar: (json['motorlar'] as List? ?? const [])
          .map((e) => GameMotor.fromJson(_map(e)))
          .toList(),
    );
  }

  static const bosh = GameKatalog(
    profil: GameProfil.bosh,
    orin: 0,
    oyinlar: [],
    motorlar: [],
  );

  final GameProfil profil;
  final int orin;
  final List<GameOyin> oyinlar;
  final List<GameMotor> motorlar;
}

// ═══════════════════════════════════════════════════════════════
// O'YIN SESSIYASI
// ═══════════════════════════════════════════════════════════════

class GameSavol {
  const GameSavol({
    required this.tartib,
    required this.tur,
    required this.matn,
    required this.variantlar,
    required this.audio,
    required this.rasm,
    required this.javob,
  });

  factory GameSavol.fromJson(Map<String, dynamic> json) {
    return GameSavol(
      tartib: _int(json['tartib']),
      tur: _string(json['tur'], 'tarjima'),
      matn: _string(json['savol']),
      variantlar: _stringList(json['variantlar']),
      audio: _stringOrNull(json['audio']),
      rasm: _stringOrNull(json['rasm']),
      // Faqat xotira/juftlash motorlarida keladi.
      javob: _stringOrNull(json['javob']),
    );
  }

  final int tartib;
  final String tur;
  final String matn;
  final List<String> variantlar;
  final String? audio;
  final String? rasm;
  final String? javob;

  String get yoriqnoma => switch (tur) {
    'eshitish' => 'Tinglang va toping',
    'boshliq' => 'Bo‘shliqni to‘ldiring',
    'rasm' => 'Rasmdagini toping',
    _ => 'Tarjimasini toping',
  };
}

/// O'yin boshlanganda serverdan keladigan hamma narsa.
class GameBoshlanish {
  const GameBoshlanish({
    required this.duel,
    required this.duelId,
    required this.sessiyaId,
    required this.motor,
    required this.oyinNomi,
    required this.sozlamalar,
    required this.savolSoniya,
    required this.savollar,
    required this.raqibNomi,
    required this.raqibAvatar,
    required this.jon,
    required this.pvp,
    required this.navbatId,
    required this.kutishSoniya,
  });

  /// Server "kutish" holatini qaytardimi — raqib qidirilmoqda.
  static bool kutishmi(Map<String, dynamic> json) =>
      _string(json['tur']) == 'kutish';

  factory GameBoshlanish.fromJson(Map<String, dynamic> json) {
    return GameBoshlanish(
      duel: _string(json['tur']) == 'duel',
      duelId: _int(json['duel_id']),
      sessiyaId: _int(json['sessiya_id']),
      motor: _string(json['motor']),
      oyinNomi: _string(json['oyin_nomi'], 'O‘yin'),
      sozlamalar: _map(json['sozlamalar']),
      savolSoniya: _int(json['savol_soniya']),
      savollar: (json['savollar'] as List? ?? const [])
          .map((e) => GameSavol.fromJson(_map(e)))
          .toList(),
      raqibNomi: _stringOrNull(json['raqib_nomi']),
      raqibAvatar: _stringOrNull(json['raqib_avatar']),
      jon: _int(json['jon']),
      pvp: _bool(json['pvp']),
      navbatId: _int(json['navbat_id']),
      kutishSoniya: _int(json['kutish_soniya'], 15),
    );
  }

  final bool duel;
  final int duelId;
  final int sessiyaId;
  final String motor;
  final String oyinNomi;
  final Map<String, dynamic> sozlamalar;
  final int savolSoniya;
  final List<GameSavol> savollar;
  final String? raqibNomi;
  final String? raqibAvatar;
  final int jon;

  /// `true` — raqib jonli odam (robot emas).
  final bool pvp;

  /// Raqib qidirish navbati (0 = navbat yo'q).
  final int navbatId;
  final int kutishSoniya;

  /// Duel va yakka sessiya uchun bitta identifikator — javob yuborishda ishlatiladi.
  int get oyinId => duel ? duelId : sessiyaId;

  int sozlamaInt(String kalit, int fallback) => _int(sozlamalar[kalit], fallback);
}

class GameJavobNatijasi {
  const GameJavobNatijasi({
    required this.togri,
    required this.togriJavob,
    required this.izoh,
    required this.ball,
    required this.togriJavoblar,
    required this.xatoJavoblar,
    required this.raqibTogri,
    required this.raqibJami,
  });

  factory GameJavobNatijasi.fromJson(Map<String, dynamic> json) {
    return GameJavobNatijasi(
      togri: _bool(json['togri']),
      togriJavob: _string(json['togri_javob']),
      izoh: _string(json['izoh']),
      ball: _int(json['ball']),
      togriJavoblar: _int(json['togri_javoblar']),
      xatoJavoblar: _int(json['xato_javoblar']),
      raqibTogri: _bool(json['raqib_togri']),
      raqibJami: _int(json['raqib_jami']),
    );
  }

  final bool togri;
  final String togriJavob;
  final String izoh;
  final int ball;
  final int togriJavoblar;
  final int xatoJavoblar;
  final bool raqibTogri;
  final int raqibJami;
}

/// O'yin yakuni — duel va yakka sessiya uchun umumiy.
class GameNatija {
  const GameNatija({
    required this.oyinNomi,
    required this.ball,
    required this.togriJavoblar,
    required this.jamiSavol,
    required this.aniqlik,
    required this.olinganXp,
    required this.olinganChaqmoq,
    required this.jon,
    required this.maxJon,
    required this.xp,
    required this.chaqmoq,
    required this.streakKun,
    required this.liga,
    required this.duelNatija,
    required this.raqibNomi,
    required this.raqibBall,
    required this.pvp,
    required this.kutilmoqda,
  });

  factory GameNatija.fromJson(Map<String, dynamic> json, {String? oyinNomi}) {
    final jami = _int(json['jami_savol'], _int(json['savollar_soni']));
    final togri = _int(json['togri_javoblar']);
    return GameNatija(
      oyinNomi: oyinNomi ?? _string(json['oyin_nomi'], 'O‘yin'),
      ball: _int(json['ball']),
      togriJavoblar: togri,
      jamiSavol: jami,
      aniqlik: json.containsKey('aniqlik')
          ? _int(json['aniqlik'])
          : (jami > 0 ? (togri * 100 / jami).round() : 0),
      olinganXp: _int(json['olingan_xp']),
      olinganChaqmoq: _double(json['olingan_chaqmoq']),
      jon: _int(json['jon']),
      maxJon: _int(json['max_jon'], 3),
      xp: _int(json['xp']),
      chaqmoq: _double(json['chaqmoq']),
      streakKun: _int(json['streak_kun']),
      liga: _string(json['liga'], 'bronza'),
      duelNatija: _stringOrNull(json['natija']),
      raqibNomi: _stringOrNull(json['raqib_nomi']),
      raqibBall: _int(json['raqib_ball']),
      pvp: _bool(json['pvp']),
      kutilmoqda: _bool(json['kutilmoqda']),
    );
  }

  final String oyinNomi;
  final int ball;
  final int togriJavoblar;
  final int jamiSavol;
  final int aniqlik;
  final int olinganXp;
  final double olinganChaqmoq;
  final int jon;
  final int maxJon;
  final int xp;
  final double chaqmoq;
  final int streakKun;
  final String liga;

  /// Duelda: `galaba` | `maglubiyat` | `durrang`. Yakka o'yinda `null`.
  final String? duelNatija;
  final String? raqibNomi;
  final int raqibBall;

  /// Odam bilan duel bo'lganmi.
  final bool pvp;

  /// PvP'da raqib hali tugatmagan — g'olib keyinroq ma'lum bo'ladi.
  final bool kutilmoqda;

  bool get duel => duelNatija != null || pvp;
  bool get galaba => duelNatija == 'galaba';
}

// ═══════════════════════════════════════════════════════════════
// LIGA, DO'KON, YANGILIK, TARIX
// ═══════════════════════════════════════════════════════════════

class GameLigaQatori {
  const GameLigaQatori({
    required this.orin,
    required this.ism,
    required this.avatar,
    required this.haftaXp,
    required this.chaqmoq,
    required this.liga,
    required this.men,
  });

  factory GameLigaQatori.fromJson(Map<String, dynamic> json) {
    return GameLigaQatori(
      orin: _int(json['orin']),
      ism: _string(json['ism'], '?'),
      avatar: _stringOrNull(json['avatar']),
      haftaXp: _int(json['hafta_xp']),
      chaqmoq: _double(json['chaqmoq']),
      liga: _string(json['liga'], 'bronza'),
      men: _bool(json['men']),
    );
  }

  final int orin;
  final String ism;
  final String? avatar;
  final int haftaXp;
  final double chaqmoq;
  final String liga;
  final bool men;
}

class GameLiga {
  const GameLiga({
    required this.liga,
    required this.meningOrinim,
    required this.qatorlar,
    required this.markazBor,
  });

  factory GameLiga.fromJson(Map<String, dynamic> json) {
    return GameLiga(
      liga: _string(json['liga'], 'bronza'),
      meningOrinim: _int(json['mening_orinim']),
      qatorlar: (json['qatorlar'] as List? ?? const [])
          .map((e) => GameLigaQatori.fromJson(_map(e)))
          .toList(),
      markazBor: _bool(json['markaz_bor'], true),
    );
  }

  final String liga;
  final int meningOrinim;
  final List<GameLigaQatori> qatorlar;

  /// Markazsiz o'yinchida «Markazim» doirasining ma'nosi yo'q —
  /// almashtirgich yashiriladi.
  final bool markazBor;
}

class GameMahsulot {
  const GameMahsulot({
    required this.id,
    required this.nom,
    required this.izoh,
    required this.tur,
    required this.rasm,
    required this.narxChaqmoq,
    required this.beradiganJon,
    required this.zaxira,
    required this.mavjud,
  });

  factory GameMahsulot.fromJson(Map<String, dynamic> json) {
    return GameMahsulot(
      id: _int(json['id']),
      nom: _string(json['nom']),
      izoh: _string(json['izoh']),
      tur: _string(json['tur']),
      rasm: _stringOrNull(json['rasm']),
      narxChaqmoq: _double(json['narx_chaqmoq']),
      beradiganJon: _int(json['beradigan_jon']),
      zaxira: _int(json['zaxira'], -1),
      mavjud: _bool(json['mavjud'], true),
    );
  }

  final int id;
  final String nom;
  final String izoh;
  final String tur;
  final String? rasm;
  final double narxChaqmoq;
  final int beradiganJon;
  final int zaxira;
  final bool mavjud;

  IconData get ikonka => switch (tur) {
    'jon' => Icons.favorite_rounded,
    'ramka' => Icons.crop_square_rounded,
    'avatar' => Icons.face_rounded,
    _ => Icons.card_giftcard_rounded,
  };
}

class GameYangilik {
  const GameYangilik({
    required this.id,
    required this.sarlavha,
    required this.matn,
    required this.tur,
    required this.muhim,
    required this.rasm,
    required this.sana,
  });

  factory GameYangilik.fromJson(Map<String, dynamic> json) {
    return GameYangilik(
      id: _int(json['id']),
      sarlavha: _string(json['sarlavha']),
      matn: _string(json['matn']),
      tur: _string(json['tur'], 'yangilik'),
      muhim: _bool(json['muhim']),
      rasm: _stringOrNull(json['rasm']),
      sana: _date(json['sana']),
    );
  }

  final int id;
  final String sarlavha;
  final String matn;
  final String tur;
  final bool muhim;
  final String? rasm;
  final DateTime? sana;
}

/// Tarix elementi — duel ham, yakka o'yin ham bitta ro'yxatda ko'rinadi.
class GameTarix {
  const GameTarix({
    required this.id,
    required this.duel,
    required this.nom,
    required this.ikonka,
    required this.rangHex,
    required this.ball,
    required this.raqibBall,
    required this.togriJavoblar,
    required this.jamiSavol,
    required this.natija,
    required this.olinganChaqmoq,
    required this.sana,
  });

  factory GameTarix.duelJson(Map<String, dynamic> json) {
    return GameTarix(
      id: _int(json['id']),
      duel: true,
      nom: _string(json['raqib_nomi'], 'Raqib'),
      ikonka: '⚔️',
      rangHex: '#6366F1',
      ball: _int(json['ball']),
      raqibBall: _int(json['raqib_ball']),
      togriJavoblar: _int(json['togri_javoblar']),
      jamiSavol: _int(json['savollar_soni'], 10),
      natija: _string(json['natija']),
      olinganChaqmoq: _double(json['olingan_chaqmoq']),
      sana: _date(json['sana']),
    );
  }

  factory GameTarix.sessiyaJson(Map<String, dynamic> json) {
    return GameTarix(
      id: _int(json['id']),
      duel: false,
      nom: _string(json['oyin_nomi'], 'O‘yin'),
      ikonka: _string(json['ikonka'], '🎮'),
      rangHex: _string(json['rang'], '#0EA5E9'),
      ball: _int(json['ball']),
      raqibBall: 0,
      togriJavoblar: _int(json['togri_javoblar']),
      jamiSavol: _int(json['jami_savol']),
      natija: '',
      olinganChaqmoq: _double(json['olingan_chaqmoq']),
      sana: _date(json['sana']),
    );
  }

  final int id;
  final bool duel;
  final String nom;
  final String ikonka;
  final String rangHex;
  final int ball;
  final int raqibBall;
  final int togriJavoblar;
  final int jamiSavol;
  final String natija;
  final double olinganChaqmoq;
  final DateTime? sana;
}

// ═══════════════════════════════════════════════════════════════
// TARIFLAR VA TO'LOV
// ═══════════════════════════════════════════════════════════════

class GameTarif {
  const GameTarif({
    required this.id,
    required this.nom,
    required this.narxSom,
    required this.haftalikNarx,
    required this.kun,
    required this.jonSoni,
    required this.jonSoat,
    required this.oyinQulfSoat,
    required this.chaqmoqBonusFoiz,
    required this.tavsif,
    required this.izoh,
    required this.joriy,
  });

  factory GameTarif.fromJson(Map<String, dynamic> json) {
    return GameTarif(
      id: _int(json['id']),
      nom: _string(json['nom']),
      narxSom: _int(json['narx_som']),
      haftalikNarx: _int(json['haftalik_narx']),
      kun: _int(json['kun']),
      jonSoni: _int(json['jon_soni'], 3),
      jonSoat: _int(json['soat'], 8),
      oyinQulfSoat: _int(json['oyin_qulf_soat'], 24),
      chaqmoqBonusFoiz: _int(json['chaqmoq_bonus_foiz']),
      tavsif: _string(json['tavsif']),
      izoh: _string(json['izoh']),
      joriy: _bool(json['joriy']),
    );
  }

  final int id;
  final String nom;
  final int narxSom;
  final int haftalikNarx;
  final int kun;
  final int jonSoni;
  final int jonSoat;
  final int oyinQulfSoat;
  final int chaqmoqBonusFoiz;
  final String tavsif;
  final String izoh;
  final bool joriy;
}

/// Bepul yoki joriy rejaning qoidalari — taqqoslash uchun.
class GameReja {
  const GameReja({
    required this.jonSoni,
    required this.jonSoat,
    required this.oyinQulfSoat,
    required this.chaqmoqBonusFoiz,
  });

  factory GameReja.fromJson(Map<String, dynamic> json) {
    return GameReja(
      jonSoni: _int(json['jon_soni'], 3),
      jonSoat: _int(json['jon_soat'], 8),
      oyinQulfSoat: _int(json['oyin_qulf_soat'], 24),
      chaqmoqBonusFoiz: _int(json['chaqmoq_bonus_foiz']),
    );
  }

  final int jonSoni;
  final int jonSoat;
  final int oyinQulfSoat;
  final int chaqmoqBonusFoiz;
}

class GameTariflar {
  const GameTariflar({
    required this.joriyTarif,
    required this.tugaydi,
    required this.bepul,
    required this.joriy,
    required this.tariflar,
    required this.kutayotganSorov,
  });

  factory GameTariflar.fromJson(Map<String, dynamic> json) {
    final kutayotgan = json['kutayotgan_sorov'];
    return GameTariflar(
      joriyTarif: _stringOrNull(json['joriy_tarif']),
      tugaydi: _date(json['tugaydi']),
      bepul: GameReja.fromJson(_map(json['bepul'])),
      joriy: GameReja.fromJson(_map(json['joriy'])),
      tariflar: (json['tariflar'] as List? ?? const [])
          .map((e) => GameTarif.fromJson(_map(e)))
          .toList(),
      kutayotganSorov: kutayotgan == null
          ? null
          : _string(_map(kutayotgan)['tarif']),
    );
  }

  final String? joriyTarif;
  final DateTime? tugaydi;
  final GameReja bepul;
  final GameReja joriy;
  final List<GameTarif> tariflar;

  /// Tasdiqlanmagan so'rov bo'lsa — tarif nomi.
  final String? kutayotganSorov;

  bool get proMi => joriyTarif != null;
}

// ═══════════════════════════════════════════════════════════════
// SHIKOYAT VA TAKLIFLAR
// ═══════════════════════════════════════════════════════════════

class GameMurojaat {
  const GameMurojaat({
    required this.id,
    required this.tur,
    required this.turNomi,
    required this.matn,
    required this.holat,
    required this.holatNomi,
    required this.javob,
    required this.sana,
  });

  factory GameMurojaat.fromJson(Map<String, dynamic> json) {
    return GameMurojaat(
      id: _int(json['id']),
      tur: _string(json['tur']),
      turNomi: _string(json['tur_nomi']),
      matn: _string(json['matn']),
      holat: _string(json['holat']),
      holatNomi: _string(json['holat_nomi']),
      javob: _string(json['javob']),
      sana: _date(json['sana']),
    );
  }

  final int id;
  final String tur;
  final String turNomi;
  final String matn;
  final String holat;
  final String holatNomi;
  final String javob;
  final DateTime? sana;

  bool get javobBor => javob.trim().isNotEmpty;
}
