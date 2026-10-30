"""Tests for blood requests: validation, permissions, transitions, expiry."""

import re
from datetime import timedelta

from django.contrib.auth.models import User
from django.core.management import call_command
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from donors.models import BloodGroup, DonorProfile
from .forms import StatusUpdateForm
from .models import (
    AbuseReport, BloodRequest, RequestStatus, RequestStatusHistory, Urgency,
)

PASSWORD = 'StrongPass!42x'


def future(**kwargs):
    return timezone.now() + timedelta(days=2, **kwargs)


def make_user(username, is_staff=False):
    return User.objects.create_user(
        username, f'{username}@example.com', PASSWORD
    ) if not is_staff else User.objects.create_superuser(
        username, f'{username}@example.com', PASSWORD
    )


def make_request(requester, blood_group=BloodGroup.O_NEG, city='Pune',
                 status=RequestStatus.OPEN, units=3,
                 needed_by=None, hospital_name='City General', **extra):
    return BloodRequest.objects.create(
        requester=requester, blood_group=blood_group, units_needed=units,
        hospital_name=hospital_name, hospital_city=city,
        urgency=Urgency.URGENT, needed_by=needed_by or future(),
        contact_number='9876500000', status=status, **extra,
    )


class RequestCreateTests(TestCase):
    """AC-014/015: creation and server-side validation."""

    def setUp(self):
        self.user = make_user('requester1')
        self.client.login(username='requester1', password=PASSWORD)
        self.url = reverse('blood_requests:create_request')
        self.valid = {
            'blood_group': 'O-',
            'units_needed': 2,
            'urgency': 'urgent',
            'hospital_name': 'City General Hospital',
            'hospital_city': 'Pune',
            'needed_by': (timezone.now() + timedelta(days=1))
            .strftime('%Y-%m-%dT%H:%M'),
            'contact_number': '98765 00000',
            'notes': 'Please help',
        }

    def test_create_request_success(self):
        response = self.client.post(self.url, self.valid, follow=True)
        self.assertEqual(response.status_code, 200)
        created = BloodRequest.objects.get(requester=self.user)
        self.assertEqual(created.status, RequestStatus.OPEN)
        self.assertEqual(created.units_needed, 2)
        self.assertEqual(created.units_fulfilled, 0)

    def test_units_bounds_rejected(self):
        for units in ('0', '11'):
            with self.subTest(units=units):
                response = self.client.post(self.url, dict(self.valid, units_needed=units))
                self.assertEqual(response.status_code, 200)
                self.assertFalse(BloodRequest.objects.exists())

    def test_past_needed_by_rejected(self):
        past = (timezone.now() - timedelta(days=1)).strftime('%Y-%m-%dT%H:%M')
        response = self.client.post(self.url, dict(self.valid, needed_by=past))
        self.assertContains(response, 'must be in the future')
        self.assertFalse(BloodRequest.objects.exists())

    def test_missing_hospital_rejected(self):
        response = self.client.post(
            self.url, dict(self.valid, hospital_name=''))
        self.assertEqual(response.status_code, 200)
        self.assertFalse(BloodRequest.objects.exists())

    def test_invalid_phone_rejected(self):
        response = self.client.post(
            self.url, dict(self.valid, contact_number='not-a-phone'))
        self.assertEqual(response.status_code, 200)
        self.assertFalse(BloodRequest.objects.exists())

    def test_database_persistence(self):
        """Values survive a fresh database round-trip."""
        self.client.post(self.url, self.valid)
        stored = BloodRequest.objects.get(requester=self.user)
        stored_fresh = BloodRequest.objects.get(pk=stored.pk)
        self.assertEqual(stored_fresh.blood_group, 'O-')
        self.assertEqual(stored_fresh.hospital_city, 'Pune')
        self.assertEqual(stored_fresh.urgency, 'urgent')


class RequestPermissionTests(TestCase):
    """AC-006/AC-016: only the owner (or staff) touches a request."""

    def setUp(self):
        self.owner = make_user('owner')
        self.stranger = make_user('stranger')
        self.staff = make_user('staffer', is_staff=True)
        self.request_obj = make_request(self.owner)
        self.detail = reverse('blood_requests:request_detail',
                              args=[self.request_obj.pk])

    def test_owner_can_view(self):
        self.client.login(username='owner', password=PASSWORD)
        self.assertEqual(self.client.get(self.detail).status_code, 200)

    def test_staff_can_view(self):
        self.client.login(username='staffer', password=PASSWORD)
        self.assertEqual(self.client.get(self.detail).status_code, 200)

    def test_stranger_gets_403(self):
        """AC-006: correct ID, wrong user → 403, never the record."""
        self.client.login(username='stranger', password=PASSWORD)
        response = self.client.get(self.detail)
        self.assertEqual(response.status_code, 403)

    def test_anonymous_redirects_to_login(self):
        response = self.client.get(self.detail)
        self.assertEqual(response.status_code, 302)

    def test_stranger_cannot_edit(self):
        self.client.login(username='stranger', password=PASSWORD)
        response = self.client.post(
            reverse('blood_requests:update_request', args=[self.request_obj.pk]),
            {'hospital_name': 'Hacked Hospital'})
        self.assertEqual(response.status_code, 403)
        self.request_obj.refresh_from_db()
        self.assertEqual(self.request_obj.hospital_name, 'City General')

    def test_stranger_cannot_cancel(self):
        self.client.login(username='stranger', password=PASSWORD)
        response = self.client.post(
            reverse('blood_requests:cancel_request', args=[self.request_obj.pk]))
        self.assertEqual(response.status_code, 403)
        self.request_obj.refresh_from_db()
        self.assertEqual(self.request_obj.status, RequestStatus.OPEN)

    def test_stranger_cannot_change_status(self):
        self.client.login(username='stranger', password=PASSWORD)
        response = self.client.post(
            reverse('blood_requests:update_status', args=[self.request_obj.pk]),
            {'to_status': 'fulfilled', 'note': ''})
        self.assertEqual(response.status_code, 403)
        self.request_obj.refresh_from_db()
        self.assertEqual(self.request_obj.status, RequestStatus.OPEN)

    def test_my_requests_lists_only_own(self):
        make_request(self.stranger)
        self.client.login(username='owner', password=PASSWORD)
        response = self.client.get(reverse('blood_requests:my_requests'))
        self.assertEqual(
            list(response.context['requests_list']), [self.request_obj])


class TransitionTests(TestCase):
    """AC-017/018/021: the state machine is enforced and audited."""

    def setUp(self):
        self.owner = make_user('owner')
        self.client.login(username='owner', password=PASSWORD)
        self.request_obj = make_request(self.owner)

    def set_status(self, to_status, units=None, note='', **kwargs):
        data = {'to_status': to_status, 'note': note}
        if units is not None:
            data['units_fulfilled'] = units
        return self.client.post(
            reverse('blood_requests:update_status', args=[self.request_obj.pk]),
            data, **kwargs)

    def test_open_to_matched(self):
        response = self.set_status('matched')
        self.assertRedirects(
            response,
            reverse('blood_requests:request_detail', args=[self.request_obj.pk]))
        self.request_obj.refresh_from_db()
        self.assertEqual(self.request_obj.status, RequestStatus.MATCHED)

    def test_illegal_transition_rejected(self):
        """open → expired is never a manual move."""
        response = self.set_status('expired', follow=True)
        self.request_obj.refresh_from_db()
        self.assertEqual(self.request_obj.status, RequestStatus.OPEN)
        self.assertContains(response, 'cannot move')

    def test_fulfilled_cannot_be_reopened(self):
        self.request_obj.status = RequestStatus.FULFILLED
        self.request_obj.save()
        response = self.set_status('open')
        self.request_obj.refresh_from_db()
        self.assertEqual(self.request_obj.status, RequestStatus.FULFILLED)

    def test_partial_fulfilment_records_units(self):
        response = self.set_status('partially_fulfilled', units=2)
        self.request_obj.refresh_from_db()
        self.assertEqual(self.request_obj.status, RequestStatus.PARTIALLY_FULFILLED)
        self.assertEqual(self.request_obj.units_fulfilled, 2)

    def test_partial_fulfilment_with_zero_units_rejected(self):
        self.set_status('matched')
        response = self.set_status('partially_fulfilled', units=0)
        self.request_obj.refresh_from_db()
        self.assertEqual(self.request_obj.status, RequestStatus.MATCHED)

    def test_partial_fulfilment_with_all_units_rejected(self):
        """Full units means 'fulfilled', not 'partially fulfilled'."""
        response = self.set_status('partially_fulfilled', units=3)
        self.request_obj.refresh_from_db()
        self.assertEqual(self.request_obj.status, RequestStatus.OPEN)

    def test_fulfilled_sets_full_units(self):
        self.set_status('fulfilled')
        self.request_obj.refresh_from_db()
        self.assertEqual(self.request_obj.status, RequestStatus.FULFILLED)
        self.assertEqual(self.request_obj.units_fulfilled,
                         self.request_obj.units_needed)

    def test_cancel_from_open(self):
        self.client.post(
            reverse('blood_requests:cancel_request', args=[self.request_obj.pk]))
        self.request_obj.refresh_from_db()
        self.assertEqual(self.request_obj.status, RequestStatus.CANCELLED)

    def test_cancel_from_terminal_rejected(self):
        self.request_obj.status = RequestStatus.CANCELLED
        self.request_obj.save()
        self.client.post(
            reverse('blood_requests:cancel_request', args=[self.request_obj.pk]))
        self.request_obj.refresh_from_db()
        self.assertEqual(self.request_obj.status, RequestStatus.CANCELLED)

    def test_status_history_recorded(self):
        """AC-021: each change stores actor, from, to, and timestamp."""
        self.set_status('matched', note='found a lead')
        history = RequestStatusHistory.objects.get(request=self.request_obj)
        self.assertEqual(history.from_status, RequestStatus.OPEN)
        self.assertEqual(history.to_status, RequestStatus.MATCHED)
        self.assertEqual(history.changed_by, self.owner)
        self.assertEqual(history.note, 'found a lead')
        self.assertIsNotNone(history.created_at)

    def test_terminal_request_edit_blocked(self):
        self.request_obj.status = RequestStatus.FULFILLED
        self.request_obj.save()
        response = self.client.get(
            reverse('blood_requests:update_request', args=[self.request_obj.pk]),
            follow=True)
        self.assertContains(response, 'no longer be edited')


class ExpiryTests(TestCase):
    """AC-018: overdue active requests expire automatically."""

    def setUp(self):
        self.owner = make_user('owner')

    def test_overdue_request_expires(self):
        stale = make_request(self.owner, needed_by=timezone.now() - timedelta(days=1))
        from .services import expire_due_requests
        count = expire_due_requests()
        self.assertEqual(count, 1)
        stale.refresh_from_db()
        self.assertEqual(stale.status, RequestStatus.EXPIRED)
        history = stale.history.get()
        self.assertIsNone(history.changed_by)  # system actor

    def test_future_and_terminal_untouched(self):
        fresh = make_request(self.owner)  # future date
        done = make_request(self.owner, status=RequestStatus.FULFILLED,
                            needed_by=timezone.now() - timedelta(days=1))
        from .services import expire_due_requests
        expire_due_requests()
        fresh.refresh_from_db()
        done.refresh_from_db()
        self.assertEqual(fresh.status, RequestStatus.OPEN)
        self.assertEqual(done.status, RequestStatus.FULFILLED)

    def test_expire_command(self):
        make_request(self.owner, needed_by=timezone.now() - timedelta(days=1))
        import io
        out = io.StringIO()
        call_command('expire_requests', stdout=out)
        self.assertIn('Expired 1 request(s)', out.getvalue())

    def test_view_trigger_expires_overdue(self):
        stale = make_request(self.owner, needed_by=timezone.now() - timedelta(days=1))
        self.client.login(username='owner', password=PASSWORD)
        self.client.get(reverse('blood_requests:my_requests'))
        stale.refresh_from_db()
        self.assertEqual(stale.status, RequestStatus.EXPIRED)


class MatchingLeadTests(TestCase):
    """AC-019/023/024: leads are display-only and privacy-aware."""

    def setUp(self):
        self.owner = make_user('owner')
        self.client.login(username='owner', password=PASSWORD)
        self.request_obj = make_request(self.owner, blood_group=BloodGroup.A_POS)

    def test_viewing_matches_does_not_change_status(self):
        DonorProfile.objects.create(
            user=make_user('donorx'), full_name='Donor X',
            blood_group=BloodGroup.A_POS, city='Pune', phone='9876500000',
            contact_consent=True,
        )
        response = self.client.get(
            reverse('blood_requests:request_detail', args=[self.request_obj.pk]))
        self.request_obj.refresh_from_db()
        self.assertEqual(self.request_obj.status, RequestStatus.OPEN)  # unchanged

    def test_match_cards_respect_privacy(self):
        DonorProfile.objects.create(
            user=make_user('yesconsent'), full_name='Public Donor',
            blood_group=BloodGroup.O_POS, city='Pune', phone='9111100000',
            contact_consent=True,
        )
        DonorProfile.objects.create(
            user=make_user('noconsent'), full_name='Private Donor',
            blood_group=BloodGroup.A_POS, city='Pune', phone='9222200000',
            contact_consent=False,
        )
        response = self.client.get(
            reverse('blood_requests:request_detail', args=[self.request_obj.pk]))
        self.assertContains(response, 'Public Donor')
        self.assertContains(response, '9111100000')
        self.assertContains(response, 'Private Donor')
        self.assertNotContains(response, '9222200000')


class CommunityBoardTests(TestCase):
    """FR-6/FR-7: the board and abuse reporting."""

    def setUp(self):
        self.owner = make_user('owner')
        self.visitor = make_user('visitor')
        self.request_obj = make_request(self.owner)

    def test_board_requires_login(self):
        response = self.client.get(reverse('blood_requests:requests_board'))
        self.assertEqual(response.status_code, 302)

    def test_board_shows_only_open_requests(self):
        cancelled = make_request(self.owner, status=RequestStatus.CANCELLED,
                                 hospital_name='Closed Hospital')
        self.client.login(username='visitor', password=PASSWORD)
        response = self.client.get(reverse('blood_requests:requests_board'))
        self.assertContains(response, 'City General')
        self.assertNotContains(response, 'Closed Hospital')

    def test_board_hides_contacts_and_patient_names(self):
        make_request(self.owner, patient_name='John Doe',
                     city='Mumbai', hospital_name='Secret Hospital')
        self.client.login(username='visitor', password=PASSWORD)
        response = self.client.get(reverse('blood_requests:requests_board'))
        self.assertNotContains(response, 'John Doe')
        self.assertNotContains(response, '9876500000')

    def test_abuse_report_flow(self):
        """AC-027: report once; duplicates blocked; own request blocked."""
        self.client.login(username='visitor', password=PASSWORD)
        url = reverse('blood_requests:report_request', args=[self.request_obj.pk])
        response = self.client.post(url, {'reason': 'Looks like a scam'},
                                    follow=True)
        self.assertEqual(AbuseReport.objects.count(), 1)

        # Duplicate report is not created.
        self.client.post(url, {'reason': 'again'})
        self.assertEqual(AbuseReport.objects.count(), 1)

    def test_cannot_report_own_request(self):
        self.client.login(username='owner', password=PASSWORD)
        url = reverse('blood_requests:report_request', args=[self.request_obj.pk])
        self.client.post(url, {'reason': 'self report'})
        self.assertEqual(AbuseReport.objects.count(), 0)

    def test_empty_reason_rejected(self):
        self.client.login(username='visitor', password=PASSWORD)
        url = reverse('blood_requests:report_request', args=[self.request_obj.pk])
        self.client.post(url, {'reason': ''})
        self.assertEqual(AbuseReport.objects.count(), 0)


class StatusUpdateFormTests(TestCase):
    """Pin the form definition that caused the 'Invalid status action.' bug.

    Root cause: to_status was once a ChoiceField with NO choices. Django's
    ChoiceField rejects every value not in its choices, so EVERY UI payload
    failed form validation and the view showed 'Invalid status action.'
    These unit tests fail immediately if the choices are dropped again.
    """

    def test_to_status_field_offers_all_six_statuses(self):
        field = StatusUpdateForm().fields['to_status']
        self.assertEqual(
            [value for value, _ in field.choices], list(RequestStatus.values)
        )

    def test_form_accepts_every_button_payload(self):
        """The exact payloads the detail-page buttons post must validate."""
        valid_payloads = [
            {'to_status': 'matched', 'note': ''},
            {'to_status': 'partially_fulfilled', 'units_fulfilled': '1', 'note': ''},
            {'to_status': 'fulfilled', 'note': ''},
            {'to_status': 'cancelled', 'note': ''},
        ]
        for payload in valid_payloads:
            with self.subTest(payload=payload):
                self.assertTrue(StatusUpdateForm(payload).is_valid())

    def test_form_rejects_unknown_status_safely(self):
        form = StatusUpdateForm({'to_status': 'deleted', 'note': ''})
        self.assertFalse(form.is_valid())
        self.assertIn('to_status', form.errors)


class StatusUpdateRegressionTests(TestCase):
    """Drive the rendered detail-page HTML through every status action —
    the same payloads the browser produces — and assert the user never sees
    'Invalid status action.', units are validated against units_needed, and
    every accepted action writes an audit-history row.
    """

    def setUp(self):
        self.owner = make_user('owner')
        self.client.login(username='owner', password=PASSWORD)
        self.request_obj = make_request(self.owner, units=3)
        self.url = reverse('blood_requests:update_status',
                           args=[self.request_obj.pk])
        self.detail_url = reverse('blood_requests:request_detail',
                                  args=[self.request_obj.pk])

    def rendered_to_status_values(self):
        """Extract the to_status values the rendered page's buttons post."""
        html = self.client.get(self.detail_url).content.decode()
        return re.findall(r'name="to_status" value="([^"]+)"', html)

    def test_open_request_renders_buttons_for_expected_actions(self):
        values = self.rendered_to_status_values()
        self.assertEqual(
            sorted(values),
            ['cancelled', 'fulfilled', 'matched', 'partially_fulfilled'],
        )

    def test_full_ui_walk_records_history_and_never_shows_invalid(self):
        # Open → Matched
        response = self.client.post(
            self.url, {'to_status': 'matched', 'note': 'found leads'},
            follow=True)
        self.assertNotContains(response, 'Invalid status action')
        self.assertContains(response, 'Status updated to &quot;Matched&quot;')

        # Matched → Partially Fulfilled (units received via the input)
        response = self.client.post(
            self.url,
            {'to_status': 'partially_fulfilled', 'units_fulfilled': '2',
             'note': ''},
            follow=True)
        self.assertNotContains(response, 'Invalid status action')
        self.request_obj.refresh_from_db()
        self.assertEqual(self.request_obj.units_fulfilled, 2)

        # Partially Fulfilled → Fulfilled (units auto-set to units_needed)
        response = self.client.post(
            self.url, {'to_status': 'fulfilled', 'note': ''}, follow=True)
        self.assertNotContains(response, 'Invalid status action')
        self.request_obj.refresh_from_db()
        self.assertEqual(self.request_obj.status, RequestStatus.FULFILLED)
        self.assertEqual(self.request_obj.units_fulfilled,
                         self.request_obj.units_needed)

        # Audit history: exactly one row per action, correct order and actor.
        history = list(self.request_obj.history.all())  # newest first
        self.assertEqual(len(history), 3)
        self.assertEqual(
            [(h.from_status, h.to_status) for h in reversed(history)],
            [
                (RequestStatus.OPEN, RequestStatus.MATCHED),
                (RequestStatus.MATCHED, RequestStatus.PARTIALLY_FULFILLED),
                (RequestStatus.PARTIALLY_FULFILLED, RequestStatus.FULFILLED),
            ],
        )
        for entry in history:
            self.assertEqual(entry.changed_by, self.owner)

    def test_cancel_path_also_writes_history(self):
        response = self.client.post(
            reverse('blood_requests:cancel_request',
                    args=[self.request_obj.pk]),
            {'to_status': 'cancelled', 'note': ''}, follow=True)
        self.assertNotContains(response, 'Invalid status action')
        self.request_obj.refresh_from_db()
        self.assertEqual(self.request_obj.status, RequestStatus.CANCELLED)
        entry = self.request_obj.history.get()
        self.assertEqual(entry.from_status, RequestStatus.OPEN)
        self.assertEqual(entry.to_status, RequestStatus.CANCELLED)
        self.assertEqual(entry.changed_by, self.owner)

    def test_malformed_to_status_rejected_with_history_untouched(self):
        response = self.client.post(
            self.url, {'to_status': 'deleted', 'note': ''}, follow=True)
        self.assertContains(response, 'Invalid status action.')
        self.request_obj.refresh_from_db()
        self.assertEqual(self.request_obj.status, RequestStatus.OPEN)
        self.assertEqual(self.request_obj.history.count(), 0)

    def test_units_fulfilled_validated_against_units_needed(self):
        """0, all, and more-than-requested units are rejected; the largest
        legal partial value (units_needed − 1) is accepted."""
        for bad_units in ('0', '3', '4'):
            with self.subTest(units=bad_units):
                response = self.client.post(
                    self.url,
                    {'to_status': 'partially_fulfilled',
                     'units_fulfilled': bad_units, 'note': ''},
                    follow=True)
                self.assertContains(
                    response, 'need units fulfilled between')
                self.request_obj.refresh_from_db()
                self.assertEqual(self.request_obj.status, RequestStatus.OPEN)
                self.assertEqual(self.request_obj.units_fulfilled, 0)

        response = self.client.post(
            self.url,
            {'to_status': 'partially_fulfilled', 'units_fulfilled': '2',
             'note': ''},
            follow=True)
        self.assertNotContains(response, 'Invalid status action')
        self.request_obj.refresh_from_db()
        self.assertEqual(self.request_obj.units_fulfilled, 2)
        self.assertEqual(self.request_obj.status,
                         RequestStatus.PARTIALLY_FULFILLED)


class PartialFulfilmentUiTests(TestCase):
    """Regression tests for the partial-fulfilment input bounds.

    Bug: the template computed max as units_needed − 1, so a 1-unit request
    rendered min="1" max="0" — an invalid range the browser rejects with
    "Minimum value (1) must be less than the maximum value (0)." Partial
    fulfilment is now hidden entirely when 1 or fewer units remain, and the
    input runs from 1 to remaining_units − 1 otherwise. The backend state
    machine (services.transition) remains the security boundary.
    """

    def setUp(self):
        self.owner = make_user('owner')
        self.client.login(username='owner', password=PASSWORD)

    def open_request(self, units):
        return make_request(self.owner, units=units)

    def detail_html(self, req):
        return self.client.get(
            reverse('blood_requests:request_detail', args=[req.pk])
        ).content.decode()

    def post_partial(self, req, units_value):
        return self.client.post(
            reverse('blood_requests:update_status', args=[req.pk]),
            {'to_status': 'partially_fulfilled',
             'units_fulfilled': units_value, 'note': ''},
            follow=True)

    def test_one_remaining_unit_hides_partial_and_keeps_fulfilled(self):
        req = self.open_request(units=1)
        html = self.detail_html(req)
        self.assertNotIn('Record partial fulfilment', html)
        self.assertNotIn('name="units_fulfilled"', html)
        # Completed actions remain available when the request can be completed.
        self.assertIn('Mark as fulfilled', html)
        self.assertIn('Mark as matched', html)
        self.assertIn('Cancel request', html)
        # Backend boundary intact: hand-crafted partial POST is still rejected.
        response = self.post_partial(req, '0')
        self.assertContains(response, 'need units fulfilled between')
        req.refresh_from_db()
        self.assertEqual(req.status, RequestStatus.OPEN)
        self.assertEqual(req.history.count(), 0)

    def test_two_remaining_units_allow_partial_up_to_one(self):
        req = self.open_request(units=2)
        html = self.detail_html(req)
        self.assertIn('Record partial fulfilment', html)
        self.assertIn('min="1"', html)
        self.assertIn('max="1"', html)  # remaining − 1
        self.assertIn('Mark as fulfilled', html)
        response = self.post_partial(req, '1')
        self.assertNotContains(response, 'Invalid status action')
        req.refresh_from_db()
        self.assertEqual(req.status, RequestStatus.PARTIALLY_FULFILLED)
        self.assertEqual(req.units_fulfilled, 1)
        self.assertEqual(req.history.get().to_status,
                         RequestStatus.PARTIALLY_FULFILLED)

    def test_three_remaining_units_allow_partial_up_to_two(self):
        req = self.open_request(units=3)
        html = self.detail_html(req)
        self.assertIn('Record partial fulfilment', html)
        self.assertIn('max="2"', html)  # remaining − 1
        # Above the bound: requesting ALL units is still rejected server-side.
        response = self.post_partial(req, '3')
        self.assertContains(response, 'need units fulfilled between')
        req.refresh_from_db()
        self.assertEqual(req.status, RequestStatus.OPEN)
        # At the bound: remaining − 1 units are accepted.
        response = self.post_partial(req, '2')
        self.assertNotContains(response, 'Invalid status action')
        req.refresh_from_db()
        self.assertEqual(req.status, RequestStatus.PARTIALLY_FULFILLED)
        self.assertEqual(req.units_fulfilled, 2)
        self.assertEqual(req.units_remaining, 1)
