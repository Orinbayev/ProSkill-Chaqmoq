import 'package:chaqmoq_mobile/screens/profile/ideal_profile_screen.dart';
import 'package:flutter/material.dart';

/// Direktor/Manager profili — to'g'ridan-to'g'ri ideal profil (ichki sahifa yo'q).
/// Asosiy joy: [DirectorAppShell] dagi "Profil" tab.
class DirectorProfileScreen extends StatelessWidget {
  const DirectorProfileScreen({super.key});

  @override
  Widget build(BuildContext context) {
    return const IdealProfileScreen(
      showAppBar: false,
      title: 'Profil',
    );
  }
}
