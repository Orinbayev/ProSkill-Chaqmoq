import 'package:chaqmoq_mobile/screens/profile/profile_shared.dart';
import 'package:flutter/material.dart';

class AboutAppScreen extends StatelessWidget {
  const AboutAppScreen({super.key});

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: ProfileUiColors.of(context).background,
      body: SafeArea(
        child: ListView(
          padding: const EdgeInsets.fromLTRB(16, 14, 16, 24),
          children: <Widget>[
            const ProfilePageHeader(title: 'Ilova haqida'),
            const SizedBox(height: 18),
            ProfilePageCard(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: <Widget>[
                  Text('ChaqmoqApp', style: ProfileUiTextStyles.of(context).title),
                  const SizedBox(height: 6),
                  Text('Versiya 1.0.0', style: ProfileUiTextStyles.of(context).muted),
                  const SizedBox(height: 14),
                  Text(
                    'ChaqmoqApp ota-onalar uchun farzand davomatini, to‘lovlarini, yutuqlarini va bildirishnomalarni qulay kuzatish imkonini beradi.',
                    style: ProfileUiTextStyles.of(context).body,
                  ),
                ],
              ),
            ),
            const SizedBox(height: 16),
            ProfilePageCard(
              padding: EdgeInsets.zero,
              child: Column(
                children: <Widget>[
                  const _InfoRow(
                    title: 'Maxfiylik siyosati',
                    subtitle: 'Tez orada to‘liq matn joylanadi',
                  ),
                  Divider(height: 1, color: ProfileUiColors.of(context).border),
                  const _InfoRow(
                    title: 'Foydalanish shartlari',
                    subtitle: 'Tez orada to‘liq matn joylanadi',
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

class _InfoRow extends StatelessWidget {
  const _InfoRow({required this.title, required this.subtitle});

  final String title;
  final String subtitle;

  @override
  Widget build(BuildContext context) {
    return ListTile(
      contentPadding: const EdgeInsets.symmetric(horizontal: 14, vertical: 4),
      title: Text(title, style: ProfileUiTextStyles.of(context).section),
      subtitle: Text(subtitle, style: ProfileUiTextStyles.of(context).muted),
      trailing: Icon(
        Icons.chevron_right_rounded,
        color: ProfileUiColors.of(context).secondaryText,
      ),
    );
  }
}
