import 'dart:async';
import 'dart:math' as math;

import 'package:chaqmoq_mobile/core/theme/student_tokens.dart';
import 'package:chaqmoq_mobile/models/game_models.dart';
import 'package:chaqmoq_mobile/providers/game_provider.dart';
import 'package:flutter/material.dart';
import 'package:google_fonts/google_fonts.dart';
import 'package:provider/provider.dart';

/// Raqib qidirish ekrani.
///
/// Server bilan har 2 soniyada gaplashamiz (polling). Belgilangan vaqt ichida
/// jonli raqib topilmasa — robot bilan davom etamiz, ya'ni o'quvchi hech qachon
/// bo'sh qo'l bilan qolmaydi.
class GameMatchmakingScreen extends StatefulWidget {
  const GameMatchmakingScreen({
    super.key,
    required this.oyin,
    required this.navbat,
  });

  final GameOyin oyin;

  /// `tur: "kutish"` javobi — navbat id va kutish davomiyligi shu yerda.
  final GameBoshlanish navbat;

  @override
  State<GameMatchmakingScreen> createState() => _GameMatchmakingScreenState();
}

class _GameMatchmakingScreenState extends State<GameMatchmakingScreen>
    with SingleTickerProviderStateMixin {
  static const _sorovOraligi = Duration(seconds: 2);

  late final AnimationController _pulse = AnimationController(
    vsync: this,
    duration: const Duration(milliseconds: 1400),
  )..repeat();

  late final DateTime _boshlandi = DateTime.now();
  late int _qolgan = widget.navbat.kutishSoniya;

  Timer? _taymer;
  bool _tugadi = false;

  @override
  void initState() {
    super.initState();
    _taymer = Timer.periodic(_sorovOraligi, (_) => _tekshir());
    // Birinchi so'rovni kutmasdan yuboramiz — raqib allaqachon turgan bo'lishi
    // mumkin, o'shanda 2 soniya bekorga kutilmaydi.
    WidgetsBinding.instance.addPostFrameCallback((_) => _tekshir());
  }

  @override
  void dispose() {
    _taymer?.cancel();
    _pulse.dispose();
    super.dispose();
  }

  Future<void> _tekshir() async {
    if (_tugadi || !mounted) return;

    final otgan = DateTime.now().difference(_boshlandi).inSeconds;
    if (mounted) {
      setState(() => _qolgan = math.max(0, widget.navbat.kutishSoniya - otgan));
    }

    try {
      final holat = await context.read<GameProvider>().navbatHolati(
        widget.navbat.navbatId,
      );
      if (!mounted || _tugadi) return;

      if (holat.holat == 'topildi' && holat.oyin != null) {
        _yakunla(holat.oyin!);
        return;
      }
      if (holat.holat == 'vaqt_tugadi' || _qolgan <= 0) {
        await _robotgaOt();
      }
    } catch (_) {
      // Bitta so'rov uzilsa o'yin buzilmasin — keyingi urinishda davom etadi.
      if (_qolgan <= 0) await _robotgaOt();
    }
  }

  Future<void> _robotgaOt() async {
    if (_tugadi || !mounted) return;
    _tugadi = true;
    _taymer?.cancel();

    try {
      final oyin = await context.read<GameProvider>().navbatRobotga(
        widget.navbat.navbatId,
      );
      if (!mounted) return;
      _yakunla(oyin);
    } catch (error) {
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text('$error')));
      Navigator.of(context).pop();
    }
  }

  void _yakunla(GameBoshlanish oyin) {
    _tugadi = true;
    _taymer?.cancel();
    Navigator.of(context).pop(oyin);
  }

  Future<void> _bekorQil() async {
    if (_tugadi) return;
    _tugadi = true;
    _taymer?.cancel();

    final navigator = Navigator.of(context);
    try {
      await context.read<GameProvider>().navbatBekor(widget.navbat.navbatId);
    } catch (_) {
      // Bekor qilish serverga yetmasa ham ekranni yopamiz — navbat o'zi eskiradi.
    }
    if (mounted) navigator.pop();
  }

  @override
  Widget build(BuildContext context) {
    final tokens = StudentTokens.of(context);
    final rang = widget.oyin.rang(tokens.primary);

    return PopScope(
      canPop: false,
      onPopInvokedWithResult: (didPop, _) {
        if (!didPop) _bekorQil();
      },
      child: Scaffold(
        backgroundColor: tokens.bg,
        body: SafeArea(
          child: Column(
            children: [
              Align(
                alignment: Alignment.centerLeft,
                child: IconButton(
                  onPressed: _bekorQil,
                  icon: Icon(Icons.close_rounded, color: tokens.textMuted),
                  tooltip: 'Bekor qilish',
                ),
              ),
              const Spacer(),
              _radar(tokens, rang),
              const SizedBox(height: 32),
              Text(
                'Raqib qidirilmoqda…',
                style: GoogleFonts.inter(
                  fontSize: 21,
                  fontWeight: FontWeight.w900,
                  color: tokens.text,
                  letterSpacing: -0.4,
                ),
              ),
              const SizedBox(height: 8),
              Padding(
                padding: const EdgeInsets.symmetric(horizontal: 40),
                child: Text(
                  _qolgan > 0
                      ? '$_qolgan soniya ichida jonli raqib topilmasa, '
                            'robot bilan o‘ynaysiz.'
                      : 'Robot tayyorlanmoqda…',
                  textAlign: TextAlign.center,
                  style: GoogleFonts.inter(
                    fontSize: 13.5,
                    fontWeight: FontWeight.w500,
                    color: tokens.textMuted,
                    height: 1.5,
                  ),
                ),
              ),
              const Spacer(),
              Padding(
                padding: const EdgeInsets.fromLTRB(20, 0, 20, 20),
                child: Column(
                  children: [
                    SizedBox(
                      width: double.infinity,
                      child: OutlinedButton.icon(
                        onPressed: _tugadi ? null : _robotgaOt,
                        icon: const Icon(Icons.smart_toy_outlined, size: 19),
                        label: Text(
                          'Kutmayman — robot bilan o‘ynayman',
                          style: GoogleFonts.inter(fontWeight: FontWeight.w700),
                        ),
                        style: OutlinedButton.styleFrom(
                          foregroundColor: tokens.text,
                          side: BorderSide(color: tokens.border),
                          padding: const EdgeInsets.symmetric(vertical: 14),
                          shape: RoundedRectangleBorder(
                            borderRadius: BorderRadius.circular(16),
                          ),
                        ),
                      ),
                    ),
                    const SizedBox(height: 8),
                    Text(
                      'Jon faqat o‘yin boshlanganda sarflanadi',
                      style: GoogleFonts.inter(
                        fontSize: 11.5,
                        fontWeight: FontWeight.w600,
                        color: tokens.textDim,
                      ),
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

  /// Tarqalayotgan halqalar — kutish "tirik" ko'rinsin.
  Widget _radar(StudentTokens tokens, Color rang) {
    return SizedBox(
      width: 190,
      height: 190,
      child: AnimatedBuilder(
        animation: _pulse,
        builder: (context, child) {
          return Stack(
            alignment: Alignment.center,
            children: [
              for (var i = 0; i < 3; i++)
                _halqa(rang, (_pulse.value + i / 3) % 1.0),
              child!,
            ],
          );
        },
        child: Container(
          width: 82,
          height: 82,
          alignment: Alignment.center,
          decoration: BoxDecoration(
            color: tokens.tonedSurface(rang),
            shape: BoxShape.circle,
          ),
          child: Text(widget.oyin.ikonka, style: const TextStyle(fontSize: 34)),
        ),
      ),
    );
  }

  Widget _halqa(Color rang, double ulush) {
    final olcham = 82 + 108 * ulush;
    return Container(
      width: olcham,
      height: olcham,
      decoration: BoxDecoration(
        shape: BoxShape.circle,
        border: Border.all(
          color: rang.withValues(alpha: (1 - ulush) * 0.45),
          width: 2,
        ),
      ),
    );
  }
}
