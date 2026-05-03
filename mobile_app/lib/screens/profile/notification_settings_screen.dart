import 'package:chaqmoq_mobile/providers/app_preferences_provider.dart';
import 'package:chaqmoq_mobile/screens/profile/profile_shared.dart';
import 'package:chaqmoq_mobile/services/api_client.dart';
import 'package:chaqmoq_mobile/services/local_notification_service.dart';
import 'package:chaqmoq_mobile/services/parent_dashboard_service.dart';
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
  bool _loading = true;
  bool _saving = false;
  String? _errorMessage;

  @override
  void initState() {
    super.initState();
    _settings = context.read<AppPreferencesProvider>().notificationSettings;
    WidgetsBinding.instance.addPostFrameCallback((_) => _load());
  }

  Future<void> _load() async {
    setState(() {
      _loading = true;
      _errorMessage = null;
    });
    try {
      final payload = await context
          .read<ParentDashboardService>()
          .fetchNotificationPreferences();
      if (!mounted) {
        return;
      }
      setState(() {
        _settings = NotificationPreferenceSettings(
          attendance: payload['attendance'] ?? true,
          payments: payload['payments'] ?? true,
          progress: payload['progress'] ?? true,
          general: payload['general'] ?? true,
        );
        _loading = false;
      });
    } on ApiException catch (error) {
      if (!mounted) {
        return;
      }
      setState(() {
        _loading = false;
        _errorMessage = error.message;
      });
    } catch (_) {
      if (!mounted) {
        return;
      }
      setState(() {
        _loading = false;
        _errorMessage = 'Bildirishnoma sozlamalari yuklanmadi';
      });
    }
  }

  Future<void> _save() async {
    final notificationService = context.read<LocalNotificationService>();
    final dashboardService = context.read<ParentDashboardService>();
    final preferencesProvider = context.read<AppPreferencesProvider>();
    final messenger = ScaffoldMessenger.of(context);
    final navigator = Navigator.of(context);
    setState(() => _saving = true);
    try {
      if (_settings.attendance ||
          _settings.payments ||
          _settings.progress ||
          _settings.general) {
        await notificationService.ensurePermissions();
      }
      final payload = await dashboardService.updateNotificationPreferences(
        attendance: _settings.attendance,
        payments: _settings.payments,
        progress: _settings.progress,
        general: _settings.general,
      );
      final normalized = NotificationPreferenceSettings(
        attendance: payload['attendance'] ?? _settings.attendance,
        payments: payload['payments'] ?? _settings.payments,
        progress: payload['progress'] ?? _settings.progress,
        general: payload['general'] ?? _settings.general,
      );
      await preferencesProvider.saveNotificationSettings(normalized);
      if (!mounted) {
        return;
      }
      messenger.showSnackBar(
        const SnackBar(content: Text('Bildirishnoma sozlamalari saqlandi')),
      );
      navigator.pop(true);
    } on ApiException catch (error) {
      if (!mounted) {
        return;
      }
      messenger.showSnackBar(SnackBar(content: Text(error.message)));
    } on LocalNotificationException catch (error) {
      if (!mounted) {
        return;
      }
      messenger.showSnackBar(SnackBar(content: Text(error.message)));
    } finally {
      if (mounted) {
        setState(() => _saving = false);
      }
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: ProfileUiColors.of(context).background,
      body: SafeArea(
        child: ListView(
          padding: const EdgeInsets.fromLTRB(16, 14, 16, 24),
          children: <Widget>[
            const ProfilePageHeader(title: 'Bildirishnoma sozlamalari'),
            const SizedBox(height: 18),
            if (_loading)
              Center(
                child: Padding(
                  padding: const EdgeInsets.symmetric(vertical: 24),
                  child: CircularProgressIndicator(
                    color: ProfileUiColors.of(context).primary,
                  ),
                ),
              )
            else if (_errorMessage != null)
              ProfilePageCard(
                child: Column(
                  children: <Widget>[
                    Text(
                      'Sozlamalar yuklanmadi',
                      style: ProfileUiTextStyles.of(context).section,
                    ),
                    const SizedBox(height: 8),
                    Text(
                      _errorMessage!,
                      textAlign: TextAlign.center,
                      style: ProfileUiTextStyles.of(context).muted,
                    ),
                    const SizedBox(height: 16),
                    FilledButton(
                      onPressed: _load,
                      style: FilledButton.styleFrom(
                        backgroundColor: ProfileUiColors.of(context).primary,
                      ),
                      child: const Text('Qayta urinish'),
                    ),
                  ],
                ),
              )
            else ...<Widget>[
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
                  Divider(height: 1, color: ProfileUiColors.of(context).border),
                  _NotificationTile(
                    title: 'To‘lov eslatmalari',
                    value: _settings.payments,
                    onChanged: (bool value) {
                      setState(() {
                        _settings = _settings.copyWith(payments: value);
                      });
                    },
                  ),
                  Divider(height: 1, color: ProfileUiColors.of(context).border),
                  _NotificationTile(
                    title: 'Progress xabarnomalari',
                    value: _settings.progress,
                    onChanged: (bool value) {
                      setState(() {
                        _settings = _settings.copyWith(progress: value);
                      });
                    },
                  ),
                  Divider(height: 1, color: ProfileUiColors.of(context).border),
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
                onPressed: _saving ? null : _save,
                style: FilledButton.styleFrom(
                  backgroundColor: ProfileUiColors.of(context).primary,
                  foregroundColor: Colors.white,
                  padding: const EdgeInsets.symmetric(vertical: 15),
                  shape: RoundedRectangleBorder(
                    borderRadius: BorderRadius.circular(16),
                  ),
                ),
                child: _saving
                    ? const SizedBox(
                        width: 20,
                        height: 20,
                        child: CircularProgressIndicator(
                          strokeWidth: 2.2,
                          color: Colors.white,
                        ),
                      )
                    : Text('Saqlash', style: ProfileUiTextStyles.of(context).button),
              ),
            ),
            ],
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
      activeThumbColor: ProfileUiColors.of(context).primary,
      activeTrackColor: const Color(0xFFD9E8FF),
      contentPadding: const EdgeInsets.symmetric(horizontal: 14, vertical: 4),
      title: Text(title, style: ProfileUiTextStyles.of(context).section),
      subtitle: Text(
        value ? 'Yoqilgan' : 'O‘chirilgan',
        style: ProfileUiTextStyles.of(context).muted,
      ),
    );
  }
}
