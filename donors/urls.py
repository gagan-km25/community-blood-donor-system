from django.urls import path

from . import views

app_name = 'donors'

urlpatterns = [
    path('search/', views.search, name='search'),
    path('me/new/', views.my_profile_create, name='my_profile_create'),
    path('me/edit/', views.my_profile_edit, name='my_profile_edit'),
    path('me/toggle/', views.my_profile_toggle_active, name='my_profile_toggle'),
    path('me/dashboard/', views.donor_dashboard, name='donor_dashboard'),
]
