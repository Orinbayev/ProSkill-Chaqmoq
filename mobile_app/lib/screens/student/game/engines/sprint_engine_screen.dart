import 'dart:async';

import 'package:chaqmoq_mobile/core/theme/student_tokens.dart';
import 'package:chaqmoq_mobile/models/game_models.dart';
import 'package:chaqmoq_mobile/providers/game_provider.dart';
import 'package:chaqmoq_mobile/screens/student/game/widgets/game_widgets.dart';
import 'package:flutter/material.dart';
import 'package:flutter_animate/flutter_animate.dart';
import 'package:google_fonts/google_fonts.dart';
import 'package:provider/provider.dart';

/// Sprint motori — vaqt **umumiy**, savolma-savol emas.
///
/// Shu sababli javob qaytimi ataylab qisqa (300 ms): o'quvchi to'xtamasdan
/// keyingi savolga o'tadi va butun o'yin bitta poyga bo'lib tuyuladi.
class SprintEngineScreen extends StatefulWidget {
  const SprintEngineScreen({
    super.key,
    required this.oyin,
    required this.boshlanish,
  });

  final GameOyin oyin;
  final GameBoshlanish boshlanish;

  @override
  State<SprintEngineScreen> createState() => _SprintEngineScreenState();
}

class _SprintEngineScreenState extends State<SprintEngineScreen> {
  static const _javobKutish = Duration(milliseconds: 300);

  late final Duration _jamiVaqt = Duration(
    seconds: widget.boshlanish.sozlamaInt('davomiylik_soniya', 60),
  );

  late DateTime _boshlandi;
  Timer? _taymer;
  Duration _qolgan = Duration.zero;

  int _indeks = 0;
  String? _tanlangan;
  GameJavobNatijasi? _natija;
  bool _yuborilmoqda = false;
  bool _yakunlanmoqda = false;

  int _togri = 0;
  int _ketmaKet = 0;
  int _engUzunKetmaKet = 0;
  DateTime _savolBoshlandi = DateTime.now();

  bool get _javobBerilgan => _natija != null;
  GameSavol get _savol => widget.boshlanish.savollar[_indeks];
  int get _jamiSavol => widget.boshlanish.savollar.length;

  @override
  void initState() {
    super.initState();
    _boshlandi = DateTime.now();
    _qolgan = _jamiVaqt;
    _savolBoshlandi = DateTime.now();
    _taymer = Timer.periodic(const Duration(milliseconds: 100), (t) {
      final qolgan = _jamiVaqt - DateTime.now().difference(_boshlandi);
      if (qolgan <= Duration.zero) {
        t.cancel();
        if (mounted) setState(() => _qolgan = Duration.zero);
        _yakunla();
        return;
      }
      if (mounted) setState(() => _qolgan = qolgan);
    });
  }

  @override
  void dispose() {
    _taymer?.cancel();
    super.dispose();
  }

  Future<void> _javobYubor(String tanlangan) async {
    if (_javobBerilgan || _yuborilmoqda || _yakunlanmoqda) return;

    final sarflangan = DateTime.now().difference(_savolBoshlandi).inMilliseconds;
    setState(() {
      _tanlangan = tanlangan;
      _yuborilmoqda = true;
    });

    try {
      final natija = await context.read<GameProvider>().javobYubor(
        oyin: widget.boshlanish,
        tartib: _savol.tartib,
        tanlangan: tanlangan,
        sarflanganMs: sarflangan,
      );

      if (!mounted) return;
      setState(() {
        _natija = natija;
        _yuborilmoqda = false;
        if (natija.togri) {
          _togri++;
          _ketmaKet++;
          _engUzunKetmaKet = _ketmaKet > _engUzunKetmaKet ? _ketmaKet : _engUzunKetmaKet;
        } else {
          _ketmaKet = 0;
        }
      });

      await Future<void>.delayed(_javobKutish);
      if (!mounted || _yakunlanmoqda) return;

      if (_indeks + 1 >= _jamiSavol) {
        // Savollar tugadi — vaqt qolgan bo'lsa ham o'yin yakunlanadi.
        await _yakunla();
      } else {
        setState(() {
          _indeks++;
          _tanlangan = null;
          _natija = null;
          _savolBoshlandi = DateTime.now();
        });
      }
    } catch (error) {
      if (!mounted) return;
      setState(() {
        _yuborilmoqda = false;
        _tanlangan = null;
      });
      ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text('$error')));
    }
  }

  Future<void> _yakunla() async {
    if (_yakunlanmoqda) return;
    _yakunlanmoqda = true;
    _taymer?.cancel();

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

  GameJavobHolati _holat(String variant) {
    if (!_javobBerilgan) {
      return _tanlangan == variant
          ? GameJavobHolati.tanlangan
          : GameJavobHolati.odatiy;
    }
    if (variant == _natija!.togriJavob) return GameJavobHolati.togri;
    if (variant == _tanlangan) return GameJavobHolati.xato;
    return GameJavobHolati.odatiy;
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
                    if (_ketmaKet >= 3)
                      GameStatChip(
                        ikonka: Icons.local_fire_department_rounded,
                        matn: '$_ketmaKet',
                        rang: tokens.warning,
                      ),
                  ],
                ),
              ),
              Padding(
                padding: const EdgeInsets.fromLTRB(20, 8, 20, 4),
                child: GameTimerBar(qolgan: _qolgan, jami: _jamiVaqt),
              ),
              Expanded(
                child: SingleChildScrollView(
                  padding: const EdgeInsets.symmetric(horizontal: 20, vertical: 16),
                  child: Column(
                    children: [
                      Text(
                        '$_togri',
                        style: GoogleFonts.inter(
                          fontSize: 40,
                          fontWeight: FontWeight.w900,
                          color: tokens.primary,
                          letterSpacing: -1.4,
                        ),
                      ).animate(key: ValueKey(_togri)).scaleXY(
                        begin: 1.2,
                        end: 1,
                        duration: 220.ms,
                        curve: Curves.easeOut,
                      ),
                      Text(
                        'to‘g‘ri javob',
                        style: GoogleFonts.inter(
                          fontSize: 11.5,
                          fontWeight: FontWeight.w600,
                          color: tokens.textDim,
                        ),
                      ),
                      const SizedBox(height: 16),
                      GameSavolKartasi(savol: _savol),
                    ],
                  ),
                ),
              ),
              Padding(
                padding: const EdgeInsets.fromLTRB(20, 0, 20, 12),
                child: Column(
                  children: [
                    for (final variant in _savol.variantlar)
                      GameAnswerCard(
                        matn: variant,
                        holat: _holat(variant),
                        onTap: () => _javobYubor(variant),
                      ),
                  ],
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }
}
