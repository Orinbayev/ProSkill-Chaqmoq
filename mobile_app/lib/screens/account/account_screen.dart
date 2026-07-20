import 'package:chaqmoq_mobile/screens/profile/ideal_profile_screen.dart';
import 'package:flutter/material.dart';

/// Umumiy (fallback) hisob paneli — yagona ideal profil.
class AccountScreen extends StatelessWidget {
  const AccountScreen({super.key});

  @override
  Widget build(BuildContext context) {
    return const IdealProfileScreen(title: 'Profil');
  }
}
