from django.urls import path

from . import views

urlpatterns = [
    path("", views.index, name="index"),
    path("api/seats/", views.seats, name="seats"),
    path("api/reservations/", views.create_reservation, name="create_reservation"),
    path("api/reservations/<uuid:reservation_id>/", views.update_reservation, name="update_reservation"),
    path("api/reservations/<uuid:reservation_id>/confirm/", views.confirm, name="confirm_reservation"),
    path("api/reservations/<uuid:reservation_id>/payment/", views.create_payment_order, name="create_payment_order"),
    path("api/payments/<uuid:payment_id>/retry/", views.retry_payment_order, name="retry_payment_order"),
    path("api/payments/webhook/", views.payment_webhook, name="payment_webhook"),
    path("api/bookings/", views.booking_history, name="booking_history"),
    path("api/bookings/<uuid:booking_id>/ticket/", views.download_ticket, name="download_ticket"),
    path("api/bookings/<uuid:booking_id>/cancel/", views.cancel_booking_view, name="cancel_booking"),
    path("api/movies/", views.movie_discovery, name="movie_discovery"),
    path("api/movies/<int:movie_id>/", views.movie_detail, name="movie_detail"),
    path("movies/<int:movie_id>/", views.movie_page, name="movie_page"),
    path("api/movies/<int:movie_id>/review/", views.movie_review, name="movie_review"),
    path("api/reviews/<int:review_id>/report/", views.report_review, name="report_review"),
    path("admin-dashboard/", views.admin_dashboard, name="admin_dashboard"),
    path("admin-dashboard/report.csv", views.admin_report_csv, name="admin_report_csv"),
]