"""Create synthetic demonstration data for the demo.

All names, phone numbers, and requests below are FICTIONAL. Run only when you
want a populated demo database:  python manage.py seed_demo_data
"""

from django.contrib.auth.models import User
from django.core.management.base import BaseCommand
from django.utils import timezone
from datetime import timedelta

from blood_requests.models import BloodRequest, Urgency
from donors.models import BloodGroup, DonorProfile

DEMO_PASSWORD = 'Demo@12345'  # demo-only accounts, synthetic data

DONORS = [
    ('aarav_donor', 'Aarav Sharma', 'O+', 'Pune', '98765 40001', True, True),
    ('bhavna_donor', 'Bhavna Patel', 'A-', 'Pune', '98765 40002', True, True),
    ('chirag_donor', 'Chirag Mehta', 'B+', 'Mumbai', '98765 40003', True, False),
    ('deepa_donor', 'Deepa Rao', 'AB+', 'Mumbai', '98765 40004', True, True),
    ('eman_donor', 'Eman Khan', 'O-', 'Pune', '98765 40005', True, True),
    ('farhan_donor', 'Farhan Ali', 'A+', 'Delhi', '98765 40006', False, True),
    ('gita_donor', 'Gita Nair', 'B-', 'Delhi', '98765 40007', True, True),
    ('harish_donor', 'Harish Kumar', 'O+', 'Pune', '98765 40008', True, True),
    ('isha_donor', 'Isha Bose', 'AB-', 'Pune', '98765 40009', True, False),
    ('jatin_donor', 'Jatin Shah', 'O+', 'Pune', '98765 40010', True, True),
    ('kavya_donor', 'Kavya Iyer', 'A+', 'Mumbai', '98765 40011', True, True),
    ('lalit_donor', 'Lalit Verma', 'B+', 'Delhi', '98765 40012', True, True),
]


class Command(BaseCommand):
    help = 'Create synthetic demo users, donor profiles, and blood requests.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--force', action='store_true',
            help='Create users even if some demo users already exist.',
        )

    def handle(self, *args, **options):
        existing = User.objects.filter(username__in=[
            name for name, *_ in DONORS] + ['riya_requester', 'suresh_requester'])
        if existing.exists() and not options['force']:
            self.stdout.write(self.style.WARNING(
                'Demo users already exist. Re-run with --force to add anyway.'))
            return

        for username, full_name, group, city, phone, available, consent in DONORS:
            user = User.objects.create_user(
                username, f'{username}@example.com', DEMO_PASSWORD,
                first_name=full_name.split()[0],
            )
            DonorProfile.objects.create(
                user=user, full_name=full_name, blood_group=group, city=city,
                phone=phone, is_available=available, contact_consent=consent,
                last_donation_date=timezone.now().date() - timedelta(days=120),
            )
        self.stdout.write(f'Created {len(DONORS)} donor profiles.')

        riya = User.objects.create_user(
            'riya_requester', 'riya@example.com', DEMO_PASSWORD, first_name='Riya')
        suresh = User.objects.create_user(
            'suresh_requester', 'suresh@example.com', DEMO_PASSWORD,
            first_name='Suresh')

        requests_spec = [
            (riya, 'O-', 2, 'Ruby Hall Clinic', 'Pune', Urgency.CRITICAL,
             timezone.now() + timedelta(hours=10), 'open',
             'Thalassemia patient, regular transfusion.'),
            (riya, 'A+', 3, 'Sassoon General Hospital', 'Pune', Urgency.URGENT,
             timezone.now() + timedelta(days=2), 'matched',
             'Scheduled surgery needs 3 units.'),
            (suresh, 'B+', 1, 'KEM Hospital', 'Mumbai', Urgency.NORMAL,
             timezone.now() + timedelta(days=5), 'open', ''),
            (suresh, 'AB+', 2, 'Lilavati Hospital', 'Mumbai', Urgency.URGENT,
             timezone.now() + timedelta(days=1), 'partially_fulfilled',
             'One unit received, one pending.'),
        ]
        for requester, group, units, hospital, city, urgency, needed_by, \
                status, notes in requests_spec:
            blood_request = BloodRequest.objects.create(
                requester=requester, blood_group=group, units_needed=units,
                hospital_name=hospital, hospital_city=city, urgency=urgency,
                needed_by=needed_by, contact_number='98765 50000',
                status=status, notes=notes,
            )
            if status == 'partially_fulfilled':
                blood_request.units_fulfilled = 1
                blood_request.save()

        self.stdout.write('Created 4 demo blood requests.')
        self.stdout.write(self.style.SUCCESS(
            f'Done. Demo accounts use the password: {DEMO_PASSWORD}\n'
            'Create an administrator separately with: '
            'python manage.py createsuperuser'
        ))
