"""Blood request views.

Ownership rule used everywhere: only the requester or a staff member may view
or change a specific request. Everyone else gets 403 (PermissionDenied).
"""

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied, ValidationError
from django.db.models import Case, IntegerField, When
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from donors.matching import find_potential_donors
from donors.views import can_view_phone

from .forms import AbuseReportForm, BloodRequestForm, StatusUpdateForm
from .models import ACTIVE_STATUSES, AbuseReport, BloodRequest, RequestStatus
from .services import expire_due_requests, transition

# Next action shown to the owner for each non-terminal status.
NEXT_ACTIONS = {
    RequestStatus.OPEN: [
        (RequestStatus.MATCHED, 'Mark as matched', False),
        (RequestStatus.PARTIALLY_FULFILLED, 'Record partial fulfilment', True),
        (RequestStatus.FULFILLED, 'Mark as fulfilled', False),
    ],
    RequestStatus.MATCHED: [
        (RequestStatus.PARTIALLY_FULFILLED, 'Record partial fulfilment', True),
        (RequestStatus.FULFILLED, 'Mark as fulfilled', False),
    ],
    RequestStatus.PARTIALLY_FULFILLED: [
        (RequestStatus.FULFILLED, 'Mark as fulfilled', False),
    ],
}

URGENCY_ORDER = Case(
    When(urgency='critical', then=0),
    When(urgency='urgent', then=1),
    default=2,
    output_field=IntegerField(),
)


def _get_request_or_403(request, pk) -> BloodRequest:
    """Fetch a request and enforce the ownership rule (owner or staff)."""
    blood_request = get_object_or_404(
        BloodRequest.objects.select_related('requester'), pk=pk
    )
    if blood_request.requester_id != request.user.id and not request.user.is_staff:
        raise PermissionDenied('You can only access your own requests.')
    return blood_request


@login_required
def create_request(request):
    if request.method == 'POST':
        form = BloodRequestForm(request.POST)
        if form.is_valid():
            blood_request = form.save(commit=False)
            blood_request.requester = request.user
            blood_request.save()
            messages.success(
                request, 'Blood request created. Track its progress below.'
            )
            return redirect('blood_requests:request_detail', pk=blood_request.pk)
        messages.error(request, 'Please fix the errors below.')
    else:
        form = BloodRequestForm()
    return render(request, 'requests/request_form.html', {
        'form': form, 'is_edit': False,
    })


@login_required
def my_requests(request):
    """Requester dashboard: stats plus the user's own requests."""
    expire_due_requests()
    requests_list = BloodRequest.objects.filter(requester=request.user)
    stats = {
        'total': requests_list.count(),
        'open': requests_list.filter(status=RequestStatus.OPEN).count(),
        'fulfilled': requests_list.filter(status=RequestStatus.FULFILLED).count(),
        'active': requests_list.filter(status__in=ACTIVE_STATUSES).count(),
    }
    return render(request, 'requests/request_list.html', {
        'requests_list': requests_list,
        'stats': stats,
    })


@login_required
def request_detail(request, pk):
    blood_request = _get_request_or_403(request, pk)
    expire_due_requests()
    blood_request.refresh_from_db()

    # Potential donor leads (never changes the request status).
    potential_donors = []
    if not blood_request.is_terminal:
        potential_donors = [
            {'profile': p, 'show_phone': can_view_phone(p, request)}
            for p in find_potential_donors(blood_request)
        ]

    # Partial fulfilment is impossible when 1 or fewer units remain (the
    # state machine requires 0 < units_fulfilled < units_needed), so never
    # offer that action — otherwise the units input would render an invalid
    # min="1" max="0" range that the browser refuses to submit.
    next_actions = NEXT_ACTIONS.get(blood_request.status, [])
    if blood_request.units_remaining <= 1:
        next_actions = [
            action for action in next_actions
            if action[0] != RequestStatus.PARTIALLY_FULFILLED
        ]

    return render(request, 'requests/request_detail.html', {
        'blood_request': blood_request,
        'potential_donors': potential_donors,
        'next_actions': next_actions,
        'can_cancel': blood_request.status in ACTIVE_STATUSES,
        'can_edit': blood_request.status in ACTIVE_STATUSES,
    })


@login_required
def update_request(request, pk):
    blood_request = _get_request_or_403(request, pk)
    if blood_request.is_terminal:
        messages.error(
            request,
            f'A {blood_request.get_status_display().lower()} request can no '
            'longer be edited.'
        )
        return redirect('blood_requests:request_detail', pk=pk)

    if request.method == 'POST':
        form = BloodRequestForm(request.POST, instance=blood_request)
        if form.is_valid():
            form.save()
            messages.success(request, 'Blood request updated.')
            return redirect('blood_requests:request_detail', pk=pk)
        messages.error(request, 'Please fix the errors below.')
    else:
        form = BloodRequestForm(instance=blood_request)
    return render(request, 'requests/request_form.html', {
        'form': form, 'is_edit': True, 'blood_request': blood_request,
    })


@login_required
@require_POST
def cancel_request(request, pk):
    blood_request = _get_request_or_403(request, pk)
    try:
        transition(
            blood_request, RequestStatus.CANCELLED, user=request.user,
            note='Cancelled by requester.' if not request.user.is_staff
                 else 'Cancelled by administrator.',
        )
        messages.success(request, 'Request cancelled.')
    except ValidationError as exc:
        messages.error(request, exc.message)
    return redirect('blood_requests:request_detail', pk=pk)


@login_required
@require_POST
def update_status(request, pk):
    blood_request = _get_request_or_403(request, pk)
    form = StatusUpdateForm(request.POST)
    if form.is_valid():
        try:
            transition(
                blood_request,
                form.cleaned_data['to_status'],
                user=request.user,
                note=form.cleaned_data['note'],
                units_fulfilled=form.cleaned_data['units_fulfilled'],
            )
            messages.success(
                request,
                f'Status updated to "{blood_request.get_status_display()}".'
            )
        except ValidationError as exc:
            messages.error(request, exc.message)
    else:
        messages.error(request, 'Invalid status action.')
    return redirect('blood_requests:request_detail', pk=pk)


@login_required
def requests_board(request):
    """Community board of open requests (no contact details, no patient names)."""
    expire_due_requests()
    requests_list = (
        BloodRequest.objects
        .filter(status=RequestStatus.OPEN)
        .select_related('requester')
        .annotate(urgency_rank=URGENCY_ORDER)
        .order_by('urgency_rank', 'needed_by')
    )
    reported_ids = set(
        AbuseReport.objects.filter(reported_by=request.user)
        .values_list('request_id', flat=True)
    )
    return render(request, 'requests/requests_board.html', {
        'requests_list': requests_list,
        'reported_ids': reported_ids,
    })


@login_required
@require_POST
def report_request(request, pk):
    """File one abuse report per user per request from the community board."""
    blood_request = get_object_or_404(BloodRequest, pk=pk)
    if blood_request.requester_id == request.user.id:
        messages.error(request, 'You cannot report your own request.')
        return redirect('blood_requests:requests_board')

    form = AbuseReportForm(request.POST)
    if form.is_valid():
        _, created = AbuseReport.objects.get_or_create(
            request=blood_request,
            reported_by=request.user,
            defaults={'reason': form.cleaned_data['reason']},
        )
        if created:
            messages.success(
                request, 'Report submitted. An administrator will review it.'
            )
        else:
            messages.info(
                request, 'You have already reported this request.'
            )
    else:
        messages.error(request, 'Please provide a reason to report a request.')
    return redirect('blood_requests:requests_board')
