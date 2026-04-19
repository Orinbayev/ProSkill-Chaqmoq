from django.test import SimpleTestCase, override_settings

from core.services.db_backup_service import (
    BACKUP_SCHEDULE_HOUR,
    BACKUP_SCHEDULE_MINUTE,
    _get_bot_token,
    _get_group_id,
    get_backup_schedule_label,
)


class BackupScheduleTests(SimpleTestCase):
    def test_backup_schedule_constants_match_expected_time(self):
        self.assertEqual(BACKUP_SCHEDULE_HOUR, 17)
        self.assertEqual(BACKUP_SCHEDULE_MINUTE, 35)

    @override_settings(TIME_ZONE="Asia/Tashkent")
    def test_backup_schedule_label_uses_project_timezone(self):
        self.assertEqual(get_backup_schedule_label(), "17:35 Asia/Tashkent")

    def test_backup_schedule_label_accepts_explicit_timezone(self):
        self.assertEqual(get_backup_schedule_label("Asia/Samarkand"), "17:35 Asia/Samarkand")

    @override_settings(BACKUP_BOT_TOKEN="backup-token", TELEGRAM_BOT_TOKEN="main-token")
    def test_backup_token_prefers_dedicated_backup_token(self):
        self.assertEqual(_get_bot_token(), "backup-token")

    @override_settings(BACKUP_GROUP_ID="-10042", TELEGRAM_GROUP_ID="-10099")
    def test_backup_group_prefers_dedicated_backup_group(self):
        self.assertEqual(_get_group_id(), "-10042")
