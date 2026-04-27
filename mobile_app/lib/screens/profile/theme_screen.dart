import 'package:chaqmoq_mobile/providers/app_preferences_provider.dart';
import 'package:chaqmoq_mobile/screens/profile/profile_shared.dart';
import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

class ThemeScreen extends StatelessWidget {
  const ThemeScreen({super.key});

  @override
  Widget build(BuildContext context) {
    final AppPreferencesProvider preferences = context
        .watch<AppPreferencesProvider>();
    return Scaffold(
      backgroundColor: ProfileUiColors.background,
      body: SafeArea(
        child: ListView(
          padding: const EdgeInsets.fromLTRB(16, 14, 16, 24),
          children: <Widget>[
            const ProfilePageHeader(title: 'Mavzu'),
            const SizedBox(height: 18),
            ProfilePageCard(
              padding: EdgeInsets.zero,
              child: Column(
                children: <Widget>[
                  _ThemeOption(
                    title: 'Tizim bo‘yicha',
                    value: AppThemePreference.system,
                    groupValue: preferences.themePreference,
                  ),
                  const Divider(height: 1, color: ProfileUiColors.border),
                  _ThemeOption(
                    title: 'Light',
                    value: AppThemePreference.light,
                    groupValue: preferences.themePreference,
                  ),
                  const Divider(height: 1, color: ProfileUiColors.border),
                  _ThemeOption(
                    title: 'Dark',
                    value: AppThemePreference.dark,
                    groupValue: preferences.themePreference,
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

class _ThemeOption extends StatelessWidget {
  const _ThemeOption({
    required this.title,
    required this.value,
    required this.groupValue,
  });

  final String title;
  final AppThemePreference value;
  final AppThemePreference groupValue;

  @override
  Widget build(BuildContext context) {
    final bool selected = value == groupValue;
    return ListTile(
      contentPadding: const EdgeInsets.symmetric(horizontal: 14, vertical: 4),
      onTap: () async {
        await context.read<AppPreferencesProvider>().setThemePreference(value);
        if (!context.mounted) {
          return;
        }
        Navigator.of(context).pop(true);
      },
      title: Text(title, style: ProfileUiTextStyles.section),
      trailing: Icon(
        selected ? Icons.check_circle_rounded : Icons.circle_outlined,
        color: selected
            ? ProfileUiColors.primary
            : ProfileUiColors.secondaryText,
      ),
    );
  }
}
