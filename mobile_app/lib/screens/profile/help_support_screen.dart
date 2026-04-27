import 'package:chaqmoq_mobile/screens/profile/profile_shared.dart';
import 'package:flutter/material.dart';

class HelpSupportScreen extends StatelessWidget {
  const HelpSupportScreen({super.key});

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: ProfileUiColors.background,
      body: SafeArea(
        child: ListView(
          padding: const EdgeInsets.fromLTRB(16, 14, 16, 24),
          children: <Widget>[
            const ProfilePageHeader(title: 'Yordam va qo‘llab-quvvatlash'),
            const SizedBox(height: 18),
            ProfilePageCard(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: <Widget>[
                  Text(
                    'Ko‘p so‘raladigan savollar',
                    style: ProfileUiTextStyles.section,
                  ),
                  const SizedBox(height: 12),
                  const _FaqTile(
                    question: 'Farzand davomatini qayerdan ko‘raman?',
                    answer:
                        'Davomat bo‘limida tanlangan farzandning oylik va kunlik qatnashuv holatini ko‘rishingiz mumkin.',
                  ),
                  const _FaqTile(
                    question: 'To‘lov eslatmalari qayerda chiqadi?',
                    answer:
                        'Bildirishnomalar bo‘limida va to‘lov sahifasida qarzdorlik hamda keyingi to‘lov sanasi ko‘rsatiladi.',
                  ),
                  const _FaqTile(
                    question: 'Farzand qo‘shish ishlamasa nima qilaman?',
                    answer:
                        'Markaz administratori bilan bog‘lanib, sizga berilgan farzand kodini qayta tekshiring.',
                  ),
                ],
              ),
            ),
            const SizedBox(height: 16),
            ProfilePageCard(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: <Widget>[
                  Text('Bog‘lanish', style: ProfileUiTextStyles.section),
                  const SizedBox(height: 10),
                  Text(
                    'Telegram: @chaqmoq_support',
                    style: ProfileUiTextStyles.body,
                  ),
                  const SizedBox(height: 6),
                  Text(
                    'Qo‘llab-quvvatlash telefoni: +998 90 000 00 00',
                    style: ProfileUiTextStyles.body,
                  ),
                  const SizedBox(height: 16),
                  SizedBox(
                    width: double.infinity,
                    child: FilledButton.icon(
                      onPressed: () {
                        ScaffoldMessenger.of(context).showSnackBar(
                          const SnackBar(
                            content: Text(
                              'Markaz administratori bilan bog‘lanish tez orada ulanadi',
                            ),
                          ),
                        );
                      },
                      style: FilledButton.styleFrom(
                        backgroundColor: ProfileUiColors.primary,
                        foregroundColor: Colors.white,
                        padding: const EdgeInsets.symmetric(vertical: 15),
                        shape: RoundedRectangleBorder(
                          borderRadius: BorderRadius.circular(16),
                        ),
                      ),
                      icon: const Icon(Icons.support_agent_rounded),
                      label: Text(
                        'Markaz adminiga yozish',
                        style: ProfileUiTextStyles.button,
                      ),
                    ),
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

class _FaqTile extends StatelessWidget {
  const _FaqTile({required this.question, required this.answer});

  final String question;
  final String answer;

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.only(bottom: 8),
      child: ExpansionTile(
        tilePadding: EdgeInsets.zero,
        childrenPadding: const EdgeInsets.only(bottom: 8),
        iconColor: ProfileUiColors.primary,
        collapsedIconColor: ProfileUiColors.secondaryText,
        title: Text(question, style: ProfileUiTextStyles.body),
        children: <Widget>[
          Align(
            alignment: Alignment.centerLeft,
            child: Text(answer, style: ProfileUiTextStyles.muted),
          ),
        ],
      ),
    );
  }
}
