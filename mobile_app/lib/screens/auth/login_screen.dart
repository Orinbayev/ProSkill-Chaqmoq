import 'package:chaqmoq_mobile/models/app_models.dart';
import 'package:chaqmoq_mobile/providers/auth_provider.dart';
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:google_fonts/google_fonts.dart';
import 'package:provider/provider.dart';
import 'package:url_launcher/url_launcher.dart';

/// Login screen — premium iPhone-styled card layout.
/// Single auto-detecting identifier field (email / login / +998 phone).
class LoginScreen extends StatefulWidget {
  const LoginScreen({super.key});

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

  // ---------- submit ----------

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

  // ---------- mode / validation / normalisation ----------

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

  // ---------- feedback / banners ----------

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
      } catch (_) {
        // try next candidate
      }
    }
    if (!mounted) return;
    _showTopBanner(
      'Telegram ochilmadi. Iltimos, @$username manzilini qo‘lda oching.',
      isError: true,
    );
  }

  void _showTopBanner(String message, {required bool isError}) {
    final messenger = ScaffoldMessenger.of(context);
    final palette = _LoginPalette.of(context);

    final bg = isError ? palette.dangerSoft : palette.infoSoft;
    final fg = isError ? palette.dangerText : palette.infoText;
    final border = isError ? palette.dangerBorder : palette.infoBorder;
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

  // ---------- build ----------

  @override
  Widget build(BuildContext context) {
    final palette = _LoginPalette.of(context);
    final isDark = Theme.of(context).brightness == Brightness.dark;
    final auth = context.watch<AuthProvider>();
    final isLoading = auth.state == ViewState.loading;

    return AnnotatedRegion<SystemUiOverlayStyle>(
      value: SystemUiOverlayStyle(
        statusBarColor: Colors.transparent,
        statusBarIconBrightness: isDark ? Brightness.light : Brightness.dark,
        statusBarBrightness: isDark ? Brightness.dark : Brightness.light,
        systemNavigationBarColor: palette.bg,
        systemNavigationBarIconBrightness: isDark
            ? Brightness.light
            : Brightness.dark,
      ),
      child: Scaffold(
        backgroundColor: palette.bg,
        resizeToAvoidBottomInset: true,
        body: SafeArea(
          child: SingleChildScrollView(
            keyboardDismissBehavior: ScrollViewKeyboardDismissBehavior.onDrag,
            padding: const EdgeInsets.fromLTRB(22, 0, 22, 28),
            physics: const BouncingScrollPhysics(),
            child: Center(
              child: ConstrainedBox(
                constraints: const BoxConstraints(maxWidth: 440),
                child: AutofillGroup(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.stretch,
                    children: [
                      const SizedBox(height: 24),
                      const _LoginLogoHeader(),
                      const SizedBox(height: 26),
                      _AppTextField(
                        controller: _identifierController,
                        label: 'Email yoki telefon',
                        hintText: 'misol@chaqmoq.uz yoki +998 90 123 45 67',
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
                        onToggleRemember: () =>
                            setState(() => _rememberMe = !_rememberMe),
                        onForgotPassword: _openSupportTelegram,
                      ),
                      const SizedBox(height: 20),
                      _PrimaryButton(
                        text: 'Kirish',
                        isLoading: isLoading,
                        onPressed: _submit,
                      ),
                      const SizedBox(height: 18),
                      const _SecurityInfoCard(),
                      const SizedBox(height: 8),
                    ],
                  ),
                ),
              ),
            ),
          ),
        ),
      ),
    );
  }
}

enum _CredentialKind { emailOrLogin, phone }

// ============================================================================
// Sub-components
// ============================================================================

class _LoginLogoHeader extends StatelessWidget {
  const _LoginLogoHeader();

  @override
  Widget build(BuildContext context) {
    final palette = _LoginPalette.of(context);
    return Column(
      children: [
        Container(
          width: 96,
          height: 96,
          decoration: BoxDecoration(
            color: palette.surface,
            borderRadius: BorderRadius.circular(26),
            border: Border.all(color: palette.border),
            boxShadow: [
              BoxShadow(
                color: palette.shadow,
                blurRadius: 26,
                offset: const Offset(0, 12),
              ),
            ],
          ),
          alignment: Alignment.center,
          child: Padding(
            padding: const EdgeInsets.all(14),
            child: Image.asset(
              'assets/images/login_logo.png',
              fit: BoxFit.contain,
              errorBuilder: (_, _, _) =>
                  Icon(Icons.bolt_rounded, color: palette.primary, size: 48),
            ),
          ),
        ),
        const SizedBox(height: 18),
        RichText(
          textAlign: TextAlign.center,
          text: TextSpan(
            style: GoogleFonts.inter(
              fontSize: 26,
              height: 1.1,
              fontWeight: FontWeight.w800,
              letterSpacing: -0.4,
              color: palette.textDark,
            ),
            children: [
              const TextSpan(text: 'Chaqmoq'),
              TextSpan(
                text: 'App',
                style: GoogleFonts.inter(
                  fontSize: 26,
                  height: 1.1,
                  fontWeight: FontWeight.w800,
                  letterSpacing: -0.4,
                  color: palette.primary,
                ),
              ),
            ],
          ),
        ),
        const SizedBox(height: 8),
        Text(
          'Ta’lim markazi va ota-ona o‘rtasidagi\nishonchli ko‘prik',
          textAlign: TextAlign.center,
          style: GoogleFonts.inter(
            fontSize: 13.5,
            height: 1.45,
            fontWeight: FontWeight.w500,
            color: palette.textMuted,
          ),
        ),
      ],
    );
  }
}

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
    final palette = _LoginPalette.of(context);
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
              color: palette.textDark,
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
            cursorColor: palette.primary,
            style: GoogleFonts.inter(
              fontSize: 14.5,
              fontWeight: FontWeight.w500,
              color: palette.textDark,
            ),
            decoration: InputDecoration(
              hintText: hintText,
              hintStyle: GoogleFonts.inter(
                fontSize: 14,
                fontWeight: FontWeight.w500,
                color: palette.textDim,
              ),
              filled: true,
              fillColor: enabled ? palette.surface : palette.surfaceMuted,
              prefixIcon: Padding(
                padding: const EdgeInsets.only(left: 14, right: 6),
                child: Icon(icon, color: palette.iconMuted, size: 20),
              ),
              prefixIconConstraints: const BoxConstraints(minWidth: 44),
              suffixIcon: suffix,
              suffixIconConstraints: const BoxConstraints(minWidth: 48),
              contentPadding: const EdgeInsets.symmetric(
                horizontal: 14,
                vertical: 12,
              ),
              border: _border(palette.border),
              enabledBorder: _border(palette.border),
              disabledBorder: _border(palette.borderDim),
              focusedBorder: _border(palette.primary, width: 1.4),
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
    final palette = _LoginPalette.of(context);
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
          color: palette.iconMuted,
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
    final palette = _LoginPalette.of(context);
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
                      color: rememberMe ? palette.primary : palette.surface,
                      borderRadius: BorderRadius.circular(6),
                      border: Border.all(
                        color: rememberMe ? palette.primary : palette.border,
                        width: 1.4,
                      ),
                    ),
                    child: rememberMe
                        ? const Icon(
                            Icons.check_rounded,
                            color: Colors.white,
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
                        color: palette.textDark,
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
            foregroundColor: palette.primary,
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
              color: palette.primary,
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
    final palette = _LoginPalette.of(context);
    return SizedBox(
      width: double.infinity,
      height: 54,
      child: DecoratedBox(
        decoration: BoxDecoration(
          gradient: LinearGradient(
            begin: Alignment.centerLeft,
            end: Alignment.centerRight,
            colors: [palette.primary, palette.primaryLight],
          ),
          borderRadius: BorderRadius.circular(14),
          boxShadow: [
            BoxShadow(
              color: palette.primary.withValues(alpha: 0.32),
              blurRadius: 18,
              offset: const Offset(0, 10),
            ),
          ],
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
              ? const SizedBox(
                  width: 22,
                  height: 22,
                  child: CircularProgressIndicator(
                    strokeWidth: 2.4,
                    color: Colors.white,
                  ),
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
    final palette = _LoginPalette.of(context);
    return Container(
      padding: const EdgeInsets.fromLTRB(14, 12, 14, 12),
      decoration: BoxDecoration(
        color: palette.successSoft,
        borderRadius: BorderRadius.circular(14),
        border: Border.all(color: palette.successBorder),
      ),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Container(
            width: 32,
            height: 32,
            alignment: Alignment.center,
            decoration: BoxDecoration(
              color: palette.successIconBg,
              borderRadius: BorderRadius.circular(10),
            ),
            child: Icon(
              Icons.shield_rounded,
              color: palette.successText,
              size: 18,
            ),
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
                    color: palette.successText,
                  ),
                ),
                const SizedBox(height: 2),
                Text(
                  'Ma’lumotlaringiz shifrlangan kanal orqali uzatiladi',
                  style: GoogleFonts.inter(
                    fontSize: 12,
                    height: 1.35,
                    fontWeight: FontWeight.w500,
                    color: palette.successTextMuted,
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
    final palette = _LoginPalette.of(context);
    return Container(
      width: double.infinity,
      padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 10),
      decoration: BoxDecoration(
        color: palette.dangerSoft,
        borderRadius: BorderRadius.circular(12),
        border: Border.all(color: palette.dangerBorder),
      ),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Padding(
            padding: const EdgeInsets.only(top: 1),
            child: Icon(
              Icons.error_outline_rounded,
              size: 16,
              color: palette.dangerText,
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
                color: palette.dangerText,
              ),
            ),
          ),
        ],
      ),
    );
  }
}

// ============================================================================
// Theme-aware palette — single source of truth for light/dark colors.
// ============================================================================

class _LoginPalette {
  const _LoginPalette({
    required this.bg,
    required this.surface,
    required this.surfaceMuted,
    required this.border,
    required this.borderDim,
    required this.shadow,
    required this.textDark,
    required this.textMuted,
    required this.textDim,
    required this.iconMuted,
    required this.primary,
    required this.primaryLight,
    required this.successSoft,
    required this.successBorder,
    required this.successIconBg,
    required this.successText,
    required this.successTextMuted,
    required this.dangerSoft,
    required this.dangerBorder,
    required this.dangerText,
    required this.infoSoft,
    required this.infoBorder,
    required this.infoText,
  });

  final Color bg;
  final Color surface;
  final Color surfaceMuted;
  final Color border;
  final Color borderDim;
  final Color shadow;
  final Color textDark;
  final Color textMuted;
  final Color textDim;
  final Color iconMuted;
  final Color primary;
  final Color primaryLight;
  final Color successSoft;
  final Color successBorder;
  final Color successIconBg;
  final Color successText;
  final Color successTextMuted;
  final Color dangerSoft;
  final Color dangerBorder;
  final Color dangerText;
  final Color infoSoft;
  final Color infoBorder;
  final Color infoText;

  static _LoginPalette of(BuildContext context) {
    final isDark = Theme.of(context).brightness == Brightness.dark;
    return isDark ? _dark : _light;
  }

  static const _LoginPalette _light = _LoginPalette(
    bg: Color(0xFFF4F7FB),
    surface: Color(0xFFFFFFFF),
    surfaceMuted: Color(0xFFF1F3F8),
    border: Color(0xFFDDE5F0),
    borderDim: Color(0xFFE5EAF2),
    shadow: Color(0x140F172A),
    textDark: Color(0xFF0E1422),
    textMuted: Color(0xFF5F6B7E),
    textDim: Color(0xFF96A0B2),
    iconMuted: Color(0xFF6B7280),
    primary: Color(0xFF2F74F6),
    primaryLight: Color(0xFF5C94FF),
    successSoft: Color(0xFFE7F8EF),
    successBorder: Color(0xFFBDEBD0),
    successIconBg: Color(0xFFCDEFDC),
    successText: Color(0xFF15793F),
    successTextMuted: Color(0xFF2E7A55),
    dangerSoft: Color(0xFFFFF1F2),
    dangerBorder: Color(0xFFFECACA),
    dangerText: Color(0xFFB91C1C),
    infoSoft: Color(0xFFEFF6FF),
    infoBorder: Color(0xFFBFDBFE),
    infoText: Color(0xFF0F172A),
  );

  static const _LoginPalette _dark = _LoginPalette(
    bg: Color(0xFF0A111C),
    surface: Color(0xFF111B2A),
    surfaceMuted: Color(0xFF0E1726),
    border: Color(0xFF1F2C40),
    borderDim: Color(0xFF18222F),
    shadow: Color(0x66000000),
    textDark: Color(0xFFEEF2F8),
    textMuted: Color(0xFF9AA6BC),
    textDim: Color(0xFF66728A),
    iconMuted: Color(0xFF9AA6BC),
    primary: Color(0xFF3B82F6),
    primaryLight: Color(0xFF60A5FA),
    successSoft: Color(0xFF0E2A1E),
    successBorder: Color(0xFF184F37),
    successIconBg: Color(0xFF13402C),
    successText: Color(0xFF7BE0A6),
    successTextMuted: Color(0xFF8FCCB0),
    dangerSoft: Color(0xFF2A1115),
    dangerBorder: Color(0xFF5A1D26),
    dangerText: Color(0xFFFCA5A5),
    infoSoft: Color(0xFF0E1A2E),
    infoBorder: Color(0xFF1E3357),
    infoText: Color(0xFFCBD9F0),
  );
}
