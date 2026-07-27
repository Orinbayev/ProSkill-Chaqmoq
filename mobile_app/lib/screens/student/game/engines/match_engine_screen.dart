import 'dart:async';
import 'dart:math' as math;

import 'package:chaqmoq_mobile/core/theme/student_tokens.dart';
import 'package:chaqmoq_mobile/models/game_models.dart';
import 'package:chaqmoq_mobile/providers/game_provider.dart';
import 'package:chaqmoq_mobile/screens/student/game/widgets/game_widgets.dart';
import 'package:flutter/material.dart';
import 'package:google_fonts/google_fonts.dart';
import 'package:provider/provider.dart';

/// Juftlash motori — chap ustundagi so'zni o'ng ustundagi tarjimasiga ulash.
///
/// Xotira motoridagi kabi, **har so'z uchun birinchi urinish hisoblanadi**:
/// xato ulasangiz ball ketadi, lekin so'z taxtada qoladi va o'yin tugagunga
/// qadar uni to'g'ri joyiga qo'yish kerak.
class MatchEngineScreen extends StatefulWidget {
  const MatchEngineScreen({
    super.key,
    required this.oyin,
    required this.boshlanish,
  });

  final GameOyin oyin;
  final GameBoshlanish boshlanish;

  @override
  State<MatchEngineScreen> createState() => _MatchEngineScreenState();
}

class _Element {
  _Element({required this.tartib, required this.matn});

  final int tartib;
  final String matn;
  bool topilgan = false;
}

class _MatchEngineScreenState extends State<MatchEngineScreen> {
  late final List<_Element> _chap = _ustunYasa(savolTomoni: true);
  late final List<_Element> _ong = _ustunYasa(savolTomoni: false);

  final Set<int> _ballangan = {};

  int? _tanlanganChap;
  int? _xatoChap;
  int? _xatoOng;

  bool _band = false;
  bool _yakunlanmoqda = false;
  int _topilgan = 0;
  int _urinish = 0;
  DateTime _urinishBoshlandi = DateTime.now();

  int get _jamiJuft => _chap.length;

  List<_Element> _ustunYasa({required bool savolTomoni}) {
    final elementlar = <_Element>[];
    for (final savol in widget.boshlanish.savollar) {
      final javob = savol.javob;
      if (javob == null || javob.isEmpty) continue;
      elementlar.add(
        _Element(tartib: savol.tartib, matn: savolTomoni ? savol.matn : javob),
      );
    }
    elementlar.shuffle(math.Random());
    return elementlar;
  }

  Future<void> _chapBosildi(int indeks) async {
    if (_band || _yakunlanmoqda || _chap[indeks].topilgan) return;
    setState(() {
      _tanlanganChap = _tanlanganChap == indeks ? null : indeks;
      _urinishBoshlandi = DateTime.now();
    });
  }

  Future<void> _ongBosildi(int indeks) async {
    if (_band || _yakunlanmoqda || _ong[indeks].topilgan) return;

    final chapIndeks = _tanlanganChap;
    if (chapIndeks == null) {
      // Avval chap ustundan so'z tanlansin.
      return;
    }

    _band = true;
    _urinish++;

    final chap = _chap[chapIndeks];
    final ong = _ong[indeks];
    final moslik = chap.tartib == ong.tartib;

    await _ballYoz(chap: chap, tanlangan: ong.matn, moslik: moslik);
    if (!mounted) return;

    if (moslik) {
      setState(() {
        chap.topilgan = true;
        ong.topilgan = true;
        _tanlanganChap = null;
        _topilgan++;
        _band = false;
      });

      if (_topilgan >= _jamiJuft) await _yakunla();
      return;
    }

    setState(() {
      _xatoChap = chapIndeks;
      _xatoOng = indeks;
    });
    await Future<void>.delayed(const Duration(milliseconds: 550));
    if (!mounted) return;
    setState(() {
      _xatoChap = null;
      _xatoOng = null;
      _tanlanganChap = null;
      _band = false;
    });
  }

  Future<void> _ballYoz({
    required _Element chap,
    required String tanlangan,
    required bool moslik,
  }) async {
    if (_ballangan.contains(chap.tartib)) return;

    _ballangan.add(chap.tartib);
    try {
      await context.read<GameProvider>().javobYubor(
        oyin: widget.boshlanish,
        tartib: chap.tartib,
        tanlangan: tanlangan,
        sarflanganMs: DateTime.now().difference(_urinishBoshlandi).inMilliseconds,
      );
    } catch (error) {
      _ballangan.remove(chap.tartib);
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
                      ikonka: Icons.link_rounded,
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
                padding: const EdgeInsets.fromLTRB(20, 6, 20, 12),
                child: Text(
                  _tanlanganChap == null
                      ? 'Chapdagi so‘zni tanlang'
                      : 'Endi uning tarjimasini bosing',
                  style: GoogleFonts.inter(
                    fontSize: 12.5,
                    fontWeight: FontWeight.w700,
                    color: _tanlanganChap == null ? tokens.textDim : tokens.primary,
                  ),
                ),
              ),
              Expanded(
                child: SingleChildScrollView(
                  padding: const EdgeInsets.fromLTRB(16, 0, 16, 20),
                  child: Row(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Expanded(
                        child: Column(
                          children: [
                            for (var i = 0; i < _chap.length; i++)
                              _ElementWidget(
                                element: _chap[i],
                                tanlangan: _tanlanganChap == i,
                                xato: _xatoChap == i,
                                onTap: () => _chapBosildi(i),
                              ),
                          ],
                        ),
                      ),
                      const SizedBox(width: 12),
                      Expanded(
                        child: Column(
                          children: [
                            for (var i = 0; i < _ong.length; i++)
                              _ElementWidget(
                                element: _ong[i],
                                tanlangan: false,
                                xato: _xatoOng == i,
                                onTap: () => _ongBosildi(i),
                              ),
                          ],
                        ),
                      ),
                    ],
                  ),
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }
}

class _ElementWidget extends StatelessWidget {
  const _ElementWidget({
    required this.element,
    required this.tanlangan,
    required this.xato,
    required this.onTap,
  });

  final _Element element;
  final bool tanlangan;
  final bool xato;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    final tokens = StudentTokens.of(context);

    final (Color fon, Color chegara, Color matnRangi) = element.topilgan
        ? (
            tokens.tonedSurface(tokens.success),
            tokens.success,
            tokens.success,
          )
        : xato
        ? (tokens.tonedSurface(tokens.danger), tokens.danger, tokens.danger)
        : tanlangan
        ? (tokens.tonedSurface(tokens.primary), tokens.primary, tokens.text)
        : (tokens.cardBg, tokens.border, tokens.text);

    return Padding(
      padding: const EdgeInsets.only(bottom: 10),
      child: Material(
        color: fon,
        borderRadius: BorderRadius.circular(14),
        child: InkWell(
          onTap: element.topilgan ? null : onTap,
          borderRadius: BorderRadius.circular(14),
          child: AnimatedContainer(
            duration: const Duration(milliseconds: 180),
            padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 14),
            decoration: BoxDecoration(
              borderRadius: BorderRadius.circular(14),
              border: Border.all(
                color: chegara,
                width: tanlangan || xato || element.topilgan ? 1.6 : 1,
              ),
            ),
            child: Row(
              children: [
                Expanded(
                  child: Text(
                    element.matn,
                    maxLines: 2,
                    overflow: TextOverflow.ellipsis,
                    style: GoogleFonts.inter(
                      fontSize: 13.5,
                      fontWeight: FontWeight.w700,
                      color: matnRangi,
                      height: 1.25,
                    ),
                  ),
                ),
                if (element.topilgan)
                  Icon(Icons.check_rounded, size: 16, color: tokens.success),
              ],
            ),
          ),
        ),
      ),
    );
  }
}
