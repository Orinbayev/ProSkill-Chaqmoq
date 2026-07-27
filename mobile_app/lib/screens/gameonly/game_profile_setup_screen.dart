import 'package:chaqmoq_mobile/core/theme/student_tokens.dart';
import 'package:chaqmoq_mobile/providers/auth_provider.dart';
import 'package:chaqmoq_mobile/services/api_client.dart';
import 'package:chaqmoq_mobile/services/game_auth_service.dart';
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:google_fonts/google_fonts.dart';
import 'package:provider/provider.dart';

/// Ro'yxatdan o'tgandan keyingi oxirgi qadam: ism, familya, yosh.
///
/// Google faqat email va (ba'zan) ismni beradi — reyting va sovg'a topshirish
/// uchun to'liq ism va yosh kerak.
class GameProfileSetupScreen extends StatefulWidget {
  const GameProfileSetupScreen({super.key, required this.boshlangich});

  final GameOyinchiProfil boshlangich;

  @override
  State<GameProfileSetupScreen> createState() => _GameProfileSetupScreenState();
}

class _GameProfileSetupScreenState extends State<GameProfileSetupScreen> {
  late final TextEditingController _ism =
      TextEditingController(text: widget.boshlangich.ism);
  late final TextEditingController _familya =
      TextEditingController(text: widget.boshlangich.familya);
  late final TextEditingController _yosh =
      TextEditingController(text: widget.boshlangich.yosh?.toString() ?? '');

  bool _band = false;
  String? _xato;

  @override
  void dispose() {
    _ism.dispose();
    _familya.dispose();
    _yosh.dispose();
    super.dispose();
  }

  Future<void> _saqla() async {
    final ism = _ism.text.trim();
    final familya = _familya.text.trim();
    final yosh = int.tryParse(_yosh.text.trim()) ?? 0;

    // Xatoni serverga bormasdan shu yerda aytamiz — javob darhol bo'ladi.
    final mahalliy = ism.length < 2
        ? 'Ismingizni kiriting'
        : familya.length < 2
        ? 'Familyangizni kiriting'
        : (yosh < 5 || yosh > 100)
        ? 'Yoshingizni to‘g‘ri kiriting (5–100)'
        : null;

    if (mahalliy != null) {
      setState(() => _xato = mahalliy);
      return;
    }

    setState(() {
      _band = true;
      _xato = null;
    });

    try {
      await context.read<GameAuthService>().profilniToldir(
        ism: ism,
        familya: familya,
        yosh: yosh,
      );
      if (!mounted) return;
      // Profil to'ldi — sessiyani yangilaymiz va panel ochiladi.
      await context.read<AuthProvider>().refreshSession();
    } on ApiException catch (error) {
      if (mounted) setState(() => _xato = error.message);
    } catch (error) {
      if (mounted) setState(() => _xato = 'Saqlashda xatolik: $error');
    } finally {
      if (mounted) setState(() => _band = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    final tokens = StudentTokens.of(context);

    return Scaffold(
      backgroundColor: tokens.bg,
      body: SafeArea(
        child: ListView(
          padding: EdgeInsets.fromLTRB(
            24,
            32,
            24,
            24 + MediaQuery.viewInsetsOf(context).bottom,
          ),
          children: [
            Text(
              'Oz qoldi 👋',
              style: GoogleFonts.inter(
                fontSize: 26,
                fontWeight: FontWeight.w900,
                color: tokens.text,
                letterSpacing: -0.6,
              ),
            ),
            const SizedBox(height: 8),
            Text(
              'Reytingda va sovg‘a topshirishda kerak bo‘ladi.',
              style: GoogleFonts.inter(
                fontSize: 14,
                fontWeight: FontWeight.w500,
                color: tokens.textMuted,
                height: 1.5,
              ),
            ),
            const SizedBox(height: 28),

            _maydon(tokens, 'Ism', _ism, 'Masalan: Aziz'),
            const SizedBox(height: 14),
            _maydon(tokens, 'Familya', _familya, 'Masalan: Yusupov'),
            const SizedBox(height: 14),
            _maydon(
              tokens,
              'Yoshingiz',
              _yosh,
              'Masalan: 14',
              raqam: true,
            ),

            if (_xato != null) ...[
              const SizedBox(height: 14),
              Text(
                _xato!,
                style: GoogleFonts.inter(
                  fontSize: 13,
                  fontWeight: FontWeight.w600,
                  color: tokens.danger,
                ),
              ),
            ],

            const SizedBox(height: 26),
            SizedBox(
              width: double.infinity,
              child: FilledButton(
                onPressed: _band ? null : _saqla,
                style: FilledButton.styleFrom(
                  backgroundColor: tokens.primary,
                  foregroundColor: tokens.onPrimary,
                  padding: const EdgeInsets.symmetric(vertical: 16),
                  shape: RoundedRectangleBorder(
                    borderRadius: BorderRadius.circular(16),
                  ),
                ),
                child: Text(
                  _band ? 'Saqlanmoqda…' : 'Boshlash',
                  style: GoogleFonts.inter(
                    fontSize: 15,
                    fontWeight: FontWeight.w800,
                  ),
                ),
              ),
            ),
            const SizedBox(height: 12),
            Center(
              child: TextButton(
                onPressed: _band
                    ? null
                    : () => context.read<AuthProvider>().logout(),
                child: Text(
                  'Boshqa hisob bilan kirish',
                  style: GoogleFonts.inter(
                    fontSize: 13,
                    fontWeight: FontWeight.w700,
                    color: tokens.textMuted,
                  ),
                ),
              ),
            ),
          ],
        ),
      ),
    );
  }

  Widget _maydon(
    StudentTokens tokens,
    String yorliq,
    TextEditingController controller,
    String hint, {
    bool raqam = false,
  }) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Text(
          yorliq,
          style: GoogleFonts.inter(
            fontSize: 12.5,
            fontWeight: FontWeight.w700,
            color: tokens.textMuted,
          ),
        ),
        const SizedBox(height: 6),
        TextField(
          controller: controller,
          keyboardType: raqam ? TextInputType.number : TextInputType.name,
          inputFormatters: raqam
              ? [FilteringTextInputFormatter.digitsOnly, LengthLimitingTextInputFormatter(3)]
              : [LengthLimitingTextInputFormatter(60)],
          textCapitalization:
              raqam ? TextCapitalization.none : TextCapitalization.words,
          style: GoogleFonts.inter(
            fontSize: 15,
            fontWeight: FontWeight.w600,
            color: tokens.text,
          ),
          decoration: InputDecoration(
            hintText: hint,
            hintStyle: GoogleFonts.inter(fontSize: 14, color: tokens.textDim),
            filled: true,
            fillColor: tokens.cardBg,
            contentPadding:
                const EdgeInsets.symmetric(horizontal: 14, vertical: 14),
            border: OutlineInputBorder(
              borderRadius: BorderRadius.circular(14),
              borderSide: BorderSide(color: tokens.border),
            ),
            enabledBorder: OutlineInputBorder(
              borderRadius: BorderRadius.circular(14),
              borderSide: BorderSide(color: tokens.border),
            ),
            focusedBorder: OutlineInputBorder(
              borderRadius: BorderRadius.circular(14),
              borderSide: BorderSide(color: tokens.primary, width: 1.6),
            ),
          ),
        ),
      ],
    );
  }
}
