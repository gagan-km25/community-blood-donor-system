"""Tests for registration, login/logout, and page protection."""

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

VALID_PASSWORD = 'StrongPass!42x'


class RegistrationTests(TestCase):
    def test_registration_success_creates_and_logs_in(self):
        """AC-001: valid registration creates an account and logs the user in."""
        response = self.client.post(reverse('accounts:register'), {
            'username': 'asha',
            'email': 'asha@example.com',
            'first_name': 'Asha',
            'password1': VALID_PASSWORD,
            'password2': VALID_PASSWORD,
        }, follow=True)
        self.assertEqual(response.status_code, 200)
        self.assertTrue(User.objects.filter(username='asha').exists())
        self.assertTrue(response.context['user'].is_authenticated)

    def test_registration_duplicate_username_rejected(self):
        """AC-002: duplicate usernames are rejected with a safe error."""
        User.objects.create_user('asha', password=VALID_PASSWORD)
        response = self.client.post(reverse('accounts:register'), {
            'username': 'asha',
            'email': 'other@example.com',
            'password1': VALID_PASSWORD,
            'password2': VALID_PASSWORD,
        })
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'already exists')
        self.assertEqual(User.objects.filter(username='asha').count(), 1)

    def test_registration_password_mismatch_rejected(self):
        """AC-002: mismatched passwords are rejected."""
        response = self.client.post(reverse('accounts:register'), {
            'username': 'newuser',
            'email': 'new@example.com',
            'password1': VALID_PASSWORD,
            'password2': 'DifferentPass!42x',
        })
        self.assertEqual(response.status_code, 200)
        self.assertFalse(User.objects.filter(username='newuser').exists())
        self.assertContains(response, 'did not match')

    def test_registration_weak_password_rejected(self):
        response = self.client.post(reverse('accounts:register'), {
            'username': 'weakling',
            'email': 'weak@example.com',
            'password1': '123',
            'password2': '123',
        })
        self.assertEqual(response.status_code, 200)
        self.assertFalse(User.objects.filter(username='weakling').exists())

    def test_registration_requires_email(self):
        response = self.client.post(reverse('accounts:register'), {
            'username': 'noemail',
            'email': '',
            'password1': VALID_PASSWORD,
            'password2': VALID_PASSWORD,
        })
        self.assertEqual(response.status_code, 200)
        self.assertFalse(User.objects.filter(username='noemail').exists())


class LoginLogoutTests(TestCase):
    def setUp(self):
        self.credentials = {'username': 'vikram', 'password': VALID_PASSWORD}
        self.user = User.objects.create_user(
            'vikram', 'vikram@example.com', VALID_PASSWORD
        )

    def post_login(self, username='vikram', password=VALID_PASSWORD):
        return self.client.post(
            reverse('accounts:login'),
            {'username': username, 'password': password},
            follow=True,
        )

    def test_login_success(self):
        """AC-004: valid credentials log the user in."""
        response = self.post_login()
        self.assertTrue(response.context['user'].is_authenticated)

    def test_invalid_login_rejected(self):
        """Wrong credentials keep the user out and show a generic error."""
        response = self.post_login(password='WrongPassword!1')
        self.assertFalse(response.context['user'].is_authenticated)
        self.assertContains(response, 'Invalid username or password')

    def test_unknown_user_login_rejected(self):
        response = self.post_login(username='nobody')
        self.assertFalse(response.context['user'].is_authenticated)

    def test_logout_post_only(self):
        self.client.login(**self.credentials)
        response = self.client.post(reverse('accounts:logout'))
        self.assertRedirects(response, reverse('dashboard:home'))
        # Session really ended.
        response = self.client.get(reverse('blood_requests:my_requests'))
        self.assertEqual(response.status_code, 302)

    def test_logout_get_not_allowed(self):
        """Logout is POST-only so it cannot be triggered by a plain link."""
        self.client.login(**self.credentials)
        response = self.client.get(reverse('accounts:logout'))
        self.assertEqual(response.status_code, 405)

    def test_login_redirects_staff_to_admin_dashboard(self):
        self.user.is_staff = True
        self.user.save()
        response = self.post_login()
        self.assertRedirects(
            response, reverse('dashboard:admin_dashboard')
        )

    def test_login_redirects_donor_to_donor_dashboard(self):
        from donors.models import DonorProfile, BloodGroup
        DonorProfile.objects.create(
            user=self.user, full_name='Vikram', blood_group=BloodGroup.O_POS,
            city='Pune', phone='9876543210',
        )
        response = self.post_login()
        self.assertRedirects(response, reverse('donors:donor_dashboard'))

    def test_login_redirects_plain_user_to_requester_dashboard(self):
        response = self.post_login()
        self.assertRedirects(response, reverse('blood_requests:my_requests'))


class ProtectedPageTests(TestCase):
    """AC-005: protected pages send anonymous users to login."""

    PROTECTED_URLS = [
        'blood_requests:create_request',
        'blood_requests:my_requests',
        'blood_requests:requests_board',
        'donors:my_profile_create',
        'donors:donor_dashboard',
        'donors:my_profile_edit',
    ]

    def test_protected_pages_redirect_anonymous(self):
        for url_name in self.PROTECTED_URLS:
            with self.subTest(url=url_name):
                response = self.client.get(reverse(url_name))
                self.assertEqual(response.status_code, 302)
                self.assertIn('/accounts/login/', response['Location'])
