from django.urls import path

from . import views

urlpatterns = [
    path("", views.index, name="index"),
    path("api/seats/", views.seats, name="seats"),
    path("api/reservations/", views.create_reservation, name="create_reservation"),
    path("api/reservations/<uuid:reservation_id>/", views.update_reservation, name="update_reservation"),
    path("api/reservations/<uuid:reservation_id>/confirm/", views.confirm, name="confirm_reservation"),
]