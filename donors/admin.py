from django.contrib import admin

from .models import DonorProfile


@admin.register(DonorProfile)
class DonorProfileAdmin(admin.ModelAdmin):
    list_display = (
        'full_name', 'blood_group', 'city', 'is_available',
        'contact_consent', 'is_active', 'updated_at',
    )
    list_filter = ('blood_group', 'city', 'is_available', 'is_active')
    search_fields = ('full_name', 'city', 'user__username')
    readonly_fields = ('created_at', 'updated_at')
