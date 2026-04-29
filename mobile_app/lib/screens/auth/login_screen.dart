import 'package:chaqmoq_mobile/models/app_models.dart';
import 'package:chaqmoq_mobile/providers/auth_provider.dart';
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:google_fonts/google_fonts.dart';
import 'package:provider/provider.dart';

enum _CredentialMode { emailOrLogin, phone }

class LoginScreen extends StatefulWidget {
  const LoginScreen({super.key});

  @override
  State<LoginScreen> createState() => _LoginScreenState();
}

class _LoginScreenState extends State<LoginScreen> {
  final TextEditingController _loginController = TextEditingController();
  final TextEditingController _passwordController = TextEditingController();

  _CredentialMode _credentialMode = _CredentialMode.emailOrLogin;
  String? _formErrorMessage;
  bool _obscurePassword = true;
  bool _rememberMe = true;
  int _bannerSequence = 0;

  bool get _isPhoneMode => _credentialMode == _CredentialMode.phone;

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
    _clearFeedback();
    final identifierError = _validateIdentifier(_loginController.text);
    if (identifierError != null) {
      _setFormError(identifierError);
      return;
    }

    final password = _passwordController.text;
    if (password.trim().isEmpty) {
      _setFormError('Parolni kiriting');
      return;
    }

    final identifier = _normalizeIdentifier(_loginController.text);
    final success = await auth.login(
      login: _isPhoneMode ? null : identifier,
      phoneNumber: _isPhoneMode ? identifier : null,
      password: password,
    );
    if (!mounted || success) {
      return;
    }
    final inlineError = auth.inlineErrorMessage;
    if (inlineError != null && inlineError.isNotEmpty) {
      _setFormError(inlineError);
      return;
    }
    _showTopBanner(
      auth.bannerErrorMessage ?? 'Kutilmagan xatolik yuz berdi',
      isError: true,
    );
  }

  void _showPendingFeature(String message) {
    _showTopBanner(message);
  }

  void _setFormError(String message) {
    if (_formErrorMessage == message) {
      return;
    }
    setState(() => _formErrorMessage = message);
  }

  void _clearFeedback() {
    final auth = context.read<AuthProvider>();
    if (_formErrorMessage != null) {
      setState(() => _formErrorMessage = null);
    }
    auth.clearError();
    final messenger = ScaffoldMessenger.of(context);
    messenger
      ..hideCurrentMaterialBanner()
      ..clearSnackBars();
  }

  void _showTopBanner(String message, {bool isError = false}) {
    final messenger = ScaffoldMessenger.of(context);
    final foregroundColor = isError
        ? const Color(0xFF7F1D1D)
        : const Color(0xFF0F172A);
    final backgroundColor = isError
        ? const Color(0xFFFFF1F2)
        : const Color(0xFFEFF6FF);
    final borderColor = isError
        ? const Color(0xFFFECACA)
        : const Color(0xFFBFDBFE);
    final icon = isError ? Icons.error_outline_rounded : Icons.info_outline;
    final sequence = ++_bannerSequence;

    messenger
      ..hideCurrentMaterialBanner()
      ..clearSnackBars()
      ..showMaterialBanner(
        MaterialBanner(
          forceActionsBelow: false,
          overflowAlignment: OverflowBarAlignment.end,
          backgroundColor: backgroundColor,
          surfaceTintColor: Colors.transparent,
          dividerColor: borderColor,
          padding: const EdgeInsets.fromLTRB(14, 10, 6, 10),
          leading: Icon(icon, color: foregroundColor, size: 20),
          content: Text(
            message,
            style: GoogleFonts.inter(
              fontSize: 13,
              height: 1.3,
              fontWeight: FontWeight.w600,
              color: foregroundColor,
            ),
          ),
          actions: [
            IconButton(
              onPressed: messenger.hideCurrentMaterialBanner,
              splashRadius: 18,
              visualDensity: VisualDensity.compact,
              icon: Icon(Icons.close_rounded, color: foregroundColor, size: 18),
            ),
          ],
        ),
      );

    Future<void>.delayed(const Duration(seconds: 4), () {
      if (!mounted || sequence != _bannerSequence) {
        return;
      }
      messenger.hideCurrentMaterialBanner();
    });
  }

  void _setCredentialMode(_CredentialMode mode) {
    if (_credentialMode == mode) {
      return;
    }

    setState(() {
      _credentialMode = mode;
      _loginController.clear();
      _formErrorMessage = null;
    });
    context.read<AuthProvider>().clearError();
    final messenger = ScaffoldMessenger.of(context);
    messenger
      ..hideCurrentMaterialBanner()
      ..clearSnackBars();
  }

  String? _validateIdentifier(String rawValue) {
    final value = rawValue.trim();
    if (value.isEmpty) {
      return _isPhoneMode
          ? 'Telefon raqamini kiriting'
          : 'Email yoki loginni kiriting';
    }

    if (_isPhoneMode) {
      final digits = _extractPhoneDigits(value);
      if (digits.length != 9) {
        return 'Telefon raqamini 9 xonali formatda kiriting';
      }
      return null;
    }

    if (value.contains(RegExp(r'\s'))) {
      return 'Email yoki login bo‘sh joysiz bo‘lishi kerak';
    }

    if (value.contains('@') && !_isValidEmail(value)) {
      return 'Email manzil noto‘g‘ri kiritildi';
    }

    if (!value.contains('@') && value.length < 3) {
      return 'Login kamida 3 belgidan iborat bo‘lsin';
    }

    return null;
  }

  String _normalizeIdentifier(String rawValue) {
    final value = rawValue.trim();
    if (!_isPhoneMode) {
      return value;
    }

    final digits = _extractPhoneDigits(value);
    return '+998$digits';
  }

  String _extractPhoneDigits(String rawValue) {
    final digits = rawValue.replaceAll(RegExp(r'\D'), '');
    if (digits.startsWith('998') && digits.length == 12) {
      return digits.substring(3);
    }
    return digits;
  }

  bool _isValidEmail(String value) {
    return RegExp(
      r'^[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}$',
      caseSensitive: false,
    ).hasMatch(value);
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
                          credentialMode: _credentialMode,
                          obscurePassword: _obscurePassword,
                          rememberMe: _rememberMe,
                          isLoading: isLoading,
                          errorMessage: _formErrorMessage,
                          onCredentialModeChanged: _setCredentialMode,
                          onFieldChanged: _clearFeedback,
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
    required this.credentialMode,
    required this.obscurePassword,
    required this.rememberMe,
    required this.isLoading,
    required this.onCredentialModeChanged,
    required this.onFieldChanged,
    required this.onTogglePassword,
    required this.onToggleRemember,
    required this.onSubmit,
    required this.onForgotPassword,
    required this.onRegister,
    this.errorMessage,
  });

  final TextEditingController loginController;
  final TextEditingController passwordController;
  final _CredentialMode credentialMode;
  final bool obscurePassword;
  final bool rememberMe;
  final bool isLoading;
  final String? errorMessage;
  final ValueChanged<_CredentialMode> onCredentialModeChanged;
  final VoidCallback onFieldChanged;
  final VoidCallback onTogglePassword;
  final VoidCallback onToggleRemember;
  final VoidCallback onSubmit;
  final VoidCallback onForgotPassword;
  final VoidCallback onRegister;

  @override
  Widget build(BuildContext context) {
    final isPhoneMode = credentialMode == _CredentialMode.phone;

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
            'Email, login yoki telefon orqali tizimga kiring',
            textAlign: TextAlign.center,
            style: GoogleFonts.inter(
              fontSize: 13,
              height: 1.3,
              fontWeight: FontWeight.w500,
              color: _LoginColors.textMuted,
            ),
          ),
          const SizedBox(height: 20),
          _CredentialModeSwitcher(
            value: credentialMode,
            enabled: !isLoading,
            onChanged: onCredentialModeChanged,
          ),
          const SizedBox(height: 16),
          Align(
            alignment: Alignment.centerLeft,
            child: _FieldLabel(
              text: isPhoneMode ? 'Telefon raqam' : 'Email yoki login',
            ),
          ),
          const SizedBox(height: 8),
          CustomTextField(
            controller: loginController,
            hintText: isPhoneMode ? '901234567' : 'Email yoki login',
            enabled: !isLoading,
            keyboardType: isPhoneMode
                ? TextInputType.phone
                : TextInputType.emailAddress,
            textInputAction: TextInputAction.next,
            autofillHints: isPhoneMode
                ? const [AutofillHints.telephoneNumber]
                : const [AutofillHints.username, AutofillHints.email],
            icon: isPhoneMode ? null : Icons.alternate_email_rounded,
            prefix: isPhoneMode ? const _LoginPrefix() : null,
            enableSuggestions: !isPhoneMode,
            autocorrect: false,
            inputFormatters: isPhoneMode
                ? [
                    FilteringTextInputFormatter.digitsOnly,
                    LengthLimitingTextInputFormatter(9),
                  ]
                : null,
            onChanged: (_) => onFieldChanged(),
          ),
          const SizedBox(height: 12),
          const Align(
            alignment: Alignment.centerLeft,
            child: _FieldLabel(text: 'Parol'),
          ),
          const SizedBox(height: 8),
          CustomTextField(
            controller: passwordController,
            hintText: 'Parol',
            enabled: !isLoading,
            icon: Icons.lock_outline_rounded,
            obscureText: obscurePassword,
            keyboardType: TextInputType.visiblePassword,
            textInputAction: TextInputAction.done,
            autofillHints: const [AutofillHints.password],
            enableSuggestions: false,
            autocorrect: false,
            onChanged: (_) => onFieldChanged(),
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
    this.inputFormatters,
    this.enableSuggestions = true,
    this.autocorrect = true,
    this.onChanged,
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
  final List<TextInputFormatter>? inputFormatters;
  final bool enableSuggestions;
  final bool autocorrect;
  final ValueChanged<String>? onChanged;

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
        onChanged: onChanged,
        onSubmitted: onSubmitted,
        autofillHints: autofillHints,
        inputFormatters: inputFormatters,
        enableSuggestions: enableSuggestions,
        autocorrect: autocorrect,
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

class _CredentialModeSwitcher extends StatelessWidget {
  const _CredentialModeSwitcher({
    required this.value,
    required this.enabled,
    required this.onChanged,
  });

  final _CredentialMode value;
  final bool enabled;
  final ValueChanged<_CredentialMode> onChanged;

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.all(4),
      decoration: BoxDecoration(
        color: const Color(0xFFF3F6FB),
        borderRadius: BorderRadius.circular(14),
        border: Border.all(color: const Color(0xFFE2E8F0)),
      ),
      child: Row(
        children: [
          Expanded(
            child: _CredentialModeChip(
              label: 'Email yoki login',
              icon: Icons.alternate_email_rounded,
              isSelected: value == _CredentialMode.emailOrLogin,
              enabled: enabled,
              onTap: () => onChanged(_CredentialMode.emailOrLogin),
            ),
          ),
          const SizedBox(width: 6),
          Expanded(
            child: _CredentialModeChip(
              label: 'Telefon',
              icon: Icons.phone_rounded,
              isSelected: value == _CredentialMode.phone,
              enabled: enabled,
              onTap: () => onChanged(_CredentialMode.phone),
            ),
          ),
        ],
      ),
    );
  }
}

class _CredentialModeChip extends StatelessWidget {
  const _CredentialModeChip({
    required this.label,
    required this.icon,
    required this.isSelected,
    required this.enabled,
    required this.onTap,
  });

  final String label;
  final IconData icon;
  final bool isSelected;
  final bool enabled;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    return InkWell(
      onTap: enabled ? onTap : null,
      borderRadius: BorderRadius.circular(10),
      child: AnimatedContainer(
        duration: const Duration(milliseconds: 160),
        padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 10),
        decoration: BoxDecoration(
          color: isSelected ? _LoginColors.white : Colors.transparent,
          borderRadius: BorderRadius.circular(10),
          boxShadow: isSelected
              ? const [
                  BoxShadow(
                    color: Color(0x120F172A),
                    blurRadius: 12,
                    offset: Offset(0, 4),
                  ),
                ]
              : const [],
        ),
        child: Row(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            Icon(
              icon,
              size: 18,
              color: isSelected ? _LoginColors.primary : _LoginColors.textMuted,
            ),
            const SizedBox(width: 8),
            Flexible(
              child: Text(
                label,
                maxLines: 1,
                overflow: TextOverflow.ellipsis,
                style: GoogleFonts.inter(
                  fontSize: 12.5,
                  fontWeight: FontWeight.w700,
                  color: isSelected
                      ? _LoginColors.textDark
                      : _LoginColors.textMuted,
                ),
              ),
            ),
          ],
        ),
      ),
    );
  }
}

class _FieldLabel extends StatelessWidget {
  const _FieldLabel({required this.text});

  final String text;

  @override
  Widget build(BuildContext context) {
    return Text(
      text,
      style: GoogleFonts.inter(
        fontSize: 13,
        fontWeight: FontWeight.w700,
        color: _LoginColors.textDark,
      ),
    );
  }
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
      padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 9),
      decoration: BoxDecoration(
        color: const Color(0xFFFFF1F2),
        borderRadius: BorderRadius.circular(12),
        border: Border.all(color: const Color(0xFFFECACA)),
      ),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          const Padding(
            padding: EdgeInsets.only(top: 1),
            child: Icon(
              Icons.error_outline_rounded,
              size: 16,
              color: Color(0xFFB91C1C),
            ),
          ),
          const SizedBox(width: 8),
          Expanded(
            child: Text(
              message,
              style: GoogleFonts.inter(
                fontSize: 12.5,
                height: 1.25,
                fontWeight: FontWeight.w600,
                color: const Color(0xFFB91C1C),
              ),
            ),
          ),
        ],
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
