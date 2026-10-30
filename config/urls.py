"""Root URL configuration: wires the four local apps and error handlers."""

from django.contrib import admin
from django.urls import include, path

from config import views as config_views

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', include('dashboard.urls')),
    path('accounts/', include('accounts.urls')),
    path('donors/', include('donors.urls')),
    path('requests/', include('blood_requests.urls')),
]

# Custom error pages (visible when DEBUG is False; see README).
handler403 = 'config.views.error_403'
handler404 = 'config.views.error_404'
handler500 = 'config.views.error_500'
