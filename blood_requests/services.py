"""Request state machine and expiry logic.

Every status change in the whole application goes through ``transition`` so the
rules, unit bookkeeping, and history records stay consistent in one place.
"""

from django.core.exceptions import ValidationError
from django.utils import timezone

from .models import (
    ACTIVE_STATUSES, BloodRequest, RequestStatus, RequestStatusHistory,
)

# Allowed moves. Terminal statuses (fulfilled/cancelled/expired) allow nothing.
ALLOWED_TRANSITIONS = {
    RequestStatus.OPEN: {
        RequestStatus.MATCHED,
        RequestStatus.PARTIALLY_FULFILLED,
        RequestStatus.FULFILLED,
        RequestStatus.CANCELLED,
    },
    RequestStatus.MATCHED: {
        RequestStatus.PARTIALLY_FULFILLED,
        RequestStatus.FULFILLED,
        RequestStatus.CANCELLED,
    },
    RequestStatus.PARTIALLY_FULFILLED: {
        RequestStatus.FULFILLED,
        RequestStatus.CANCELLED,
    },
    RequestStatus.FULFILLED: set(),
    RequestStatus.CANCELLED: set(),
    RequestStatus.EXPIRED: set(),
}


def transition(blood_request, to_status: str, user, note: str = '',
               units_fulfilled=None, automatic: bool = False) -> None:
    """Move ``blood_request`` to ``to_status`` following the state machine.

    ``automatic=True`` is reserved for the system (auto-expiry): it is the
    only path allowed to move a request to ``expired``. Users can never do
    that through forms.

    Raises ``ValidationError`` for illegal moves so views can surface a
    friendly message. Writes a RequestStatusHistory row on success.
    """
    from_status = blood_request.status
    try:
        to_status = RequestStatus(to_status)
    except ValueError:
        raise ValidationError(f'Unknown status: {to_status}')

    allowed = set(ALLOWED_TRANSITIONS.get(RequestStatus(from_status), set()))
    if automatic:
        allowed.add(RequestStatus.EXPIRED)
    if to_status not in allowed:
        raise ValidationError(
            f'A request cannot move from "{RequestStatus(from_status).label}" '
            f'to "{to_status.label}".'
        )

    if to_status == RequestStatus.FULFILLED:
        blood_request.units_fulfilled = blood_request.units_needed
    elif to_status == RequestStatus.PARTIALLY_FULFILLED:
        units = int(units_fulfilled or 0)
        if not 0 < units < blood_request.units_needed:
            raise ValidationError(
                'Partially fulfilled requests need units fulfilled between 1 '
                f'and {blood_request.units_needed - 1}.'
            )
        blood_request.units_fulfilled = units

    blood_request.status = to_status
    blood_request.save()
    RequestStatusHistory.objects.create(
        request=blood_request,
        from_status=from_status,
        to_status=to_status,
        changed_by=user if (user is not None and user.is_authenticated) else None,
        note=note[:200],
    )


def expire_due_requests() -> int:
    """Expire every non-terminal request whose needed_by date has passed.

    Called from list/dashboard views (lazy expiry) and from the
    ``expire_requests`` management command. Returns the number expired.
    """
    now = timezone.now()
    overdue = BloodRequest.objects.filter(
        status__in=ACTIVE_STATUSES, needed_by__lt=now
    )
    count = 0
    for request_obj in overdue:
        transition(
            request_obj,
            RequestStatus.EXPIRED,
            user=None,
            note='Automatically expired: required date passed.',
            automatic=True,
        )
        count += 1
    return count
