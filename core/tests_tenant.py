"""Unit tests for core.tenant isolation helpers (IDOR foundation)."""
from __future__ import annotations

from django.http import Http404
from django.test import RequestFactory, TestCase

from accounts.models import Center, User
from core.tenant import (
    assert_same_center,
    get_request_center,
    get_tenant_object_or_404,
    tenant_filter_qs,
)
from education.models import Category, Group


class TenantHelperTests(TestCase):
    def setUp(self):
        self.factory = RequestFactory()
        self.center_a = Center.objects.create(name="Center A", slug="tenant-a")
        self.center_b = Center.objects.create(name="Center B", slug="tenant-b")

        self.student_a = User.objects.create_user(
            email="student_a@example.com",
            password="password",
            role="student",
            center=self.center_a,
            ism="Ali",
            familya="A",
        )
        self.student_b = User.objects.create_user(
            email="student_b@example.com",
            password="password",
            role="student",
            center=self.center_b,
            ism="Bob",
            familya="B",
        )
        self.group_a = Group.objects.create(
            nom="G-A", center=self.center_a, kurs_narxi=1000, oqituvchi_foiz=40
        )
        self.group_b = Group.objects.create(
            nom="G-B", center=self.center_b, kurs_narxi=1000, oqituvchi_foiz=40
        )
        self.cat_a = Category.objects.create(name="Cat A", center=self.center_a)
        self.cat_b = Category.objects.create(name="Cat B", center=self.center_b)
        self.cat_global = Category.objects.create(name="Global Cat", center=None)

    def _request(self, center):
        request = self.factory.get("/")
        request.center = center
        request.user = User.objects.create_user(
            email=f"mgr-{center.slug}@example.com",
            password="password",
            role="manager",
            center=center,
            ism="Mgr",
            familya=center.slug,
        )
        return request

    def test_get_request_center_prefers_request_center(self):
        request = self.factory.get("/")
        request.center = self.center_a
        request.user = self.student_b  # different center on user
        self.assertEqual(get_request_center(request), self.center_a)

    def test_get_tenant_object_or_404_allows_own_center(self):
        request = self._request(self.center_a)
        student = get_tenant_object_or_404(
            User, request, pk=self.student_a.pk, role="student"
        )
        self.assertEqual(student.pk, self.student_a.pk)

    def test_get_tenant_object_or_404_blocks_other_center(self):
        request = self._request(self.center_a)
        with self.assertRaises(Http404):
            get_tenant_object_or_404(
                User, request, pk=self.student_b.pk, role="student"
            )

    def test_get_tenant_object_or_404_group_other_center(self):
        request = self._request(self.center_a)
        with self.assertRaises(Http404):
            get_tenant_object_or_404(Group, request, pk=self.group_b.pk)

    def test_allow_global_category(self):
        request = self._request(self.center_a)
        cat = get_tenant_object_or_404(
            Category, request, id=self.cat_global.id, allow_global=True
        )
        self.assertEqual(cat.pk, self.cat_global.pk)

    def test_allow_global_still_blocks_other_center_category(self):
        request = self._request(self.center_a)
        with self.assertRaises(Http404):
            get_tenant_object_or_404(
                Category, request, id=self.cat_b.id, allow_global=True
            )

    def test_assert_same_center(self):
        request = self._request(self.center_a)
        assert_same_center(request, self.group_a)
        with self.assertRaises(Http404):
            assert_same_center(request, self.group_b)

    def test_tenant_filter_qs(self):
        request = self._request(self.center_a)
        qs = tenant_filter_qs(User.objects.filter(role="student"), request)
        self.assertEqual(list(qs.values_list("pk", flat=True)), [self.student_a.pk])

    def test_no_center_on_request_does_not_filter(self):
        request = self.factory.get("/")
        request.center = None
        request.user = type("Anon", (), {"center": None, "is_authenticated": False})()
        # Without active center, helper does not invent isolation (superuser/platform).
        student = get_tenant_object_or_404(
            User, request, pk=self.student_b.pk, role="student"
        )
        self.assertEqual(student.pk, self.student_b.pk)
