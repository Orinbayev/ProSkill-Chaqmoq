import 'package:chaqmoq_mobile/providers/app_preferences_provider.dart';
import 'package:chaqmoq_mobile/screens/profile/profile_shared.dart';
import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

class NotificationSettingsScreen extends StatefulWidget {
  const NotificationSettingsScreen({super.key});

  @override
  State<NotificationSettingsScreen> createState() =>
      _NotificationSettingsScreenState();
}

class _NotificationSettingsScreenState
    extends State<NotificationSettingsScreen> {
  late NotificationPreferenceSettings _settings;

  @override
  void initState() {
    super.initState();
    _settings = context.read<AppPreferencesProvider>().notificationSettings;
  }

  Future<void> _save() async {
    await context.read<AppPreferencesProvider>().saveNotificationSettings(
      _settings,
    );
    if (!mounted) {
      return;
    }
    ScaffoldMessenger.of(context).showSnackBar(
      const SnackBar(content: Text('Bildirishnoma sozlamalari saqlandi')),
    );
    Navigator.of(context).pop(true);
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: ProfileUiColors.background,
      body: SafeArea(
        child: ListView(
          padding: const EdgeInsets.fromLTRB(16, 14, 16, 24),
          children: <Widget>[
            const ProfilePageHeader(title: 'Bildirishnoma sozlamalari'),
            const SizedBox(height: 18),
            ProfilePageCard(
              padding: EdgeInsets.zero,
              child: Column(
                children: <Widget>[
                  _NotificationTile(
                    title: 'Davomat bildirishnomalari',
                    value: _settings.attendance,
                    onChanged: (bool value) {
                      setState(() {
                        _settings = _settings.copyWith(attendance: value);
                      });
                    },
                  ),
                  const Divider(height: 1, color: ProfileUiColors.border),
                  _NotificationTile(
                    title: 'To‘lov eslatmalari',
                    value: _settings.payments,
                    onChanged: (bool value) {
                      setState(() {
                        _settings = _settings.copyWith(payments: value);
                      });
                    },
                  ),
                  const Divider(height: 1, color: ProfileUiColors.border),
                  _NotificationTile(
                    title: 'Baholar bildirishnomalari',
                    value: _settings.grades,
                    onChanged: (bool value) {
                      setState(() {
                        _settings = _settings.copyWith(grades: value);
                      });
                    },
                  ),
                  const Divider(height: 1, color: ProfileUiColors.border),
                  _NotificationTile(
                    title: 'Umumiy bildirishnomalar',
                    value: _settings.general,
                    onChanged: (bool value) {
                      setState(() {
                        _settings = _settings.copyWith(general: value);
                      });
                    },
                  ),
                ],
              ),
            ),
            const SizedBox(height: 18),
            SizedBox(
              width: double.infinity,
              child: FilledButton(
                onPressed: _save,
                style: FilledButton.styleFrom(
                  backgroundColor: ProfileUiColors.primary,
                  foregroundColor: Colors.white,
                  padding: const EdgeInsets.symmetric(vertical: 15),
                  shape: RoundedRectangleBorder(
                    borderRadius: BorderRadius.circular(16),
                  ),
                ),
                child: Text('Saqlash', style: ProfileUiTextStyles.button),
              ),
            ),
          ],
        ),
      ),
    );
  }
}

class _NotificationTile extends StatelessWidget {
  const _NotificationTile({
    required this.title,
    required this.value,
    required this.onChanged,
  });

  final String title;
  final bool value;
  final ValueChanged<bool> onChanged;

  @override
  Widget build(BuildContext context) {
    return SwitchListTile(
      value: value,
      onChanged: onChanged,
      activeThumbColor: ProfileUiColors.primary,
      activeTrackColor: const Color(0xFFD9E8FF),
      contentPadding: const EdgeInsets.symmetric(horizontal: 14, vertical: 4),
      title: Text(title, style: ProfileUiTextStyles.section),
      subtitle: Text(
        value ? 'Yoqilgan' : 'O‘chirilgan',
        style: ProfileUiTextStyles.muted,
      ),
    );
  }
}
