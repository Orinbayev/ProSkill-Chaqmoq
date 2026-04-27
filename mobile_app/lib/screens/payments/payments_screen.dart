import 'package:chaqmoq_mobile/core/utils/formatters.dart';
import 'package:chaqmoq_mobile/models/app_models.dart';
import 'package:chaqmoq_mobile/models/parent_models.dart';
import 'package:chaqmoq_mobile/providers/parent_dashboard_provider.dart';
import 'package:chaqmoq_mobile/services/api_client.dart';
import 'package:chaqmoq_mobile/services/parent_dashboard_service.dart';
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:google_fonts/google_fonts.dart';
import 'package:provider/provider.dart';

class PaymentsScreen extends StatefulWidget {
  const PaymentsScreen({super.key, this.showBottomNav = true});

  final bool showBottomNav;

  @override
  State<PaymentsScreen> createState() => _PaymentsScreenState();
}

class _PaymentsScreenState extends State<PaymentsScreen> {
  ParentPaymentsModel? _data;
  ViewState _state = ViewState.idle;
  String? _errorMessage;
  int? _loadedChildId;

  @override
  void didChangeDependencies() {
    super.didChangeDependencies();
    final dashboard = context.watch<ParentDashboardProvider>();
    final childId =
        dashboard.selectedChildId ?? dashboard.data?.selectedChild.id;
    if (childId != null && childId > 0 && childId != _loadedChildId) {
      _loadedChildId = childId;
      WidgetsBinding.instance.addPostFrameCallback((_) {
        if (mounted) {
          _load(force: true);
        }
      });
    }
  }

  Future<void> _load({bool force = false}) async {
    if (_state == ViewState.loading && !force) {
      return;
    }
    setState(() {
      _state = ViewState.loading;
      _errorMessage = null;
    });
    try {
      final data = await context.read<ParentDashboardService>().fetchPayments(
        childId: _loadedChildId,
      );
      if (!mounted) {
        return;
      }
      setState(() {
        _data = data;
        _state = ViewState.success;
      });
    } on ApiException catch (error) {
      if (!mounted) {
        return;
      }
      setState(() {
        _state = ViewState.error;
        _errorMessage = error.message;
      });
    } catch (_) {
      if (!mounted) {
        return;
      }
      setState(() {
        _state = ViewState.error;
        _errorMessage = 'To‘lovlar yuklanmadi';
      });
    }
  }

  @override
  Widget build(BuildContext context) {
    final fallbackChild = context
        .watch<ParentDashboardProvider>()
        .data
        ?.selectedChild;
    final child = _data?.child ?? fallbackChild;
    final summary =
        _data?.summary ??
        const ParentPaymentSummaryModel(
          totalPlan: 0,
          totalBalance: 0,
          paidTotal: 0,
          debtAmount: 0,
        );

    return AnnotatedRegion<SystemUiOverlayStyle>(
      value: const SystemUiOverlayStyle(
        statusBarColor: Colors.transparent,
        statusBarIconBrightness: Brightness.dark,
        statusBarBrightness: Brightness.light,
        systemNavigationBarColor: Colors.white,
        systemNavigationBarIconBrightness: Brightness.dark,
      ),
      child: Scaffold(
        backgroundColor: PaymentColors.background,
        bottomNavigationBar: widget.showBottomNav
            ? const ParentBottomNav()
            : null,
        body: SafeArea(
          child: RefreshIndicator(
            color: PaymentColors.primaryBlue,
            onRefresh: () => _load(force: true),
            child: SingleChildScrollView(
              physics: const AlwaysScrollableScrollPhysics(
                parent: BouncingScrollPhysics(),
              ),
              padding: const EdgeInsets.fromLTRB(16, 14, 16, 32),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  PaymentsHeader(child: child),
                  const SizedBox(height: 16),
                  if (_state == ViewState.loading && _data == null)
                    const _PaymentStateCard.loading()
                  else if (_state == ViewState.error && _data == null)
                    _PaymentStateCard(
                      title: 'To‘lovlar yuklanmadi',
                      message: _errorMessage ?? 'Qayta urinib ko‘ring',
                      onPressed: () => _load(force: true),
                    )
                  else ...[
                    if (_state == ViewState.loading) ...[
                      const LinearProgressIndicator(
                        minHeight: 3,
                        color: PaymentColors.primaryBlue,
                        backgroundColor: Color(0xFFEAF4FF),
                      ),
                      const SizedBox(height: 10),
                    ],
                    PaymentSummaryCard(summary: summary),
                    const SizedBox(height: 16),
                    NextPaymentCard(summary: summary),
                    const SizedBox(height: 14),
                    PaymentPlanCard(summary: summary),
                    const SizedBox(height: 14),
                    PaymentHistoryCard(items: _data?.history ?? const []),
                    const SizedBox(height: 18),
                    const PayButton(),
                  ],
                ],
              ),
            ),
          ),
        ),
      ),
    );
  }
}

class PaymentsHeader extends StatelessWidget {
  const PaymentsHeader({super.key, this.child});

  final ParentChildModel? child;

  @override
  Widget build(BuildContext context) {
    final childLine = child == null
        ? 'Farzand tanlanmoqda'
        : _childGroupLine(child!);
    return Row(
      children: [
        Expanded(
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              FittedBox(
                fit: BoxFit.scaleDown,
                alignment: Alignment.centerLeft,
                child: Text(
                  'To‘lovlar',
                  maxLines: 1,
                  style: PaymentTextStyles.title.copyWith(fontSize: 23),
                ),
              ),
              const SizedBox(height: 5),
              Text(
                childLine,
                maxLines: 1,
                overflow: TextOverflow.ellipsis,
                style: PaymentTextStyles.body.copyWith(
                  color: PaymentColors.secondaryText,
                  fontSize: 14,
                ),
              ),
            ],
          ),
        ),
        const SizedBox(width: 10),
        const _NotificationButton(),
      ],
    );
  }
}

class PaymentSummaryCard extends StatelessWidget {
  const PaymentSummaryCard({super.key, required this.summary});

  final ParentPaymentSummaryModel summary;

  @override
  Widget build(BuildContext context) {
    return LayoutBuilder(
      builder: (context, constraints) {
        final compact = constraints.maxWidth < 330;
        const illustrationWidth = 94.0;

        return SizedBox(
          height: compact ? 140 : 154,
          child: Row(
            children: [
              Expanded(
                flex: 7,
                child: Container(
                  height: double.infinity,
                  padding: EdgeInsets.fromLTRB(
                    compact ? 15 : 18,
                    compact ? 15 : 18,
                    compact ? 15 : 18,
                    compact ? 14 : 16,
                  ),
                  decoration: BoxDecoration(
                    borderRadius: BorderRadius.circular(20),
                    gradient: const LinearGradient(
                      begin: Alignment.topLeft,
                      end: Alignment.bottomRight,
                      colors: [PaymentColors.primaryBlue, Color(0xFF0057FF)],
                    ),
                    boxShadow: const [
                      BoxShadow(
                        color: Color(0x331E73F8),
                        blurRadius: 24,
                        offset: Offset(0, 12),
                      ),
                    ],
                  ),
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text(
                        'Jami to‘lovlar',
                        style: PaymentTextStyles.body.copyWith(
                          color: Colors.white,
                          fontSize: compact ? 12.5 : 14,
                        ),
                      ),
                      const SizedBox(height: 8),
                      FittedBox(
                        fit: BoxFit.scaleDown,
                        alignment: Alignment.centerLeft,
                        child: Text(
                          _uzs(summary.payableTotal),
                          maxLines: 1,
                          style: PaymentTextStyles.title.copyWith(
                            color: Colors.white,
                            fontSize: compact ? 21 : 25,
                          ),
                        ),
                      ),
                      const SizedBox(height: 10),
                      Container(
                        height: 1,
                        color: Colors.white.withValues(alpha: 0.34),
                      ),
                      const Spacer(),
                      Row(
                        children: [
                          Expanded(
                            child: _SummaryAmount(
                              title: 'To‘langan',
                              amount: _uzs(summary.paidTotal),
                              amountColor: PaymentColors.green,
                              compact: compact,
                            ),
                          ),
                          const SizedBox(width: 10),
                          Expanded(
                            child: _SummaryAmount(
                              title: 'Qarzdorlik (qolgan)',
                              amount: _uzs(summary.debtAmount),
                              amountColor: PaymentColors.red,
                              compact: compact,
                            ),
                          ),
                        ],
                      ),
                    ],
                  ),
                ),
              ),
              if (!compact) ...[
                const SizedBox(width: 0),
                Container(
                  width: illustrationWidth,
                  height: double.infinity,
                  decoration: const BoxDecoration(
                    color: Color(0xFFF4F7FB),
                    borderRadius: BorderRadius.horizontal(
                      right: Radius.circular(20),
                    ),
                  ),
                  child: const _FinanceIllustration(),
                ),
              ],
            ],
          ),
        );
      },
    );
  }
}

class NextPaymentCard extends StatelessWidget {
  const NextPaymentCard({super.key, required this.summary});

  final ParentPaymentSummaryModel summary;

  @override
  Widget build(BuildContext context) {
    return PaymentCard(
      padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 14),
      child: LayoutBuilder(
        builder: (context, constraints) {
          final compact = constraints.maxWidth < 330;
          return Row(
            children: [
              const _BlueIconBox(icon: Icons.event_available_outlined),
              const SizedBox(width: 12),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      'Keyingi to‘lov sanasi',
                      style: PaymentTextStyles.body.copyWith(
                        color: PaymentColors.secondaryText,
                        fontSize: 13,
                      ),
                    ),
                    const SizedBox(height: 4),
                    Text(
                      Formatters.date(summary.nextPaymentDate),
                      maxLines: 1,
                      overflow: TextOverflow.ellipsis,
                      style: PaymentTextStyles.title.copyWith(fontSize: 20),
                    ),
                    const SizedBox(height: 3),
                    Text(
                      _daysUntil(summary.nextPaymentDate),
                      style: PaymentTextStyles.body.copyWith(
                        color: PaymentColors.secondaryText,
                        fontSize: 13.5,
                      ),
                    ),
                  ],
                ),
              ),
              if (!compact) ...[
                const SizedBox(width: 10),
                _ReminderButton(onTap: () {}),
              ],
            ],
          );
        },
      ),
    );
  }
}

class PaymentPlanCard extends StatelessWidget {
  const PaymentPlanCard({super.key, required this.summary});

  final ParentPaymentSummaryModel summary;

  @override
  Widget build(BuildContext context) {
    return PaymentCard(
      padding: const EdgeInsets.fromLTRB(16, 16, 16, 16),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Expanded(
                child: Text(
                  'To‘lov rejasi',
                  maxLines: 1,
                  overflow: TextOverflow.ellipsis,
                  style: PaymentTextStyles.title.copyWith(fontSize: 18),
                ),
              ),
              TextButton(
                onPressed: () {},
                style: TextButton.styleFrom(
                  foregroundColor: PaymentColors.primaryBlue,
                  padding: EdgeInsets.zero,
                  minimumSize: const Size(0, 30),
                  tapTargetSize: MaterialTapTargetSize.shrinkWrap,
                ),
                child: Row(
                  mainAxisSize: MainAxisSize.min,
                  children: [
                    Text(
                      'Batafsil ko‘rish',
                      style: PaymentTextStyles.link.copyWith(fontSize: 14),
                    ),
                    const SizedBox(width: 4),
                    const Icon(Icons.chevron_right_rounded, size: 20),
                  ],
                ),
              ),
            ],
          ),
          const SizedBox(height: 16),
          ClipRRect(
            borderRadius: BorderRadius.circular(999),
            child: LinearProgressIndicator(
              value: summary.paidRatio,
              minHeight: 8,
              backgroundColor: const Color(0xFFEFF2F6),
              valueColor: const AlwaysStoppedAnimation<Color>(
                PaymentColors.green,
              ),
            ),
          ),
          const SizedBox(height: 18),
          Row(
            children: [
              Expanded(
                child: _PlanMetric(
                  label: 'Jami',
                  value: _uzs(summary.payableTotal),
                ),
              ),
              const SizedBox(width: 8),
              Expanded(
                child: _PlanMetric(
                  label: 'To‘langan',
                  value: _uzs(summary.paidTotal),
                  valueColor: PaymentColors.green,
                ),
              ),
              const SizedBox(width: 8),
              Expanded(
                child: _PlanMetric(
                  label: 'Qolgan',
                  value: _uzs(summary.remaining),
                  valueColor: PaymentColors.red,
                ),
              ),
            ],
          ),
        ],
      ),
    );
  }
}

class PaymentHistoryCard extends StatelessWidget {
  const PaymentHistoryCard({super.key, required this.items});

  final List<ParentPaymentHistoryModel> items;

  @override
  Widget build(BuildContext context) {
    final rows = items.map(_historyItem).toList(growable: false);
    return PaymentCard(
      padding: EdgeInsets.zero,
      child: Column(
        children: [
          Padding(
            padding: const EdgeInsets.fromLTRB(16, 16, 16, 10),
            child: Row(
              children: [
                Expanded(
                  child: Text(
                    'To‘lov tarixi',
                    style: PaymentTextStyles.title.copyWith(fontSize: 18),
                  ),
                ),
                const _HistoryFilterButton(),
              ],
            ),
          ),
          if (rows.isEmpty)
            Padding(
              padding: const EdgeInsets.fromLTRB(16, 8, 16, 20),
              child: Text(
                'To‘lov tarixi topilmadi',
                textAlign: TextAlign.center,
                style: PaymentTextStyles.body.copyWith(
                  color: PaymentColors.secondaryText,
                  fontSize: 13.5,
                ),
              ),
            )
          else
            for (int index = 0; index < rows.length; index++)
              PaymentHistoryRow(
                item: rows[index],
                showDivider: index != rows.length - 1,
              ),
          const SizedBox(height: 10),
        ],
      ),
    );
  }
}

class PaymentHistoryRow extends StatelessWidget {
  const PaymentHistoryRow({
    super.key,
    required this.item,
    required this.showDivider,
  });

  final PaymentHistoryItem item;
  final bool showDivider;

  @override
  Widget build(BuildContext context) {
    return LayoutBuilder(
      builder: (context, constraints) {
        final compact = constraints.maxWidth < 330;
        final sidePadding = compact ? 12.0 : 16.0;
        final statusSize = compact ? 38.0 : 42.0;
        final rightMaxWidth = compact ? 104.0 : 124.0;

        return Column(
          children: [
            Padding(
              padding: EdgeInsets.fromLTRB(sidePadding, 12, sidePadding, 12),
              child: Row(
                children: [
                  _PaymentStatusIcon(status: item.status, size: statusSize),
                  SizedBox(width: compact ? 10 : 12),
                  Expanded(
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Text(
                          item.title,
                          maxLines: 1,
                          overflow: TextOverflow.ellipsis,
                          style: PaymentTextStyles.title.copyWith(
                            fontSize: compact ? 14 : 15.5,
                          ),
                        ),
                        const SizedBox(height: 5),
                        Text(
                          item.date,
                          maxLines: 1,
                          overflow: TextOverflow.ellipsis,
                          style: PaymentTextStyles.body.copyWith(
                            color: PaymentColors.secondaryText,
                            fontSize: compact ? 12.5 : 13.5,
                          ),
                        ),
                      ],
                    ),
                  ),
                  SizedBox(width: compact ? 5 : 8),
                  ConstrainedBox(
                    constraints: BoxConstraints(maxWidth: rightMaxWidth),
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.end,
                      children: [
                        FittedBox(
                          fit: BoxFit.scaleDown,
                          alignment: Alignment.centerRight,
                          child: Text(
                            item.amount,
                            maxLines: 1,
                            style: PaymentTextStyles.title.copyWith(
                              color: item.status.amountColor,
                              fontSize: compact ? 13 : 14.5,
                            ),
                          ),
                        ),
                        const SizedBox(height: 5),
                        StatusPill(status: item.status, compact: compact),
                      ],
                    ),
                  ),
                  SizedBox(width: compact ? 4 : 8),
                  Icon(
                    Icons.chevron_right_rounded,
                    color: const Color(0xFF9AA4B2),
                    size: compact ? 18 : 20,
                  ),
                ],
              ),
            ),
            if (showDivider)
              Padding(
                padding: EdgeInsets.only(
                  left: compact ? 62 : 72,
                  right: sidePadding,
                ),
                child: const Divider(height: 1, color: PaymentColors.border),
              ),
          ],
        );
      },
    );
  }
}

class StatusPill extends StatelessWidget {
  const StatusPill({super.key, required this.status, this.compact = false});

  final PaymentStatus status;
  final bool compact;

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: EdgeInsets.symmetric(
        horizontal: compact ? 8 : 11,
        vertical: compact ? 5 : 6,
      ),
      decoration: BoxDecoration(
        color: status.pillBackground,
        borderRadius: BorderRadius.circular(13),
      ),
      child: Text(
        status.label,
        maxLines: 1,
        style: PaymentTextStyles.body.copyWith(
          color: status.pillText,
          fontSize: compact ? 11.5 : 12.5,
          fontWeight: FontWeight.w700,
        ),
      ),
    );
  }
}

class PayButton extends StatelessWidget {
  const PayButton({super.key});

  @override
  Widget build(BuildContext context) {
    return SizedBox(
      width: double.infinity,
      height: 48,
      child: TextButton(
        onPressed: () {},
        style: TextButton.styleFrom(
          backgroundColor: const Color(0xFFEAF4FF),
          foregroundColor: PaymentColors.primaryBlue,
          shape: RoundedRectangleBorder(
            borderRadius: BorderRadius.circular(14),
          ),
        ),
        child: Row(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            const Icon(Icons.credit_card_rounded, size: 22),
            const SizedBox(width: 10),
            Text(
              'To‘lov qilish',
              style: PaymentTextStyles.link.copyWith(fontSize: 15),
            ),
          ],
        ),
      ),
    );
  }
}

class ParentBottomNav extends StatelessWidget {
  const ParentBottomNav({super.key});

  @override
  Widget build(BuildContext context) {
    return Container(
      decoration: const BoxDecoration(
        color: Colors.white,
        borderRadius: BorderRadius.vertical(top: Radius.circular(24)),
        boxShadow: PaymentShadows.topNav,
      ),
      child: SafeArea(
        top: false,
        child: ClipRRect(
          borderRadius: const BorderRadius.vertical(top: Radius.circular(24)),
          child: BottomNavigationBar(
            currentIndex: 2,
            onTap: (_) {},
            type: BottomNavigationBarType.fixed,
            backgroundColor: Colors.white,
            elevation: 0,
            iconSize: 24,
            selectedItemColor: PaymentColors.primaryBlue,
            unselectedItemColor: PaymentColors.secondaryText,
            selectedLabelStyle: PaymentTextStyles.label.copyWith(
              fontSize: 11.5,
            ),
            unselectedLabelStyle: PaymentTextStyles.label.copyWith(
              fontSize: 11.5,
              fontWeight: FontWeight.w600,
            ),
            items: const [
              BottomNavigationBarItem(
                icon: Icon(Icons.home_rounded),
                label: 'Bosh sahifa',
              ),
              BottomNavigationBarItem(
                icon: Icon(Icons.event_available_outlined),
                label: 'Davomat',
              ),
              BottomNavigationBarItem(
                icon: Icon(Icons.account_balance_wallet_outlined),
                label: 'To‘lovlar',
              ),
              BottomNavigationBarItem(
                icon: Icon(Icons.bar_chart_rounded),
                label: 'Yutuqlar',
              ),
              BottomNavigationBarItem(
                icon: Icon(Icons.person_rounded),
                label: 'Profil',
              ),
            ],
          ),
        ),
      ),
    );
  }
}

class PaymentCard extends StatelessWidget {
  const PaymentCard({super.key, required this.child, required this.padding});

  final Widget child;
  final EdgeInsetsGeometry padding;

  @override
  Widget build(BuildContext context) {
    return Container(
      width: double.infinity,
      padding: padding,
      decoration: BoxDecoration(
        color: Colors.white,
        borderRadius: BorderRadius.circular(20),
        border: Border.all(color: PaymentColors.border),
        boxShadow: PaymentShadows.card,
      ),
      child: child,
    );
  }
}

class _SummaryAmount extends StatelessWidget {
  const _SummaryAmount({
    required this.title,
    required this.amount,
    required this.amountColor,
    required this.compact,
  });

  final String title;
  final String amount;
  final Color amountColor;
  final bool compact;

  @override
  Widget build(BuildContext context) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Text(
          title,
          maxLines: 1,
          overflow: TextOverflow.ellipsis,
          style: PaymentTextStyles.body.copyWith(
            color: Colors.white,
            fontSize: compact ? 12 : 14,
          ),
        ),
        const SizedBox(height: 6),
        FittedBox(
          fit: BoxFit.scaleDown,
          alignment: Alignment.centerLeft,
          child: Text(
            amount,
            maxLines: 1,
            style: PaymentTextStyles.title.copyWith(
              color: amountColor,
              fontSize: compact ? 15.5 : 17.5,
            ),
          ),
        ),
      ],
    );
  }
}

class _PlanMetric extends StatelessWidget {
  const _PlanMetric({
    required this.label,
    required this.value,
    this.valueColor = PaymentColors.text,
  });

  final String label;
  final String value;
  final Color valueColor;

  @override
  Widget build(BuildContext context) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Text(
          label,
          maxLines: 1,
          overflow: TextOverflow.ellipsis,
          style: PaymentTextStyles.body.copyWith(
            color: PaymentColors.secondaryText,
            fontSize: 12.5,
          ),
        ),
        const SizedBox(height: 7),
        FittedBox(
          fit: BoxFit.scaleDown,
          alignment: Alignment.centerLeft,
          child: Text(
            value,
            maxLines: 1,
            style: PaymentTextStyles.title.copyWith(
              color: valueColor,
              fontSize: 14.5,
            ),
          ),
        ),
      ],
    );
  }
}

class _NotificationButton extends StatelessWidget {
  const _NotificationButton();

  @override
  Widget build(BuildContext context) {
    final unreadCount =
        context.watch<ParentDashboardProvider>().data?.unreadNotifications ?? 0;
    return Stack(
      clipBehavior: Clip.none,
      children: [
        InkWell(
          onTap: () {},
          customBorder: const CircleBorder(),
          child: Container(
            width: 46,
            height: 46,
            alignment: Alignment.center,
            decoration: BoxDecoration(
              color: Colors.white,
              shape: BoxShape.circle,
              border: Border.all(color: PaymentColors.border),
              boxShadow: PaymentShadows.soft,
            ),
            child: const Icon(
              Icons.notifications_none_rounded,
              color: PaymentColors.text,
              size: 25,
            ),
          ),
        ),
        if (unreadCount > 0)
          Positioned(
            right: 4,
            top: 2,
            child: Container(
              constraints: const BoxConstraints(minWidth: 18),
              height: 18,
              alignment: Alignment.center,
              padding: const EdgeInsets.symmetric(horizontal: 4),
              decoration: BoxDecoration(
                color: PaymentColors.red,
                borderRadius: BorderRadius.circular(999),
                border: Border.all(color: Colors.white, width: 2),
              ),
              child: Text(
                unreadCount > 99 ? '99+' : '$unreadCount',
                style: PaymentTextStyles.label.copyWith(
                  color: Colors.white,
                  fontSize: 9.5,
                  height: 1,
                ),
              ),
            ),
          ),
      ],
    );
  }
}

class _ReminderButton extends StatelessWidget {
  const _ReminderButton({required this.onTap});

  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    return TextButton.icon(
      onPressed: onTap,
      style: TextButton.styleFrom(
        backgroundColor: const Color(0xFFEAF4FF),
        foregroundColor: PaymentColors.primaryBlue,
        padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 10),
        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(14)),
      ),
      icon: const Icon(Icons.notifications_none_rounded, size: 20),
      label: Text(
        'Eslatma o‘rnatish',
        style: PaymentTextStyles.link.copyWith(fontSize: 13),
      ),
    );
  }
}

class _HistoryFilterButton extends StatelessWidget {
  const _HistoryFilterButton();

  @override
  Widget build(BuildContext context) {
    return TextButton(
      onPressed: () {},
      style: TextButton.styleFrom(
        backgroundColor: const Color(0xFFF7F9FC),
        foregroundColor: PaymentColors.secondaryText,
        padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 9),
        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(14)),
      ),
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          const Icon(Icons.filter_list_rounded, size: 18),
          const SizedBox(width: 6),
          Text(
            'Filtr',
            style: PaymentTextStyles.body.copyWith(
              color: PaymentColors.text,
              fontSize: 13.5,
            ),
          ),
          const SizedBox(width: 3),
          const Icon(Icons.keyboard_arrow_down_rounded, size: 18),
        ],
      ),
    );
  }
}

class _BlueIconBox extends StatelessWidget {
  const _BlueIconBox({required this.icon});

  final IconData icon;

  @override
  Widget build(BuildContext context) {
    return Container(
      width: 46,
      height: 46,
      decoration: BoxDecoration(
        color: const Color(0xFFE8F1FF),
        borderRadius: BorderRadius.circular(14),
      ),
      child: Icon(icon, color: PaymentColors.primaryBlue, size: 25),
    );
  }
}

class _PaymentStatusIcon extends StatelessWidget {
  const _PaymentStatusIcon({required this.status, this.size = 54});

  final PaymentStatus status;
  final double size;

  @override
  Widget build(BuildContext context) {
    return Container(
      width: size,
      height: size,
      decoration: BoxDecoration(
        color: status.iconBackground,
        shape: BoxShape.circle,
      ),
      child: Icon(status.icon, color: status.iconColor, size: size * 0.48),
    );
  }
}

class _FinanceIllustration extends StatelessWidget {
  const _FinanceIllustration();

  @override
  Widget build(BuildContext context) {
    return CustomPaint(
      painter: _FinanceIllustrationPainter(),
      child: const SizedBox.expand(),
    );
  }
}

class _FinanceIllustrationPainter extends CustomPainter {
  @override
  void paint(Canvas canvas, Size size) {
    final receiptPaint = Paint()..color = const Color(0xFFDDE8FF);
    final linePaint = Paint()
      ..color = const Color(0xFF9DB5F4)
      ..strokeWidth = 4
      ..strokeCap = StrokeCap.round;
    final coinPaint = Paint()..color = const Color(0xFFFFC638);
    final coinStroke = Paint()
      ..color = const Color(0xFFF59E0B)
      ..strokeWidth = 3
      ..style = PaintingStyle.stroke;
    final shieldPaint = Paint()..color = PaymentColors.green;

    final w = size.width;
    final h = size.height;

    final receipt = RRect.fromRectAndRadius(
      Rect.fromLTWH(w * 0.22, h * 0.18, w * 0.46, h * 0.55),
      const Radius.circular(12),
    );
    canvas.drawRRect(receipt, receiptPaint);
    canvas.drawRRect(
      RRect.fromRectAndRadius(
        Rect.fromLTWH(w * 0.57, h * 0.18, w * 0.18, h * 0.18),
        const Radius.circular(12),
      ),
      Paint()..color = const Color(0xFFBBD0FF),
    );

    for (final entry in [
      [0.27, 0.28, 0.22],
      [0.27, 0.40, 0.34],
      [0.27, 0.52, 0.26],
      [0.27, 0.64, 0.34],
      [0.43, 0.72, 0.16],
    ]) {
      final x = w * entry[0];
      final y = h * entry[1];
      final length = w * entry[2];
      canvas.drawLine(Offset(x, y), Offset(x + length, y), linePaint);
    }

    final shield = Path()
      ..moveTo(w * 0.23, h * 0.60)
      ..lineTo(w * 0.40, h * 0.52)
      ..lineTo(w * 0.57, h * 0.60)
      ..quadraticBezierTo(w * 0.55, h * 0.82, w * 0.40, h * 0.90)
      ..quadraticBezierTo(w * 0.25, h * 0.82, w * 0.23, h * 0.60)
      ..close();
    canvas.drawPath(shield, shieldPaint);
    canvas.drawPath(
      shield,
      Paint()
        ..color = Colors.white.withValues(alpha: 0.24)
        ..style = PaintingStyle.stroke
        ..strokeWidth = 3,
    );
    final checkPaint = Paint()
      ..color = Colors.white
      ..strokeWidth = 4
      ..strokeCap = StrokeCap.round
      ..style = PaintingStyle.stroke;
    canvas.drawPath(
      Path()
        ..moveTo(w * 0.34, h * 0.70)
        ..lineTo(w * 0.39, h * 0.75)
        ..lineTo(w * 0.49, h * 0.64),
      checkPaint,
    );

    final coins = [
      Rect.fromLTWH(w * 0.66, h * 0.62, w * 0.28, h * 0.15),
      Rect.fromLTWH(w * 0.57, h * 0.74, w * 0.32, h * 0.17),
      Rect.fromLTWH(w * 0.78, h * 0.76, w * 0.25, h * 0.14),
      Rect.fromLTWH(w * 0.72, h * 0.54, w * 0.27, h * 0.12),
    ];
    for (final coin in coins) {
      canvas.drawOval(coin, coinPaint);
      canvas.drawOval(coin.deflate(4), coinStroke);
    }
  }

  @override
  bool shouldRepaint(covariant CustomPainter oldDelegate) => false;
}

class _PaymentStateCard extends StatelessWidget {
  const _PaymentStateCard({
    required this.title,
    required this.message,
    this.onPressed,
  }) : loading = false;

  const _PaymentStateCard.loading()
    : title = '',
      message = '',
      onPressed = null,
      loading = true;

  final String title;
  final String message;
  final VoidCallback? onPressed;
  final bool loading;

  @override
  Widget build(BuildContext context) {
    return PaymentCard(
      padding: const EdgeInsets.fromLTRB(18, 36, 18, 36),
      child: loading
          ? const SizedBox(
              height: 220,
              child: Center(
                child: CircularProgressIndicator(
                  color: PaymentColors.primaryBlue,
                ),
              ),
            )
          : Column(
              children: [
                const Icon(
                  Icons.info_outline_rounded,
                  color: PaymentColors.primaryBlue,
                  size: 40,
                ),
                const SizedBox(height: 12),
                Text(
                  title,
                  textAlign: TextAlign.center,
                  style: PaymentTextStyles.title.copyWith(fontSize: 19),
                ),
                const SizedBox(height: 8),
                Text(
                  message,
                  textAlign: TextAlign.center,
                  style: PaymentTextStyles.body.copyWith(
                    color: PaymentColors.secondaryText,
                    fontSize: 14,
                  ),
                ),
                if (onPressed != null) ...[
                  const SizedBox(height: 16),
                  TextButton(
                    onPressed: onPressed,
                    style: TextButton.styleFrom(
                      backgroundColor: const Color(0xFFEAF4FF),
                      foregroundColor: PaymentColors.primaryBlue,
                    ),
                    child: const Text('Qayta urinish'),
                  ),
                ],
              ],
            ),
    );
  }
}

String _uzs(num value) => '${Formatters.number(value)} UZS';

String _daysUntil(DateTime? date) {
  if (date == null) {
    return 'Sana belgilanmagan';
  }
  final today = DateTime.now();
  final current = DateTime(today.year, today.month, today.day);
  final target = DateTime(date.year, date.month, date.day);
  final days = target.difference(current).inDays;
  if (days == 0) {
    return 'Bugun';
  }
  if (days < 0) {
    return '${days.abs()} kun o‘tdi';
  }
  return '$days kun qoldi';
}

PaymentHistoryItem _historyItem(ParentPaymentHistoryModel item) {
  return PaymentHistoryItem(
    title: item.title,
    date: Formatters.date(item.date),
    amount: _uzs(item.amount),
    status: _paymentStatusFor(item.status),
  );
}

PaymentStatus _paymentStatusFor(String status) {
  final normalized = status.toLowerCase();
  if (normalized.contains('pending') || normalized.contains('kutil')) {
    return PaymentStatus.pending;
  }
  if (normalized.contains('unpaid') ||
      normalized.contains('debt') ||
      normalized.contains('qarz')) {
    return PaymentStatus.unpaid;
  }
  return PaymentStatus.paid;
}

String _childGroupLine(ParentChildModel child) {
  final parts = <String>[
    if (child.fullName.trim().isNotEmpty) child.fullName.trim(),
    if (child.className.trim().isNotEmpty) child.className.trim(),
    if (child.groupName.trim().isNotEmpty) child.groupName.trim(),
  ];
  return parts.isEmpty ? 'Guruh biriktirilmagan' : parts.join(' • ');
}

class PaymentHistoryItem {
  const PaymentHistoryItem({
    required this.title,
    required this.date,
    required this.amount,
    required this.status,
  });

  final String title;
  final String date;
  final String amount;
  final PaymentStatus status;
}

enum PaymentStatus { paid, pending, unpaid }

extension PaymentStatusStyle on PaymentStatus {
  String get label {
    return switch (this) {
      PaymentStatus.paid => 'To‘langan',
      PaymentStatus.pending => 'Kutilmoqda',
      PaymentStatus.unpaid => 'To‘lanmagan',
    };
  }

  IconData get icon {
    return switch (this) {
      PaymentStatus.paid => Icons.check_circle_outline_rounded,
      PaymentStatus.pending => Icons.access_time_rounded,
      PaymentStatus.unpaid => Icons.remove_circle_outline_rounded,
    };
  }

  Color get iconColor {
    return switch (this) {
      PaymentStatus.paid => PaymentColors.green,
      PaymentStatus.pending => const Color(0xFF6B7280),
      PaymentStatus.unpaid => PaymentColors.red,
    };
  }

  Color get iconBackground {
    return switch (this) {
      PaymentStatus.paid => const Color(0xFFE7F8EF),
      PaymentStatus.pending => const Color(0xFFF0F2F6),
      PaymentStatus.unpaid => const Color(0xFFFFE7E7),
    };
  }

  Color get pillBackground {
    return switch (this) {
      PaymentStatus.paid => const Color(0xFFE7F8EF),
      PaymentStatus.pending => const Color(0xFFFFF4DA),
      PaymentStatus.unpaid => const Color(0xFFFFE7E7),
    };
  }

  Color get pillText {
    return switch (this) {
      PaymentStatus.paid => const Color(0xFF047857),
      PaymentStatus.pending => PaymentColors.orange,
      PaymentStatus.unpaid => const Color(0xFFDC2626),
    };
  }

  Color get amountColor {
    return switch (this) {
      PaymentStatus.paid => PaymentColors.green,
      PaymentStatus.pending => PaymentColors.text,
      PaymentStatus.unpaid => PaymentColors.text,
    };
  }
}

class PaymentColors {
  const PaymentColors._();

  static const Color background = Color(0xFFF7FBFF);
  static const Color primaryBlue = Color(0xFF1E73F8);
  static const Color green = Color(0xFF10B981);
  static const Color red = Color(0xFFEF4444);
  static const Color orange = Color(0xFFF59E0B);
  static const Color text = Color(0xFF111827);
  static const Color secondaryText = Color(0xFF6B7280);
  static const Color border = Color(0xFFE5EAF2);
}

class PaymentTextStyles {
  const PaymentTextStyles._();

  static TextStyle get title {
    return GoogleFonts.inter(
      fontSize: 18,
      height: 1.16,
      fontWeight: FontWeight.w800,
      color: PaymentColors.text,
      letterSpacing: 0,
    );
  }

  static TextStyle get body {
    return GoogleFonts.inter(
      fontSize: 15,
      height: 1.28,
      fontWeight: FontWeight.w500,
      color: PaymentColors.text,
      letterSpacing: 0,
    );
  }

  static TextStyle get label {
    return GoogleFonts.inter(
      fontSize: 13,
      height: 1.16,
      fontWeight: FontWeight.w800,
      color: PaymentColors.text,
      letterSpacing: 0,
    );
  }

  static TextStyle get link {
    return GoogleFonts.inter(
      fontSize: 15,
      height: 1.16,
      fontWeight: FontWeight.w800,
      color: PaymentColors.primaryBlue,
      letterSpacing: 0,
    );
  }
}

class PaymentShadows {
  const PaymentShadows._();

  static const List<BoxShadow> soft = [
    BoxShadow(color: Color(0x0F0B1220), blurRadius: 18, offset: Offset(0, 8)),
  ];

  static const List<BoxShadow> card = [
    BoxShadow(color: Color(0x0D0B1220), blurRadius: 18, offset: Offset(0, 8)),
  ];

  static const List<BoxShadow> topNav = [
    BoxShadow(color: Color(0x140B1220), blurRadius: 24, offset: Offset(0, -8)),
  ];
}
