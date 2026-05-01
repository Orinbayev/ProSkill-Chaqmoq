import 'package:chaqmoq_mobile/models/app_models.dart';
import 'package:chaqmoq_mobile/providers/auth_provider.dart';
import 'package:chaqmoq_mobile/providers/notifications_provider.dart';
import 'package:chaqmoq_mobile/screens/groups/groups_screen.dart';
import 'package:chaqmoq_mobile/screens/notifications/notification_presenter.dart';
import 'package:chaqmoq_mobile/screens/payments/payments_screen.dart';
import 'package:chaqmoq_mobile/screens/students/students_screen.dart';
import 'package:chaqmoq_mobile/screens/student/student_payments_screen.dart';
import 'package:flutter/material.dart';
import 'package:google_fonts/google_fonts.dart';
import 'package:provider/provider.dart';

class NotificationsScreen extends StatefulWidget {
  const NotificationsScreen({super.key});

  @override
  State<NotificationsScreen> createState() => _NotificationsScreenState();
}

class _NotificationsScreenState extends State<NotificationsScreen> {
  bool _loaded = false;

  @override
  void didChangeDependencies() {
    super.didChangeDependencies();
    if (_loaded) {
      return;
    }
    _loaded = true;
    WidgetsBinding.instance.addPostFrameCallback((_) {
      if (mounted) {
        context.read<NotificationsProvider>().load();
      }
    });
  }

  @override
  Widget build(BuildContext context) {
    final provider = context.watch<NotificationsProvider>();
    final items = provider.items;

    return ColoredBox(
      color: _NotificationsColors.background,
      child: RefreshIndicator(
        color: _NotificationsColors.accentBlue,
        onRefresh: provider.refresh,
        child: ListView(
          physics: const AlwaysScrollableScrollPhysics(
            parent: BouncingScrollPhysics(),
          ),
          padding: const EdgeInsets.fromLTRB(14, 14, 14, 24),
          children: [
            _NotificationsHeader(
              unreadCount: provider.unreadCount,
              canMarkAllRead: items.isNotEmpty && provider.unreadCount > 0,
              onMarkAllRead: () => _markAllRead(provider),
            ),
            if (provider.state == ViewState.loading && items.isNotEmpty) ...[
              const SizedBox(height: 12),
              const LinearProgressIndicator(
                minHeight: 3,
                color: _NotificationsColors.accentBlue,
                backgroundColor: Color(0xFFEAF4FF),
              ),
            ],
            const SizedBox(height: 14),
            if (provider.state == ViewState.loading && items.isEmpty)
              const _NotificationsStateCard.loading()
            else if (provider.state == ViewState.error && items.isEmpty)
              _NotificationsStateCard(
                title: 'Bildirishnomalar yuklanmadi',
                message:
                    provider.errorMessage ??
                    'Server bilan aloqa uzildi. Qayta urinib ko‘ring.',
                icon: Icons.notifications_off_rounded,
                actionLabel: 'Qayta yuklash',
                onAction: provider.refresh,
              )
            else if (items.isEmpty)
              const _NotificationsStateCard(
                title: 'Hozircha bildirishnomalar yo‘q',
                message: 'Yangi xabar yoki ogohlantirish kelganda shu yerda paydo bo‘ladi.',
                icon: Icons.mark_email_read_rounded,
              )
            else
              ...items.map(
                (item) => Padding(
                  padding: const EdgeInsets.only(bottom: 10),
                  child: _NotificationCard(
                    item: item,
                    onTap: () => _openNotification(provider, item),
                  ),
                ),
              ),
          ],
        ),
      ),
    );
  }

  Future<void> _markAllRead(NotificationsProvider provider) async {
    await provider.markAllRead();
    if (!mounted) {
      return;
    }
    ScaffoldMessenger.of(context).showSnackBar(
      const SnackBar(
        content: Text('Barcha bildirishnomalar o‘qildi deb belgilandi'),
      ),
    );
  }

  Future<void> _openNotification(
    NotificationsProvider provider,
    NotificationModel item,
  ) async {
    await provider.markRead(item);
    if (!mounted) {
      return;
    }
    final role = context.read<AuthProvider>().user?.role.trim().toLowerCase();
    final resolvedItem = item.copyWith(isRead: true);
    final target = _targetForNotification(resolvedItem, role);
    final shouldNavigate = await showModalBottomSheet<bool>(
      context: context,
      backgroundColor: Colors.transparent,
      isScrollControlled: true,
      builder: (_) => _NotificationDetailSheet(
        item: resolvedItem,
        actionLabel: _actionLabelFor(target),
      ),
    );

    if (shouldNavigate == true && mounted) {
      _navigateToTarget(target, role);
    }
  }

  _NotificationTarget? _targetForNotification(
    NotificationModel item,
    String? role,
  ) {
    final kind = resolveNotificationKind(item);
    final lower = '${item.type} ${item.target} ${item.title} ${item.body}'
        .toLowerCase()
        .replaceAll('’', "'")
        .replaceAll('‘', "'");
    if (kind == NotificationKind.payment) {
      return role == 'student'
          ? _NotificationTarget.studentPayments
          : _NotificationTarget.payments;
    }
    if ((lower.contains('student') || lower.contains("o'quvchi")) &&
        role != 'student' &&
        role != 'parent') {
      return _NotificationTarget.students;
    }
    if (lower.contains('group') && role != 'student' && role != 'parent') {
      return _NotificationTarget.groups;
    }
    return null;
  }

  String? _actionLabelFor(_NotificationTarget? target) {
    switch (target) {
      case _NotificationTarget.payments:
      case _NotificationTarget.studentPayments:
        return 'To‘lovlar bo‘limiga o‘tish';
      case _NotificationTarget.students:
        return 'O‘quvchilar bo‘limiga o‘tish';
      case _NotificationTarget.groups:
        return 'Guruhlar bo‘limiga o‘tish';
      case null:
        return null;
    }
  }

  void _navigateToTarget(_NotificationTarget? target, String? role) {
    switch (target) {
      case _NotificationTarget.payments:
        Navigator.of(
          context,
        ).push(MaterialPageRoute<void>(builder: (_) => const PaymentsScreen()));
        return;
      case _NotificationTarget.studentPayments:
        Navigator.of(context).push(
          MaterialPageRoute<void>(builder: (_) => const StudentPaymentsScreen()),
        );
        return;
      case _NotificationTarget.students:
        if (role != 'student' && role != 'parent') {
          Navigator.of(context).push(
            MaterialPageRoute<void>(builder: (_) => const StudentsScreen()),
          );
        }
        return;
      case _NotificationTarget.groups:
        if (role != 'student' && role != 'parent') {
          Navigator.of(
            context,
          ).push(MaterialPageRoute<void>(builder: (_) => const GroupsScreen()));
        }
        return;
      case null:
        return;
    }
  }
}

enum _NotificationTarget { payments, studentPayments, students, groups }

class _NotificationsHeader extends StatelessWidget {
  const _NotificationsHeader({
    required this.unreadCount,
    required this.canMarkAllRead,
    required this.onMarkAllRead,
  });

  final int unreadCount;
  final bool canMarkAllRead;
  final VoidCallback onMarkAllRead;

  @override
  Widget build(BuildContext context) {
    final badgeLabel = unreadCount > 99 ? '99+' : '$unreadCount';
    return Container(
      padding: const EdgeInsets.fromLTRB(16, 16, 16, 14),
      decoration: _cardDecoration(),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Container(
                width: 46,
                height: 46,
                decoration: BoxDecoration(
                  color: const Color(0xFFEAF4FF),
                  borderRadius: BorderRadius.circular(16),
                ),
                child: const Icon(
                  Icons.notifications_active_rounded,
                  color: _NotificationsColors.accentBlue,
                  size: 24,
                ),
              ),
              const SizedBox(width: 12),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      'Bildirishnomalar',
                      style: _NotificationsTextStyles.title,
                    ),
                    const SizedBox(height: 4),
                    Text(
                      'Yangi xabarlar va muhim ogohlantirishlar shu yerda jamlanadi.',
                      style: _NotificationsTextStyles.subtitle,
                    ),
                  ],
                ),
              ),
              Container(
                padding: const EdgeInsets.symmetric(
                  horizontal: 10,
                  vertical: 6,
                ),
                decoration: BoxDecoration(
                  color: const Color(0xFFEAF4FF),
                  borderRadius: BorderRadius.circular(999),
                ),
                child: Text(badgeLabel, style: _NotificationsTextStyles.badge),
              ),
            ],
          ),
          const SizedBox(height: 12),
          Align(
            alignment: Alignment.centerRight,
            child: TextButton.icon(
              onPressed: canMarkAllRead ? onMarkAllRead : null,
              style: TextButton.styleFrom(
                foregroundColor: _NotificationsColors.accentBlue,
                disabledForegroundColor: const Color(0xFF9AA4B2),
                padding: const EdgeInsets.symmetric(
                  horizontal: 10,
                  vertical: 9,
                ),
                shape: RoundedRectangleBorder(
                  borderRadius: BorderRadius.circular(14),
                ),
              ),
              icon: const Icon(Icons.done_all_rounded, size: 18),
              label: Text(
                'Barchasini o‘qildi',
                style: _NotificationsTextStyles.action,
              ),
            ),
          ),
        ],
      ),
    );
  }
}

class _NotificationCard extends StatelessWidget {
  const _NotificationCard({required this.item, required this.onTap});

  final NotificationModel item;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    final presentation = buildNotificationPresentation(item);
    final accent = item.isRead
        ? presentation.accentColor.withOpacity(0.28)
        : presentation.accentColor;

    return Material(
      color: Colors.transparent,
      child: InkWell(
        borderRadius: BorderRadius.circular(20),
        onTap: onTap,
        child: Container(
          decoration: _cardDecoration(
            borderColor: item.isRead
                ? _NotificationsColors.border
                : presentation.accentColor.withOpacity(0.2),
          ),
          child: Row(
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: [
              Container(
                width: 4,
                decoration: BoxDecoration(
                  color: accent,
                  borderRadius: const BorderRadius.horizontal(
                    left: Radius.circular(20),
                  ),
                ),
              ),
              Expanded(
                child: Padding(
                  padding: const EdgeInsets.fromLTRB(14, 14, 12, 14),
                  child: Row(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Container(
                        width: 44,
                        height: 44,
                        decoration: BoxDecoration(
                          color: presentation.iconBackground,
                          borderRadius: BorderRadius.circular(15),
                        ),
                        alignment: Alignment.center,
                        child: Icon(
                          presentation.icon,
                          color: presentation.iconColor,
                          size: 22,
                        ),
                      ),
                      const SizedBox(width: 12),
                      Expanded(
                        child: Column(
                          crossAxisAlignment: CrossAxisAlignment.start,
                          children: [
                            Row(
                              crossAxisAlignment: CrossAxisAlignment.start,
                              children: [
                                Expanded(
                                  child: Text(
                                    presentation.title,
                                    maxLines: 2,
                                    overflow: TextOverflow.ellipsis,
                                    style: _NotificationsTextStyles.cardTitle,
                                  ),
                                ),
                                const SizedBox(width: 8),
                                _StatePill(
                                  label: item.isRead ? 'O‘qilgan' : 'Yangi',
                                  backgroundColor: item.isRead
                                      ? const Color(0xFFF3F6FB)
                                      : presentation.iconBackground,
                                  foregroundColor: item.isRead
                                      ? _NotificationsColors.secondaryText
                                      : presentation.iconColor,
                                ),
                              ],
                            ),
                            const SizedBox(height: 6),
                            Text(
                              presentation.description,
                              maxLines: 3,
                              overflow: TextOverflow.ellipsis,
                              style: _NotificationsTextStyles.cardBody,
                            ),
                            if ((presentation.reason ?? '').trim().isNotEmpty) ...[
                              const SizedBox(height: 8),
                              Row(
                                crossAxisAlignment: CrossAxisAlignment.start,
                                children: [
                                  Icon(
                                    Icons.info_outline_rounded,
                                    size: 15,
                                    color: presentation.iconColor,
                                  ),
                                  const SizedBox(width: 6),
                                  Expanded(
                                    child: Text(
                                      'Sabab: ${presentation.reason}',
                                      maxLines: 2,
                                      overflow: TextOverflow.ellipsis,
                                      style: _NotificationsTextStyles.reason,
                                    ),
                                  ),
                                ],
                              ),
                            ],
                            const SizedBox(height: 10),
                            Wrap(
                              spacing: 8,
                              runSpacing: 8,
                              children: [
                                _MetaChip(
                                  icon: Icons.schedule_rounded,
                                  label: presentation.timeLabel,
                                ),
                                _MetaChip(
                                  icon: Icons.sell_outlined,
                                  label: presentation.typeLabel,
                                  foregroundColor: presentation.iconColor,
                                  backgroundColor: presentation.iconBackground,
                                ),
                                if ((presentation.childName ?? '').trim().isNotEmpty)
                                  _MetaChip(
                                    icon: Icons.person_outline_rounded,
                                    label: presentation.childName!,
                                  ),
                              ],
                            ),
                          ],
                        ),
                      ),
                      const SizedBox(width: 8),
                      Icon(
                        Icons.chevron_right_rounded,
                        size: 20,
                        color: _NotificationsColors.secondaryText.withOpacity(0.7),
                      ),
                    ],
                  ),
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }
}

class _NotificationDetailSheet extends StatelessWidget {
  const _NotificationDetailSheet({
    required this.item,
    required this.actionLabel,
  });

  final NotificationModel item;
  final String? actionLabel;

  @override
  Widget build(BuildContext context) {
    final presentation = buildNotificationPresentation(item);
    return SafeArea(
      top: false,
      child: Container(
        margin: const EdgeInsets.all(12),
        padding: const EdgeInsets.fromLTRB(16, 12, 16, 16),
        decoration: BoxDecoration(
          color: Colors.white,
          borderRadius: BorderRadius.circular(24),
          boxShadow: const [
            BoxShadow(
              color: Color(0x1A0B1220),
              blurRadius: 24,
              offset: Offset(0, 12),
            ),
          ],
        ),
        child: SingleChildScrollView(
          child: Column(
            mainAxisSize: MainAxisSize.min,
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Center(
                child: Container(
                  width: 42,
                  height: 5,
                  margin: const EdgeInsets.only(bottom: 14),
                  decoration: BoxDecoration(
                    color: const Color(0xFFD8E0EC),
                    borderRadius: BorderRadius.circular(999),
                  ),
                ),
              ),
              Row(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Container(
                    width: 48,
                    height: 48,
                    decoration: BoxDecoration(
                      color: presentation.iconBackground,
                      borderRadius: BorderRadius.circular(16),
                    ),
                    alignment: Alignment.center,
                    child: Icon(
                      presentation.icon,
                      color: presentation.iconColor,
                      size: 24,
                    ),
                  ),
                  const SizedBox(width: 12),
                  Expanded(
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Text(
                          presentation.title,
                          style: _NotificationsTextStyles.sheetTitle,
                        ),
                        const SizedBox(height: 6),
                        Wrap(
                          spacing: 8,
                          runSpacing: 8,
                          children: [
                            _StatePill(
                              label: presentation.typeLabel,
                              backgroundColor: presentation.iconBackground,
                              foregroundColor: presentation.iconColor,
                            ),
                            _StatePill(
                              label: presentation.readLabel,
                              backgroundColor: item.isRead
                                  ? const Color(0xFFF3F6FB)
                                  : presentation.iconBackground,
                              foregroundColor: item.isRead
                                  ? _NotificationsColors.secondaryText
                                  : presentation.iconColor,
                            ),
                          ],
                        ),
                      ],
                    ),
                  ),
                ],
              ),
              const SizedBox(height: 16),
              Text(
                presentation.description,
                style: _NotificationsTextStyles.sheetBody,
              ),
              if ((presentation.reason ?? '').trim().isNotEmpty) ...[
                const SizedBox(height: 14),
                Container(
                  width: double.infinity,
                  padding: const EdgeInsets.all(12),
                  decoration: BoxDecoration(
                    color: presentation.iconBackground,
                    borderRadius: BorderRadius.circular(16),
                  ),
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text('Sabab', style: _NotificationsTextStyles.detailLabel),
                      const SizedBox(height: 4),
                      Text(
                        presentation.reason!,
                        style: _NotificationsTextStyles.detailValue,
                      ),
                    ],
                  ),
                ),
              ],
              const SizedBox(height: 16),
              _DetailInfoRow(
                label: 'Kim tomonidan',
                value: (presentation.actorName ?? '').trim().isNotEmpty
                    ? presentation.actorName!
                    : 'Tizim',
              ),
              _DetailInfoRow(
                label: 'Qachon',
                value: presentation.timeLabel,
              ),
              _DetailInfoRow(
                label: 'Holati',
                value: presentation.readLabel,
              ),
              _DetailInfoRow(
                label: 'Turi',
                value: presentation.typeLabel,
              ),
              if ((presentation.childName ?? '').trim().isNotEmpty)
                _DetailInfoRow(
                  label: 'Qabul qiluvchi',
                  value: presentation.childName!,
                ),
              if ((presentation.amountLabel ?? '').trim().isNotEmpty)
                _DetailInfoRow(
                  label: 'Miqdor',
                  value: presentation.amountLabel!,
                ),
              const SizedBox(height: 18),
              Row(
                children: [
                  Expanded(
                    child: OutlinedButton(
                      onPressed: () => Navigator.of(context).pop(false),
                      style: OutlinedButton.styleFrom(
                        foregroundColor: _NotificationsColors.text,
                        padding: const EdgeInsets.symmetric(vertical: 13),
                        shape: RoundedRectangleBorder(
                          borderRadius: BorderRadius.circular(16),
                        ),
                        side: const BorderSide(color: _NotificationsColors.border),
                      ),
                      child: Text(
                        'Yopish',
                        style: _NotificationsTextStyles.button.copyWith(
                          color: _NotificationsColors.text,
                        ),
                      ),
                    ),
                  ),
                  if (actionLabel != null) ...[
                    const SizedBox(width: 10),
                    Expanded(
                      child: FilledButton(
                        onPressed: () => Navigator.of(context).pop(true),
                        style: FilledButton.styleFrom(
                          backgroundColor: presentation.accentColor,
                          foregroundColor: Colors.white,
                          padding: const EdgeInsets.symmetric(vertical: 13),
                          shape: RoundedRectangleBorder(
                            borderRadius: BorderRadius.circular(16),
                          ),
                        ),
                        child: Text(
                          actionLabel!,
                          textAlign: TextAlign.center,
                          style: _NotificationsTextStyles.button,
                        ),
                      ),
                    ),
                  ],
                ],
              ),
            ],
          ),
        ),
      ),
    );
  }
}

class _MetaChip extends StatelessWidget {
  const _MetaChip({
    required this.icon,
    required this.label,
    this.backgroundColor = const Color(0xFFF3F6FB),
    this.foregroundColor = _NotificationsColors.secondaryText,
  });

  final IconData icon;
  final String label;
  final Color backgroundColor;
  final Color foregroundColor;

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 9, vertical: 6),
      decoration: BoxDecoration(
        color: backgroundColor,
        borderRadius: BorderRadius.circular(999),
      ),
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          Icon(icon, size: 14, color: foregroundColor),
          const SizedBox(width: 5),
          ConstrainedBox(
            constraints: const BoxConstraints(maxWidth: 144),
            child: Text(
              label,
              overflow: TextOverflow.ellipsis,
              maxLines: 1,
              style: _NotificationsTextStyles.chip.copyWith(
                color: foregroundColor,
              ),
            ),
          ),
        ],
      ),
    );
  }
}

class _StatePill extends StatelessWidget {
  const _StatePill({
    required this.label,
    required this.backgroundColor,
    required this.foregroundColor,
  });

  final String label;
  final Color backgroundColor;
  final Color foregroundColor;

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 9, vertical: 5),
      decoration: BoxDecoration(
        color: backgroundColor,
        borderRadius: BorderRadius.circular(999),
      ),
      child: Text(
        label,
        style: _NotificationsTextStyles.chip.copyWith(color: foregroundColor),
      ),
    );
  }
}

class _DetailInfoRow extends StatelessWidget {
  const _DetailInfoRow({required this.label, required this.value});

  final String label;
  final String value;

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.only(bottom: 10),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          SizedBox(
            width: 110,
            child: Text(label, style: _NotificationsTextStyles.detailLabel),
          ),
          const SizedBox(width: 12),
          Expanded(
            child: Text(value, style: _NotificationsTextStyles.detailValue),
          ),
        ],
      ),
    );
  }
}

class _NotificationsStateCard extends StatelessWidget {
  const _NotificationsStateCard({
    required this.title,
    required this.message,
    required this.icon,
    this.actionLabel,
    this.onAction,
  });

  const _NotificationsStateCard.loading()
    : title = 'Yuklanmoqda',
      message = 'Bildirishnomalar tayyorlanmoqda...',
      icon = Icons.notifications_active_outlined,
      actionLabel = null,
      onAction = null;

  final String title;
  final String message;
  final IconData icon;
  final String? actionLabel;
  final VoidCallback? onAction;

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.fromLTRB(18, 22, 18, 18),
      decoration: _cardDecoration(),
      child: Column(
        mainAxisSize: MainAxisSize.min,
        children: [
          Container(
            width: 54,
            height: 54,
            decoration: BoxDecoration(
              color: const Color(0xFFEAF4FF),
              borderRadius: BorderRadius.circular(18),
            ),
            alignment: Alignment.center,
            child: actionLabel == null && onAction == null
                ? const SizedBox(
                    width: 22,
                    height: 22,
                    child: CircularProgressIndicator(
                      strokeWidth: 2.2,
                      color: _NotificationsColors.accentBlue,
                    ),
                  )
                : Icon(icon, color: _NotificationsColors.accentBlue, size: 26),
          ),
          const SizedBox(height: 14),
          Text(
            title,
            textAlign: TextAlign.center,
            style: _NotificationsTextStyles.title,
          ),
          const SizedBox(height: 8),
          Text(
            message,
            textAlign: TextAlign.center,
            style: _NotificationsTextStyles.subtitle,
          ),
          if (actionLabel != null && onAction != null) ...[
            const SizedBox(height: 16),
            FilledButton(
              onPressed: onAction,
              style: FilledButton.styleFrom(
                backgroundColor: _NotificationsColors.accentBlue,
                foregroundColor: Colors.white,
                padding: const EdgeInsets.symmetric(
                  horizontal: 18,
                  vertical: 13,
                ),
                shape: RoundedRectangleBorder(
                  borderRadius: BorderRadius.circular(14),
                ),
              ),
              child: Text(actionLabel!, style: _NotificationsTextStyles.button),
            ),
          ],
        ],
      ),
    );
  }
}

BoxDecoration _cardDecoration({Color borderColor = _NotificationsColors.border}) {
  return BoxDecoration(
    color: _NotificationsColors.card,
    borderRadius: const BorderRadius.all(Radius.circular(20)),
    border: Border.fromBorderSide(BorderSide(color: borderColor)),
    boxShadow: const [
      BoxShadow(color: Color(0x0F0B1220), blurRadius: 18, offset: Offset(0, 8)),
    ],
  );
}

class _NotificationsColors {
  const _NotificationsColors._();

  static const Color background = Color(0xFFF7FBFF);
  static const Color card = Color(0xFFFFFFFF);
  static const Color text = Color(0xFF111827);
  static const Color secondaryText = Color(0xFF6B7280);
  static const Color accentBlue = Color(0xFF1E73F8);
  static const Color border = Color(0xFFE5EAF2);
}

class _NotificationsTextStyles {
  const _NotificationsTextStyles._();

  static TextStyle get title => GoogleFonts.inter(
    fontSize: 18,
    fontWeight: FontWeight.w800,
    height: 1.2,
    color: _NotificationsColors.text,
  );

  static TextStyle get subtitle => GoogleFonts.inter(
    fontSize: 13.2,
    fontWeight: FontWeight.w500,
    height: 1.45,
    color: _NotificationsColors.secondaryText,
  );

  static TextStyle get action => GoogleFonts.inter(
    fontSize: 13.4,
    fontWeight: FontWeight.w700,
    color: _NotificationsColors.accentBlue,
  );

  static TextStyle get badge => GoogleFonts.inter(
    fontSize: 12,
    fontWeight: FontWeight.w800,
    color: _NotificationsColors.accentBlue,
  );

  static TextStyle get cardTitle => GoogleFonts.inter(
    fontSize: 14.4,
    fontWeight: FontWeight.w700,
    height: 1.3,
    color: _NotificationsColors.text,
  );

  static TextStyle get cardBody => GoogleFonts.inter(
    fontSize: 12.9,
    fontWeight: FontWeight.w500,
    height: 1.5,
    color: _NotificationsColors.text,
  );

  static TextStyle get reason => GoogleFonts.inter(
    fontSize: 12.2,
    fontWeight: FontWeight.w600,
    height: 1.35,
    color: _NotificationsColors.secondaryText,
  );

  static TextStyle get chip => GoogleFonts.inter(
    fontSize: 11.1,
    fontWeight: FontWeight.w700,
    height: 1.1,
    color: _NotificationsColors.secondaryText,
  );

  static TextStyle get detailLabel => GoogleFonts.inter(
    fontSize: 12.2,
    fontWeight: FontWeight.w600,
    height: 1.35,
    color: _NotificationsColors.secondaryText,
  );

  static TextStyle get detailValue => GoogleFonts.inter(
    fontSize: 13.2,
    fontWeight: FontWeight.w600,
    height: 1.35,
    color: _NotificationsColors.text,
  );

  static TextStyle get sheetTitle => GoogleFonts.inter(
    fontSize: 17,
    fontWeight: FontWeight.w800,
    height: 1.24,
    color: _NotificationsColors.text,
  );

  static TextStyle get sheetBody => GoogleFonts.inter(
    fontSize: 13.2,
    fontWeight: FontWeight.w500,
    height: 1.52,
    color: _NotificationsColors.text,
  );

  static TextStyle get button => GoogleFonts.inter(
    fontSize: 13.2,
    fontWeight: FontWeight.w700,
    color: Colors.white,
  );
}
