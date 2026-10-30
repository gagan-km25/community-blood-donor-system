"""Donor profile model shared by the whole project (blood group choices too)."""

from django.contrib.auth.models import User
from django.core.validators import RegexValidator
from django.db import models


class BloodGroup(models.TextChoices):
    """The eight supported ABO/Rh blood groups."""

    A_POS = 'A+', 'A+'
    A_NEG = 'A-', 'A-'
    B_POS = 'B+', 'B+'
    B_NEG = 'B-', 'B-'
    AB_POS = 'AB+', 'AB+'
    AB_NEG = 'AB-', 'AB-'
    O_POS = 'O+', 'O+'
    O_NEG = 'O-', 'O-'


phone_validator = RegexValidator(
    regex=r'^\+?[0-9][0-9\s\-()]{6,17}$',
    message='Enter a valid phone number (7–18 digits, may start with + and '
            'contain spaces, dashes or brackets).',
)


class DonorProfile(models.Model):
    """A user's public-facing donor profile.

    Privacy notes:
    - ``phone`` is only shown when ``contact_consent`` is set AND the viewer
      is authenticated (enforced in views/templates, never in public HTML).
    - ``is_active`` is a soft-delete flag: deactivated profiles are hidden
      from search and matching but the row is kept.
    """

    user = models.OneToOneField(
        User, on_delete=models.CASCADE, related_name='donor_profile'
    )
    full_name = models.CharField(max_length=120)
    blood_group = models.CharField(max_length=3, choices=BloodGroup.choices)
    city = models.CharField(max_length=80)
    phone = models.CharField(max_length=20, validators=[phone_validator])
    is_available = models.BooleanField(default=True)
    last_donation_date = models.DateField(null=True, blank=True)
    contact_consent = models.BooleanField(
        default=False,
        help_text='Allow logged-in requesters to see my phone number.',
    )
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-updated_at']
        indexes = [
            models.Index(fields=['blood_group', 'city']),
        ]

    def __str__(self):
        return f'{self.full_name} ({self.blood_group}) — {self.city}'
