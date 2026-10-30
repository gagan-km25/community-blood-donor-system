"""Tests for public pages, admin dashboard gating, and abuse review."""

from datetime import timedelta

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from blood_requests.models import (
    AbuseReport, BloodRequest, RequestStatus, Urgency,
)
from donors.models import BloodGroup, DonorProfile

PASSWORD = 'StrongPass!42x'


def make_user(username, is_staff=False):
    if is_staff:
        return User.objects.create_superuser(
            username, f'{username}@example.com', PASSWORD)
    return User.objects.create_user(username, f'{username}@example.com', PASSWORD)


class PublicPageTests(TestCase):
    def test_home_loads_with_live_stats(self):
        donor_user = make_user('d1')
        DonorProfile.objects.create(
            user=donor_user, full_name='D One', blood_group=BloodGroup.O_POS,
            city='Pune', phone='9876500000',
        )
        requester = make_user('r1')
        BloodRequest.objects.create(
            requester=requester, blood_group=BloodGroup.O_POS, units_needed=1,
            hospital_name='H', hospital_city='Pune', urgency=Urgency.NORMAL,
            needed_by=timezone.now() + timedelta(days=2),
            contact_number='9876500000', status=RequestStatus.FULFILLED,
        )
        response = self.client.get(reverse('dashboard:home'))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['stats']['active_donors'], 1)
        self.assertEqual(response.context['stats']['fulfilled_requests'], 1)

    def test_about_loads(self):
        self.assertEqual(
            self.client.get(reverse('dashboard:about')).status_code, 200)


class DashboardEntryTests(TestCase):
    def test_anonymous_redirects_to_login(self):
        response = self.client.get(reverse('dashboard:dashboard_entry'))
        self.assertRedirects(response, reverse('accounts:login'))

    def test_donor_goes_to_donor_dashboard(self):
        user = make_user('hero')
        DonorProfile.objects.create(
            user=user, full_name='Hero', blood_group=BloodGroup.A_POS,
            city='Pune', phone='9876500000',
        )
        self.client.login(username='hero', password=PASSWORD)
        response = self.client.get(reverse('dashboard:dashboard_entry'))
        self.assertRedirects(response, reverse('donors:donor_dashboard'))

    def test_plain_user_goes_to_requester_dashboard(self):
        make_user('plain')
        self.client.login(username='plain', password=PASSWORD)
        response = self.client.get(reverse('dashboard:dashboard_entry'))
        self.assertRedirects(response, reverse('blood_requests:my_requests'))


class AdminDashboardTests(TestCase):
    """AC-007/AC-026: staff-only access, real database statistics."""

    def setUp(self):
        self.url = reverse('dashboard:admin_dashboard')
        self.staff = make_user('chief', is_staff=True)
        self.plain = make_user('visitor')

    def test_anonymous_redirected_to_admin_login(self):
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 302)
        self.assertIn('/admin/login/', response['Location'])

    def test_non_staff_rejected(self):
        self.client.login(username='visitor', password=PASSWORD)
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 302)
        self.assertIn('/admin/login/', response['Location'])

    def test_staff_sees_dashboard_with_real_stats(self):
        donor = make_user('d2')
        DonorProfile.objects.create(
            user=donor, full_name='Dee', blood_group=BloodGroup.AB_POS,
            city='Pune', phone='9876500000',
        )
        requester = make_user('r2')
        BloodRequest.objects.create(
            requester=requester, blood_group=BloodGroup.AB_POS, units_needed=2,
            hospital_name='H', hospital_city='Pune', urgency=Urgency.CRITICAL,
            needed_by=timezone.now() + timedelta(days=1),
            contact_number='9876500000', status=RequestStatus.OPEN,
        )
        self.client.login(username='chief', password=PASSWORD)
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        stats = response.context['stats']
        self.assertGreaterEqual(stats['total_users'], 3)
        self.assertEqual(stats['active_donors'], 1)
        self.assertEqual(stats['open_requests'], 1)
        self.assertEqual(stats['fulfilled_requests'], 0)


class AbuseReviewTests(TestCase):
    """AC-027: administrators review reports; non-admins cannot."""

    def setUp(self):
        self.owner = make_user('owner')
        self.reporter = make_user('reporter')
        self.staff = make_user('chief', is_staff=True)
        self.request_obj = BloodRequest.objects.create(
            requester=self.owner, blood_group=BloodGroup.O_NEG, units_needed=1,
            hospital_name='H', hospital_city='Pune', urgency=Urgency.NORMAL,
            needed_by=timezone.now() + timedelta(days=2),
            contact_number='9876500000',
        )
        self.report = AbuseReport.objects.create(
            request=self.request_obj, reported_by=self.reporter,
            reason='inappropriate content',
        )
        self.resolve_url = reverse(
            'dashboard:resolve_abuse_report', args=[self.report.pk])

    def test_non_staff_cannot_resolve(self):
        self.client.login(username='reporter', password=PASSWORD)
        response = self.client.post(self.resolve_url, {'action': 'reviewed'})
        self.assertEqual(response.status_code, 302)
        self.assertIn('/admin/login/', response['Location'])
        self.report.refresh_from_db()
        self.assertEqual(self.report.status, AbuseReport.ReviewStatus.PENDING)

    def test_staff_marks_reviewed(self):
        self.client.login(username='chief', password=PASSWORD)
        self.client.post(self.resolve_url, {'action': 'reviewed'})
        self.report.refresh_from_db()
        self.assertEqual(self.report.status, AbuseReport.ReviewStatus.REVIEWED)
        self.assertEqual(self.report.reviewed_by, self.staff)
        self.assertIsNotNone(self.report.reviewed_at)

    def test_staff_dismisses(self):
        self.client.login(username='chief', password=PASSWORD)
        self.client.post(self.resolve_url, {'action': 'dismissed'})
        self.report.refresh_from_db()
        self.assertEqual(self.report.status, AbuseReport.ReviewStatus.DISMISSED)

    def test_unknown_action_rejected(self):
        self.client.login(username='chief', password=PASSWORD)
        self.client.post(self.resolve_url, {'action': 'explode'})
        self.report.refresh_from_db()
        self.assertEqual(self.report.status, AbuseReport.ReviewStatus.PENDING)
