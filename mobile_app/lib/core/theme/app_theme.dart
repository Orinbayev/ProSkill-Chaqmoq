import 'package:chaqmoq_mobile/core/design/ds_theme.dart';
import 'package:flutter/material.dart';

/// Ilova temasi — yagona "Chaqmoq Panellar" dizayn tizimi ([DsTheme]).
class AppTheme {
  const AppTheme._();

  static ThemeData get darkTheme => DsTheme.dark();
  static ThemeData get lightTheme => DsTheme.light();
}
