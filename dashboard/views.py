"""Public pages (home/about) and the staff-only administrator dashboard."""

from django.contrib import messages
from django.contrib.admin.views.decorators import staff_member_required
from django.contrib.auth.models import User
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from accounts.views import dashboard_url_for
from blood_requests.models import (
    AbuseReport, BloodRequest, RequestStatus, RequestStatusHistory,
)
from donors.models import DonorProfile


def home(request):
    """Landing page with a few live site statistics."""
    stats = {
        'active_donors': DonorProfile.objects.filter(is_active=True).count(),
        'open_requests': BloodRequest.objects.filter(status=RequestStatus.OPEN).count(),
        'fulfilled_requests': BloodRequest.objects.filter(
            status=RequestStatus.FULFILLED
        ).count(),
    }
    return render(request, 'dashboard/home.html', {'stats': stats})


def about(request):
    return render(request, 'dashboard/about.html')


def dashboard_entry(request):
    """Send the logged-in user to the dashboard that fits their role."""
    if not request.user.is_authenticated:
        return redirect('accounts:login')
    return redirect(dashboard_url_for(request.user))


@staff_member_required
def admin_dashboard(request):
    """Administrator overview. Every number is computed from the database."""
    stats = {
        'total_users': User.objects.count(),
        'active_donors': DonorProfile.objects.filter(is_active=True).count(),
        'open_requests': BloodRequest.objects.filter(status=RequestStatus.OPEN).count(),
        'fulfilled_requests': BloodRequest.objects.filter(
            status=RequestStatus.FULFILLED
        ).count(),
        'pending_reports': AbuseReport.objects.filter(
            status=AbuseReport.ReviewStatus.PENDING
        ).count(),
    }
    recent_users = User.objects.order_by('-date_joined')[:5]
    recent_requests = (
        BloodRequest.objects.select_related('requester').order_by('-created_at')[:5]
    )
    recent_history = (
        RequestStatusHistory.objects.select_related('request', 'changed_by')[:10]
    )
    pending_reports = (
        AbuseReport.objects.filter(status=AbuseReport.ReviewStatus.PENDING)
        .select_related('request', 'reported_by')
    )
    return render(request, 'dashboard/admin_dashboard.html', {
        'stats': stats,
        'recent_users': recent_users,
        'recent_requests': recent_requests,
        'recent_history': recent_history,
        'pending_reports': pending_reports,
    })


@staff_member_required
@require_POST
def resolve_abuse_report(request, report_id):
    """Mark an abuse report reviewed or dismissed (admin action)."""
    report = get_object_or_404(AbuseReport, pk=report_id)
    action = request.POST.get('action')
    if action == 'reviewed':
        report.status = AbuseReport.ReviewStatus.REVIEWED
        messages.success(request, f'Report #{report.pk} marked as reviewed.')
    elif action == 'dismissed':
        report.status = AbuseReport.ReviewStatus.DISMISSED
        messages.success(request, f'Report #{report.pk} dismissed.')
    else:
        messages.error(request, 'Unknown review action.')
        return redirect('dashboard:admin_dashboard')
    report.reviewed_by = request.user
    report.reviewed_at = timezone.now()
    report.save()
    return redirect('dashboard:admin_dashboard')
