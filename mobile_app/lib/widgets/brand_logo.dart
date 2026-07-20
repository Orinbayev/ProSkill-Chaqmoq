import 'package:chaqmoq_mobile/core/design/ds_colors.dart';
import 'package:chaqmoq_mobile/core/design/ds_tokens.dart';
import 'package:flutter/material.dart';

/// Asosiy ChaqmoqApp platforma logosi — barcha rollarda bir xil.
class BrandLogo extends StatelessWidget {
  const BrandLogo({
    super.key,
    this.size = 40,
    this.radius = 12,
    this.showShadow = true,
  });

  final double size;
  final double radius;
  final bool showShadow;

  @override
  Widget build(BuildContext context) {
    final ds = context.ds;
    return Container(
      width: size,
      height: size,
      decoration: BoxDecoration(
        borderRadius: BorderRadius.circular(radius),
        color: ds.card,
        border: Border.all(color: ds.border),
        boxShadow: showShadow
            ? [
                BoxShadow(
                  color: ds.primary.withValues(alpha: ds.isDark ? 0.28 : 0.14),
                  blurRadius: 12,
                  offset: const Offset(0, 4),
                ),
              ]
            : null,
      ),
      clipBehavior: Clip.antiAlias,
      child: Image.asset(
        ds.isDark
            ? 'assets/images/brand_logo_navy.png'
            : 'assets/images/brand_logo.png',
        fit: BoxFit.cover,
        errorBuilder: (_, _, _) => Icon(
          Icons.bolt_rounded,
          color: ds.primary,
          size: size * 0.55,
        ),
      ),
    );
  }
}

/// Login/splash uchun katta brand mark.
class BrandLogoHero extends StatelessWidget {
  const BrandLogoHero({super.key, this.size = 108});

  final double size;

  @override
  Widget build(BuildContext context) {
    final ds = context.ds;
    return Container(
      width: size,
      height: size,
      decoration: BoxDecoration(
        borderRadius: BorderRadius.circular(size * 0.26),
        gradient: LinearGradient(
          begin: Alignment.topLeft,
          end: Alignment.bottomRight,
          colors: ds.isDark
              ? const [Color(0xFF0C4A6E), Color(0xFF0369A1)]
              : [DsPalette.white, DsPalette.sky50],
        ),
        border: Border.all(
          color: ds.isDark
              ? DsPalette.sky700.withValues(alpha: 0.5)
              : DsPalette.sky200,
        ),
        boxShadow: [
          BoxShadow(
            color: ds.primary.withValues(alpha: ds.isDark ? 0.35 : 0.18),
            blurRadius: 28,
            offset: const Offset(0, 14),
          ),
          ...DsShadow.card(ds.isDark),
        ],
      ),
      padding: EdgeInsets.all(size * 0.09),
      child: ClipRRect(
        borderRadius: BorderRadius.circular(size * 0.18),
        child: Image.asset(
          ds.isDark
              ? 'assets/images/brand_logo_navy.png'
              : 'assets/images/brand_logo.png',
          fit: BoxFit.cover,
          errorBuilder: (_, _, _) => Icon(
            Icons.bolt_rounded,
            color: ds.primary,
            size: size * 0.45,
          ),
        ),
      ),
    );
  }
}
