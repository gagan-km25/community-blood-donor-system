from django.urls import path

from . import views

app_name = 'blood_requests'

urlpatterns = [
    path('board/', views.requests_board, name='requests_board'),
    path('new/', views.create_request, name='create_request'),
    path('mine/', views.my_requests, name='my_requests'),
    path('<int:pk>/', views.request_detail, name='request_detail'),
    path('<int:pk>/edit/', views.update_request, name='update_request'),
    path('<int:pk>/cancel/', views.cancel_request, name='cancel_request'),
    path('<int:pk>/status/', views.update_status, name='update_status'),
    path('<int:pk>/report/', views.report_request, name='report_request'),
]
