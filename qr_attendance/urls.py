# qr_attendance/urls.py
from django.urls import path
from . import views

urlpatterns = [
    path('', views.upload_excel, name='upload_excel'),
    path('attendees/', views.attendee_list, name='attendee_list'),
    path('get_attendees_paginated/', views.get_attendees_paginated, name='get_attendees_paginated'),
    path('scan/<str:code>/', views.scan_qr, name='scan_qr'),
    path('scan/', views.scan_page, name='scan_page'),
    path('attendance/', views.attendance_list, name='attendance_list'),
    path('generate_qr_stickers/', views.generate_qr_stickers, name='generate_qr_stickers'),
    path('flush_attendees/', views.flush_attendees, name='flush_attendees'),
    path('flush_attendance/', views.flush_attendance, name='flush_attendance'),
]