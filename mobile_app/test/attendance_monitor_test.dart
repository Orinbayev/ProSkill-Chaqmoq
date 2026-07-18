import 'package:flutter_test/flutter_test.dart';
import 'package:chaqmoq_mobile/screens/director/data/director_data.dart';

void main() {
  group('DirectorAttendanceMonitor.fromJson', () {
    test('backend JSON to\'liq parse qilinadi', () {
      final json = {
        'date': '2026-07-20',
        'summary': {
          'scheduled': 2, 'taken': 1, 'missing': 1, 'pending': 0, 'unscheduled': 1,
          'present': 3, 'late': 1, 'absent_excused': 1, 'absent_unexcused': 1,
        },
        'rows': [
          {
            'group_id': 1, 'group_name': 'English - 07', 'teacher_name': 'Aziz',
            'start_time': '10:00', 'has_time': true, 'status': 'missing',
            'present': 0, 'late': 0, 'absent_excused': 0, 'absent_unexcused': 0,
            'total_marked': 0, 'absentees': [],
          },
          {
            'group_id': 2, 'group_name': 'CEFR - 02', 'teacher_name': 'Malika',
            'start_time': '09:00', 'has_time': true, 'status': 'taken',
            'present': 3, 'late': 1, 'absent_excused': 1, 'absent_unexcused': 1,
            'total_marked': 6,
            'absentees': [
              {'name': 'Jasur', 'status': 'absent_unexcused', 'status_label': 'Sababsiz (Kelmadi)'},
            ],
          },
        ],
        'unscheduled': [
          {'group_id': 3, 'group_name': 'Matematika - 05', 'teacher_name': 'Kamola'},
        ],
      };

      final m = DirectorAttendanceMonitor.fromJson(json);

      expect(m.scheduled, 2);
      expect(m.taken, 1);
      expect(m.missing, 1);
      expect(m.unscheduled, 1);
      expect(m.isEmpty, false);

      expect(m.rows.length, 2);
      // Missing guruh
      expect(m.rows[0].status, 'missing');
      expect(m.rows[0].groupName, 'English - 07');
      // Taken guruh + kelmaganlar
      expect(m.rows[1].status, 'taken');
      expect(m.rows[1].present, 3);
      expect(m.rows[1].absentUnexcused, 1);
      expect(m.rows[1].absentees.length, 1);
      expect(m.rows[1].absentees.first.name, 'Jasur');
      expect(m.rows[1].absentees.first.statusLabel, 'Sababsiz (Kelmadi)');

      // Jadvalsiz guruh
      expect(m.unscheduledGroups.length, 1);
      expect(m.unscheduledGroups.first.groupName, 'Matematika - 05');
    });

    test('null JSON -> bo\'sh monitor', () {
      final m = DirectorAttendanceMonitor.fromJson(null);
      expect(m.isEmpty, true);
      expect(m.scheduled, 0);
      expect(m.rows, isEmpty);
      expect(m.unscheduledGroups, isEmpty);
    });

    test('empty konstanta bo\'sh', () {
      expect(DirectorAttendanceMonitor.empty.isEmpty, true);
    });
  });
}
