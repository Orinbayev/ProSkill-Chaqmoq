import 'dart:async';
import 'dart:math' as math;

import 'package:chaqmoq_mobile/core/theme/student_tokens.dart';
import 'package:chaqmoq_mobile/models/game_models.dart';
import 'package:chaqmoq_mobile/providers/game_provider.dart';
import 'package:chaqmoq_mobile/screens/student/game/widgets/game_widgets.dart';
import 'package:flutter/material.dart';
import 'package:google_fonts/google_fonts.dart';
import 'package:provider/provider.dart';

/// Xotira motori — so'z va tarjimasi yopiq kartalar orasidan topiladi.
///
/// Ball qoidasi: **har so'z uchun birinchi urinish hisoblanadi.** Noto'g'ri
/// juftlagan bo'lsangiz, o'sha so'z xato deb yoziladi, lekin karta taxtada
/// qoladi — o'yinni oxirigacha tugatish kerak. Shunda o'yin xotirani sinaydi,
/// tasodifiy bosishni emas.
class MemoryEngineScreen extends StatefulWidget {
  const MemoryEngineScreen({
    super.key,
    required this.oyin,
    required this.boshlanish,
  });

  final GameOyin oyin;
  final GameBoshlanish boshlanish;

  @override
  State<MemoryEngineScreen> createState() => _MemoryEngineScreenState();
}

class _Karta {
  _Karta({required this.tartib, required this.matn, required this.savolTomoni});

  /// Qaysi savolga tegishli (server tartibi).
  final int tartib;
  final String matn;

  /// `true` — so'z tomoni, `false` — tarjima tomoni.
  final bool savolTomoni;

  bool topilgan = false;
}

class _MemoryEngineScreenState extends State<MemoryEngineScreen> {
  late final Duration _ochiqQolish = Duration(
    milliseconds: widget.boshlanish.sozlamaInt('ochiq_qolish_ms', 900),
  );

  late final List<_Karta> _kartalar = _kartalarniYasa();

  /// Hozir ochiq turgan (hali juftlanmagan) kartalar indeksi.
  final List<int> _ochiq = [];

  /// Serverga bali yozilgan savollar — ikkinchi marta yozilmaydi.
  final Set<int> _ballangan = {};

  bool _band = false;
  bool _yakunlanmoqda = false;
  int _topilgan = 0;
  int _urinish = 0;
  DateTime _juftBoshlandi = DateTime.now();

  int get _jamiJuft => widget.boshlanish.savollar.length;

  List<_Karta> _kartalarniYasa() {
    final kartalar = <_Karta>[];
    for (final savol in widget.boshlanish.savollar) {
      // `javob` faqat javob_ochiq motorlarda keladi; bo'lmasa savolni tashlaymiz.
      final javob = savol.javob;
      if (javob == null || javob.isEmpty) continue;
      kartalar.add(_Karta(tartib: savol.tartib, matn: savol.matn, savolTomoni: true));
      kartalar.add(_Karta(tartib: savol.tartib, matn: javob, savolTomoni: false));
    }
    kartalar.shuffle(math.Random());
    return kartalar;
  }

  Future<void> _kartaBosildi(int indeks) async {
    if (_band || _yakunlanmoqda) return;
    final karta = _kartalar[indeks];
    if (karta.topilgan || _ochiq.contains(indeks)) return;

    setState(() {
      if (_ochiq.isEmpty) _juftBoshlandi = DateTime.now();
      _ochiq.add(indeks);
    });

    if (_ochiq.length < 2) return;

    _band = true;
    _urinish++;

    final birinchi = _kartalar[_ochiq[0]];
    final ikkinchi = _kartalar[_ochiq[1]];
    final moslik = birinchi.tartib == ikkinchi.tartib;

    await _ballYoz(birinchi: birinchi, ikkinchi: ikkinchi, moslik: moslik);
    if (!mounted) return;

    if (moslik) {
      setState(() {
        birinchi.topilgan = true;
        ikkinchi.topilgan = true;
        _ochiq.clear();
        _topilgan++;
        _band = false;
      });

      if (_topilgan >= _jamiJuft) {
        await _yakunla();
      }
      return;
    }

    await Future<void>.delayed(_ochiqQolish);
    if (!mounted) return;
    setState(() {
      _ochiq.clear();
      _band = false;
    });
  }

  /// Bitta juft urinishi uchun serverga javob yuboradi.
  ///
  /// Har savol faqat bir marta baholanadi — shuning uchun allaqachon
  /// baholangan so'zni qayta yubormaymiz.
  Future<void> _ballYoz({
    required _Karta birinchi,
    required _Karta ikkinchi,
    required bool moslik,
  }) async {
    final tartib = birinchi.tartib;
    if (_ballangan.contains(tartib)) return;

    // To'g'ri juftlikda javob — tarjima tomonidagi matn.
    final tanlangan = moslik
        ? (birinchi.savolTomoni ? ikkinchi.matn : birinchi.matn)
        : ikkinchi.matn;

    _ballangan.add(tartib);
    try {
      await context.read<GameProvider>().javobYubor(
        oyin: widget.boshlanish,
        tartib: tartib,
        tanlangan: tanlangan,
        sarflanganMs: DateTime.now().difference(_juftBoshlandi).inMilliseconds,
      );
    } catch (error) {
      // Yozilmadi — keyingi urinishda qayta yozishga ruxsat beramiz.
      _ballangan.remove(tartib);
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text('$error')));
    }
  }

  Future<void> _yakunla() async {
    if (_yakunlanmoqda) return;
    _yakunlanmoqda = true;

    final navigator = Navigator.of(context);
    try {
      final natija = await context.read<GameProvider>().yakunla(widget.boshlanish);
      if (!mounted) return;
      navigator.pop(natija);
    } catch (error) {
      if (!mounted) return;
      _yakunlanmoqda = false;
      ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text('$error')));
    }
  }

  Future<void> _chiqishSorovi() async {
    if (_yakunlanmoqda) return;
    final chiq = await gameChiqishSorovi(context, jonKetadi: widget.oyin.jonNarxi > 0);
    if (!mounted) return;
    if (chiq) await _yakunla();
  }

  @override
  Widget build(BuildContext context) {
    final tokens = StudentTokens.of(context);
    final ustunlar = _kartalar.length <= 8 ? 3 : 4;

    return PopScope(
      canPop: false,
      onPopInvokedWithResult: (didPop, _) {
        if (!didPop) _chiqishSorovi();
      },
      child: Scaffold(
        backgroundColor: tokens.bg,
        body: SafeArea(
          child: Column(
            children: [
              Padding(
                padding: const EdgeInsets.fromLTRB(6, 6, 16, 0),
                child: Row(
                  children: [
                    IconButton(
                      onPressed: _chiqishSorovi,
                      icon: Icon(Icons.close_rounded, color: tokens.textMuted),
                      tooltip: 'O‘yindan chiqish',
                    ),
                    Expanded(
                      child: Text(
                        widget.oyin.nom,
                        maxLines: 1,
                        overflow: TextOverflow.ellipsis,
                        style: GoogleFonts.inter(
                          fontSize: 15,
                          fontWeight: FontWeight.w800,
                          color: tokens.text,
                        ),
                      ),
                    ),
                    GameStatChip(
                      ikonka: Icons.style_rounded,
                      matn: '$_topilgan/$_jamiJuft',
                      rang: tokens.primary,
                    ),
                    const SizedBox(width: 8),
                    GameStatChip(
                      ikonka: Icons.touch_app_rounded,
                      matn: '$_urinish',
                      rang: tokens.textMuted,
                    ),
                  ],
                ),
              ),
              Padding(
                padding: const EdgeInsets.fromLTRB(20, 6, 20, 10),
                child: Text(
                  'So‘zni tarjimasi bilan juftlang',
                  style: GoogleFonts.inter(
                    fontSize: 12.5,
                    fontWeight: FontWeight.w600,
                    color: tokens.textDim,
                  ),
                ),
              ),
              Expanded(
                child: GridView.builder(
                  padding: const EdgeInsets.fromLTRB(16, 4, 16, 20),
                  gridDelegate: SliverGridDelegateWithFixedCrossAxisCount(
                    crossAxisCount: ustunlar,
                    crossAxisSpacing: 10,
                    mainAxisSpacing: 10,
                    childAspectRatio: 0.86,
                  ),
                  itemCount: _kartalar.length,
                  itemBuilder: (context, i) {
                    final karta = _kartalar[i];
                    return _KartaWidget(
                      karta: karta,
                      ochiq: karta.topilgan || _ochiq.contains(i),
                      onTap: () => _kartaBosildi(i),
                    );
                  },
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }
}

class _KartaWidget extends StatelessWidget {
  const _KartaWidget({
    required this.karta,
    required this.ochiq,
    required this.onTap,
  });

  final _Karta karta;
  final bool ochiq;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    final tokens = StudentTokens.of(context);

    final fon = karta.topilgan
        ? tokens.tonedSurface(tokens.success)
        : ochiq
        ? tokens.tonedSurface(tokens.primary)
        : tokens.cardBg;
    final chegara = karta.topilgan
        ? tokens.success
        : ochiq
        ? tokens.primary
        : tokens.border;

    return Material(
      color: fon,
      borderRadius: BorderRadius.circular(16),
      child: InkWell(
        onTap: karta.topilgan ? null : onTap,
        borderRadius: BorderRadius.circular(16),
        child: AnimatedContainer(
          duration: const Duration(milliseconds: 200),
          decoration: BoxDecoration(
            borderRadius: BorderRadius.circular(16),
            border: Border.all(color: chegara, width: ochiq ? 1.6 : 1),
          ),
          padding: const EdgeInsets.all(8),
          child: Center(
            child: AnimatedSwitcher(
              duration: const Duration(milliseconds: 180),
              transitionBuilder: (child, animation) =>
                  ScaleTransition(scale: animation, child: child),
              child: ochiq
                  ? FittedBox(
                      key: const ValueKey('ochiq'),
                      fit: BoxFit.scaleDown,
                      child: Padding(
                        padding: const EdgeInsets.all(2),
                        child: Text(
                          karta.matn,
                          textAlign: TextAlign.center,
                          style: GoogleFonts.inter(
                            fontSize: 14,
                            fontWeight: FontWeight.w800,
                            color: tokens.text,
                            height: 1.2,
                          ),
                        ),
                      ),
                    )
                  : Icon(
                      Icons.bolt_rounded,
                      key: const ValueKey('yopiq'),
                      size: 24,
                      color: tokens.textDim,
                    ),
            ),
          ),
        ),
      ),
    );
  }
}
