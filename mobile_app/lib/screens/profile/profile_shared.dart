import 'package:flutter/material.dart';
import 'package:google_fonts/google_fonts.dart';

class ProfileUiColors {
  const ProfileUiColors._({
    required this.background,
    required this.card,
    required this.primary,
    required this.text,
    required this.secondaryText,
    required this.hint,
    required this.border,
    required this.inputBorder,
    required this.danger,
    required this.surfaceMuted,
  });

  final Color background;
  final Color card;
  final Color primary;
  final Color text;
  final Color secondaryText;
  final Color hint;
  final Color border;
  final Color inputBorder;
  final Color danger;
  final Color surfaceMuted;

  bool get isDark => background == _dark.background;

  static const ProfileUiColors _light = ProfileUiColors._(
    background: Color(0xFFF7FBFF),
    card: Color(0xFFFFFFFF),
    primary: Color(0xFF1E73F8),
    text: Color(0xFF111827),
    secondaryText: Color(0xFF6B7280),
    hint: Color(0xFF9CA3AF),
    border: Color(0xFFE5EAF2),
    inputBorder: Color(0xFFDDE5F0),
    danger: Color(0xFFEF4444),
    surfaceMuted: Color(0xFFF8FAFD),
  );

  static const ProfileUiColors _dark = ProfileUiColors._(
    background: Color(0xFF0B0F17),
    card: Color(0xFF141926),
    primary: Color(0xFF4D8DFF),
    text: Color(0xFFEAF1FB),
    secondaryText: Color(0xFF94A3B8),
    hint: Color(0xFF6F7C90),
    border: Color(0xFF24304A),
    inputBorder: Color(0xFF2C3854),
    danger: Color(0xFFFF6F6F),
    surfaceMuted: Color(0xFF1A2030),
  );

  static ProfileUiColors of(BuildContext context) {
    return Theme.of(context).brightness == Brightness.dark ? _dark : _light;
  }
}

class ProfileUiTextStyles {
  const ProfileUiTextStyles._(this._c);

  final ProfileUiColors _c;

  TextStyle get title => GoogleFonts.inter(
        fontSize: 22,
        fontWeight: FontWeight.w800,
        color: _c.text,
      );

  TextStyle get section => GoogleFonts.inter(
        fontSize: 16,
        fontWeight: FontWeight.w700,
        color: _c.text,
      );

  TextStyle get body => GoogleFonts.inter(
        fontSize: 14,
        fontWeight: FontWeight.w500,
        height: 1.45,
        color: _c.text,
      );

  TextStyle get input => GoogleFonts.inter(
        fontSize: 15,
        fontWeight: FontWeight.w500,
        color: _c.text,
      );

  TextStyle get label => GoogleFonts.inter(
        fontSize: 13.5,
        fontWeight: FontWeight.w500,
        color: _c.secondaryText,
      );

  TextStyle get hint => GoogleFonts.inter(
        fontSize: 14.5,
        fontWeight: FontWeight.w500,
        color: _c.hint,
      );

  TextStyle get muted => GoogleFonts.inter(
        fontSize: 13.5,
        fontWeight: FontWeight.w500,
        height: 1.4,
        color: _c.secondaryText,
      );

  TextStyle get button => GoogleFonts.inter(
        fontSize: 14.5,
        fontWeight: FontWeight.w700,
        color: Colors.white,
      );

  static ProfileUiTextStyles of(BuildContext context) {
    return ProfileUiTextStyles._(ProfileUiColors.of(context));
  }
}

class ProfileUiDecorations {
  const ProfileUiDecorations._(this._c);

  final ProfileUiColors _c;

  static const List<BoxShadow> _lightShadow = <BoxShadow>[
    BoxShadow(color: Color(0x0F0B1220), blurRadius: 18, offset: Offset(0, 8)),
  ];

  static const List<BoxShadow> _darkShadow = <BoxShadow>[
    BoxShadow(color: Color(0x66000000), blurRadius: 22, offset: Offset(0, 10)),
  ];

  List<BoxShadow> get softShadow => _c.isDark ? _darkShadow : _lightShadow;

  BoxDecoration get cardDecoration => BoxDecoration(
        color: _c.card,
        borderRadius: const BorderRadius.all(Radius.circular(20)),
        border: Border.fromBorderSide(BorderSide(color: _c.border)),
        boxShadow: softShadow,
      );

  static ProfileUiDecorations of(BuildContext context) {
    return ProfileUiDecorations._(ProfileUiColors.of(context));
  }
}

class ProfilePageHeader extends StatelessWidget {
  const ProfilePageHeader({super.key, required this.title});

  final String title;

  @override
  Widget build(BuildContext context) {
    return Row(
      children: <Widget>[
        _HeaderButton(
          icon: Icons.arrow_back_rounded,
          onTap: () => Navigator.of(context).pop(),
        ),
        const SizedBox(width: 12),
        Expanded(
          child: Text(
            title,
            maxLines: 1,
            overflow: TextOverflow.ellipsis,
            style: ProfileUiTextStyles.of(context).title,
          ),
        ),
      ],
    );
  }
}

class ProfilePageCard extends StatelessWidget {
  const ProfilePageCard({super.key, required this.child, this.padding});

  final Widget child;
  final EdgeInsetsGeometry? padding;

  @override
  Widget build(BuildContext context) {
    return Container(
      width: double.infinity,
      padding: padding ?? const EdgeInsets.all(18),
      decoration: ProfileUiDecorations.of(context).cardDecoration,
      child: child,
    );
  }
}

class ProfileActionSheetOption<T> {
  const ProfileActionSheetOption({
    required this.value,
    required this.title,
    required this.icon,
    this.subtitle,
    this.destructive = false,
  });

  final T value;
  final String title;
  final String? subtitle;
  final IconData icon;
  final bool destructive;
}

Future<T?> showProfileActionSheet<T>({
  required BuildContext context,
  required String title,
  required List<ProfileActionSheetOption<T>> options,
}) {
  return showModalBottomSheet<T>(
    context: context,
    backgroundColor: Colors.transparent,
    isScrollControlled: true,
    builder: (sheetContext) {
      final c = ProfileUiColors.of(sheetContext);
      final styles = ProfileUiTextStyles.of(sheetContext);
      final decos = ProfileUiDecorations.of(sheetContext);
      final destructiveBg = c.isDark ? const Color(0xFF3A1818) : const Color(0xFFFFF3F2);
      final destructiveBorder = c.isDark ? const Color(0xFF5E2424) : const Color(0xFFFFD6D3);
      final destructiveIconBg = c.isDark ? const Color(0xFF4A1F1F) : const Color(0xFFFFE6E3);
      final iconBg = c.isDark ? const Color(0xFF1F2C44) : const Color(0xFFEAF4FF);
      return SafeArea(
        top: false,
        child: Container(
          margin: const EdgeInsets.fromLTRB(12, 12, 12, 18),
          padding: const EdgeInsets.fromLTRB(18, 12, 18, 18),
          decoration: BoxDecoration(
            color: c.card,
            borderRadius: BorderRadius.circular(26),
            boxShadow: decos.softShadow,
          ),
          child: Column(
            mainAxisSize: MainAxisSize.min,
            crossAxisAlignment: CrossAxisAlignment.start,
            children: <Widget>[
              Center(
                child: Container(
                  width: 42,
                  height: 5,
                  margin: const EdgeInsets.only(bottom: 16),
                  decoration: BoxDecoration(
                    color: c.border,
                    borderRadius: BorderRadius.circular(999),
                  ),
                ),
              ),
              Text(
                title,
                style: styles.section.copyWith(fontSize: 18),
              ),
              const SizedBox(height: 14),
              for (final option in options)
                Padding(
                  padding: const EdgeInsets.only(bottom: 8),
                  child: Material(
                    color: Colors.transparent,
                    child: InkWell(
                      borderRadius: BorderRadius.circular(18),
                      onTap: () => Navigator.of(sheetContext).pop(option.value),
                      child: Container(
                        width: double.infinity,
                        padding: const EdgeInsets.fromLTRB(14, 14, 14, 14),
                        decoration: BoxDecoration(
                          color: option.destructive ? destructiveBg : c.surfaceMuted,
                          borderRadius: BorderRadius.circular(18),
                          border: Border.all(
                            color: option.destructive ? destructiveBorder : c.border,
                          ),
                        ),
                        child: Row(
                          children: <Widget>[
                            Container(
                              width: 42,
                              height: 42,
                              decoration: BoxDecoration(
                                color: option.destructive ? destructiveIconBg : iconBg,
                                shape: BoxShape.circle,
                              ),
                              child: Icon(
                                option.icon,
                                color: option.destructive ? c.danger : c.primary,
                                size: 20,
                              ),
                            ),
                            const SizedBox(width: 12),
                            Expanded(
                              child: Column(
                                crossAxisAlignment: CrossAxisAlignment.start,
                                children: <Widget>[
                                  Text(
                                    option.title,
                                    style: styles.body.copyWith(
                                      fontSize: 14.2,
                                      color: option.destructive ? c.danger : c.text,
                                      fontWeight: FontWeight.w700,
                                    ),
                                  ),
                                  if ((option.subtitle ?? '').trim().isNotEmpty)
                                    Padding(
                                      padding: const EdgeInsets.only(top: 4),
                                      child: Text(
                                        option.subtitle!,
                                        maxLines: 2,
                                        overflow: TextOverflow.ellipsis,
                                        style: styles.muted.copyWith(
                                          color: option.destructive
                                              ? c.danger
                                              : c.secondaryText,
                                        ),
                                      ),
                                    ),
                                ],
                              ),
                            ),
                            Icon(
                              Icons.chevron_right_rounded,
                              color: option.destructive ? c.danger : c.secondaryText,
                            ),
                          ],
                        ),
                      ),
                    ),
                  ),
                ),
            ],
          ),
        ),
      );
    },
  );
}

ThemeData buildProfileFormTheme(BuildContext context) {
  final base = Theme.of(context);
  final c = ProfileUiColors.of(context);
  return base.copyWith(
    scaffoldBackgroundColor: c.background,
    textSelectionTheme: TextSelectionThemeData(
      cursorColor: c.primary,
      selectionColor: c.primary.withValues(alpha: 0.2),
      selectionHandleColor: c.primary,
    ),
  );
}

InputDecoration profileInputDecoration(
  BuildContext context, {
  required String label,
  required IconData icon,
  String? hintText,
  String? helperText,
}) {
  final c = ProfileUiColors.of(context);
  final styles = ProfileUiTextStyles.of(context);
  return InputDecoration(
    labelText: label,
    hintText: hintText,
    helperText: helperText,
    helperStyle: styles.muted.copyWith(fontSize: 12.5),
    hintStyle: styles.hint,
    prefixIcon: Icon(icon, color: c.primary),
    isDense: true,
    filled: true,
    fillColor: c.card,
    labelStyle: styles.label,
    floatingLabelStyle: styles.label.copyWith(color: c.secondaryText),
    border: OutlineInputBorder(
      borderRadius: BorderRadius.circular(16),
      borderSide: BorderSide(color: c.inputBorder),
    ),
    enabledBorder: OutlineInputBorder(
      borderRadius: BorderRadius.circular(16),
      borderSide: BorderSide(color: c.inputBorder),
    ),
    focusedBorder: OutlineInputBorder(
      borderRadius: BorderRadius.circular(16),
      borderSide: BorderSide(color: c.primary, width: 1.4),
    ),
    errorBorder: OutlineInputBorder(
      borderRadius: BorderRadius.circular(16),
      borderSide: const BorderSide(color: Color(0xFFFF4D4F)),
    ),
    focusedErrorBorder: OutlineInputBorder(
      borderRadius: BorderRadius.circular(16),
      borderSide: const BorderSide(color: Color(0xFFFF4D4F)),
    ),
    contentPadding: const EdgeInsets.symmetric(horizontal: 16, vertical: 14),
  );
}

class _HeaderButton extends StatelessWidget {
  const _HeaderButton({required this.icon, required this.onTap});

  final IconData icon;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    final c = ProfileUiColors.of(context);
    final decos = ProfileUiDecorations.of(context);
    return Material(
      color: c.card,
      borderRadius: BorderRadius.circular(16),
      child: InkWell(
        borderRadius: BorderRadius.circular(16),
        onTap: onTap,
        child: Container(
          width: 46,
          height: 46,
          decoration: BoxDecoration(
            color: c.card,
            borderRadius: BorderRadius.circular(16),
            border: Border.all(color: c.border),
            boxShadow: decos.softShadow,
          ),
          alignment: Alignment.center,
          child: Icon(icon, color: c.text),
        ),
      ),
    );
  }
}
