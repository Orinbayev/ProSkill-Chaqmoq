import 'package:flutter/material.dart';
import 'package:google_fonts/google_fonts.dart';

class ProfileUiColors {
  const ProfileUiColors._();

  static const Color background = Color(0xFFF7FBFF);
  static const Color card = Color(0xFFFFFFFF);
  static const Color primary = Color(0xFF1E73F8);
  static const Color text = Color(0xFF111827);
  static const Color secondaryText = Color(0xFF6B7280);
  static const Color hint = Color(0xFF9CA3AF);
  static const Color border = Color(0xFFE5EAF2);
  static const Color inputBorder = Color(0xFFDDE5F0);
  static const Color danger = Color(0xFFEF4444);
}

class ProfileUiTextStyles {
  const ProfileUiTextStyles._();

  static TextStyle get title => GoogleFonts.inter(
    fontSize: 22,
    fontWeight: FontWeight.w800,
    color: ProfileUiColors.text,
  );

  static TextStyle get section => GoogleFonts.inter(
    fontSize: 16,
    fontWeight: FontWeight.w700,
    color: ProfileUiColors.text,
  );

  static TextStyle get body => GoogleFonts.inter(
    fontSize: 14,
    fontWeight: FontWeight.w500,
    height: 1.45,
    color: ProfileUiColors.text,
  );

  static TextStyle get input => GoogleFonts.inter(
    fontSize: 15,
    fontWeight: FontWeight.w500,
    color: ProfileUiColors.text,
  );

  static TextStyle get label => GoogleFonts.inter(
    fontSize: 13.5,
    fontWeight: FontWeight.w500,
    color: ProfileUiColors.secondaryText,
  );

  static TextStyle get hint => GoogleFonts.inter(
    fontSize: 14.5,
    fontWeight: FontWeight.w500,
    color: ProfileUiColors.hint,
  );

  static TextStyle get muted => GoogleFonts.inter(
    fontSize: 13.5,
    fontWeight: FontWeight.w500,
    height: 1.4,
    color: ProfileUiColors.secondaryText,
  );

  static TextStyle get button => GoogleFonts.inter(
    fontSize: 14.5,
    fontWeight: FontWeight.w700,
    color: Colors.white,
  );
}

class ProfileUiDecorations {
  const ProfileUiDecorations._();

  static const List<BoxShadow> softShadow = <BoxShadow>[
    BoxShadow(color: Color(0x0F0B1220), blurRadius: 18, offset: Offset(0, 8)),
  ];

  static BoxDecoration get cardDecoration => const BoxDecoration(
    color: ProfileUiColors.card,
    borderRadius: BorderRadius.all(Radius.circular(20)),
    border: Border.fromBorderSide(BorderSide(color: ProfileUiColors.border)),
    boxShadow: softShadow,
  );
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
            style: ProfileUiTextStyles.title,
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
      decoration: ProfileUiDecorations.cardDecoration,
      child: child,
    );
  }
}

ThemeData buildProfileFormTheme(BuildContext context) {
  final base = Theme.of(context);
  return base.copyWith(
    brightness: Brightness.light,
    scaffoldBackgroundColor: ProfileUiColors.background,
    textSelectionTheme: const TextSelectionThemeData(
      cursorColor: ProfileUiColors.primary,
      selectionColor: Color(0x331E73F8),
      selectionHandleColor: ProfileUiColors.primary,
    ),
  );
}

InputDecoration profileInputDecoration({
  required String label,
  required IconData icon,
  String? hintText,
  String? helperText,
}) {
  return InputDecoration(
    labelText: label,
    hintText: hintText,
    helperText: helperText,
    helperStyle: ProfileUiTextStyles.muted.copyWith(fontSize: 12.5),
    hintStyle: ProfileUiTextStyles.hint,
    prefixIcon: Icon(icon, color: ProfileUiColors.primary),
    filled: true,
    fillColor: ProfileUiColors.card,
    labelStyle: ProfileUiTextStyles.label,
    floatingLabelStyle: ProfileUiTextStyles.label.copyWith(
      color: ProfileUiColors.secondaryText,
    ),
    border: OutlineInputBorder(
      borderRadius: BorderRadius.circular(16),
      borderSide: const BorderSide(color: ProfileUiColors.inputBorder),
    ),
    enabledBorder: OutlineInputBorder(
      borderRadius: BorderRadius.circular(16),
      borderSide: const BorderSide(color: ProfileUiColors.inputBorder),
    ),
    focusedBorder: OutlineInputBorder(
      borderRadius: BorderRadius.circular(16),
      borderSide: const BorderSide(
        color: ProfileUiColors.primary,
        width: 1.4,
      ),
    ),
    errorBorder: OutlineInputBorder(
      borderRadius: BorderRadius.circular(16),
      borderSide: const BorderSide(color: Color(0xFFFF4D4F)),
    ),
    focusedErrorBorder: OutlineInputBorder(
      borderRadius: BorderRadius.circular(16),
      borderSide: const BorderSide(color: Color(0xFFFF4D4F)),
    ),
    contentPadding: const EdgeInsets.symmetric(horizontal: 16, vertical: 16),
  );
}

class _HeaderButton extends StatelessWidget {
  const _HeaderButton({required this.icon, required this.onTap});

  final IconData icon;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    return Material(
      color: Colors.white,
      borderRadius: BorderRadius.circular(16),
      child: InkWell(
        borderRadius: BorderRadius.circular(16),
        onTap: onTap,
        child: Container(
          width: 46,
          height: 46,
          decoration: BoxDecoration(
            borderRadius: BorderRadius.circular(16),
            border: Border.all(color: ProfileUiColors.border),
            boxShadow: ProfileUiDecorations.softShadow,
          ),
          alignment: Alignment.center,
          child: Icon(icon, color: ProfileUiColors.text),
        ),
      ),
    );
  }
}
