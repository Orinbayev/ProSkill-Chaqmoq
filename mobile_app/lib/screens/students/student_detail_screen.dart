import 'package:chaqmoq_mobile/core/theme/app_colors.dart';
import 'package:chaqmoq_mobile/core/theme/app_spacing.dart';
import 'package:chaqmoq_mobile/core/theme/app_text_styles.dart';
import 'package:chaqmoq_mobile/core/utils/formatters.dart';
import 'package:chaqmoq_mobile/models/app_models.dart';
import 'package:chaqmoq_mobile/providers/students_provider.dart';
import 'package:chaqmoq_mobile/widgets/empty_state.dart';
import 'package:chaqmoq_mobile/widgets/glass_card.dart';
import 'package:chaqmoq_mobile/widgets/role_badge.dart';
import 'package:chaqmoq_mobile/widgets/stat_chip.dart';
import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

class StudentDetailScreen extends StatefulWidget {
  const StudentDetailScreen({super.key, required this.student});

  final StudentModel student;

  @override
  State<StudentDetailScreen> createState() => _StudentDetailScreenState();
}

class _StudentDetailScreenState extends State<StudentDetailScreen> {
  bool _requested = false;

  @override
  void didChangeDependencies() {
    super.didChangeDependencies();
    if (_requested) {
      return;
    }
    _requested = true;
    context.read<StudentsProvider>().loadDetail(widget.student);
  }

  @override
  Widget build(BuildContext context) {
    final provider = context.watch<StudentsProvider>();
    final detail = provider.detail;
    final student = detail?.student ?? widget.student;
    return DefaultTabController(
      length: 4,
      child: Scaffold(
        appBar: AppBar(title: const Text('O\'quvchi profili')),
        body: DecoratedBox(
          decoration: const BoxDecoration(gradient: AppColors.appBackground),
          child: ListView(
            padding: const EdgeInsets.all(AppSpacing.xl),
            children: [
              GlassCard(
                child: Column(
                  children: [
                    Hero(
                      tag: 'student-avatar-${widget.student.id}',
                      child: CircleAvatar(
                        radius: 38,
                        backgroundColor: Color(Formatters.avatarColor(student.fullName)).withValues(alpha: 0.18),
                        child: Text(
                          Formatters.initials(student.fullName),
                          style: AppTextStyles.title.copyWith(
                            color: Color(Formatters.avatarColor(student.fullName)),
                          ),
                        ),
                      ),
                    ),
                    const SizedBox(height: AppSpacing.lg),
                    Text(student.fullName, style: AppTextStyles.headline, textAlign: TextAlign.center),
                    const SizedBox(height: AppSpacing.sm),
                    const RoleBadge(role: 'student'),
                    const SizedBox(height: AppSpacing.md),
                    StatChip(
                      label: student.isActive ? 'Faol' : 'Nofaol',
                      color: student.isActive ? AppColors.success : AppColors.warning,
                    ),
                  ],
                ),
              ),
              const SizedBox(height: AppSpacing.xl),
              GlassCard(
                padding: const EdgeInsets.all(AppSpacing.sm),
                child: const TabBar(
                  tabs: [
                    Tab(text: 'Info'),
                    Tab(text: 'Attendance'),
                    Tab(text: 'Payments'),
                    Tab(text: 'Chaqmoq'),
                  ],
                ),
              ),
              const SizedBox(height: AppSpacing.lg),
              if (provider.detailState == ViewState.loading)
                const SizedBox(
                  height: 360,
                  child: Center(child: CircularProgressIndicator()),
                )
              else if (provider.detailState == ViewState.error)
                EmptyState(
                  title: 'Profil yuklanmadi',
                  message: provider.errorMessage ?? 'Qayta urinib ko\'ring',
                  icon: Icons.person_off_rounded,
                  actionLabel: 'Qayta yuklash',
                  onAction: () => provider.loadDetail(widget.student),
                )
              else
                SizedBox(
                  height: 460,
                  child: TabBarView(
                    children: [
                      _InfoTab(student: student),
                      _AttendanceTab(attendanceDates: detail?.attendance ?? const <DateTime>[]),
                      _PaymentsTab(payments: detail?.payments ?? const <PaymentModel>[]),
                      _ChaqmoqTab(
                        score: student.balance,
                        rank: student.rank,
                        badges: detail?.badges ?? const <String>[],
                        history: detail?.chaqmoqHistory ?? const <ChaqmoqEntryModel>[],
                      ),
                    ],
                  ),
                ),
            ],
          ),
        ),
      ),
    );
  }
}

class _InfoTab extends StatelessWidget {
  const _InfoTab({required this.student});

  final StudentModel student;

  @override
  Widget build(BuildContext context) {
    final items = <MapEntry<String, String>>[
      MapEntry('Telefon', student.phone.isEmpty ? 'Mavjud emas' : student.phone),
      MapEntry('Email', student.email.isEmpty ? 'Mavjud emas' : student.email),
      MapEntry('Guruh', student.groupName.isEmpty ? 'Biriktirilmagan' : student.groupName),
      MapEntry('Balans', Formatters.currency(student.balance)),
      MapEntry('Ro\'yxatdan o\'tgan sana', Formatters.date(student.registrationDate)),
    ];
    return ListView.separated(
      itemCount: items.length,
      separatorBuilder: (context, index) => const SizedBox(height: AppSpacing.lg),
      itemBuilder: (context, index) {
        final item = items[index];
        return GlassCard(
          child: Row(
            children: [
              Expanded(child: Text(item.key, style: AppTextStyles.subtitle)),
              const SizedBox(width: AppSpacing.lg),
              Expanded(
                child: Text(item.value, style: AppTextStyles.body, textAlign: TextAlign.right),
              ),
            ],
          ),
        );
      },
    );
  }
}

class _AttendanceTab extends StatelessWidget {
  const _AttendanceTab({required this.attendanceDates});

  final List<DateTime> attendanceDates;

  @override
  Widget build(BuildContext context) {
    final today = DateTime.now();
    final days = List<DateTime>.generate(
      28,
      (index) => today.subtract(Duration(days: 27 - index)),
    );
    final marked = attendanceDates
        .map((date) => DateTime(date.year, date.month, date.day))
        .toSet();

    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Text('Oylik davomat heatmap', style: AppTextStyles.title),
        const SizedBox(height: AppSpacing.lg),
        Expanded(
          child: GridView.builder(
            itemCount: days.length,
            gridDelegate: const SliverGridDelegateWithFixedCrossAxisCount(
              crossAxisCount: 7,
              crossAxisSpacing: AppSpacing.sm,
              mainAxisSpacing: AppSpacing.sm,
            ),
            itemBuilder: (context, index) {
              final day = days[index];
              final normalized = DateTime(day.year, day.month, day.day);
              final present = marked.contains(normalized);
              return Container(
                decoration: BoxDecoration(
                  color: present ? AppColors.success.withValues(alpha: 0.75) : AppColors.surfaceAlt,
                  borderRadius: BorderRadius.circular(AppRadius.md),
                  border: Border.all(color: AppColors.border),
                ),
                alignment: Alignment.center,
                child: Text(
                  '${day.day}',
                  style: AppTextStyles.bodySmall.copyWith(
                    color: present ? AppColors.white : AppColors.textMuted,
                  ),
                ),
              );
            },
          ),
        ),
      ],
    );
  }
}

class _PaymentsTab extends StatelessWidget {
  const _PaymentsTab({required this.payments});

  final List<PaymentModel> payments;

  @override
  Widget build(BuildContext context) {
    if (payments.isEmpty) {
      return const EmptyState(
        title: 'To\'lov topilmadi',
        message: 'Bu o\'quvchi uchun hozircha tarix mavjud emas',
        icon: Icons.receipt_long_rounded,
      );
    }
    return ListView.separated(
      itemCount: payments.length,
      separatorBuilder: (context, index) => const SizedBox(height: AppSpacing.lg),
      itemBuilder: (context, index) {
        final payment = payments[index];
        return GlassCard(
          child: Row(
            children: [
              Container(
                width: 42,
                height: 42,
                decoration: BoxDecoration(
                  color: AppColors.success.withValues(alpha: 0.16),
                  borderRadius: BorderRadius.circular(AppRadius.lg),
                ),
                alignment: Alignment.center,
                child: const Icon(Icons.payments_rounded, color: AppColors.success),
              ),
              const SizedBox(width: AppSpacing.md),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(payment.groupName.isEmpty ? 'To\'lov' : payment.groupName, style: AppTextStyles.body),
                    const SizedBox(height: AppSpacing.xs),
                    Text(Formatters.date(payment.date), style: AppTextStyles.bodySmall),
                  ],
                ),
              ),
              Text(
                Formatters.currency(payment.amount),
                style: AppTextStyles.label.copyWith(color: AppColors.success),
              ),
            ],
          ),
        );
      },
    );
  }
}

class _ChaqmoqTab extends StatelessWidget {
  const _ChaqmoqTab({
    required this.score,
    required this.rank,
    required this.badges,
    required this.history,
  });

  final int score;
  final int rank;
  final List<String> badges;
  final List<ChaqmoqEntryModel> history;

  @override
  Widget build(BuildContext context) {
    return ListView(
      children: [
        GlassCard(
          child: Row(
            children: [
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text('Joriy ball', style: AppTextStyles.subtitle),
                    const SizedBox(height: AppSpacing.sm),
                    Text('$score', style: AppTextStyles.headline),
                  ],
                ),
              ),
              StatChip(
                label: 'Rank #$rank',
                color: AppColors.warning,
                icon: Icons.emoji_events_rounded,
              ),
            ],
          ),
        ),
        const SizedBox(height: AppSpacing.lg),
        Wrap(
          spacing: AppSpacing.sm,
          runSpacing: AppSpacing.sm,
          children: badges
              .map((badge) => StatChip(label: badge, color: AppColors.secondary))
              .toList(),
        ),
        const SizedBox(height: AppSpacing.lg),
        ...history.map(
          (item) => Padding(
            padding: const EdgeInsets.only(bottom: AppSpacing.lg),
            child: GlassCard(
              child: ListTile(
                contentPadding: EdgeInsets.zero,
                leading: const Icon(Icons.bolt_rounded, color: AppColors.primary),
                title: Text(item.ruleName, style: AppTextStyles.body),
                subtitle: Text(Formatters.relative(item.createdAt), style: AppTextStyles.bodySmall),
                trailing: Text(
                  '${item.points > 0 ? '+' : ''}${item.points}',
                  style: AppTextStyles.label.copyWith(
                    color: item.points >= 0 ? AppColors.success : AppColors.danger,
                  ),
                ),
              ),
            ),
          ),
        ),
      ],
    );
  }
}
