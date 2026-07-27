import 'package:chaqmoq_mobile/core/theme/student_tokens.dart';
import 'package:chaqmoq_mobile/providers/auth_provider.dart';
import 'package:chaqmoq_mobile/services/api_client.dart';
import 'package:chaqmoq_mobile/services/game_auth_service.dart';
import 'package:flutter/material.dart';
import 'package:google_fonts/google_fonts.dart';
import 'package:provider/provider.dart';

/// «Profilingiz yo'q» ekrani — Google bilan ro'yxatdan o'tish.
///
/// Bu ekran o'quv markazi o'quvchilari uchun emas: ular odatdagi login
/// oynasidan kiradi. Bu yerda ilovani o'zi o'rnatganlar hisob ochadi va
/// faqat O'yin bo'limidan foydalanadi.
class GameRegisterScreen extends StatefulWidget {
  const GameRegisterScreen({super.key, this.onLoginBosildi});

  /// «Markazda o'qiyman» tugmasi — odatdagi login oynasiga qaytadi.
  final VoidCallback? onLoginBosildi;

  @override
  State<GameRegisterScreen> createState() => _GameRegisterScreenState();
}

class _GameRegisterScreenState extends State<GameRegisterScreen> {
  bool _band = false;
  String? _xato;

  Future<void> _googleBilan() async {
    final auth = context.read<AuthProvider>();
    setState(() {
      _band = true;
      _xato = null;
    });

    try {
      final natija = await context.read<GameAuthService>().googleBilanKirish();
      if (natija == null) {
        // Foydalanuvchi Google oynasini yopdi — xato emas.
        if (mounted) setState(() => _band = false);
        return;
      }
      await auth.applyGameToken(natija.accessToken);
    } on ApiException catch (error) {
      if (mounted) setState(() => _xato = error.message);
    } catch (error) {
      if (mounted) {
        setState(() => _xato = 'Kirishda xatolik: $error');
      }
    } finally {
      if (mounted) setState(() => _band = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    final tokens = StudentTokens.of(context);
    final googleBor = GameAuthService.mavjud;

    return Scaffold(
      backgroundColor: tokens.bg,
      body: SafeArea(
        child: Padding(
          padding: const EdgeInsets.symmetric(horizontal: 24),
          child: Column(
            children: [
              const Spacer(flex: 2),
              Container(
                width: 96,
                height: 96,
                alignment: Alignment.center,
                decoration: BoxDecoration(
                  color: tokens.tonedSurface(tokens.primary),
                  borderRadius: BorderRadius.circular(28),
                ),
                child: const Text('⚡', style: TextStyle(fontSize: 46)),
              ),
              const SizedBox(height: 22),
              Text(
                'Chaqmoq Game',
                style: GoogleFonts.inter(
                  fontSize: 27,
                  fontWeight: FontWeight.w900,
                  color: tokens.text,
                  letterSpacing: -0.7,
                ),
              ),
              const SizedBox(height: 10),
              Text(
                'Profilingiz yo‘q. Ro‘yxatdan o‘ting va o‘ynab chaqmoq yig‘ing — '
                'to‘plagan chaqmog‘ingizga do‘kondan sovg‘a olasiz.',
                textAlign: TextAlign.center,
                style: GoogleFonts.inter(
                  fontSize: 14,
                  fontWeight: FontWeight.w500,
                  color: tokens.textMuted,
                  height: 1.55,
                ),
              ),
              const SizedBox(height: 26),
              _afzalliklar(tokens),
              const Spacer(flex: 3),

              if (_xato != null) ...[
                Container(
                  width: double.infinity,
                  padding: const EdgeInsets.all(12),
                  decoration: BoxDecoration(
                    color: tokens.tonedSurface(tokens.danger),
                    borderRadius: BorderRadius.circular(14),
                  ),
                  child: Text(
                    _xato!,
                    textAlign: TextAlign.center,
                    style: GoogleFonts.inter(
                      fontSize: 12.5,
                      fontWeight: FontWeight.w600,
                      color: tokens.danger,
                    ),
                  ),
                ),
                const SizedBox(height: 12),
              ],

              if (googleBor)
                SizedBox(
                  width: double.infinity,
                  child: FilledButton.icon(
                    onPressed: _band ? null : _googleBilan,
                    icon: _band
                        ? const SizedBox(
                            width: 17,
                            height: 17,
                            child: CircularProgressIndicator(strokeWidth: 2),
                          )
                        : const Icon(Icons.g_mobiledata_rounded, size: 26),
                    label: Text(
                      _band ? 'Kirilmoqda…' : 'Google bilan ro‘yxatdan o‘tish',
                      style: GoogleFonts.inter(
                        fontSize: 15,
                        fontWeight: FontWeight.w800,
                      ),
                    ),
                    style: FilledButton.styleFrom(
                      backgroundColor: tokens.primary,
                      foregroundColor: tokens.onPrimary,
                      padding: const EdgeInsets.symmetric(vertical: 16),
                      shape: RoundedRectangleBorder(
                        borderRadius: BorderRadius.circular(16),
                      ),
                    ),
                  ),
                )
              else
                Container(
                  width: double.infinity,
                  padding: const EdgeInsets.all(14),
                  decoration: BoxDecoration(
                    color: tokens.tonedSurface(tokens.warning),
                    borderRadius: BorderRadius.circular(16),
                  ),
                  child: Text(
                    'Google orqali ro‘yxatdan o‘tish hozircha sozlanmagan. '
                    'Iltimos, keyinroq urinib ko‘ring.',
                    textAlign: TextAlign.center,
                    style: GoogleFonts.inter(
                      fontSize: 12.5,
                      fontWeight: FontWeight.w600,
                      color: tokens.warning,
                      height: 1.45,
                    ),
                  ),
                ),

              const SizedBox(height: 12),
              TextButton(
                onPressed: widget.onLoginBosildi,
                child: Text(
                  'O‘quv markazida o‘qiyman — hisobim bor',
                  style: GoogleFonts.inter(
                    fontSize: 13.5,
                    fontWeight: FontWeight.w700,
                    color: tokens.primary,
                  ),
                ),
              ),
              const SizedBox(height: 10),
            ],
          ),
        ),
      ),
    );
  }

  Widget _afzalliklar(StudentTokens tokens) {
    const qatorlar = [
      (Icons.sports_esports_rounded, 'Har kuni yangi o‘yinlar'),
      (Icons.bolt_rounded, 'Chaqmoq yig‘ing va sovg‘a oling'),
      (Icons.leaderboard_rounded, 'Reytingda yuqoriga chiqing'),
    ];

    return Column(
      children: [
        for (final (ikonka, matn) in qatorlar)
          Padding(
            padding: const EdgeInsets.only(bottom: 10),
            child: Row(
              children: [
                Container(
                  width: 34,
                  height: 34,
                  alignment: Alignment.center,
                  decoration: BoxDecoration(
                    color: tokens.tonedSurface(tokens.primary),
                    borderRadius: BorderRadius.circular(11),
                  ),
                  child: Icon(ikonka, size: 17, color: tokens.primary),
                ),
                const SizedBox(width: 12),
                Expanded(
                  child: Text(
                    matn,
                    style: GoogleFonts.inter(
                      fontSize: 13.5,
                      fontWeight: FontWeight.w600,
                      color: tokens.text,
                    ),
                  ),
                ),
              ],
            ),
          ),
      ],
    );
  }
}
