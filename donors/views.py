"""Donor profile management, public donor search, and the donor dashboard."""

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Q
from django.shortcuts import redirect, render
from django.views.decorators.http import require_POST

from blood_requests.models import BloodRequest, RequestStatus
from blood_requests.services import expire_due_requests
from .forms import DonorProfileForm, DonorSearchForm
from .matching import recipient_groups_for_donor
from .models import DonorProfile

# How many leads / opportunities to show on dashboard pages.
DASHBOARD_OPPORTUNITY_LIMIT = 5
SEARCH_PAGE_SIZE = 8


def can_view_phone(profile: DonorProfile, request) -> bool:
    """Privacy rule: phone is visible only with donor consent AND a
    logged-in viewer. Guests never see phone numbers."""
    return profile.contact_consent and request.user.is_authenticated


def search(request):
    """Public donor search (guests allowed, but they never see phone numbers)."""
    form = DonorSearchForm(request.GET or None)
    profiles_qs = DonorProfile.objects.filter(is_active=True).select_related('user')

    if form.is_valid():
        blood_group = form.cleaned_data['blood_group']
        city = form.cleaned_data['city'].strip()
        availability = form.cleaned_data['availability']

        if blood_group:
            profiles_qs = profiles_qs.filter(blood_group=blood_group)
        if city:
            profiles_qs = profiles_qs.filter(city__icontains=city)
        if availability == 'available':
            profiles_qs = profiles_qs.filter(is_available=True)
    searched = bool(request.GET)

    page_obj = Paginator(profiles_qs, SEARCH_PAGE_SIZE).get_page(request.GET.get('page'))

    # Attach the privacy decision once per profile so templates stay dumb.
    results = [
        {'profile': p, 'show_phone': can_view_phone(p, request)}
        for p in page_obj.object_list
    ]

    return render(request, 'donors/search.html', {
        'form': form,
        'page_obj': page_obj,
        'results': results,
        'searched': searched,
    })


@login_required
def my_profile_create(request):
    """Create the donor profile (one per user); bounces to edit if it exists."""
    if hasattr(request.user, 'donor_profile'):
        return redirect('donors:my_profile_edit')

    if request.method == 'POST':
        form = DonorProfileForm(request.POST)
        if form.is_valid():
            profile = form.save(commit=False)
            profile.user = request.user
            profile.save()
            messages.success(request, 'Your donor profile has been created. Thank you!')
            return redirect('donors:donor_dashboard')
        messages.error(request, 'Please fix the errors below.')
    else:
        form = DonorProfileForm()
    return render(request, 'donors/donor_form.html', {
        'form': form, 'is_edit': False,
    })


@login_required
def my_profile_edit(request):
    profile = getattr(request.user, 'donor_profile', None)
    if profile is None:
        return redirect('donors:my_profile_create')

    if request.method == 'POST':
        form = DonorProfileForm(request.POST, instance=profile)
        if form.is_valid():
            form.save()
            messages.success(request, 'Donor profile updated.')
            return redirect('donors:donor_dashboard')
        messages.error(request, 'Please fix the errors below.')
    else:
        form = DonorProfileForm(instance=profile)
    return render(request, 'donors/donor_form.html', {
        'form': form, 'is_edit': True,
    })


@login_required
@require_POST
def my_profile_toggle_active(request):
    """Deactivate/reactivate own donor profile (soft delete)."""
    profile = getattr(request.user, 'donor_profile', None)
    if profile is None:
        return redirect('donors:my_profile_create')

    profile.is_active = not profile.is_active
    profile.save(update_fields=['is_active', 'updated_at'])
    if profile.is_active:
        messages.success(request, 'Your donor profile is active again.')
    else:
        messages.success(
            request,
            'Your donor profile has been deactivated and is hidden from search.'
        )
    return redirect('donors:donor_dashboard')


@login_required
def donor_dashboard(request):
    """Donor home: profile summary plus compatible open requests (leads)."""
    profile = getattr(request.user, 'donor_profile', None)
    if profile is None:
        messages.info(request, 'Create your donor profile to get started.')
        return redirect('donors:my_profile_create')

    expire_due_requests()

    opportunities = []
    if profile.is_active:
        recipient_groups = recipient_groups_for_donor(profile.blood_group)
        opportunities = (
            BloodRequest.objects
            .filter(status=RequestStatus.OPEN, blood_group__in=recipient_groups)
            .filter(Q(hospital_city__icontains=profile.city))
            .exclude(requester=request.user)
            .order_by('needed_by')[:DASHBOARD_OPPORTUNITY_LIMIT]
        )

    return render(request, 'donors/donor_dashboard.html', {
        'profile': profile,
        'opportunities': opportunities,
    })
