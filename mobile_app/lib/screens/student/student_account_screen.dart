import 'package:chaqmoq_mobile/screens/profile/ideal_profile_screen.dart';
import 'package:flutter/material.dart';

/// O'quvchi profili — rasm o'zgartirish + telefon; ism markaz tomonidan.
class StudentAccountScreen extends StatelessWidget {
  const StudentAccountScreen({super.key});

  @override
  Widget build(BuildContext context) {
    return const IdealProfileScreen(title: 'Profil');
  }
}
