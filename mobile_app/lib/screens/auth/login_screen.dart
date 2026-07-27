import 'package:chaqmoq_mobile/core/design/ds_colors.dart';
import 'package:chaqmoq_mobile/core/design/ds_tokens.dart';
import 'package:chaqmoq_mobile/models/app_models.dart';
import 'package:chaqmoq_mobile/providers/auth_provider.dart';
import 'package:chaqmoq_mobile/widgets/brand_logo.dart';
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:google_fonts/google_fonts.dart';
import 'package:provider/provider.dart';
import 'package:url_launcher/url_launcher.dart';

/// Login — premium ChaqmoqApp (Sky/Slate) + platform brand logo.
class LoginScreen extends StatefulWidget {
  const LoginScreen({super.key, this.onRoyxatdanOtish});

  /// «Hisobim yo'q» — markazsiz o'yinchi sifatida ro'yxatdan o'tish.
  final VoidCallback? onRoyxatdanOtish;

  @override
  State<LoginScreen> createState() => _LoginScreenState();
}

class _LoginScreenState extends State<LoginScreen> {
  final TextEditingController _identifierController = TextEditingController();
  final TextEditingController _passwordController = TextEditingController();

  String? _formErrorMessage;
  bool _obscurePassword = true;
  bool _rememberMe = true;
  int _bannerSequence = 0;

  @override
  void dispose() {
    _identifierController.dispose();
    _passwordController.dispose();
    super.dispose();
  }

  Future<void> _submit() async {
    final auth = context.read<AuthProvider>();
    if (auth.state == ViewState.loading) return;

    FocusScope.of(context).unfocus();
    _clearFeedback();

    final raw = _identifierController.text.trim();
    if (raw.isEmpty) {
      _setFormError('Email yoki telefon kiriting');
      return;
    }
    final password = _passwordController.text;
    if (password.trim().isEmpty) {
      _setFormError('Parol kiriting');
      return;
    }

    final mode = _detectMode(raw);
    final validationError = _validate(raw, mode);
    if (validationError != null) {
      _setFormError(validationError);
      return;
    }

    final identifier = _normalize(raw, mode);
    final success = await auth.login(
      login: mode == _CredentialKind.phone ? null : identifier,
      phoneNumber: mode == _CredentialKind.phone ? identifier : null,
      password: password,
    );
    if (!mounted || success) return;

    final inlineError = auth.inlineErrorMessage;
    if (inlineError != null && inlineError.isNotEmpty) {
      _setFormError(inlineError);
      return;
    }
    _showTopBanner(
      auth.bannerErrorMessage ?? 'Login yoki parol noto‘g‘ri',
      isError: true,
    );
  }

  _CredentialKind _detectMode(String value) {
    final compact = value.replaceAll(' ', '');
    if (compact.startsWith('+') ||
        RegExp(r'^[0-9()\-\s]+$').hasMatch(compact)) {
      return _CredentialKind.phone;
    }
    return _CredentialKind.emailOrLogin;
  }

  String? _validate(String value, _CredentialKind mode) {
    if (mode == _CredentialKind.phone) {
      final digits = _phoneDigits(value);
      if (digits.length != 9) {
        return 'Email yoki telefon raqam noto‘g‘ri';
      }
      return null;
    }
    if (value.contains('@') && !_isValidEmail(value)) {
      return 'Email yoki telefon raqam noto‘g‘ri';
    }
    if (!value.contains('@') && value.length < 3) {
      return 'Login kamida 3 belgidan iborat bo‘lsin';
    }
    return null;
  }

  String _normalize(String value, _CredentialKind mode) {
    if (mode != _CredentialKind.phone) return value.trim();
    final digits = _phoneDigits(value);
    return '+998$digits';
  }

  String _phoneDigits(String value) {
    final digits = value.replaceAll(RegExp(r'\D'), '');
    if (digits.startsWith('998') && digits.length == 12) {
      return digits.substring(3);
    }
    return digits;
  }

  bool _isValidEmail(String value) => RegExp(
        r'^[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}$',
        caseSensitive: false,
      ).hasMatch(value);

  void _setFormError(String message) {
    if (_formErrorMessage == message) return;
    setState(() => _formErrorMessage = message);
  }

  void _clearFeedback() {
    if (_formErrorMessage != null) {
      setState(() => _formErrorMessage = null);
    }
    context.read<AuthProvider>().clearError();
    final messenger = ScaffoldMessenger.of(context);
    messenger
      ..hideCurrentMaterialBanner()
      ..clearSnackBars();
  }

  Future<void> _openSupportTelegram() async {
    const username = 'de_amirxon';
    final candidates = <Uri>[
      Uri.parse('tg://resolve?domain=$username'),
      Uri.parse('https://t.me/$username'),
    ];
    for (final uri in candidates) {
      try {
        final ok = await launchUrl(uri, mode: LaunchMode.externalApplication);
        if (ok) return;
      } catch (_) {}
    }
    if (!mounted) return;
    _showTopBanner(
      'Telegram ochilmadi. Iltimos, @$username manzilini qo‘lda oching.',
      isError: true,
    );
  }

  void _showTopBanner(String message, {required bool isError}) {
    final messenger = ScaffoldMessenger.of(context);
    final ds = context.ds;

    final bg = isError ? ds.dangerBg : ds.primarySoft;
    final fg = isError ? ds.dangerFg : ds.primarySoftFg;
    final border = isError ? ds.danger.withValues(alpha: 0.35) : ds.border;
    final icon = isError ? Icons.error_outline_rounded : Icons.info_outline;
    final sequence = ++_bannerSequence;

    messenger
      ..hideCurrentMaterialBanner()
      ..clearSnackBars()
      ..showMaterialBanner(
        MaterialBanner(
          forceActionsBelow: false,
          overflowAlignment: OverflowBarAlignment.end,
          backgroundColor: bg,
          surfaceTintColor: Colors.transparent,
          dividerColor: border,
          padding: const EdgeInsets.fromLTRB(14, 10, 6, 10),
          leading: Icon(icon, color: fg, size: 20),
          content: Text(
            message,
            style: GoogleFonts.inter(
              fontSize: 13,
              height: 1.3,
              fontWeight: FontWeight.w600,
              color: fg,
            ),
          ),
          actions: [
            IconButton(
              onPressed: messenger.hideCurrentMaterialBanner,
              splashRadius: 18,
              visualDensity: VisualDensity.compact,
              icon: Icon(Icons.close_rounded, color: fg, size: 18),
            ),
          ],
        ),
      );

    Future<void>.delayed(const Duration(seconds: 4), () {
      if (!mounted || sequence != _bannerSequence) return;
      messenger.hideCurrentMaterialBanner();
    });
  }

  @override
  Widget build(BuildContext context) {
    final ds = context.ds;
    final isDark = ds.isDark;
    final auth = context.watch<AuthProvider>();
    final isLoading = auth.state == ViewState.loading;
    final bottomInset = MediaQuery.viewInsetsOf(context).bottom;

    return AnnotatedRegion<SystemUiOverlayStyle>(
      value: SystemUiOverlayStyle(
        statusBarColor: Colors.transparent,
        statusBarIconBrightness: isDark ? Brightness.light : Brightness.dark,
        statusBarBrightness: isDark ? Brightness.dark : Brightness.light,
        systemNavigationBarColor: ds.bg,
        systemNavigationBarIconBrightness:
            isDark ? Brightness.light : Brightness.dark,
      ),
      child: Scaffold(
        backgroundColor: ds.bg,
        resizeToAvoidBottomInset: true,
        body: Stack(
          children: [
            // Soft brand atmosphere
            Positioned(
              top: -80,
              left: -40,
              right: -40,
              child: Container(
                height: 320,
                decoration: BoxDecoration(
                  gradient: RadialGradient(
                    center: const Alignment(0, -0.2),
                    radius: 0.95,
                    colors: [
                      ds.primary.withValues(alpha: isDark ? 0.22 : 0.16),
                      ds.bg.withValues(alpha: 0),
                    ],
                  ),
                ),
              ),
            ),
            SafeArea(
              child: SingleChildScrollView(
                keyboardDismissBehavior:
                    ScrollViewKeyboardDismissBehavior.onDrag,
                padding: EdgeInsets.fromLTRB(20, 12, 20, 24 + bottomInset * 0.1),
                physics: const BouncingScrollPhysics(),
                child: Center(
                  child: ConstrainedBox(
                    constraints: const BoxConstraints(maxWidth: 440),
                    child: AutofillGroup(
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.stretch,
                        children: [
                          const SizedBox(height: 20),
                          const _LoginBrandHeader(),
                          const SizedBox(height: 28),
                          Container(
                            padding: const EdgeInsets.fromLTRB(18, 20, 18, 18),
                            decoration: BoxDecoration(
                              color: ds.card,
                              borderRadius: DsRadius.all(DsRadius.xl),
                              border: Border.all(color: ds.border),
                              boxShadow: DsShadow.card(isDark),
                            ),
                            child: Column(
                              crossAxisAlignment: CrossAxisAlignment.stretch,
                              children: [
                                Text(
                                  'Hisobingizga kiring',
                                  style: GoogleFonts.inter(
                                    fontSize: 18,
                                    fontWeight: FontWeight.w800,
                                    letterSpacing: -0.3,
                                    color: ds.textPrimary,
                                  ),
                                ),
                                const SizedBox(height: 4),
                                Text(
                                  'Email, login yoki telefon raqam bilan',
                                  style: GoogleFonts.inter(
                                    fontSize: 13,
                                    fontWeight: FontWeight.w500,
                                    color: ds.textMuted,
                                  ),
                                ),
                                const SizedBox(height: 18),
                                _AppTextField(
                                  controller: _identifierController,
                                  label: 'Login',
                                  hintText: 'Email yoki +998 90 123 45 67',
                                  icon: Icons.alternate_email_rounded,
                                  enabled: !isLoading,
                                  keyboardType: TextInputType.emailAddress,
                                  textInputAction: TextInputAction.next,
                                  autofillHints: const [
                                    AutofillHints.username,
                                    AutofillHints.email,
                                    AutofillHints.telephoneNumber,
                                  ],
                                  onChanged: (_) => _clearFeedback(),
                                ),
                                const SizedBox(height: 14),
                                _PasswordTextField(
                                  controller: _passwordController,
                                  enabled: !isLoading,
                                  obscure: _obscurePassword,
                                  onToggleObscure: () => setState(
                                    () => _obscurePassword = !_obscurePassword,
                                  ),
                                  onSubmitted: (_) {
                                    if (!isLoading) _submit();
                                  },
                                  onChanged: (_) => _clearFeedback(),
                                ),
                                if (_formErrorMessage != null) ...[
                                  const SizedBox(height: 12),
                                  _ErrorMessage(message: _formErrorMessage!),
                                ],
                                const SizedBox(height: 14),
                                _RememberForgotRow(
                                  rememberMe: _rememberMe,
                                  enabled: !isLoading,
                                  onToggleRemember: () => setState(
                                    () => _rememberMe = !_rememberMe,
                                  ),
                                  onForgotPassword: _openSupportTelegram,
                                ),
                                const SizedBox(height: 18),
                                _PrimaryButton(
                                  text: 'Kirish',
                                  isLoading: isLoading,
                                  onPressed: _submit,
                                ),
                                if (widget.onRoyxatdanOtish != null) ...[
                                  const SizedBox(height: 6),
                                  TextButton(
                                    onPressed: isLoading
                                        ? null
                                        : widget.onRoyxatdanOtish,
                                    child: const Text(
                                      'Hisobim yo‘q — o‘yin uchun ro‘yxatdan o‘tish',
                                      textAlign: TextAlign.center,
                                    ),
                                  ),
                                ],
                              ],
                            ),
                          ),
                          const SizedBox(height: 16),
                          const _SecurityInfoCard(),
                          const SizedBox(height: 20),
                          Text(
                            '© ChaqmoqApp · Ta’lim markazlari uchun',
                            textAlign: TextAlign.center,
                            style: GoogleFonts.inter(
                              fontSize: 11.5,
                              fontWeight: FontWeight.w500,
                              color: ds.textFaint,
                            ),
                          ),
                        ],
                      ),
                    ),
                  ),
                ),
              ),
            ),
          ],
        ),
      ),
    );
  }
}

enum _CredentialKind { emailOrLogin, phone }

// ─── Brand header (platform logo) ───────────────────────────────────────────

class _LoginBrandHeader extends StatelessWidget {
  const _LoginBrandHeader();

  @override
  Widget build(BuildContext context) {
    final ds = context.ds;
    return Column(
      children: [
        const BrandLogoHero(size: 108),
        const SizedBox(height: 18),
        RichText(
          textAlign: TextAlign.center,
          text: TextSpan(
            style: GoogleFonts.inter(
              fontSize: 28,
              height: 1.05,
              fontWeight: FontWeight.w800,
              letterSpacing: -0.6,
              color: ds.textPrimary,
            ),
            children: [
              const TextSpan(text: 'Chaqmoq'),
              TextSpan(
                text: 'App',
                style: GoogleFonts.inter(
                  fontSize: 28,
                  height: 1.05,
                  fontWeight: FontWeight.w800,
                  letterSpacing: -0.6,
                  color: ds.primary,
                ),
              ),
            ],
          ),
        ),
        const SizedBox(height: 8),
        Text(
          'Ta’lim markazi boshqaruvi va ota-ona\nbilan ishonchli bog‘lanish',
          textAlign: TextAlign.center,
          style: GoogleFonts.inter(
            fontSize: 13.5,
            height: 1.45,
            fontWeight: FontWeight.w500,
            color: ds.textMuted,
          ),
        ),
      ],
    );
  }
}

// ─── Fields ─────────────────────────────────────────────────────────────────

class _AppTextField extends StatelessWidget {
  const _AppTextField({
    required this.controller,
    required this.label,
    required this.hintText,
    required this.icon,
    this.enabled = true,
    this.keyboardType,
    this.textInputAction,
    this.autofillHints,
    this.onChanged,
    this.suffix,
    this.obscureText = false,
    this.onSubmitted,
  });

  final TextEditingController controller;
  final String label;
  final String hintText;
  final IconData icon;
  final bool enabled;
  final TextInputType? keyboardType;
  final TextInputAction? textInputAction;
  final Iterable<String>? autofillHints;
  final ValueChanged<String>? onChanged;
  final Widget? suffix;
  final bool obscureText;
  final ValueChanged<String>? onSubmitted;

  @override
  Widget build(BuildContext context) {
    final ds = context.ds;
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Padding(
          padding: const EdgeInsets.only(left: 4, bottom: 8),
          child: Text(
            label,
            style: GoogleFonts.inter(
              fontSize: 13,
              fontWeight: FontWeight.w700,
              color: ds.textPrimary,
            ),
          ),
        ),
        SizedBox(
          height: 54,
          child: TextField(
            controller: controller,
            enabled: enabled,
            keyboardType: keyboardType,
            textInputAction: textInputAction,
            obscureText: obscureText,
            onChanged: onChanged,
            onSubmitted: onSubmitted,
            autofillHints: autofillHints,
            enableSuggestions: !obscureText,
            autocorrect: false,
            cursorColor: ds.primary,
            style: GoogleFonts.inter(
              fontSize: 14.5,
              fontWeight: FontWeight.w500,
              color: ds.textPrimary,
            ),
            decoration: InputDecoration(
              hintText: hintText,
              hintStyle: GoogleFonts.inter(
                fontSize: 14,
                fontWeight: FontWeight.w500,
                color: ds.textFaint,
              ),
              filled: true,
              fillColor: enabled ? ds.cardAlt : ds.cardAlt.withValues(alpha: 0.6),
              prefixIcon: Padding(
                padding: const EdgeInsets.only(left: 14, right: 6),
                child: Icon(icon, color: ds.textMuted, size: 20),
              ),
              prefixIconConstraints: const BoxConstraints(minWidth: 44),
              suffixIcon: suffix,
              suffixIconConstraints: const BoxConstraints(minWidth: 48),
              contentPadding: const EdgeInsets.symmetric(
                horizontal: 14,
                vertical: 12,
              ),
              border: _border(ds.border),
              enabledBorder: _border(ds.border),
              disabledBorder: _border(ds.border.withValues(alpha: 0.6)),
              focusedBorder: _border(ds.primary, width: 1.5),
            ),
          ),
        ),
      ],
    );
  }

  OutlineInputBorder _border(Color color, {double width = 1}) {
    return OutlineInputBorder(
      borderRadius: BorderRadius.circular(14),
      borderSide: BorderSide(color: color, width: width),
    );
  }
}

class _PasswordTextField extends StatelessWidget {
  const _PasswordTextField({
    required this.controller,
    required this.enabled,
    required this.obscure,
    required this.onToggleObscure,
    required this.onSubmitted,
    required this.onChanged,
  });

  final TextEditingController controller;
  final bool enabled;
  final bool obscure;
  final VoidCallback onToggleObscure;
  final ValueChanged<String> onSubmitted;
  final ValueChanged<String> onChanged;

  @override
  Widget build(BuildContext context) {
    final ds = context.ds;
    return _AppTextField(
      controller: controller,
      label: 'Parol',
      hintText: '••••••••',
      icon: Icons.lock_outline_rounded,
      enabled: enabled,
      keyboardType: TextInputType.visiblePassword,
      textInputAction: TextInputAction.done,
      autofillHints: const [AutofillHints.password],
      obscureText: obscure,
      onChanged: onChanged,
      onSubmitted: onSubmitted,
      suffix: IconButton(
        onPressed: enabled ? onToggleObscure : null,
        splashRadius: 20,
        icon: Icon(
          obscure ? Icons.visibility_off_outlined : Icons.visibility_outlined,
          color: ds.textMuted,
          size: 22,
        ),
      ),
    );
  }
}

class _RememberForgotRow extends StatelessWidget {
  const _RememberForgotRow({
    required this.rememberMe,
    required this.enabled,
    required this.onToggleRemember,
    required this.onForgotPassword,
  });

  final bool rememberMe;
  final bool enabled;
  final VoidCallback onToggleRemember;
  final VoidCallback onForgotPassword;

  @override
  Widget build(BuildContext context) {
    final ds = context.ds;
    return Row(
      children: [
        Expanded(
          child: InkWell(
            onTap: enabled ? onToggleRemember : null,
            borderRadius: BorderRadius.circular(8),
            child: Padding(
              padding: const EdgeInsets.symmetric(vertical: 6),
              child: Row(
                mainAxisSize: MainAxisSize.min,
                children: [
                  AnimatedContainer(
                    duration: const Duration(milliseconds: 160),
                    width: 20,
                    height: 20,
                    decoration: BoxDecoration(
                      color: rememberMe ? ds.primary : ds.card,
                      borderRadius: BorderRadius.circular(6),
                      border: Border.all(
                        color: rememberMe ? ds.primary : ds.border,
                        width: 1.4,
                      ),
                    ),
                    child: rememberMe
                        ? Icon(
                            Icons.check_rounded,
                            color: ds.primaryFg,
                            size: 16,
                          )
                        : null,
                  ),
                  const SizedBox(width: 10),
                  Flexible(
                    child: Text(
                      'Eslab qolish',
                      maxLines: 1,
                      overflow: TextOverflow.ellipsis,
                      style: GoogleFonts.inter(
                        fontSize: 13,
                        fontWeight: FontWeight.w600,
                        color: ds.textPrimary,
                      ),
                    ),
                  ),
                ],
              ),
            ),
          ),
        ),
        const SizedBox(width: 8),
        TextButton(
          onPressed: enabled ? onForgotPassword : null,
          style: TextButton.styleFrom(
            foregroundColor: ds.primary,
            padding: EdgeInsets.zero,
            minimumSize: const Size(0, 32),
            tapTargetSize: MaterialTapTargetSize.shrinkWrap,
          ),
          child: Text(
            'Parolni unutdingizmi?',
            maxLines: 1,
            overflow: TextOverflow.ellipsis,
            style: GoogleFonts.inter(
              fontSize: 13,
              fontWeight: FontWeight.w700,
              color: ds.primary,
            ),
          ),
        ),
      ],
    );
  }
}

class _PrimaryButton extends StatelessWidget {
  const _PrimaryButton({
    required this.text,
    required this.onPressed,
    required this.isLoading,
  });

  final String text;
  final VoidCallback onPressed;
  final bool isLoading;

  @override
  Widget build(BuildContext context) {
    final ds = context.ds;
    return SizedBox(
      width: double.infinity,
      height: 54,
      child: DecoratedBox(
        decoration: BoxDecoration(
          gradient: LinearGradient(
            begin: Alignment.centerLeft,
            end: Alignment.centerRight,
            colors: ds.primaryGradient,
          ),
          borderRadius: BorderRadius.circular(14),
          boxShadow: DsShadow.primaryGlow(ds.primary),
        ),
        child: ElevatedButton(
          onPressed: isLoading ? null : onPressed,
          style: ElevatedButton.styleFrom(
            elevation: 0,
            shadowColor: Colors.transparent,
            backgroundColor: Colors.transparent,
            disabledBackgroundColor: Colors.transparent,
            foregroundColor: Colors.white,
            disabledForegroundColor: Colors.white,
            shape: RoundedRectangleBorder(
              borderRadius: BorderRadius.circular(14),
            ),
          ),
          child: isLoading
              ? Row(
                  mainAxisAlignment: MainAxisAlignment.center,
                  children: [
                    const SizedBox(
                      width: 20,
                      height: 20,
                      child: CircularProgressIndicator(
                        strokeWidth: 2.4,
                        color: Colors.white,
                      ),
                    ),
                    const SizedBox(width: 12),
                    Text(
                      'Tekshirilmoqda...',
                      style: GoogleFonts.inter(
                        fontSize: 14.5,
                        fontWeight: FontWeight.w700,
                        color: Colors.white,
                        letterSpacing: 0.2,
                      ),
                    ),
                  ],
                )
              : Text(
                  text,
                  style: GoogleFonts.inter(
                    fontSize: 15.5,
                    fontWeight: FontWeight.w700,
                    color: Colors.white,
                    letterSpacing: 0.2,
                  ),
                ),
        ),
      ),
    );
  }
}

class _SecurityInfoCard extends StatelessWidget {
  const _SecurityInfoCard();

  @override
  Widget build(BuildContext context) {
    final ds = context.ds;
    return Container(
      padding: const EdgeInsets.fromLTRB(14, 12, 14, 12),
      decoration: BoxDecoration(
        color: ds.successBg,
        borderRadius: BorderRadius.circular(14),
        border: Border.all(color: ds.success.withValues(alpha: 0.28)),
      ),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Container(
            width: 32,
            height: 32,
            alignment: Alignment.center,
            decoration: BoxDecoration(
              color: ds.success.withValues(alpha: 0.15),
              borderRadius: BorderRadius.circular(10),
            ),
            child: Icon(Icons.shield_rounded, color: ds.successFg, size: 18),
          ),
          const SizedBox(width: 12),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  'Xavfsiz ulanish',
                  style: GoogleFonts.inter(
                    fontSize: 13,
                    fontWeight: FontWeight.w700,
                    color: ds.successFg,
                  ),
                ),
                const SizedBox(height: 2),
                Text(
                  'Ma’lumotlaringiz shifrlangan kanal orqali uzatiladi',
                  style: GoogleFonts.inter(
                    fontSize: 12,
                    height: 1.35,
                    fontWeight: FontWeight.w500,
                    color: ds.successFg.withValues(alpha: 0.85),
                  ),
                ),
              ],
            ),
          ),
        ],
      ),
    );
  }
}

class _ErrorMessage extends StatelessWidget {
  const _ErrorMessage({required this.message});

  final String message;

  @override
  Widget build(BuildContext context) {
    final ds = context.ds;
    return Container(
      width: double.infinity,
      padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 10),
      decoration: BoxDecoration(
        color: ds.dangerBg,
        borderRadius: BorderRadius.circular(12),
        border: Border.all(color: ds.danger.withValues(alpha: 0.3)),
      ),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Padding(
            padding: const EdgeInsets.only(top: 1),
            child: Icon(
              Icons.error_outline_rounded,
              size: 16,
              color: ds.dangerFg,
            ),
          ),
          const SizedBox(width: 8),
          Expanded(
            child: Text(
              message,
              style: GoogleFonts.inter(
                fontSize: 12.5,
                height: 1.3,
                fontWeight: FontWeight.w600,
                color: ds.dangerFg,
              ),
            ),
          ),
        ],
      ),
    );
  }
}
