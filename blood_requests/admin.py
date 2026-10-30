from django.contrib import admin
from django.utils import timezone

from .models import AbuseReport, BloodRequest, RequestStatusHistory


@admin.register(BloodRequest)
class BloodRequestAdmin(admin.ModelAdmin):
    list_display = (
        'id', 'requester', 'blood_group', 'units_needed', 'units_fulfilled',
        'urgency', 'status', 'needed_by', 'hospital_city',
    )
    list_filter = ('status', 'urgency', 'blood_group', 'hospital_city')
    search_fields = ('requester__username', 'patient_name', 'hospital_name')
    readonly_fields = ('created_at', 'updated_at')


@admin.register(RequestStatusHistory)
class RequestStatusHistoryAdmin(admin.ModelAdmin):
    list_display = ('request', 'from_status', 'to_status', 'changed_by', 'created_at')
    list_filter = ('to_status',)
    readonly_fields = ('request', 'from_status', 'to_status', 'changed_by', 'note', 'created_at')

    def has_add_permission(self, request):
        return False  # history rows are only written by the app


@admin.register(AbuseReport)
class AbuseReportAdmin(admin.ModelAdmin):
    list_display = ('request', 'reported_by', 'status', 'created_at', 'reviewed_at')
    list_filter = ('status',)
    search_fields = ('reason', 'reported_by__username')

    actions = ['mark_reviewed', 'dismiss_reports']

    @admin.action(description='Mark selected reports as reviewed')
    def mark_reviewed(self, request, queryset):
        queryset.update(status=AbuseReport.ReviewStatus.REVIEWED,
                        reviewed_by=request.user, reviewed_at=timezone.now())

    @admin.action(description='Dismiss selected reports')
    def dismiss_reports(self, request, queryset):
        queryset.update(status=AbuseReport.ReviewStatus.DISMISSED,
                        reviewed_by=request.user, reviewed_at=timezone.now())
