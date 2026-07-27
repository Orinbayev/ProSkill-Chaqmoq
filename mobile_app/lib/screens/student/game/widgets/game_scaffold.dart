import 'package:chaqmoq_mobile/core/theme/student_tokens.dart';
import 'package:chaqmoq_mobile/services/api_client.dart';
import 'package:chaqmoq_mobile/widgets/app_state_widgets.dart';
import 'package:flutter/material.dart';
import 'package:google_fonts/google_fonts.dart';

/// O'yin bo'limidagi ichki ekranlar (reyting, do'kon, tarix, yangiliklar)
/// uchun umumiy qobiq: sarlavha, birinchi yuklash, xatolik va tortib-yangilash.
///
/// Har ekran shu bir xil holat mantiqini takrorlamasin degan maqsadda ajratilgan.
class GameScaffold extends StatefulWidget {
  const GameScaffold({
    super.key,
    required this.sarlavha,
    required this.yuklash,
    required this.qurilish,
    this.harakat,
    this.orqagaTugma = true,
  });

  final String sarlavha;
  final Future<void> Function() yuklash;
  final WidgetBuilder qurilish;
  final Widget? harakat;

  /// Tab sifatida ochilganda orqaga tugmasi ko'rsatilmaydi.
  final bool orqagaTugma;

  @override
  State<GameScaffold> createState() => _GameScaffoldState();
}

class _GameScaffoldState extends State<GameScaffold> {
  bool _yuklanmoqda = true;
  String? _xato;

  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addPostFrameCallback((_) => _yukla());
  }

  Future<void> _yukla() async {
    if (mounted) setState(() => _xato = null);
    try {
      await widget.yuklash();
      if (!mounted) return;
      setState(() => _yuklanmoqda = false);
    } catch (error) {
      if (!mounted) return;
      setState(() {
        _yuklanmoqda = false;
        _xato = error is ApiException ? error.message : 'Ma’lumot yuklanmadi';
      });
    }
  }

  @override
  Widget build(BuildContext context) {
    final tokens = StudentTokens.of(context);

    return Scaffold(
      backgroundColor: tokens.bg,
      appBar: AppBar(
        backgroundColor: tokens.bg,
        surfaceTintColor: Colors.transparent,
        elevation: 0,
        centerTitle: false,
        automaticallyImplyLeading: widget.orqagaTugma,
        iconTheme: IconThemeData(color: tokens.text),
        title: Text(
          widget.sarlavha,
          style: GoogleFonts.inter(
            fontSize: 17,
            fontWeight: FontWeight.w900,
            color: tokens.text,
            letterSpacing: -0.3,
          ),
        ),
        actions: [if (widget.harakat != null) widget.harakat!],
      ),
      body: _tanla(tokens),
    );
  }

  Widget _tanla(StudentTokens tokens) {
    if (_yuklanmoqda) {
      return AppLoadingState(dark: tokens.isDark);
    }
    if (_xato != null) {
      return AppErrorState(
        message: _xato!,
        dark: tokens.isDark,
        onRetry: () {
          setState(() => _yuklanmoqda = true);
          _yukla();
        },
      );
    }
    return RefreshIndicator(
      color: tokens.primary,
      onRefresh: _yukla,
      child: widget.qurilish(context),
    );
  }
}
