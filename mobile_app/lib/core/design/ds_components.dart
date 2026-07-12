import 'package:flutter/material.dart';

import 'ds_colors.dart';
import 'ds_tokens.dart';
import 'ds_typography.dart';

// ═══════════════════════════════════════════════════════════════════
//  Tugmalar
// ═══════════════════════════════════════════════════════════════════

enum DsButtonVariant { primary, secondary, outline, ghost, danger }

class DsButton extends StatelessWidget {
  const DsButton({
    super.key,
    required this.label,
    this.onPressed,
    this.variant = DsButtonVariant.primary,
    this.icon,
    this.expand = true,
    this.loading = false,
    this.height = 52,
  });

  final String label;
  final VoidCallback? onPressed;
  final DsButtonVariant variant;
  final IconData? icon;
  final bool expand;
  final bool loading;
  final double height;

  bool get _compact => height <= 40;

  @override
  Widget build(BuildContext context) {
    final ds = context.ds;
    final (bg, fg, border, shadow) = _style(ds);
    final disabled = onPressed == null || loading;

    final child = Row(
      mainAxisSize: expand ? MainAxisSize.max : MainAxisSize.min,
      mainAxisAlignment: MainAxisAlignment.center,
      children: [
        if (loading)
          SizedBox(
            width: 18,
            height: 18,
            child: CircularProgressIndicator(strokeWidth: 2.2, valueColor: AlwaysStoppedAnimation(fg)),
          )
        else ...[
          if (icon != null) ...[Icon(icon, size: _compact ? 16 : 18, color: fg), const SizedBox(width: 6)],
          Text(label, style: _compact ? DsType.caption(fg).copyWith(fontWeight: FontWeight.w600) : DsType.bodyStrong(fg)),
        ],
      ],
    );

    return Opacity(
      opacity: disabled ? 0.55 : 1,
      child: Material(
        color: bg,
        borderRadius: DsRadius.all(DsRadius.md),
        child: InkWell(
          onTap: disabled ? null : onPressed,
          borderRadius: DsRadius.all(DsRadius.md),
          child: Container(
            height: height,
            padding: EdgeInsets.symmetric(horizontal: _compact ? 14 : 20),
            decoration: BoxDecoration(
              borderRadius: DsRadius.all(DsRadius.md),
              border: border != null ? Border.all(color: border) : null,
              boxShadow: disabled ? null : shadow,
            ),
            child: Center(child: child),
          ),
        ),
      ),
    );
  }

  (Color, Color, Color?, List<BoxShadow>?) _style(DsColors ds) {
    switch (variant) {
      case DsButtonVariant.primary:
        return (ds.primary, ds.primaryFg, null, DsShadow.primaryGlow(ds.primary));
      case DsButtonVariant.secondary:
        return (ds.primarySoft, ds.primarySoftFg, null, null);
      case DsButtonVariant.outline:
        return (ds.card, ds.textPrimary, ds.border, null);
      case DsButtonVariant.ghost:
        return (Colors.transparent, ds.primarySoftFg, null, null);
      case DsButtonVariant.danger:
        return (ds.dangerBg, ds.dangerFg, null, null);
    }
  }
}

// ═══════════════════════════════════════════════════════════════════
//  Status badge (pill)
// ═══════════════════════════════════════════════════════════════════

enum DsStatus { success, warning, danger, neutral, info }

class DsBadge extends StatelessWidget {
  const DsBadge(this.label, {super.key, this.status = DsStatus.neutral});

  final String label;
  final DsStatus status;

  @override
  Widget build(BuildContext context) {
    final ds = context.ds;
    final (bg, fg) = switch (status) {
      DsStatus.success => (ds.successBg, ds.successFg),
      DsStatus.warning => (ds.warningBg, ds.warningFg),
      DsStatus.danger => (ds.dangerBg, ds.dangerFg),
      DsStatus.info => (ds.primarySoft, ds.primarySoftFg),
      DsStatus.neutral => (ds.cardAlt, ds.textMuted),
    };
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 4),
      decoration: BoxDecoration(color: bg, borderRadius: DsRadius.all(DsRadius.pill)),
      child: Text(label, style: DsType.micro(fg)),
    );
  }
}

// ═══════════════════════════════════════════════════════════════════
//  Filter chip
// ═══════════════════════════════════════════════════════════════════

class DsChip extends StatelessWidget {
  const DsChip({super.key, required this.label, this.selected = false, this.onTap});

  final String label;
  final bool selected;
  final VoidCallback? onTap;

  @override
  Widget build(BuildContext context) {
    final ds = context.ds;
    return Material(
      color: selected ? ds.primary : ds.cardAlt,
      borderRadius: DsRadius.all(DsRadius.pill),
      child: InkWell(
        onTap: onTap,
        borderRadius: DsRadius.all(DsRadius.pill),
        child: Container(
          padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 8),
          decoration: BoxDecoration(
            borderRadius: DsRadius.all(DsRadius.pill),
            border: selected ? null : Border.all(color: ds.border),
          ),
          child: Text(
            label,
            style: DsType.small(selected ? ds.primaryFg : ds.textSecondary)
                .copyWith(fontWeight: FontWeight.w600),
          ),
        ),
      ),
    );
  }
}

// ═══════════════════════════════════════════════════════════════════
//  Karta
// ═══════════════════════════════════════════════════════════════════

class DsCard extends StatelessWidget {
  const DsCard({super.key, required this.child, this.padding, this.color, this.radius = DsRadius.card, this.onTap});

  final Widget child;
  final EdgeInsetsGeometry? padding;
  final Color? color;
  final double radius;
  final VoidCallback? onTap;

  @override
  Widget build(BuildContext context) {
    final ds = context.ds;
    final content = Container(
      padding: padding ?? const EdgeInsets.all(DsSpace.x5),
      decoration: dsCardDecoration(ds, radius: radius, color: color),
      child: child,
    );
    if (onTap == null) return content;
    return Material(
      color: Colors.transparent,
      child: InkWell(onTap: onTap, borderRadius: DsRadius.all(radius), child: content),
    );
  }
}

// ═══════════════════════════════════════════════════════════════════
//  KPI tile (ikon · qiymat · yorliq · delta)
// ═══════════════════════════════════════════════════════════════════

class DsKpiTile extends StatelessWidget {
  const DsKpiTile({
    super.key,
    required this.icon,
    required this.value,
    required this.label,
    this.tone = DsStatus.info,
    this.delta,
    this.deltaUp = true,
  });

  final IconData icon;
  final String value;
  final String label;
  final DsStatus tone;
  final String? delta;
  final bool deltaUp;

  @override
  Widget build(BuildContext context) {
    final ds = context.ds;
    final (iconBg, iconFg) = switch (tone) {
      DsStatus.success => (ds.successBg, ds.successFg),
      DsStatus.warning => (ds.warningBg, ds.warningFg),
      DsStatus.danger => (ds.dangerBg, ds.dangerFg),
      DsStatus.info || DsStatus.neutral => (ds.primarySoft, ds.primarySoftFg),
    };
    return DsCard(
      padding: const EdgeInsets.all(DsSpace.x4),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Container(
                width: 34,
                height: 34,
                decoration: BoxDecoration(color: iconBg, borderRadius: DsRadius.all(DsRadius.sm)),
                child: Icon(icon, size: 18, color: iconFg),
              ),
              const Spacer(),
              if (delta != null)
                Row(
                  children: [
                    Icon(deltaUp ? Icons.arrow_drop_up : Icons.arrow_drop_down,
                        size: 18, color: deltaUp ? ds.success : ds.danger),
                    Text(delta!, style: DsType.small(deltaUp ? ds.success : ds.danger)),
                  ],
                ),
            ],
          ),
          const SizedBox(height: 14),
          Text(value, style: DsType.h1(ds.textPrimary)),
          const SizedBox(height: 2),
          Text(label, style: DsType.small(ds.textMuted)),
        ],
      ),
    );
  }
}

// ═══════════════════════════════════════════════════════════════════
//  Input maydonlari
// ═══════════════════════════════════════════════════════════════════

class DsTextField extends StatelessWidget {
  const DsTextField({
    super.key,
    this.label,
    this.hint,
    this.controller,
    this.suffixText,
    this.prefixIcon,
    this.keyboardType,
    this.big = false,
    this.onChanged,
    this.obscureText = false,
  });

  final String? label;
  final String? hint;
  final TextEditingController? controller;
  final String? suffixText;
  final IconData? prefixIcon;
  final TextInputType? keyboardType;
  final ValueChanged<String>? onChanged;
  final bool obscureText;

  /// Katta summa inputi uchun (balandroq, yirikroq matn).
  final bool big;

  @override
  Widget build(BuildContext context) {
    final ds = context.ds;
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        if (label != null) ...[
          Text(label!, style: DsType.small(ds.textMuted).copyWith(fontWeight: FontWeight.w600)),
          const SizedBox(height: 6),
        ],
        TextField(
          controller: controller,
          keyboardType: keyboardType,
          onChanged: onChanged,
          obscureText: obscureText,
          style: big ? DsType.h2(ds.textPrimary) : DsType.body(ds.textPrimary),
          cursorColor: ds.primary,
          decoration: InputDecoration(
            hintText: hint,
            hintStyle: DsType.body(ds.textFaint),
            filled: true,
            fillColor: ds.card,
            isDense: true,
            contentPadding: EdgeInsets.symmetric(horizontal: 14, vertical: big ? 16 : 13),
            prefixIcon: prefixIcon != null ? Icon(prefixIcon, size: 18, color: ds.textMuted) : null,
            suffixText: suffixText,
            suffixStyle: DsType.caption(ds.textMuted),
            enabledBorder: OutlineInputBorder(
              borderRadius: DsRadius.all(DsRadius.md),
              borderSide: BorderSide(color: ds.border),
            ),
            focusedBorder: OutlineInputBorder(
              borderRadius: DsRadius.all(DsRadius.md),
              borderSide: BorderSide(color: ds.primary, width: 1.6),
            ),
          ),
        ),
      ],
    );
  }
}

// ═══════════════════════════════════════════════════════════════════
//  Avatar (bosh harflar)
// ═══════════════════════════════════════════════════════════════════

class DsAvatar extends StatelessWidget {
  const DsAvatar(this.name, {super.key, this.size = 40, this.tone = DsStatus.info});

  final String name;
  final double size;
  final DsStatus tone;

  String get _initials {
    final parts = name.trim().split(RegExp(r'\s+')).where((p) => p.isNotEmpty).toList();
    if (parts.isEmpty) return '?';
    if (parts.length == 1) return parts.first.characters.first.toUpperCase();
    return (parts[0].characters.first + parts[1].characters.first).toUpperCase();
  }

  @override
  Widget build(BuildContext context) {
    final ds = context.ds;
    final (bg, fg) = switch (tone) {
      DsStatus.success => (ds.successBg, ds.successFg),
      DsStatus.warning => (ds.warningBg, ds.warningFg),
      DsStatus.danger => (ds.dangerBg, ds.dangerFg),
      DsStatus.info || DsStatus.neutral => (ds.primarySoft, ds.primarySoftFg),
    };
    return Container(
      width: size,
      height: size,
      alignment: Alignment.center,
      decoration: BoxDecoration(color: bg, shape: BoxShape.circle),
      child: Text(_initials, style: DsType.small(fg).copyWith(fontWeight: FontWeight.w700)),
    );
  }
}

// ═══════════════════════════════════════════════════════════════════
//  Ro'yxat qatori (avatar · sarlavha · izoh · trailing)
// ═══════════════════════════════════════════════════════════════════

class DsListRow extends StatelessWidget {
  const DsListRow({
    super.key,
    required this.title,
    this.subtitle,
    this.leading,
    this.trailing,
    this.onTap,
  });

  final String title;
  final String? subtitle;
  final Widget? leading;
  final Widget? trailing;
  final VoidCallback? onTap;

  @override
  Widget build(BuildContext context) {
    final ds = context.ds;
    return Material(
      color: Colors.transparent,
      child: InkWell(
        onTap: onTap,
        borderRadius: DsRadius.all(DsRadius.md),
        child: Padding(
          padding: const EdgeInsets.symmetric(vertical: 8),
          child: Row(
            children: [
              if (leading != null) ...[leading!, const SizedBox(width: 12)],
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(title, style: DsType.bodyStrong(ds.textPrimary), maxLines: 1, overflow: TextOverflow.ellipsis),
                    if (subtitle != null) ...[
                      const SizedBox(height: 2),
                      Text(subtitle!, style: DsType.small(ds.textMuted), maxLines: 1, overflow: TextOverflow.ellipsis),
                    ],
                  ],
                ),
              ),
              if (trailing != null) ...[const SizedBox(width: 12), trailing!],
            ],
          ),
        ),
      ),
    );
  }
}

// ═══════════════════════════════════════════════════════════════════
//  Bo'lim sarlavhasi (title + "Barchasi" harakati)
// ═══════════════════════════════════════════════════════════════════

class DsSectionHeader extends StatelessWidget {
  const DsSectionHeader(this.title, {super.key, this.actionLabel, this.onAction});

  final String title;
  final String? actionLabel;
  final VoidCallback? onAction;

  @override
  Widget build(BuildContext context) {
    final ds = context.ds;
    return Row(
      children: [
        Expanded(child: Text(title, style: DsType.bodyStrong(ds.textPrimary))),
        if (actionLabel != null)
          GestureDetector(
            onTap: onAction,
            child: Text(actionLabel!, style: DsType.caption(ds.primary).copyWith(fontWeight: FontWeight.w600)),
          ),
      ],
    );
  }
}
