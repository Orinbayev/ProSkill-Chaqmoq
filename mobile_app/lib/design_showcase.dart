// Dizayn tizimi galereyasini ishga tushirish uchun alohida entrypoint.
//
// Ishga tushirish (web orqali ko'rish):
//   flutter run -d chrome -t lib/design_showcase.dart
//
// Bu fayl ishlab chiqarish ilovasiga (main.dart) ta'sir qilmaydi.
import 'package:flutter/material.dart';

import 'core/design/ds_showcase.dart';

void main() => runApp(const DsShowcaseApp());
