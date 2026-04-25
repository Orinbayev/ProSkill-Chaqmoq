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
        self.assertEqual(BACKUP_SCHEDULE_HOUR, 18)
        self.assertEqual(BACKUP_SCHEDULE_MINUTE, 0)

    @override_settings(TIME_ZONE="Asia/Tashkent")
    def test_backup_schedule_label_uses_project_timezone(self):
        self.assertEqual(get_backup_schedule_label(), "18:00 Asia/Tashkent")

    def test_backup_schedule_label_accepts_explicit_timezone(self):
        self.assertEqual(get_backup_schedule_label("Asia/Samarkand"), "18:00 Asia/Samarkand")

    @override_settings(BACKUP_BOT_TOKEN="backup-token", TELEGRAM_BOT_TOKEN="main-token")
    def test_backup_token_prefers_telegram_bot_token(self):
        self.assertEqual(_get_bot_token(), "main-token")

    @override_settings(TELEGRAM_BACKUP_CHAT_ID="-10042", BACKUP_GROUP_ID="-10077", TELEGRAM_GROUP_ID="-10099")
    def test_backup_group_prefers_dedicated_backup_chat(self):
        self.assertEqual(_get_group_id(), "-10042")
