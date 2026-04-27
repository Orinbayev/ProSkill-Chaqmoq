import 'package:chaqmoq_mobile/models/app_models.dart';
import 'package:chaqmoq_mobile/providers/auth_provider.dart';
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:google_fonts/google_fonts.dart';
import 'package:provider/provider.dart';

class LoginScreen extends StatefulWidget {
  const LoginScreen({super.key});

  @override
  State<LoginScreen> createState() => _LoginScreenState();
}

class _LoginScreenState extends State<LoginScreen> {
  final TextEditingController _loginController = TextEditingController();
  final TextEditingController _passwordController = TextEditingController();

  bool _obscurePassword = true;
  bool _rememberMe = true;

  @override
  void dispose() {
    _loginController.dispose();
    _passwordController.dispose();
    super.dispose();
  }

  Future<void> _submit() async {
    final auth = context.read<AuthProvider>();
    if (auth.state == ViewState.loading) {
      return;
    }

    FocusScope.of(context).unfocus();
    final login = _normalizeLogin(_loginController.text);
    final password = _passwordController.text;

    if (login.isEmpty || password.isEmpty) {
      _showError('Telefon raqam yoki login va parolni kiriting');
      return;
    }

    final success = await auth.login(login: login, password: password);
    if (!mounted || success) {
      return;
    }
    _showError(auth.errorMessage ?? 'Login yoki parol noto‘g‘ri');
  }

  void _showPendingFeature(String message) {
    ScaffoldMessenger.of(
      context,
    ).showSnackBar(SnackBar(content: Text(message)));
  }

  void _showError(String message) {
    ScaffoldMessenger.of(context)
      ..clearSnackBars()
      ..showSnackBar(
        SnackBar(
          content: Text(message),
          behavior: SnackBarBehavior.floating,
          backgroundColor: const Color(0xFFB91C1C),
        ),
      );
  }

  String _normalizeLogin(String rawValue) {
    final value = rawValue.trim();
    if (value.isEmpty) {
      return '';
    }

    final compact = value.replaceAll(RegExp(r'[\s()\-.]'), '');
    final numeric = compact.startsWith('+') ? compact.substring(1) : compact;
    if (RegExp(r'^\d+$').hasMatch(numeric)) {
      return numeric.length == 9 ? '998$numeric' : numeric;
    }
    return value;
  }

  @override
  Widget build(BuildContext context) {
    final size = MediaQuery.sizeOf(context);
    final isCompact = size.height < 760;
    final illustrationHeight = (size.height * 0.21)
        .clamp(130.0, 190.0)
        .toDouble();
    final topSpacing = isCompact ? 10.0 : 18.0;
    final auth = context.watch<AuthProvider>();
    final isLoading = auth.state == ViewState.loading;

    return AnnotatedRegion<SystemUiOverlayStyle>(
      value: const SystemUiOverlayStyle(
        statusBarColor: Colors.transparent,
        statusBarIconBrightness: Brightness.dark,
        statusBarBrightness: Brightness.light,
        systemNavigationBarColor: Colors.white,
        systemNavigationBarIconBrightness: Brightness.dark,
      ),
      child: Scaffold(
        resizeToAvoidBottomInset: true,
        body: Container(
          decoration: const BoxDecoration(
            gradient: LinearGradient(
              begin: Alignment.topCenter,
              end: Alignment.bottomCenter,
              colors: [_LoginColors.backgroundTop, _LoginColors.white],
            ),
          ),
          child: SafeArea(
            child: SingleChildScrollView(
              keyboardDismissBehavior: ScrollViewKeyboardDismissBehavior.onDrag,
              padding: const EdgeInsets.fromLTRB(20, 0, 20, 20),
              physics: const BouncingScrollPhysics(),
              child: Center(
                child: ConstrainedBox(
                  constraints: const BoxConstraints(maxWidth: 430),
                  child: AutofillGroup(
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.center,
                      children: [
                        SizedBox(height: topSpacing),
                        Image.asset(
                          'assets/images/login_logo.png',
                          height: isCompact ? 54 : 68,
                          fit: BoxFit.contain,
                        ),
                        const SizedBox(height: 8),
                        const _BrandTitle(),
                        const SizedBox(height: 8),
                        Text(
                          'Ta’lim markazi va ota-ona o‘rtasidagi\nishonchli ko‘prik',
                          textAlign: TextAlign.center,
                          style: GoogleFonts.inter(
                            fontSize: 13,
                            height: 1.42,
                            fontWeight: FontWeight.w500,
                            color: _LoginColors.textMuted,
                          ),
                        ),
                        SizedBox(height: isCompact ? 8 : 12),
                        Image.asset(
                          'assets/images/login_illustration.png',
                          height: illustrationHeight,
                          width: double.infinity,
                          fit: BoxFit.contain,
                        ),
                        _LoginCard(
                          loginController: _loginController,
                          passwordController: _passwordController,
                          obscurePassword: _obscurePassword,
                          rememberMe: _rememberMe,
                          isLoading: isLoading,
                          errorMessage: auth.errorMessage,
                          onTogglePassword: () {
                            setState(
                              () => _obscurePassword = !_obscurePassword,
                            );
                          },
                          onToggleRemember: () {
                            setState(() => _rememberMe = !_rememberMe);
                          },
                          onSubmit: _submit,
                          onForgotPassword: () {
                            _showPendingFeature(
                              'Parolni tiklash tez orada ulanadi.',
                            );
                          },
                          onRegister: () {
                            _showPendingFeature(
                              'Ro‘yxatdan o‘tish tez orada ulanadi.',
                            );
                          },
                        ),
                      ],
                    ),
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

class _BrandTitle extends StatelessWidget {
  const _BrandTitle();

  @override
  Widget build(BuildContext context) {
    final style = GoogleFonts.inter(
      fontSize: 22,
      height: 1.1,
      fontWeight: FontWeight.w800,
      letterSpacing: 0,
    );

    return RichText(
      textAlign: TextAlign.center,
      text: TextSpan(
        style: style.copyWith(color: _LoginColors.textDark),
        children: [
          const TextSpan(text: 'Chaqmoq'),
          TextSpan(
            text: 'App',
            style: style.copyWith(color: _LoginColors.primary),
          ),
        ],
      ),
    );
  }
}

class _LoginCard extends StatelessWidget {
  const _LoginCard({
    required this.loginController,
    required this.passwordController,
    required this.obscurePassword,
    required this.rememberMe,
    required this.isLoading,
    required this.onTogglePassword,
    required this.onToggleRemember,
    required this.onSubmit,
    required this.onForgotPassword,
    required this.onRegister,
    this.errorMessage,
  });

  final TextEditingController loginController;
  final TextEditingController passwordController;
  final bool obscurePassword;
  final bool rememberMe;
  final bool isLoading;
  final String? errorMessage;
  final VoidCallback onTogglePassword;
  final VoidCallback onToggleRemember;
  final VoidCallback onSubmit;
  final VoidCallback onForgotPassword;
  final VoidCallback onRegister;

  @override
  Widget build(BuildContext context) {
    return Container(
      width: double.infinity,
      padding: const EdgeInsets.fromLTRB(18, 20, 18, 22),
      decoration: BoxDecoration(
        color: _LoginColors.white,
        borderRadius: BorderRadius.circular(22),
        boxShadow: const [
          BoxShadow(
            color: Colors.black12,
            blurRadius: 18,
            offset: Offset(0, 8),
          ),
        ],
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.center,
        children: [
          Text(
            'Tizimga kirish',
            textAlign: TextAlign.center,
            style: GoogleFonts.inter(
              fontSize: 20,
              height: 1.2,
              fontWeight: FontWeight.w700,
              color: _LoginColors.textDark,
            ),
          ),
          const SizedBox(height: 6),
          Text(
            'Iltimos, ma’lumotlaringizni kiriting',
            textAlign: TextAlign.center,
            style: GoogleFonts.inter(
              fontSize: 13,
              height: 1.3,
              fontWeight: FontWeight.w500,
              color: _LoginColors.textMuted,
            ),
          ),
          const SizedBox(height: 20),
          CustomTextField(
            controller: loginController,
            hintText: 'Telefon raqam yoki login',
            enabled: !isLoading,
            keyboardType: TextInputType.text,
            textInputAction: TextInputAction.next,
            autofillHints: const [
              AutofillHints.username,
              AutofillHints.telephoneNumber,
            ],
            prefix: const _LoginPrefix(),
          ),
          const SizedBox(height: 12),
          CustomTextField(
            controller: passwordController,
            hintText: 'Parol',
            enabled: !isLoading,
            icon: Icons.lock_outline_rounded,
            obscureText: obscurePassword,
            textInputAction: TextInputAction.done,
            autofillHints: const [AutofillHints.password],
            onSubmitted: (_) {
              if (!isLoading) {
                onSubmit();
              }
            },
            suffix: IconButton(
              onPressed: isLoading ? null : onTogglePassword,
              splashRadius: 20,
              icon: Icon(
                obscurePassword
                    ? Icons.visibility_off_outlined
                    : Icons.visibility_outlined,
                color: _LoginColors.iconMuted,
                size: 22,
              ),
            ),
          ),
          if (errorMessage != null) ...[
            const SizedBox(height: 10),
            _ErrorMessage(message: errorMessage!),
          ],
          const SizedBox(height: 14),
          Row(
            children: [
              Expanded(
                child: _RememberMeControl(
                  value: rememberMe,
                  enabled: !isLoading,
                  onChanged: onToggleRemember,
                ),
              ),
              const SizedBox(width: 10),
              Flexible(
                child: Align(
                  alignment: Alignment.centerRight,
                  child: TextButton(
                    onPressed: isLoading ? null : onForgotPassword,
                    style: TextButton.styleFrom(
                      foregroundColor: _LoginColors.primary,
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
                        fontWeight: FontWeight.w600,
                        color: _LoginColors.primary,
                      ),
                    ),
                  ),
                ),
              ),
            ],
          ),
          const SizedBox(height: 16),
          PrimaryButton(
            text: 'Kirish',
            isLoading: isLoading,
            onPressed: onSubmit,
          ),
          const SizedBox(height: 18),
          _RegisterRow(onRegister: isLoading ? null : onRegister),
        ],
      ),
    );
  }
}

class CustomTextField extends StatelessWidget {
  const CustomTextField({
    super.key,
    required this.controller,
    required this.hintText,
    this.enabled = true,
    this.keyboardType,
    this.textInputAction,
    this.obscureText = false,
    this.icon,
    this.prefix,
    this.suffix,
    this.onSubmitted,
    this.autofillHints,
  });

  final TextEditingController controller;
  final String hintText;
  final bool enabled;
  final TextInputType? keyboardType;
  final TextInputAction? textInputAction;
  final bool obscureText;
  final IconData? icon;
  final Widget? prefix;
  final Widget? suffix;
  final ValueChanged<String>? onSubmitted;
  final Iterable<String>? autofillHints;

  @override
  Widget build(BuildContext context) {
    return SizedBox(
      height: 48,
      child: TextField(
        controller: controller,
        enabled: enabled,
        keyboardType: keyboardType,
        textInputAction: textInputAction,
        obscureText: obscureText,
        onSubmitted: onSubmitted,
        autofillHints: autofillHints,
        cursorColor: _LoginColors.primary,
        style: GoogleFonts.inter(
          fontSize: 14,
          fontWeight: FontWeight.w500,
          color: _LoginColors.textDark,
        ),
        decoration: InputDecoration(
          hintText: hintText,
          hintStyle: GoogleFonts.inter(
            fontSize: 14,
            fontWeight: FontWeight.w500,
            color: _LoginColors.textMuted,
          ),
          filled: true,
          fillColor: enabled ? _LoginColors.white : const Color(0xFFF9FAFB),
          prefixIcon:
              prefix ??
              (icon == null
                  ? null
                  : Icon(icon, color: _LoginColors.iconMuted, size: 21)),
          prefixIconConstraints: prefix == null
              ? const BoxConstraints(minWidth: 44)
              : const BoxConstraints(minWidth: 76),
          suffixIcon: suffix,
          suffixIconConstraints: const BoxConstraints(minWidth: 48),
          contentPadding: const EdgeInsets.symmetric(horizontal: 14),
          border: _outlineBorder,
          enabledBorder: _outlineBorder,
          disabledBorder: _outlineBorder.copyWith(
            borderSide: const BorderSide(color: Color(0xFFE5EAF2)),
          ),
          focusedBorder: _outlineBorder.copyWith(
            borderSide: const BorderSide(
              color: _LoginColors.primary,
              width: 1.2,
            ),
          ),
        ),
      ),
    );
  }

  static final OutlineInputBorder _outlineBorder = OutlineInputBorder(
    borderRadius: BorderRadius.circular(12),
    borderSide: const BorderSide(color: _LoginColors.border),
  );
}

class _LoginPrefix extends StatelessWidget {
  const _LoginPrefix();

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.only(left: 14, right: 10),
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          Text(
            '+998',
            style: GoogleFonts.inter(
              fontSize: 14,
              height: 1,
              fontWeight: FontWeight.w700,
              color: _LoginColors.textDark,
            ),
          ),
          const SizedBox(width: 10),
          Container(width: 1, height: 20, color: _LoginColors.border),
        ],
      ),
    );
  }
}

class PrimaryButton extends StatelessWidget {
  const PrimaryButton({
    super.key,
    required this.text,
    required this.onPressed,
    this.isLoading = false,
  });

  final String text;
  final VoidCallback onPressed;
  final bool isLoading;

  @override
  Widget build(BuildContext context) {
    return SizedBox(
      width: double.infinity,
      height: 48,
      child: DecoratedBox(
        decoration: BoxDecoration(
          gradient: const LinearGradient(
            begin: Alignment.centerLeft,
            end: Alignment.centerRight,
            colors: [_LoginColors.primary, _LoginColors.primaryLight],
          ),
          borderRadius: BorderRadius.circular(12),
          boxShadow: const [
            BoxShadow(
              color: Color(0x2B1E73F8),
              blurRadius: 14,
              offset: Offset(0, 7),
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
            foregroundColor: _LoginColors.white,
            disabledForegroundColor: _LoginColors.white,
            shape: RoundedRectangleBorder(
              borderRadius: BorderRadius.circular(12),
            ),
          ),
          child: isLoading
              ? const SizedBox(
                  width: 20,
                  height: 20,
                  child: CircularProgressIndicator(
                    strokeWidth: 2.2,
                    color: _LoginColors.white,
                  ),
                )
              : Text(
                  text,
                  style: GoogleFonts.inter(
                    fontSize: 15,
                    fontWeight: FontWeight.w700,
                    color: _LoginColors.white,
                  ),
                ),
        ),
      ),
    );
  }
}

class _RememberMeControl extends StatelessWidget {
  const _RememberMeControl({
    required this.value,
    required this.enabled,
    required this.onChanged,
  });

  final bool value;
  final bool enabled;
  final VoidCallback onChanged;

  @override
  Widget build(BuildContext context) {
    return InkWell(
      onTap: enabled ? onChanged : null,
      borderRadius: BorderRadius.circular(6),
      child: Padding(
        padding: const EdgeInsets.symmetric(vertical: 5),
        child: Row(
          mainAxisSize: MainAxisSize.min,
          children: [
            AnimatedContainer(
              duration: const Duration(milliseconds: 160),
              width: 18,
              height: 18,
              decoration: BoxDecoration(
                color: value ? _LoginColors.primary : _LoginColors.white,
                borderRadius: BorderRadius.circular(5),
                border: Border.all(
                  color: value ? _LoginColors.primary : _LoginColors.border,
                  width: 1.2,
                ),
              ),
              child: value
                  ? const Icon(
                      Icons.check_rounded,
                      color: _LoginColors.white,
                      size: 16,
                    )
                  : null,
            ),
            const SizedBox(width: 8),
            Flexible(
              child: Text(
                'Meni eslab qolish',
                maxLines: 1,
                overflow: TextOverflow.ellipsis,
                style: GoogleFonts.inter(
                  fontSize: 13,
                  fontWeight: FontWeight.w500,
                  color: _LoginColors.textMuted,
                ),
              ),
            ),
          ],
        ),
      ),
    );
  }
}

class _RegisterRow extends StatelessWidget {
  const _RegisterRow({required this.onRegister});

  final VoidCallback? onRegister;

  @override
  Widget build(BuildContext context) {
    return Wrap(
      alignment: WrapAlignment.center,
      crossAxisAlignment: WrapCrossAlignment.center,
      spacing: 8,
      runSpacing: 4,
      children: [
        Text(
          'Hisobingiz yo‘qmi?',
          style: GoogleFonts.inter(
            fontSize: 13.5,
            fontWeight: FontWeight.w500,
            color: _LoginColors.textMuted,
          ),
        ),
        GestureDetector(
          onTap: onRegister,
          child: Text(
            'Ro‘yxatdan o‘tish',
            style: GoogleFonts.inter(
              fontSize: 13.5,
              fontWeight: FontWeight.w700,
              color: _LoginColors.primary,
            ),
          ),
        ),
      ],
    );
  }
}

class _ErrorMessage extends StatelessWidget {
  const _ErrorMessage({required this.message});

  final String message;

  @override
  Widget build(BuildContext context) {
    return Container(
      width: double.infinity,
      padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 10),
      decoration: BoxDecoration(
        color: const Color(0xFFFFF1F2),
        borderRadius: BorderRadius.circular(12),
        border: Border.all(color: const Color(0xFFFECACA)),
      ),
      child: Text(
        message,
        style: GoogleFonts.inter(
          fontSize: 12.5,
          height: 1.25,
          fontWeight: FontWeight.w600,
          color: const Color(0xFFB91C1C),
        ),
      ),
    );
  }
}

class _LoginColors {
  const _LoginColors._();

  static const Color backgroundTop = Color(0xFFEAF3FF);
  static const Color white = Color(0xFFFFFFFF);
  static const Color textDark = Color(0xFF111827);
  static const Color textMuted = Color(0xFF6B7280);
  static const Color iconMuted = Color(0xFF6B7280);
  static const Color border = Color(0xFFDDE5F0);
  static const Color primary = Color(0xFF1E73F8);
  static const Color primaryLight = Color(0xFF4F8CFF);
}
