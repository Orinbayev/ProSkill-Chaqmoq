import json

from django.test import TestCase, override_settings
from django.utils import timezone

from accounts.models import Center, ParentTelegramLinkToken, User
from accounts.services.parent_telegram_link import (
    ParentLinkError,
    consume_parent_telegram_invite,
    create_parent_telegram_invite,
)


@override_settings(
    TELEGRAM_BOT_USERNAME="chaqmoq_test_bot",
    TELEGRAM_BOT_USERNAME_FAMILY="chaqmoq_test_bot",
    API_SECRET="x" * 40,
)
class ParentTelegramLinkTests(TestCase):
    def setUp(self):
        self.center = Center.objects.create(name="Parent Link Center", slug="parent-link-center")
        self.admin = User.objects.create_user(
            email="admin-parent-link@test.uz",
            password="pass",
            role="director",
            center=self.center,
            ism="Admin",
            familya="User",
        )
        self.student = User.objects.create_user(
            email="student-parent-link@test.uz",
            password="pass",
            role="student",
            center=self.center,
            ism="Ali",
            familya="Valiyev",
        )

    def test_invite_consumption_links_parent_to_student_once(self):
        invite = create_parent_telegram_invite(student=self.student, created_by=self.admin)

        self.assertIn("https://t.me/chaqmoq_test_bot?start=parent_", invite.link)

        result = consume_parent_telegram_invite(
            raw_token=invite.token,
            telegram_id="90001",
            telegram_username="ali_parent",
            first_name="Parent",
            last_name="Valiyev",
        )

        self.student.refresh_from_db()
        parent = User.objects.get(pk=result["parent"]["id"])
        token = ParentTelegramLinkToken.objects.get(token=invite.token)

        self.assertEqual(self.student.parent_telegram_id, "90001")
        self.assertEqual(self.student.parent_telegram_username, "ali_parent")
        self.assertTrue(parent.children.filter(pk=self.student.pk).exists())
        self.assertIsNotNone(token.used_at)
        self.assertEqual(token.used_by_id, parent.id)

        with self.assertRaises(ParentLinkError):
            consume_parent_telegram_invite(raw_token=invite.token, telegram_id="90002")

    def test_new_invite_expires_previous_active_invite(self):
        first = create_parent_telegram_invite(student=self.student, created_by=self.admin)
        second = create_parent_telegram_invite(student=self.student, created_by=self.admin)

        first_token = ParentTelegramLinkToken.objects.get(token=first.token)
        self.assertLessEqual(first_token.expires_at, timezone.now())
        self.assertNotEqual(first.token, second.token)

    @override_settings(TELEGRAM_BOT_USERNAME="YOUR_BOT", TELEGRAM_BOT_USERNAME_FAMILY="")
    def test_link_never_uses_placeholder_bot(self):
        """'YOUR_BOT' placeholder ('You Bot') hech qachon linkga tushmasligi kerak."""
        invite = create_parent_telegram_invite(student=self.student, created_by=self.admin)
        self.assertNotIn("YOUR_BOT", invite.link)
        self.assertIn("https://t.me/ChaqmoqApp_Student_Bot?start=parent_", invite.link)

    def test_bot_api_consumes_parent_token(self):
        invite = create_parent_telegram_invite(student=self.student, created_by=self.admin)
        response = self.client.post(
            "/hisob/login/bot-parent-connect/",
            data=json.dumps(
                {
                    "token": invite.token,
                    "telegram_id": "777001",
                    "telegram_username": "bot_parent",
                    "first_name": "Bot",
                    "last_name": "Parent",
                }
            ),
            content_type="application/json",
            HTTP_X_API_SECRET="x" * 40,
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertTrue(payload["ok"])
        self.assertEqual(payload["student"]["id"], self.student.id)

        self.student.refresh_from_db()
        self.assertEqual(self.student.parent_telegram_id, "777001")
