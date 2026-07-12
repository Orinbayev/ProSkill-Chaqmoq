// Director rolini (mock ma'lumot bilan) ko'rish uchun alohida entrypoint.
//
//   flutter run -d chrome -t lib/director_preview.dart
//
// Ishlab chiqarish ilovasiga (main.dart) ta'sir qilmaydi.
import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import 'core/design/ds_theme.dart';
import 'screens/director/data/director_mock_repository.dart';
import 'screens/director/data/director_provider.dart';
import 'screens/director/director_app_shell.dart';

void main() => runApp(const _DirectorPreviewApp());

class _DirectorPreviewApp extends StatefulWidget {
  const _DirectorPreviewApp();
  @override
  State<_DirectorPreviewApp> createState() => _DirectorPreviewAppState();
}

class _DirectorPreviewAppState extends State<_DirectorPreviewApp> {
  bool _dark = false;

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      debugShowCheckedModeBanner: false,
      title: 'Director — Chaqmoq',
      theme: DsTheme.light(),
      darkTheme: DsTheme.dark(),
      themeMode: _dark ? ThemeMode.dark : ThemeMode.light,
      home: ChangeNotifierProvider(
        create: (_) => DirectorProvider(const MockDirectorRepository()),
        child: DirectorAppShell(
          isDark: _dark,
          onToggleTheme: () => setState(() => _dark = !_dark),
        ),
      ),
    );
  }
}
