from unittest.mock import patch

from django.conf import settings
from django.core.handlers.base import BaseHandler
from django.db import connections
from django.test import SimpleTestCase

from core.db_router import ensure_connection, uses_default_database


class TenantDatabaseRouterTests(SimpleTestCase):
    dynamic_alias = "tenant_test_atomic_requests"

    def tearDown(self):
        settings.DATABASES.pop(self.dynamic_alias, None)
        connections.databases.pop(self.dynamic_alias, None)
        if hasattr(connections._connections, self.dynamic_alias):
            delattr(connections._connections, self.dynamic_alias)
        super().tearDown()

    def test_dynamic_connection_is_normalized_for_request_atomic_scan(self):
        ensure_connection(
            self.dynamic_alias,
            {
                "ENGINE": "django.db.backends.sqlite3",
                "NAME": ":memory:",
            },
        )

        dynamic_config = connections.databases[self.dynamic_alias]
        self.assertIn("ATOMIC_REQUESTS", dynamic_config)
        self.assertIn("AUTOCOMMIT", dynamic_config)
        self.assertIn("CONN_MAX_AGE", dynamic_config)
        self.assertIn("OPTIONS", dynamic_config)
        self.assertIn("TEST", dynamic_config)

        BaseHandler().make_view_atomic(lambda request: None)

    def test_default_postgres_identity_does_not_need_tenant_alias(self):
        databases = {
            "default": {
                "ENGINE": "django.db.backends.postgresql",
                "NAME": "chaqmoq",
                "USER": "chaqmoq_user",
                "PASSWORD": "secret",
                "HOST": "db.internal",
                "PORT": "5432",
            }
        }
        with patch.object(settings, "DATABASES", databases):
            self.assertTrue(
                uses_default_database(
                    {
                        "ENGINE": "django.db.backends.postgresql",
                        "NAME": "chaqmoq",
                        "USER": "chaqmoq_user",
                        "PASSWORD": "other-secret",
                        "HOST": "db.internal",
                        "PORT": "5432",
                    }
                )
            )
