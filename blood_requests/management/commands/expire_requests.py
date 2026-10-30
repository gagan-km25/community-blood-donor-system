"""Expire overdue blood requests on demand (no cron needed on Windows)."""

from django.core.management.base import BaseCommand

from blood_requests.services import expire_due_requests


class Command(BaseCommand):
    help = 'Mark overdue open/matched/partially-fulfilled requests as expired.'

    def handle(self, *args, **options):
        count = expire_due_requests()
        self.stdout.write(self.style.SUCCESS(f'Expired {count} request(s).'))
