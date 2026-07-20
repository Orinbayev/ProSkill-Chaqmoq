import 'package:chaqmoq_mobile/screens/profile/ideal_profile_screen.dart';
import 'package:flutter/material.dart';

/// Ustoz profili — yagona ideal profil (rasm, tahrirlash, parol, sozlamalar).
class TeacherProfileScreen extends StatelessWidget {
  const TeacherProfileScreen({super.key, this.onGoTab});

  final ValueChanged<int>? onGoTab;

  @override
  Widget build(BuildContext context) {
    return const IdealProfileScreen(title: 'Profil');
  }
}
