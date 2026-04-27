import 'package:chaqmoq_mobile/providers/app_preferences_provider.dart';
import 'package:chaqmoq_mobile/screens/profile/profile_shared.dart';
import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

class LanguageScreen extends StatelessWidget {
  const LanguageScreen({super.key});

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
            const ProfilePageHeader(title: 'Til'),
            const SizedBox(height: 18),
            ProfilePageCard(
              padding: EdgeInsets.zero,
              child: Column(
                children: <Widget>[
                  _LanguageOption(
                    title: 'O‘zbekcha',
                    value: AppLanguage.uzbek,
                    groupValue: preferences.language,
                  ),
                  const Divider(height: 1, color: ProfileUiColors.border),
                  _LanguageOption(
                    title: 'Русский',
                    value: AppLanguage.russian,
                    groupValue: preferences.language,
                  ),
                  const Divider(height: 1, color: ProfileUiColors.border),
                  _LanguageOption(
                    title: 'English',
                    value: AppLanguage.english,
                    groupValue: preferences.language,
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

class _LanguageOption extends StatelessWidget {
  const _LanguageOption({
    required this.title,
    required this.value,
    required this.groupValue,
  });

  final String title;
  final AppLanguage value;
  final AppLanguage groupValue;

  @override
  Widget build(BuildContext context) {
    final bool selected = value == groupValue;
    return ListTile(
      contentPadding: const EdgeInsets.symmetric(horizontal: 14, vertical: 4),
      onTap: () async {
        await context.read<AppPreferencesProvider>().setLanguage(value);
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
