import 'package:chaqmoq_mobile/core/utils/formatters.dart';
import 'package:flutter/material.dart';
import 'package:google_fonts/google_fonts.dart';

class AdaptiveAvatar extends StatelessWidget {
  const AdaptiveAvatar({
    super.key,
    required this.name,
    this.imageUrl = '',
    this.size = 56,
    this.icon = Icons.person_rounded,
    this.backgroundColor = const Color(0xFFEAF4FF),
    this.foregroundColor = const Color(0xFF1E73F8),
    this.iconScale = 0.46,
    this.fontScale = 0.34,
  });

  final String name;
  final String imageUrl;
  final double size;
  final IconData icon;
  final Color backgroundColor;
  final Color foregroundColor;
  final double iconScale;
  final double fontScale;

  @override
  Widget build(BuildContext context) {
    final placeholder = Container(
      width: size,
      height: size,
      alignment: Alignment.center,
      decoration: BoxDecoration(
        color: backgroundColor,
        shape: BoxShape.circle,
      ),
      child: _buildPlaceholderContent(),
    );

    if (imageUrl.trim().isEmpty) {
      return placeholder;
    }

    return ClipOval(
      child: Image.network(
        imageUrl,
        width: size,
        height: size,
        fit: BoxFit.cover,
        errorBuilder: (context, error, stackTrace) => placeholder,
      ),
    );
  }

  Widget _buildPlaceholderContent() {
    final initials = Formatters.initials(name).trim();
    if (initials.isNotEmpty && initials != 'CH') {
      return Text(
        initials,
        style: GoogleFonts.inter(
          color: foregroundColor,
          fontSize: size * fontScale,
          fontWeight: FontWeight.w800,
          height: 1,
        ),
      );
    }
    return Icon(icon, color: foregroundColor, size: size * iconScale);
  }
}
