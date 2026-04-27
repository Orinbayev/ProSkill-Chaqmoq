import 'package:chaqmoq_mobile/providers/app_preferences_provider.dart';
import 'package:flutter/material.dart';
import 'package:google_fonts/google_fonts.dart';
import 'package:provider/provider.dart';

class SettingsScreen extends StatelessWidget {
  const SettingsScreen({super.key});

  @override
  Widget build(BuildContext context) {
    final preferences = context.watch<AppPreferencesProvider>();
    return Scaffold(
      backgroundColor: const Color(0xFFF7FBFF),
      body: SafeArea(
        child: ListView(
          padding: const EdgeInsets.fromLTRB(16, 14, 16, 24),
          children: [
            Row(
              children: [
                _HeaderButton(
                  icon: Icons.arrow_back_rounded,
                  onTap: () => Navigator.of(context).pop(),
                ),
                const SizedBox(width: 12),
                Text('Sozlamalar', style: _SettingsTextStyles.title),
              ],
            ),
            const SizedBox(height: 18),
            Container(
              padding: const EdgeInsets.all(18),
              decoration: _cardDecoration,
              child: Column(
                children: [
                  _SettingsRow(
                    icon: Icons.language_rounded,
                    title: 'Til',
                    subtitle: preferences.languageLabel,
                  ),
                  const Divider(height: 24, color: _SettingsColors.border),
                  _SettingsRow(
                    icon: Icons.palette_outlined,
                    title: 'Mavzu',
                    subtitle: preferences.themeLabel,
                  ),
                  const Divider(height: 24, color: _SettingsColors.border),
                  const _SettingsRow(
                    icon: Icons.notifications_none_rounded,
                    title: 'Bildirishnomalar',
                    subtitle: 'Yoqilgan',
                  ),
                  const Divider(height: 24, color: _SettingsColors.border),
                  const _SettingsRow(
                    icon: Icons.info_outline_rounded,
                    title: 'Ilova versiyasi',
                    subtitle: '1.0.0+1',
                  ),
                ],
              ),
            ),
          ],
        ),
      ),
    );
  }
}

class _SettingsRow extends StatelessWidget {
  const _SettingsRow({
    required this.icon,
    required this.title,
    required this.subtitle,
  });

  final IconData icon;
  final String title;
  final String subtitle;

  @override
  Widget build(BuildContext context) {
    return Row(
      children: [
        Container(
          width: 44,
          height: 44,
          decoration: BoxDecoration(
            color: const Color(0xFFEAF4FF),
            borderRadius: BorderRadius.circular(14),
          ),
          alignment: Alignment.center,
          child: Icon(icon, color: _SettingsColors.accentBlue),
        ),
        const SizedBox(width: 14),
        Expanded(
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text(title, style: _SettingsTextStyles.rowTitle),
              const SizedBox(height: 3),
              Text(subtitle, style: _SettingsTextStyles.subtitle),
            ],
          ),
        ),
      ],
    );
  }
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
            border: Border.all(color: _SettingsColors.border),
            boxShadow: const [
              BoxShadow(
                color: Color(0x0F0B1220),
                blurRadius: 18,
                offset: Offset(0, 8),
              ),
            ],
          ),
          alignment: Alignment.center,
          child: Icon(icon, color: _SettingsColors.text),
        ),
      ),
    );
  }
}

const BoxDecoration _cardDecoration = BoxDecoration(
  color: Colors.white,
  borderRadius: BorderRadius.all(Radius.circular(20)),
  border: Border.fromBorderSide(BorderSide(color: _SettingsColors.border)),
  boxShadow: [
    BoxShadow(color: Color(0x0F0B1220), blurRadius: 18, offset: Offset(0, 8)),
  ],
);

class _SettingsColors {
  const _SettingsColors._();

  static const Color text = Color(0xFF111827);
  static const Color subtitle = Color(0xFF6B7280);
  static const Color accentBlue = Color(0xFF1E73F8);
  static const Color border = Color(0xFFE5EAF2);
}

class _SettingsTextStyles {
  const _SettingsTextStyles._();

  static TextStyle get title => GoogleFonts.inter(
    fontSize: 22,
    fontWeight: FontWeight.w800,
    color: _SettingsColors.text,
  );

  static TextStyle get rowTitle => GoogleFonts.inter(
    fontSize: 15,
    fontWeight: FontWeight.w700,
    color: _SettingsColors.text,
  );

  static TextStyle get subtitle => GoogleFonts.inter(
    fontSize: 13.5,
    fontWeight: FontWeight.w500,
    color: _SettingsColors.subtitle,
  );
}
