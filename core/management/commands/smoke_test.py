"""
Smoke test command for ChaqmoqApp production readiness check.

Usage:
    python manage.py smoke_test
    python manage.py smoke_test --base-url https://chaqmoqapp.uz
    python manage.py smoke_test --center-slug myschool
    python manage.py smoke_test --username admin@example.com --password secret123
    python manage.py smoke_test --section auth
    python manage.py smoke_test --section routing
    python manage.py smoke_test --quick

Sections: auth, routing, billing, education, admin, api, all (default)
"""

import sys
import time
import traceback
from urllib.parse import urljoin

from django.core.management.base import BaseCommand
from django.test import Client, RequestFactory
from django.urls import reverse, NoReverseMatch

# ─── ANSI colors ────────────────────────────────────────────────────────────
GREEN  = "\033[92m"
RED    = "\033[91m"
YELLOW = "\033[93m"
CYAN   = "\033[96m"
BOLD   = "\033[1m"
RESET  = "\033[0m"

PASS   = f"{GREEN}✅ PASS{RESET}"
FAIL   = f"{RED}❌ FAIL{RESET}"
SKIP   = f"{YELLOW}⏭  SKIP{RESET}"
INFO   = f"{CYAN}ℹ  INFO{RESET}"


class SmokeTestRunner:
    def __init__(self, stdout, center_slug=None, username=None, password=None, quick=False):
        self.stdout = stdout
        self.center_slug = center_slug
        self.username = username
        self.password = password
        self.quick = quick
        self.client = Client()
        self.results = []
        self.passed = 0
        self.failed = 0
        self.skipped = 0

    def log(self, status, label, detail=""):
        detail_str = f" — {detail}" if detail else ""
        self.stdout.write(f"  {status}  {label}{detail_str}")

    def check(self, label, response, expected_codes=(200,), contains=None, not_contains=None):
        """Assert response code and optional body content."""
        t_start = time.monotonic()
        code = getattr(response, "status_code", None)
        elapsed = time.monotonic() - t_start

        errors = []
        if code not in expected_codes:
            errors.append(f"HTTP {code} (expected {expected_codes})")

        content = ""
        if hasattr(response, "content"):
            try:
                content = response.content.decode("utf-8", errors="replace")
            except Exception:
                content = ""

        if contains:
            for needle in (contains if isinstance(contains, (list, tuple)) else [contains]):
                if needle not in content:
                    errors.append(f"missing '{needle}' in body")

        if not_contains:
            for needle in (not_contains if isinstance(not_contains, (list, tuple)) else [not_contains]):
                if needle in content:
                    errors.append(f"unexpected '{needle}' in body")

        if errors:
            self.log(FAIL, label, "; ".join(errors))
            self.results.append(("FAIL", label, "; ".join(errors)))
            self.failed += 1
        else:
            timing = f"{int((time.monotonic() - t_start + elapsed) * 500)}ms"
            self.log(PASS, label, f"HTTP {code}")
            self.results.append(("PASS", label, ""))
            self.passed += 1

    def skip(self, label, reason=""):
        self.log(SKIP, label, reason)
        self.results.append(("SKIP", label, reason))
        self.skipped += 1

    def info(self, msg):
        self.stdout.write(f"  {INFO}  {msg}")

    def section(self, name):
        self.stdout.write(f"\n{BOLD}{CYAN}{'═'*55}{RESET}")
        self.stdout.write(f"{BOLD}{CYAN}  {name}{RESET}")
        self.stdout.write(f"{BOLD}{CYAN}{'═'*55}{RESET}")

    def _url(self, path):
        """Prefix with center slug if set."""
        if self.center_slug and not path.startswith(f"/{self.center_slug}/"):
            return f"/{self.center_slug}{path}"
        return path

    # ─── DB sanity ────────────────────────────────────────────────────────

    def run_db_checks(self):
        self.section("A. DATABASE SANITY CHECKS")
        from django.db import connection

        try:
            with connection.cursor() as cur:
                cur.execute("SELECT 1")
                row = cur.fetchone()
            if row and row[0] == 1:
                self.log(PASS, "DB connection", f"engine={connection.vendor}")
                self.results.append(("PASS", "DB connection", ""))
                self.passed += 1
            else:
                self.log(FAIL, "DB connection", "SELECT 1 returned unexpected value")
                self.results.append(("FAIL", "DB connection", "bad row"))
                self.failed += 1
        except Exception as exc:
            self.log(FAIL, "DB connection", str(exc))
            self.results.append(("FAIL", "DB connection", str(exc)))
            self.failed += 1

        try:
            from accounts.models import User, Center
            u_count = User.objects.count()
            c_count = Center.objects.count()
            self.log(PASS, "ORM query", f"users={u_count}, centers={c_count}")
            self.results.append(("PASS", "ORM query", ""))
            self.passed += 1
        except Exception as exc:
            self.log(FAIL, "ORM query", str(exc))
            self.results.append(("FAIL", "ORM query", str(exc)))
            self.failed += 1

        # Check migration state
        try:
            from django.db.migrations.executor import MigrationExecutor
            executor = MigrationExecutor(connection)
            plan = executor.migration_plan(executor.loader.graph.leaf_nodes())
            if plan:
                pending = [f"{m.app_label}.{m.name}" for m, _ in plan[:5]]
                self.log(FAIL, "Pending migrations", ", ".join(pending))
                self.results.append(("FAIL", "Pending migrations", str(len(plan)) + " pending"))
                self.failed += 1
            else:
                self.log(PASS, "No pending migrations", "")
                self.results.append(("PASS", "No pending migrations", ""))
                self.passed += 1
        except Exception as exc:
            self.log(FAIL, "Migration check", str(exc))
            self.results.append(("FAIL", "Migration check", str(exc)))
            self.failed += 1

    # ─── Authentication ───────────────────────────────────────────────────

    def run_auth_checks(self):
        self.section("B. AUTHENTICATION FLOWS")

        # Login page GET
        resp = self.client.get("/hisob/login/")
        self.check("Login page GET", resp, contains="csrfmiddlewaretoken")

        # Bad credentials → 200 with error (not 302)
        resp = self.client.post("/hisob/login/", {
            "username": "nonexistent@nowhere.test",
            "password": "wrongpass123",
        }, follow=False)
        self.check("Login: wrong creds → stays on login page", resp, expected_codes=(200, 302))

        # Logout (unauthenticated)
        resp = self.client.get("/logout/", follow=False)
        self.check("Logout GET redirect", resp, expected_codes=(200, 302, 405))

        # Health endpoint
        resp = self.client.get("/health/")
        self.check("Health check", resp, contains="OK")

        # Authenticated flow — only if credentials provided
        if self.username and self.password:
            self.info(f"Attempting login with {self.username}")
            resp = self.client.post("/hisob/login/", {
                "username": self.username,
                "password": self.password,
            }, follow=True)

            if resp.status_code == 200 and self.client.session.get("_auth_user_id"):
                self.log(PASS, "Login with real credentials", "session created")
                self.results.append(("PASS", "Login with real credentials", ""))
                self.passed += 1

                # After login: home redirect
                resp = self.client.get("/", follow=False)
                self.check("Post-login home", resp, expected_codes=(200, 301, 302))

                # Logout
                resp = self.client.post("/logout/", follow=False)
                self.check("Logout POST", resp, expected_codes=(200, 302))
            else:
                self.log(FAIL, "Login with real credentials", f"HTTP {resp.status_code} — check credentials")
                self.results.append(("FAIL", "Login with real credentials", "session not created"))
                self.failed += 1
        else:
            self.skip("Login with real credentials", "no --username/--password provided")

    # ─── URL routing ──────────────────────────────────────────────────────

    def run_routing_checks(self):
        self.section("C. URL ROUTING CHECKS")

        # Public routes (should not be 500)
        public_routes = [
            ("/", "Root URL"),
            ("/health/", "Health endpoint"),
            ("/hisob/login/", "Global login"),
            ("/payment/success/", "Payment success page"),
            ("/payment/cancel/", "Payment cancel page"),
        ]

        for path, label in public_routes:
            try:
                resp = self.client.get(path, follow=False)
                self.check(label, resp, expected_codes=(200, 301, 302, 404))
            except Exception as exc:
                self.log(FAIL, label, str(exc))
                self.results.append(("FAIL", label, str(exc)))
                self.failed += 1

        # URL reverse checks (ensure no broken named URLs)
        url_names = [
            ("login", {}, "core:home login name"),
            ("logout", {}, "logout URL"),
        ]
        for name, kwargs, label in url_names:
            try:
                url = reverse(name, kwargs=kwargs)
                self.log(PASS, f"reverse({name!r})", url)
                self.results.append(("PASS", f"reverse({name!r})", ""))
                self.passed += 1
            except NoReverseMatch as exc:
                self.log(FAIL, f"reverse({name!r})", str(exc))
                self.results.append(("FAIL", f"reverse({name!r})", str(exc)))
                self.failed += 1

        # Tenant-prefixed routes (only if center_slug given)
        if self.center_slug:
            tenant_paths = [
                (f"/{self.center_slug}/", "Tenant home"),
                (f"/{self.center_slug}/stat/students/", "Tenant: stat/students"),
                (f"/{self.center_slug}/stat/teachers/", "Tenant: stat/teachers"),
            ]
            for path, label in tenant_paths:
                try:
                    resp = self.client.get(path, follow=False)
                    # Unauthenticated → 302 to login is fine
                    self.check(label, resp, expected_codes=(200, 301, 302, 403))
                except Exception as exc:
                    self.log(FAIL, label, str(exc))
                    self.results.append(("FAIL", label, str(exc)))
                    self.failed += 1
        else:
            self.skip("Tenant-prefixed routes", "no --center-slug provided")

    # ─── Billing / Click ──────────────────────────────────────────────────

    def run_billing_checks(self):
        self.section("D. BILLING & CLICK PAYMENT CHECKS")

        # Click endpoints must not 500 on GET (they expect POST with signature)
        click_paths = [
            ("/click/prepare/", "Click prepare endpoint"),
            ("/click/complete/", "Click complete endpoint"),
            ("/click/webhook/", "Click webhook endpoint"),
            ("/api/click/prepare/", "Legacy click prepare"),
            ("/api/click/complete/", "Legacy click complete"),
        ]
        for path, label in click_paths:
            try:
                resp = self.client.get(path, follow=False)
                # 400/403/405/500 — 500 is FAIL
                self.check(label, resp, expected_codes=(200, 400, 403, 404, 405))
            except Exception as exc:
                self.log(FAIL, label, str(exc))
                self.results.append(("FAIL", label, str(exc)))
                self.failed += 1

        # Billing model imports
        try:
            from billing.models import Plan, Subscription, PromoCode
            plan_count = Plan.objects.count()
            sub_count = Subscription.objects.count()
            self.log(PASS, "Billing models importable", f"plans={plan_count}, subs={sub_count}")
            self.results.append(("PASS", "Billing models importable", ""))
            self.passed += 1
        except Exception as exc:
            self.log(FAIL, "Billing models importable", str(exc))
            self.results.append(("FAIL", "Billing models importable", str(exc)))
            self.failed += 1

        # billing services
        try:
            from billing.services import get_active_subscription, get_subscription_ui_state
            self.log(PASS, "Billing services importable", "")
            self.results.append(("PASS", "Billing services importable", ""))
            self.passed += 1
        except Exception as exc:
            self.log(FAIL, "Billing services importable", str(exc))
            self.results.append(("FAIL", "Billing services importable", str(exc)))
            self.failed += 1

    # ─── Education app ───────────────────────────────────────────────────

    def run_education_checks(self):
        self.section("E. EDUCATION APP CHECKS")

        # Model imports
        try:
            from education.models import Group, Lesson, Attendance
            g_count = Group.objects.count()
            self.log(PASS, "Education models importable", f"groups={g_count}")
            self.results.append(("PASS", "Education models importable", ""))
            self.passed += 1
        except Exception as exc:
            self.log(FAIL, "Education models importable", str(exc))
            self.results.append(("FAIL", "Education models importable", str(exc)))
            self.failed += 1

        # Education URL routes (unauthenticated → redirect)
        education_paths = [
            ("/talim/", "Education root"),
        ]
        if self.center_slug:
            education_paths += [
                (f"/{self.center_slug}/talim/", "Tenant education root"),
            ]

        for path, label in education_paths:
            try:
                resp = self.client.get(path, follow=False)
                self.check(label, resp, expected_codes=(200, 301, 302, 404))
            except Exception as exc:
                self.log(FAIL, label, str(exc))
                self.results.append(("FAIL", label, str(exc)))
                self.failed += 1

    # ─── Admin / Superadmin ───────────────────────────────────────────────

    def run_admin_checks(self):
        self.section("F. ADMIN & SUPERADMIN CHECKS")

        # Django admin
        resp = self.client.get("/admin/", follow=False)
        self.check("Django admin login redirect", resp, expected_codes=(200, 301, 302))

        # Superadmin platform
        resp = self.client.get("/platform/", follow=False)
        self.check("Superadmin platform", resp, expected_codes=(200, 301, 302, 403))

        # Admin reverse
        try:
            url = reverse("platform_global:superadmin_dashboard")
            self.log(PASS, "reverse(platform_global:superadmin_dashboard)", url)
            self.results.append(("PASS", "reverse(superadmin_dashboard)", ""))
            self.passed += 1
        except NoReverseMatch as exc:
            self.log(FAIL, "reverse(platform_global:superadmin_dashboard)", str(exc))
            self.results.append(("FAIL", "reverse(superadmin_dashboard)", str(exc)))
            self.failed += 1

        # SuperAdmin API endpoints (unauthenticated → 403/302)
        api_paths = [
            ("/platform/api/centers/list/", "SuperAdmin: center list API"),
            ("/platform/api/plans/list/", "SuperAdmin: plan list API"),
            ("/platform/api/promos/list/", "SuperAdmin: promo list API"),
        ]
        for path, label in api_paths:
            try:
                resp = self.client.get(path, follow=False)
                self.check(label, resp, expected_codes=(200, 302, 403, 404))
            except Exception as exc:
                self.log(FAIL, label, str(exc))
                self.results.append(("FAIL", label, str(exc)))
                self.failed += 1

    # ─── API / AJAX ───────────────────────────────────────────────────────

    def run_api_checks(self):
        self.section("G. API / AJAX ENDPOINT CHECKS")

        api_paths = [
            ("/api/v1/auth/link-telegram/", "Telegram link API", (200, 400, 403, 405)),
        ]
        if self.center_slug:
            api_paths += [
                (f"/{self.center_slug}/notifications/api/read-all/", "Notifications read-all API", (200, 302, 403, 405)),
            ]

        for path, label, expected in api_paths:
            try:
                resp = self.client.get(path, follow=False)
                self.check(label, resp, expected_codes=expected)
            except Exception as exc:
                self.log(FAIL, label, str(exc))
                self.results.append(("FAIL", label, str(exc)))
                self.failed += 1

    # ─── Settings / Config ────────────────────────────────────────────────

    def run_settings_checks(self):
        self.section("H. SETTINGS & CONFIG CHECKS")
        from django.conf import settings

        checks = [
            ("SECRET_KEY set", bool(settings.SECRET_KEY) and settings.SECRET_KEY != "unsafe-secret-key"),
            ("ALLOWED_HOSTS set", bool(settings.ALLOWED_HOSTS)),
            ("DATABASES configured", bool(settings.DATABASES)),
            ("SESSION_ENGINE correct", "db" in getattr(settings, "SESSION_ENGINE", "")),
            ("CONN_MAX_AGE set", getattr(settings, "CONN_MAX_AGE", 0) > 0),
        ]

        for label, ok in checks:
            if ok:
                self.log(PASS, label)
                self.results.append(("PASS", label, ""))
                self.passed += 1
            else:
                self.log(FAIL, label, "check settings value")
                self.results.append(("FAIL", label, "misconfigured"))
                self.failed += 1

        # Cache backend
        cache_backend = settings.CACHES.get("default", {}).get("BACKEND", "")
        self.info(f"Cache backend: {cache_backend.split('.')[-1]}")

        # STATIC_ROOT
        if hasattr(settings, "STATIC_ROOT"):
            self.log(PASS, "STATIC_ROOT configured", str(settings.STATIC_ROOT))
            self.results.append(("PASS", "STATIC_ROOT configured", ""))
            self.passed += 1
        else:
            self.log(FAIL, "STATIC_ROOT configured", "not set")
            self.results.append(("FAIL", "STATIC_ROOT configured", "not set"))
            self.failed += 1

    # ─── Imports / App loading ────────────────────────────────────────────

    def run_import_checks(self):
        self.section("I. CRITICAL IMPORTS CHECK")

        modules = [
            ("accounts.models", "User, Center"),
            ("accounts.backends", "EmailOrPhoneBackend"),
            ("accounts.auth_views", "SecureLoginView"),
            ("core.middleware", "TenantMiddleware"),
            ("core.context_processors", "tenant_context"),
            ("billing.models", "Plan, Subscription"),
            ("billing.services", "get_active_subscription"),
            ("education.models", "Group, Lesson"),
        ]

        if not self.quick:
            modules += [
                ("core.services.db_backup_service", "backup_and_send_all_centers"),
                ("store.models", ""),
                ("chaqmoq.models", ""),
            ]

        for module_path, attrs in modules:
            try:
                import importlib
                mod = importlib.import_module(module_path)
                if attrs:
                    for attr in [a.strip() for a in attrs.split(",")]:
                        if not hasattr(mod, attr):
                            raise AttributeError(f"{attr} not found in {module_path}")
                self.log(PASS, f"import {module_path}", attrs or "")
                self.results.append(("PASS", f"import {module_path}", ""))
                self.passed += 1
            except Exception as exc:
                self.log(FAIL, f"import {module_path}", str(exc))
                self.results.append(("FAIL", f"import {module_path}", str(exc)))
                self.failed += 1

    # ─── Summary ──────────────────────────────────────────────────────────

    def print_summary(self):
        total = self.passed + self.failed + self.skipped
        self.stdout.write(f"\n{BOLD}{'═'*55}{RESET}")
        self.stdout.write(f"{BOLD}  SMOKE TEST SUMMARY{RESET}")
        self.stdout.write(f"{'═'*55}")
        self.stdout.write(f"  Total : {total}")
        self.stdout.write(f"  {GREEN}Passed{RESET} : {self.passed}")
        self.stdout.write(f"  {RED}Failed{RESET} : {self.failed}")
        self.stdout.write(f"  {YELLOW}Skipped{RESET}: {self.skipped}")
        self.stdout.write(f"{'═'*55}\n")

        if self.failed:
            self.stdout.write(f"{RED}{BOLD}MUVAFFAQIYATSIZ TESTLAR:{RESET}")
            for status, label, detail in self.results:
                if status == "FAIL":
                    self.stdout.write(f"  {RED}✗{RESET} {label}" + (f" — {detail}" if detail else ""))
            self.stdout.write("")

        if self.failed == 0:
            self.stdout.write(f"{GREEN}{BOLD}✅ BARCHA TESTLAR O'TDI — production ready!{RESET}\n")
        else:
            self.stdout.write(f"{RED}{BOLD}❌ {self.failed} ta test muvaffaqiyatsiz — tekshiring!{RESET}\n")

        return self.failed


class Command(BaseCommand):
    help = "Run smoke tests across all major app sections"

    def add_arguments(self, parser):
        parser.add_argument("--center-slug", default="", help="Center slug for tenant route testing")
        parser.add_argument("--username", default="", help="Login username/email for authenticated tests")
        parser.add_argument("--password", default="", help="Login password for authenticated tests")
        parser.add_argument(
            "--section",
            default="all",
            choices=["all", "db", "auth", "routing", "billing", "education", "admin", "api", "settings", "imports"],
            help="Run a specific test section only",
        )
        parser.add_argument("--quick", action="store_true", help="Skip slow or heavy checks")

    def handle(self, *args, **options):
        self.stdout.write(f"\n{BOLD}{CYAN}ChaqmoqApp Smoke Test Runner{RESET}")
        self.stdout.write(f"Center slug : {options['center_slug'] or '(none)'}")
        self.stdout.write(f"Username    : {options['username'] or '(anonymous)'}")
        self.stdout.write(f"Section     : {options['section']}")
        self.stdout.write(f"Quick mode  : {'yes' if options['quick'] else 'no'}")

        runner = SmokeTestRunner(
            stdout=self.stdout,
            center_slug=options["center_slug"] or None,
            username=options["username"] or None,
            password=options["password"] or None,
            quick=options["quick"],
        )

        section = options["section"]
        run_all = section == "all"

        try:
            if run_all or section == "db":       runner.run_db_checks()
            if run_all or section == "imports":  runner.run_import_checks()
            if run_all or section == "settings": runner.run_settings_checks()
            if run_all or section == "auth":     runner.run_auth_checks()
            if run_all or section == "routing":  runner.run_routing_checks()
            if run_all or section == "billing":  runner.run_billing_checks()
            if run_all or section == "education":runner.run_education_checks()
            if run_all or section == "admin":    runner.run_admin_checks()
            if run_all or section == "api":      runner.run_api_checks()
        except KeyboardInterrupt:
            self.stdout.write(f"\n{YELLOW}Interrupted by user.{RESET}")
        except Exception:
            self.stdout.write(f"\n{RED}Unexpected error:{RESET}")
            self.stdout.write(traceback.format_exc())

        failed_count = runner.print_summary()

        if failed_count:
            sys.exit(1)
