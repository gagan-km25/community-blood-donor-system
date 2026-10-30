"""Blood request models: requests, status history, and abuse reports."""

from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator, MaxValueValidator
from django.db import models

from donors.models import BloodGroup, phone_validator


class Urgency(models.TextChoices):
    NORMAL = 'normal', 'Normal'
    URGENT = 'urgent', 'Urgent'
    CRITICAL = 'critical', 'Critical'


class RequestStatus(models.TextChoices):
    OPEN = 'open', 'Open'
    MATCHED = 'matched', 'Matched'
    PARTIALLY_FULFILLED = 'partially_fulfilled', 'Partially Fulfilled'
    FULFILLED = 'fulfilled', 'Fulfilled'
    CANCELLED = 'cancelled', 'Cancelled'
    EXPIRED = 'expired', 'Expired'


#: Statuses that still need blood. Everything else is terminal.
ACTIVE_STATUSES = (
    RequestStatus.OPEN,
    RequestStatus.MATCHED,
    RequestStatus.PARTIALLY_FULFILLED,
)


class BloodRequest(models.Model):
    """An emergency blood request created by a registered requester."""

    requester = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name='blood_requests'
    )
    patient_name = models.CharField(
        max_length=120, blank=True,
        help_text='Optional — only if needed to identify the beneficiary.',
    )
    blood_group = models.CharField(max_length=3, choices=BloodGroup.choices)
    units_needed = models.PositiveSmallIntegerField(
        validators=[MinValueValidator(1), MaxValueValidator(10)]
    )
    units_fulfilled = models.PositiveSmallIntegerField(
        default=0, validators=[MinValueValidator(0), MaxValueValidator(10)]
    )
    hospital_name = models.CharField(max_length=150)
    hospital_city = models.CharField(max_length=80)
    urgency = models.CharField(
        max_length=10, choices=Urgency.choices, default=Urgency.NORMAL
    )
    needed_by = models.DateTimeField(
        help_text='Date and time by which the blood is required.'
    )
    contact_number = models.CharField(max_length=20, validators=[phone_validator])
    notes = models.TextField(blank=True)
    status = models.CharField(
        max_length=20, choices=RequestStatus.choices,
        default=RequestStatus.OPEN,
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']

    def clean(self):
        if self.units_fulfilled and self.units_fulfilled > self.units_needed:
            raise ValidationError(
                'Units fulfilled cannot exceed units needed.'
            )

    @property
    def is_terminal(self) -> bool:
        return self.status not in ACTIVE_STATUSES

    @property
    def units_remaining(self) -> int:
        return max(self.units_needed - self.units_fulfilled, 0)

    def __str__(self):
        return (f'{self.blood_group} × {self.units_needed} at '
                f'{self.hospital_name} ({self.hospital_city}) — {self.status}')


class RequestStatusHistory(models.Model):
    """Append-only audit trail of status changes for one request."""

    request = models.ForeignKey(
        BloodRequest, on_delete=models.CASCADE, related_name='history'
    )
    from_status = models.CharField(max_length=20, choices=RequestStatus.choices)
    to_status = models.CharField(max_length=20, choices=RequestStatus.choices)
    changed_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='status_changes_made',
        help_text='Null means the system (automatic expiry).',
    )
    note = models.CharField(max_length=200, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name_plural = 'request status histories'

    def __str__(self):
        return f'{self.from_status} → {self.to_status} at {self.created_at:%Y-%m-%d %H:%M}'


class AbuseReport(models.Model):
    """A user's report that a community-board request is inappropriate."""

    class ReviewStatus(models.TextChoices):
        PENDING = 'pending', 'Pending'
        REVIEWED = 'reviewed', 'Reviewed'
        DISMISSED = 'dismissed', 'Dismissed'

    request = models.ForeignKey(
        BloodRequest, on_delete=models.CASCADE, related_name='abuse_reports'
    )
    reported_by = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name='abuse_reports_filed'
    )
    reason = models.TextField(max_length=1000)
    status = models.CharField(
        max_length=10, choices=ReviewStatus.choices,
        default=ReviewStatus.PENDING,
    )
    reviewed_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='abuse_reviews_made',
    )
    reviewed_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=['request', 'reported_by'],
                name='unique_abuse_report_per_reporter',
            )
        ]

    def __str__(self):
        return f'Report on request #{self.request_id} by {self.reported_by} ({self.status})'
