from django.contrib.auth import views as auth_views
from django.urls import path

from . import views
from .form import StaffAuthForm

urlpatterns = [
    path("", views.index, name="index"),
    path("about/", views.about, name="about"),
    path("services/", views.services, name="services"),
    path("gallery/", views.gallery, name="gallery"),
    path("gallery/<int:pk>/delete/", views.gallery_delete, name="gallery_delete"),
    path("contact/", views.contact, name="contact"),

    path("dashboard/login/",
         auth_views.LoginView.as_view(
             template_name="dashboard/login.html",
             authentication_form=StaffAuthForm),
         name="dashboard_login"),
    path("dashboard/logout/", auth_views.LogoutView.as_view(), name="dashboard_logout"),
    path("dashboard/", views.bookings_list, name="dashboard"),
    path("dashboard/booking/<int:pk>/status/", views.update_status, name="booking_status"),
    path("pay/<uuid:ref>/", views.payment, name="payment"),
    path("pay/<uuid:ref>/status/", views.payment_status, name="payment_status"),
    path("mpesa/callback/<str:secret>/", views.mpesa_callback, name="mpesa_callback"),
]