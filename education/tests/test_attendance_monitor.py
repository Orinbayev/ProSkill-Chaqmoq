"""Kunlik davomat nazorati servisi testlari."""
from datetime import date, time

from django.test import TestCase
from django.contrib.auth import get_user_model
from freezegun import freeze_time

from accounts.models import Center
from core.test_utils import activate_center
from education.models import Attendance, Enrollment, Group, GroupSchedule
from education.services.attendance_monitor import (
    get_attendance_monitor, STATUS_TAKEN, STATUS_MISSING, STATUS_PENDING,
)

User = get_user_model()

FROZEN = "2026-07-20 09:00:00"          # UTC 09:00 = Asia/Tashkent 14:00 (dushanba)
TODAY = date(2026, 7, 20)
ISO = TODAY.isoweekday()                # bugungi kun (isoweekday)
OTHER_ISO = ISO % 7 + 1                 # boshqa kun


@freeze_time(FROZEN)
class AttendanceMonitorTests(TestCase):
    def setUp(self):
        self.center = Center.objects.create(name="AM", slug="am-center")
        activate_center(self.center)
        self.teacher = User.objects.create_user(
            email="t@am.test", password="x", role="teacher", center=self.center,
            ism="Olim", familya="Ustoz",
        )
        self.students = [
            User.objects.create_user(
                email=f"s{i}@am.test", password="x", role="student", center=self.center,
                ism=f"O'quvchi{i}", familya="Test",
            ) for i in range(5)
        ]

    def _group(self, name, weekday, start=time(10, 0)):
        g = Group.objects.create(
            center=self.center, nom=name, oqituvchi=self.teacher,
            kurs_narxi=300_000, oqituvchi_foiz=40, oy_dars_soni=12,
        )
        GroupSchedule.objects.create(
            center=self.center, group=g, weekday=weekday,
            start_time=start, end_time=time(start.hour + 1, 0),
        )
        for s in self.students:
            Enrollment.objects.create(
                center=self.center, group=g, student=s, kurs_narhi=300_000,
                oqituvchi_foiz=40, is_active=True,
            )
        return g

    def _mark(self, group, statuses):
        for s, st in zip(self.students, statuses):
            Attendance.objects.create(
                center=self.center, group=group, student=s, teacher=self.teacher,
                date=TODAY, status=st, present=(st == "present"),
            )

    def test_taken_group_reports_counts(self):
        g = self._group("Taken", ISO, start=time(9, 0))
        self._mark(g, ["present", "present", "present", "absent_excused", "absent_unexcused"])
        data = get_attendance_monitor(self.center, TODAY)
        row = next(r for r in data["rows"] if r["group_id"] == g.id)
        self.assertEqual(row["status"], STATUS_TAKEN)
        self.assertEqual(row["present"], 3)
        self.assertEqual(row["absent_excused"], 1)
        self.assertEqual(row["absent_unexcused"], 1)
        # kelmaganlar sabab bilan
        self.assertEqual(len(row["absentees"]), 2)
        labels = {a["status"] for a in row["absentees"]}
        self.assertEqual(labels, {"absent_excused", "absent_unexcused"})

    def test_missing_when_time_passed_and_no_attendance(self):
        # dars 09:00 da, hozir 14:00 → o'tib ketgan, davomat yo'q → MISSING
        g = self._group("Forgot", ISO, start=time(9, 0))
        data = get_attendance_monitor(self.center, TODAY)
        row = next(r for r in data["rows"] if r["group_id"] == g.id)
        self.assertEqual(row["status"], STATUS_MISSING)

    def test_pending_when_lesson_not_due_yet(self):
        # dars 18:00 da, hozir 14:00 → hali vaqti kelmagan → PENDING
        g = self._group("Later", ISO, start=time(18, 0))
        data = get_attendance_monitor(self.center, TODAY)
        row = next(r for r in data["rows"] if r["group_id"] == g.id)
        self.assertEqual(row["status"], STATUS_PENDING)

    def test_group_not_scheduled_today_is_excluded(self):
        self._group("OtherDay", OTHER_ISO, start=time(10, 0))
        data = get_attendance_monitor(self.center, TODAY)
        self.assertEqual(data["rows"], [])

    def test_summary_aggregation(self):
        g1 = self._group("A", ISO, start=time(9, 0))
        self._mark(g1, ["present"] * 5)                       # taken
        self._group("B", ISO, start=time(8, 0))               # missing (o'tib ketgan)
        self._group("C", ISO, start=time(20, 0))              # pending (kelmagan)
        data = get_attendance_monitor(self.center, TODAY)
        s = data["summary"]
        self.assertEqual(s["scheduled"], 3)
        self.assertEqual(s["taken"], 1)
        self.assertEqual(s["missing"], 1)
        self.assertEqual(s["pending"], 1)
        self.assertEqual(s["present"], 5)
        # tartib: missing avval keladi
        self.assertEqual(data["rows"][0]["status"], STATUS_MISSING)

    def test_past_day_without_attendance_is_missing(self):
        # o'tgan kun (jadval bo'yicha dars bo'lган) — davomat yo'q → MISSING
        past = TODAY  # frozen bugun; kelasi darsni tekshirish uchun bugunni ishlatamiz
        g = self._group("Past", ISO, start=time(10, 0))
        data = get_attendance_monitor(self.center, past)
        row = next(r for r in data["rows"] if r["group_id"] == g.id)
        self.assertEqual(row["status"], STATUS_MISSING)
