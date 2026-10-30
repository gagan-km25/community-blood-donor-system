from django.urls import path

from . import views

app_name = 'dashboard'

urlpatterns = [
    path('', views.home, name='home'),
    path('about/', views.about, name='about'),
    path('dashboard/', views.dashboard_entry, name='dashboard_entry'),
    path('admin-dashboard/', views.admin_dashboard, name='admin_dashboard'),
    path('reports/<int:report_id>/resolve/', views.resolve_abuse_report,
         name='resolve_abuse_report'),
]
