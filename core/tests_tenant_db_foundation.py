"""Phase 10: multi-tenant DB routing foundation."""
from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import patch

from django.conf import settings
from django.test import SimpleTestCase, TestCase, override_settings

from accounts.models import Center
from core.db_config import (
    build_tenant_db_config,
    center_has_dedicated_db,
    mask_db_config,
    resolve_routing_center,
    resolve_tenant_db_password,
    tenant_db_routing_enabled,
)
from core.db_router import (
    SHARED_APPS,
    TENANT_APPS,
    TenantDatabaseRouter,
    resolve_tenant_db_alias,
    uses_default_database,
)
from core.tenant_context import (
    clear_current_tenant,
    get_current_tenant,
    set_current_tenant,
    tenant_db_alias,
)
from core.test_utils import create_active_center
from education.models import Group


class TenantContextTests(SimpleTestCase):
    def tearDown(self):
        clear_current_tenant()

    def test_set_get_clear(self):
        center = SimpleNamespace(pk=1, parent_center_id=None, get_root_center=lambda: None)
        # no get_root that returns self
        center.get_root_center = lambda: center
        set_current_tenant(center)
        self.assertIs(get_current_tenant(), center)
        clear_current_tenant()
        self.assertIsNone(get_current_tenant())

    def test_stores_root_for_branch(self):
        root = SimpleNamespace(pk=10, parent_center_id=None, slug="root")
        root.get_root_center = lambda: root
        branch = SimpleNamespace(pk=11, parent_center_id=10, slug="branch")
        branch.get_root_center = lambda: root
        set_current_tenant(branch)
        self.assertIs(get_current_tenant(), root)
        self.assertEqual(tenant_db_alias(branch), None)  # no db_name


class DbConfigTests(SimpleTestCase):
    def test_password_from_env_by_id(self):
        center = SimpleNamespace(pk=42, slug="acme", db_password="legacy-plain")
        with patch.dict("os.environ", {"TENANT_DB_PASSWORD_42": "from-env"}, clear=False):
            self.assertEqual(resolve_tenant_db_password(center), "from-env")

    def test_password_falls_back_to_field(self):
        center = SimpleNamespace(pk=99, slug="x", db_password="field-secret")
        with patch.dict("os.environ", {}, clear=False):
            # Ensure specific keys absent
            import os

            os.environ.pop("TENANT_DB_PASSWORD_99", None)
            os.environ.pop("TENANT_DB_PASSWORD_X", None)
            os.environ.pop("TENANT_DB_PASSWORD", None)
            self.assertEqual(resolve_tenant_db_password(center), "field-secret")

    def test_mask_password(self):
        masked = mask_db_config({"PASSWORD": "secret", "NAME": "db"})
        self.assertEqual(masked["PASSWORD"], "***")
        self.assertEqual(masked["NAME"], "db")

    def test_branch_resolves_to_root_config(self):
        root = SimpleNamespace(
            pk=1,
            slug="root",
            parent_center_id=None,
            db_name="tenant_root",
            db_user="u",
            db_password="",
            db_host="db.host",
            db_port="5432",
            get_root_center=lambda: root,
        )
        branch = SimpleNamespace(
            pk=2,
            slug="branch",
            parent_center_id=1,
            db_name=None,
            get_root_center=lambda: root,
        )
        self.assertIs(resolve_routing_center(branch), root)
        with patch.dict("os.environ", {"TENANT_DB_PASSWORD_1": "pw"}):
            cfg = build_tenant_db_config(branch)
        self.assertEqual(cfg["NAME"], "tenant_root")
        self.assertEqual(cfg["PASSWORD"], "pw")


@override_settings(TENANT_DB_ROUTING_ENABLED=False)
class RouterDisabledTests(TestCase):
    def test_routing_flag_off(self):
        self.assertFalse(tenant_db_routing_enabled())

    def test_always_default_when_disabled(self):
        center = create_active_center(name="R", slug="route-off")
        center.db_name = "other_db"
        center.save(update_fields=["db_name"])
        set_current_tenant(center)
        try:
            self.assertEqual(resolve_tenant_db_alias(center), "default")
            router = TenantDatabaseRouter()
            self.assertEqual(router.db_for_read(Group), "default")
            self.assertEqual(router.db_for_read(Center), "default")
        finally:
            clear_current_tenant()


@override_settings(TENANT_DB_ROUTING_ENABLED=True)
class RouterEnabledTests(TestCase):
    def tearDown(self):
        clear_current_tenant()
        # drop dynamic aliases
        for key in list(settings.DATABASES.keys()):
            if key.startswith("tenant_"):
                settings.DATABASES.pop(key, None)

    def test_shared_apps_always_default(self):
        router = TenantDatabaseRouter()
        self.assertEqual(router.db_for_read(Center), "default")
        self.assertIn("accounts", SHARED_APPS)

    def test_dedicated_db_routes_tenant_apps(self):
        center = create_active_center(name="Dedicated", slug="ded-db")
        center.db_name = "tenant_ded"
        center.db_user = "tu"
        center.db_host = "127.0.0.1"
        center.db_port = "5432"
        center.save(update_fields=["db_name", "db_user", "db_host", "db_port"])

        with patch.dict("os.environ", {"TENANT_DB_PASSWORD_1": "x"}, clear=False):
            # id may not be 1 — set by actual pk
            import os

            os.environ[f"TENANT_DB_PASSWORD_{center.pk}"] = "secret-pw"
            set_current_tenant(center)
            # Mock uses_default_database False by pointing default to different name
            with patch(
                "core.db_router.uses_default_database", return_value=False
            ), patch("core.db_router.ensure_connection") as ensure:
                ensure.side_effect = lambda alias, config: config
                alias = resolve_tenant_db_alias(center)
                self.assertEqual(alias, f"tenant_{center.pk}")
                router = TenantDatabaseRouter()
                # education is tenant app
                self.assertEqual(router.db_for_read(Group), f"tenant_{center.pk}")
                # accounts is shared
                self.assertEqual(router.db_for_read(Center), "default")

    def test_same_as_default_stays_on_default(self):
        center = create_active_center(name="Same", slug="same-db")
        # Match sqlite default identity path → uses_default True for non-postgres
        center.db_name = "anything"
        center.save(update_fields=["db_name"])
        set_current_tenant(center)
        # Local ENGINE is sqlite → uses_default_database returns True
        self.assertEqual(resolve_tenant_db_alias(center), "default")

    def test_allow_migrate_tenant_alias(self):
        router = TenantDatabaseRouter()
        self.assertTrue(router.allow_migrate("default", "education"))
        self.assertTrue(router.allow_migrate("tenant_9", "education"))
        self.assertFalse(router.allow_migrate("tenant_9", "accounts"))
        self.assertIn("education", TENANT_APPS)


class CenterSaveNoPasswordAutofillTests(TestCase):
    @override_settings(
        TENANT_DB_AUTO_FILL_METADATA=False,
        DATABASES={
            "default": {
                "ENGINE": "django.db.backends.postgresql",
                "NAME": "main",
                "USER": "main_user",
                "PASSWORD": "MAIN_SECRET",
                "HOST": "db",
                "PORT": "5432",
            }
        },
    )
    def test_does_not_copy_default_password(self):
        c = Center(name="NoPw", slug="no-pw-copy")
        c.save()
        c.refresh_from_db()
        self.assertIn(c.db_password in (None, ""), [True])
