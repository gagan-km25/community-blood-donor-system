"""Tests for donor profiles, search, privacy, and compatibility matching."""

from datetime import date, timedelta

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from .matching import (
    COMPATIBLE_DONORS, compatible_donor_groups, find_potential_donors,
    recipient_groups_for_donor,
)
from .models import BloodGroup, DonorProfile
from blood_requests.models import BloodRequest, RequestStatus, Urgency

PASSWORD = 'StrongPass!42x'
FUTURE_DATE = date.today() + timedelta(days=3)


def make_user(username):
    return User.objects.create_user(username, f'{username}@example.com', PASSWORD)


def make_donor(username, blood_group=BloodGroup.O_POS, city='Pune',
               available=True, consent=False, active=True, phone='98765 43210'):
    user = make_user(username)
    return DonorProfile.objects.create(
        user=user, full_name=username.title(), blood_group=blood_group,
        city=city, phone=phone, is_available=available,
        contact_consent=consent, is_active=active,
    )


class CompatibilityMapTests(TestCase):
    """AC-022: the ABO/Rh map is exact for all eight groups."""

    EXPECTED = {
        'O-': ['O-'],
        'O+': ['O+', 'O-'],
        'A-': ['A-', 'O-'],
        'A+': ['A+', 'A-', 'O+', 'O-'],
        'B-': ['B-', 'O-'],
        'B+': ['B+', 'B-', 'O+', 'O-'],
        'AB-': ['AB-', 'A-', 'B-', 'O-'],
        'AB+': ['A+', 'A-', 'B+', 'B-', 'AB+', 'AB-', 'O+', 'O-'],
    }

    def test_all_eight_groups(self):
        for group, expected in self.EXPECTED.items():
            with self.subTest(group=group):
                self.assertEqual(compatible_donor_groups(group), expected)

    def test_map_covers_every_choice(self):
        self.assertEqual(set(COMPATIBLE_DONORS), set(BloodGroup.values))

    def test_inverse_lookup(self):
        """O- is the universal donor; AB+ the universal recipient."""
        self.assertEqual(recipient_groups_for_donor('O-'), list(BloodGroup.values))
        self.assertEqual(recipient_groups_for_donor('AB+'), ['AB+'])

    def test_find_potential_donors_filters_correctly(self):
        """Matching combines group compatibility + city + availability + active."""
        compatible = make_donor('lead1', blood_group=BloodGroup.O_POS, city='Pune')
        make_donor('wronggroup', blood_group=BloodGroup.AB_POS, city='Pune')
        make_donor('wrongcity', blood_group=BloodGroup.O_POS, city='Mumbai')
        make_donor('unavailable', blood_group=BloodGroup.O_POS, city='Pune',
                   available=False)
        make_donor('deactivated', blood_group=BloodGroup.O_POS, city='Pune',
                   active=False)

        requester = make_user('requester1')
        request_obj = BloodRequest.objects.create(
            requester=requester, blood_group=BloodGroup.A_POS,
            units_needed=2, hospital_name='General', hospital_city='Pune',
            urgency=Urgency.URGENT,
            needed_by=timezone.now() + timedelta(days=2),
            contact_number='9876500000',
        )
        leads = list(find_potential_donors(request_obj))
        self.assertEqual([p.pk for p in leads], [compatible.pk])


class DonorProfileTests(TestCase):
    """AC-008/009/010: profile create, edit, and validation."""

    VALID_DATA = {
        'full_name': 'Asha Verma',
        'blood_group': 'O+',
        'city': 'Pune',
        'phone': '+91 98765 43210',
        'is_available': 'on',
        'last_donation_date': '2026-01-10',
        'contact_consent': 'on',
    }

    def setUp(self):
        self.user = make_user('asha')
        self.client.login(username='asha', password=PASSWORD)

    def test_profile_create_and_edit(self):
        response = self.client.post(
            reverse('donors:my_profile_create'), self.VALID_DATA, follow=True)
        self.assertEqual(response.status_code, 200)
        profile = DonorProfile.objects.get(user=self.user)
        self.assertEqual(profile.blood_group, 'O+')
        self.assertTrue(profile.contact_consent)

        # Edit: change city and turn consent OFF (field omitted = unchecked).
        edit_data = {k: v for k, v in self.VALID_DATA.items()
                     if k != 'contact_consent'}
        edit_data['city'] = 'Mumbai'
        response = self.client.post(
            reverse('donors:my_profile_edit'), edit_data, follow=True)
        self.assertEqual(response.status_code, 200)
        profile.refresh_from_db()
        self.assertEqual(profile.city, 'Mumbai')
        self.assertFalse(profile.contact_consent)

    def test_profile_phone_validation(self):
        """AC-009: invalid phone numbers are rejected server-side."""
        bad = dict(self.VALID_DATA, phone='call-me-maybe')
        response = self.client.post(reverse('donors:my_profile_create'), bad)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'valid phone number')
        self.assertFalse(DonorProfile.objects.exists())

    def test_profile_future_donation_date_rejected(self):
        bad = dict(self.VALID_DATA,
                   last_donation_date=FUTURE_DATE.strftime('%Y-%m-%d'))
        response = self.client.post(reverse('donors:my_profile_create'), bad)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'cannot be in the future')
        self.assertFalse(DonorProfile.objects.exists())

    def test_second_profile_redirects_to_edit(self):
        self.client.post(reverse('donors:my_profile_create'), self.VALID_DATA)
        response = self.client.get(reverse('donors:my_profile_create'))
        self.assertRedirects(response, reverse('donors:my_profile_edit'))

    def test_deactivation_hides_profile(self):
        """AC-013/AC-030: deactivated profiles disappear from search."""
        self.client.post(reverse('donors:my_profile_create'), self.VALID_DATA)
        self.client.post(reverse('donors:my_profile_toggle'))
        self.assertFalse(
            DonorProfile.objects.get(user=self.user).is_active)
        response = self.client.get(reverse('donors:search'))
        self.assertNotContains(response, 'Asha Verma')
        # Reactivate and it is visible again.
        self.client.post(reverse('donors:my_profile_toggle'))
        response = self.client.get(reverse('donors:search'))
        self.assertContains(response, 'Asha Verma')


class DonorSearchTests(TestCase):
    """AC-011/012: filtering and contact privacy."""

    def setUp(self):
        make_donor('donor_a', blood_group=BloodGroup.O_POS, city='Pune',
                   consent=True)
        make_donor('donor_b', blood_group=BloodGroup.A_NEG, city='Mumbai',
                   consent=True, available=False)
        make_donor('donor_c', blood_group=BloodGroup.O_POS, city='Mumbai',
                   consent=False)

    def test_search_filter_blood_group(self):
        response = self.client.get(
            reverse('donors:search'), {'blood_group': 'O+'})
        self.assertContains(response, 'Donor_A')
        self.assertNotContains(response, 'Donor_B')
        self.assertNotContains(response, 'Donor C')

    def test_search_filter_city(self):
        response = self.client.get(reverse('donors:search'), {'city': 'mumbai'})
        self.assertContains(response, 'Donor_B')
        self.assertNotContains(response, 'Donor_A')

    def test_search_filter_availability(self):
        response = self.client.get(
            reverse('donors:search'), {'availability': 'available'})
        self.assertContains(response, 'Donor_A')
        self.assertNotContains(response, 'Donor_B')

    def test_search_empty_state(self):
        response = self.client.get(reverse('donors:search'),
                                   {'city': 'Atlantis'})
        self.assertContains(response, 'No donors match')

    def test_deactivated_profile_hidden_from_search(self):
        donor = make_donor('ghost')
        donor.is_active = False
        donor.save()
        response = self.client.get(reverse('donors:search'))
        self.assertNotContains(response, 'Ghost')

    def test_guest_never_sees_phone(self):
        """AC-012: guests cannot see phone numbers, even with consent."""
        response = self.client.get(reverse('donors:search'))
        self.assertNotContains(response, '98765 43210')
        self.assertContains(response, 'log in')

    def test_authenticated_sees_phone_only_with_consent(self):
        make_user('viewer')
        self.client.login(username='viewer', password=PASSWORD)
        response = self.client.get(reverse('donors:search'))
        self.assertContains(response, '98765 43210')      # donor_a consented
        self.assertNotContains(response, '9876543210')    # donor_c did not

    def test_search_pagination(self):
        for i in range(12):
            make_donor(f'bulk{i}')
        response = self.client.get(reverse('donors:search'))
        self.assertEqual(len(response.context['page_obj'].object_list), 8)


class DonorDashboardTests(TestCase):
    def test_requires_login(self):
        response = self.client.get(reverse('donors:donor_dashboard'))
        self.assertEqual(response.status_code, 302)

    def test_no_profile_redirects_to_create(self):
        make_user('plain')
        self.client.login(username='plain', password=PASSWORD)
        response = self.client.get(reverse('donors:donor_dashboard'))
        self.assertRedirects(response, reverse('donors:my_profile_create'))

    def test_dashboard_shows_compatible_opportunities(self):
        donor = make_donor('hero', blood_group=BloodGroup.A_POS, city='Pune')
        self.client.login(username='hero', password=PASSWORD)

        requester = make_user('needy')
        BloodRequest.objects.create(
            requester=requester, blood_group=BloodGroup.A_POS,
            units_needed=1, hospital_name='City Hospital', hospital_city='Pune',
            urgency=Urgency.NORMAL, needed_by=timezone.now() + timedelta(days=2),
            contact_number='9876500000',
        )
        response = self.client.get(reverse('donors:donor_dashboard'))
        self.assertContains(response, 'City Hospital')

    def test_dashboard_hides_incompatible_opportunities(self):
        make_donor('om', blood_group=BloodGroup.A_POS)
        self.client.login(username='om', password=PASSWORD)
        requester = make_user('needy2')
        BloodRequest.objects.create(
            requester=requester, blood_group=BloodGroup.O_NEG,  # A+ cannot give
            units_needed=1, hospital_name='Far Hospital', hospital_city='Pune',
            urgency=Urgency.NORMAL, needed_by=timezone.now() + timedelta(days=2),
            contact_number='9876500000',
        )
        response = self.client.get(reverse('donors:donor_dashboard'))
        self.assertNotContains(response, 'Far Hospital')
