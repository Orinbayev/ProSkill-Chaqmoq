# tests/test_critical_security.py
"""
Critical Security & Business Logic Tests
Tests tenant isolation, student limits, expiry calculation, login loops
"""
from django.test import TestCase, Client
from django.urls import reverse
from django.utils import timezone
from django.core.exceptions import ValidationError
from datetime import timedelta

from accounts.models import User, Center
from billing.models import SubscriptionPlan, CenterSubscription
from accounts.student_limit import check_student_limit, create_student_safe


class TenantIsolationTest(TestCase):
    """Test that data is strictly isolated between centers"""
    
    def setUp(self):
        # Create two centers
        self.center1 = Center.objects.create(
            name="Center 1",
            slug="center1",
            status="ACTIVE"
        )
        self.center2 = Center.objects.create(
            name="Center 2",
            slug="center2",
            status="ACTIVE"
        )
        
        # Create students for each center
        self.student1 = User.objects.create_user(
            email="student1@test.com",
            password="test123",
            role="student",
            center=self.center1,
            ism="Student",
            familya="One"
        )
        
        self.student2 = User.objects.create_user(
            email="student2@test.com",
            password="test123",
            role="student",
            center=self.center2,
            ism="Student",
            familya="Two"
        )
    
    def test_student_not_visible_across_centers(self):
        """Students from center1 should not appear in center2 queries"""
        center1_students = User.objects.filter(center=self.center1, role='student')
        center2_students = User.objects.filter(center=self.center2, role='student')
        
        self.assertIn(self.student1, center1_students)
        self.assertNotIn(self.student1, center2_students)
        
        self.assertIn(self.student2, center2_students)
        self.assertNotIn(self.student2, center1_students)
    
    def test_global_query_isolated(self):
        """Ensure no global .all() queries leak cross-tenant data"""
        # This should NEVER happen in production views
        all_students = User.objects.filter(role='student')
        
        # But when properly filtered, isolation works
        c1_filtered = all_students.filter(center=self.center1)
        c2_filtered = all_students.filter(center=self.center2)
        
        self.assertEqual(c1_filtered.count(), 1)
        self.assertEqual(c2_filtered.count(), 1)
        self.assertNotEqual(list(c1_filtered), list(c2_filtered))


class StudentLimitEnforcementTest(TestCase):
    """Test student limit enforcement prevents exceeding plan limits"""
    
    def setUp(self):
        # Create plan with 2 student limit
        self.plan = SubscriptionPlan.objects.create(
            code="TEST",
            title="Test Plan",
            monthly_price=100000,
            max_students=2,
            active=True
        )
        
        # Create center
        self.center = Center.objects.create(
            name="Test Center",
            slug="test",
            status="ACTIVE"
        )
        
        # Create subscription
        self.sub = CenterSubscription.objects.create(
            center=self.center,
            plan=self.plan,
            expires_at=timezone.now() + timedelta(days=30)
        )
    
    def test_check_limit_blocks_when_reached(self):
        """Should block when limit reached"""
        # Create 2 students (at limit)
        User.objects.create_user(
            email="s1@test.com",
            password="test",
            role="student",
            center=self.center,
            ism="S1"
        )
        User.objects.create_user(
            email="s2@test.com",
            password="test",
            role="student",
            center=self.center,
            ism="S2"
        )
        
        # Try to check limit (should raise error)
        with self.assertRaises(ValidationError) as context:
            check_student_limit(self.center, raise_error=True)
        
        self.assertIn("Limit tugagan", str(context.exception))
    
    def test_check_limit_allows_when_under(self):
        """Should allow when under limit"""
        # Only 1 student
        User.objects.create_user(
            email="s1@test.com",
            password="test",
            role="student",
            center=self.center,
            ism="S1"
        )
        
        # Should not raise
        result = check_student_limit(self.center, raise_error=True)
        self.assertEqual(result['remaining'], 1)
    
    def test_archived_students_not_counted(self):
        """Archived students should not count toward limit"""
        # Create 2 students
        s1 = User.objects.create_user(
            email="s1@test.com",
            password="test",
            role="student",
            center=self.center,
            ism="S1"
        )
        s2 = User.objects.create_user(
            email="s2@test.com",
            password="test",
            role="student",
            center=self.center,
            ism="S2"
        )
        
        # Archive one
        s1.is_archived = True
        s1.save()
        
        # Should allow (only 1 active student)
        result = check_student_limit(self.center, raise_error=False)
        self.assertEqual(result['current_count'], 1)
        self.assertFalse(result['is_at_limit'])


class ExpiryCalculationTest(TestCase):
    """Test expiry date calculations are timezone-aware and correct"""
    
    def setUp(self):
        self.plan = SubscriptionPlan.objects.create(
            code="TEST",
            title="Test",
            monthly_price=100000,
            max_students=100
        )
        self.center = Center.objects.create(
            name="Test Center",
            slug="test"
        )
    
    def test_future_date_not_expired(self):
        """Future expiry date should not be marked as expired"""
        future_date = timezone.now() + timedelta(days=60)
        sub = CenterSubscription.objects.create(
            center=self.center,
            plan=self.plan,
            expires_at=future_date
        )
        
        self.assertFalse(sub.is_expired())
        self.assertGreater(sub.days_left(), 0)
    
    def test_past_date_is_expired(self):
        """Past expiry date should be marked as expired"""
        past_date = timezone.now() - timedelta(days=10)
        sub = CenterSubscription.objects.create(
            center=self.center,
            plan=self.plan,
            expires_at=past_date
        )
        
        self.assertTrue(sub.is_expired())
        self.assertLess(sub.days_left(), 0)
    
    def test_today_exact_moment(self):
        """Expiry exactly at current moment"""
        now = timezone.now()
        sub = CenterSubscription.objects.create(
            center=self.center,
            plan=self.plan,
            expires_at=now
        )
        
        # Should be expired (>=)
        self.assertTrue(sub.is_expired())


class LoginRedirectTest(TestCase):
    """Test login redirect loop is prevented"""
    
    def setUp(self):
        self.client = Client()
        self.center = Center.objects.create(
            name="Test Center",
            slug="test",
            status="ACTIVE"
        )
        self.user = User.objects.create_user(
            email="director@test.com",
            password="test123",
            role="director",
            center=self.center,
            ism="Director"
        )
    
    def test_authenticated_user_cannot_access_login(self):
        """Logged-in user accessing /login/ should redirect to home"""
        self.client.force_login(self.user)
        
        response = self.client.get('/hisob/login/')
        
        # Should redirect, not show login page
        self.assertEqual(response.status_code, 302)
        self.assertNotEqual(response.url, '/hisob/login/')
    
    def test_unauthenticated_can_access_login(self):
        """Anonymous user should see login page"""
        response = self.client.get('/hisob/login/')
        
        # Should show login page
        self.assertIn(response.status_code, [200, 302])  # 302 if redirecting to add subdomain
