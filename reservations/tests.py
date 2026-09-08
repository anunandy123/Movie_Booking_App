from datetime import timedelta
import json
from unittest.mock import patch

from django.test import TestCase
from django.contrib.auth import get_user_model
from django.utils import timezone

from .models import Booking, Movie, PaymentTransaction, Reservation, ReservationSeat, Review, Seat, Show, Theater
from .services import confirm_reservation, create_payment, record_payment_result, reserve_seats


class ReservationServiceTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.seats = list(Seat.objects.filter(row="A").order_by("number")[:4])

    def test_multiple_seats_are_held_and_can_be_modified(self):
        reservation = reserve_seats("session-one", [self.seats[0].id, self.seats[1].id])
        self.assertEqual(reservation.seats.count(), 2)
        updated = reserve_seats("session-one", [self.seats[2].id], reservation)
        self.assertEqual(list(updated.seats.values_list("id", flat=True)), [self.seats[2].id])

    def test_another_session_cannot_take_a_live_hold(self):
        reserve_seats("session-one", [self.seats[0].id])
        with self.assertRaisesMessage(ValueError, "no longer available"):
            reserve_seats("session-two", [self.seats[0].id])

    def test_expired_hold_is_released(self):
        reservation = reserve_seats("session-one", [self.seats[0].id])
        Reservation.objects.filter(id=reservation.id).update(expires_at=timezone.now() - timedelta(seconds=1))
        replacement = reserve_seats("session-two", [self.seats[0].id])
        self.assertEqual(replacement.seats.get(), self.seats[0])
        self.assertFalse(ReservationSeat.objects.filter(reservation_id=reservation.id).exists())

    def test_direct_confirmation_is_rejected_without_payment(self):
        reservation = reserve_seats("session-one", [self.seats[0].id])
        with self.assertRaisesMessage(ValueError, "Payment verification is required"):
            confirm_reservation("session-one", reservation.id)
        self.assertEqual(reservation.status, Reservation.Status.HOLD)


class ReservationViewTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.movie = Movie.objects.create(title="Checkout Movie")
        cls.theater = Theater.objects.create(name="Checkout Theater", city="Test")
        cls.show = Show.objects.create(
            movie=cls.movie,
            theater=cls.theater,
            starts_at=timezone.now() + timedelta(days=1),
            ticket_price="12.50",
        )

    def test_index_and_seat_api_are_available(self):
        self.assertEqual(self.client.get("/").status_code, 200)
        response = self.client.get("/api/seats/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.json()["seats"]), 48)

    def test_booking_page_exposes_future_show_selection(self):
        response = self.client.get("/")
        self.assertContains(response, f'value="{self.show.id}"')
        self.assertContains(response, "Checkout Movie")

    def test_reservation_cannot_be_confirmed_without_verified_payment(self):
        seat = Seat.objects.get(row="A", number=1)
        response = self.client.post(
            "/api/reservations/",
            data=json.dumps({"seat_ids": [seat.id]}),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)
        reservation_id = response.json()["reservation_id"]

        response = self.client.post(f"/api/reservations/{reservation_id}/confirm/")
        self.assertEqual(response.status_code, 402)

    def test_reservation_cannot_be_confirmed_by_another_session(self):
        seat = Seat.objects.get(row="A", number=1)
        response = self.client.post(
            "/api/reservations/",
            data=json.dumps({"seat_ids": [seat.id]}),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)
        reservation_id = response.json()["reservation_id"]

        other_client = self.client_class()
        response = other_client.post(f"/api/reservations/{reservation_id}/confirm/")
        self.assertEqual(response.status_code, 402)

    def test_payment_api_returns_json_auth_error(self):
        seat = Seat.objects.get(row="A", number=1)
        response = self.client.post(
            "/api/reservations/",
            data=json.dumps({"seat_ids": [seat.id], "show_id": self.show.id}),
            content_type="application/json",
        )
        payment_response = self.client.post(
            f"/api/reservations/{response.json()['reservation_id']}/payment/"
        )
        self.assertEqual(payment_response.status_code, 401)
        self.assertEqual(payment_response.json()["error"], "Sign in before starting payment.")


class PaymentWorkflowTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user("payer", "payer@example.com", "password")
        self.seat = Seat.objects.get(row="A", number=1)

    def test_verified_payment_creates_one_booking_and_duplicate_is_idempotent(self):
        reservation = reserve_seats("payment-session", [self.seat.id], user=self.user)
        payment = create_payment(reservation, 12.50)
        with patch("reservations.tasks.email_ticket.delay"):
            booking = record_payment_result(payment.provider_order_id, PaymentTransaction.Status.PAID, "txn_123")
            duplicate = record_payment_result(payment.provider_order_id, PaymentTransaction.Status.PAID, "txn_123")
        self.assertEqual(booking.id, duplicate.id)
        self.assertEqual(Booking.objects.count(), 1)

    def test_failed_payment_releases_seats_without_losing_transaction_record(self):
        reservation = reserve_seats("payment-session", [self.seat.id], user=self.user)
        payment = create_payment(reservation, 12.50)
        self.assertIsNone(record_payment_result(payment.provider_order_id, PaymentTransaction.Status.FAILED, "txn_failed", "Declined"))
        self.assertFalse(ReservationSeat.objects.filter(reservation=reservation).exists())
        self.assertEqual(PaymentTransaction.objects.get(pk=payment.pk).status, PaymentTransaction.Status.FAILED)


class MovieManagementTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user("viewer", "viewer@example.com", "password")
        self.movie = Movie.objects.create(title="Past Feature", trailer_url="https://www.youtube.com/watch?v=abc123")

    def test_trailer_is_restricted_to_youtube_and_embeds_privately(self):
        self.assertEqual(self.movie.youtube_video_id, "abc123")
        self.assertIn("youtube-nocookie.com/embed/abc123", self.movie.trailer_embed_url)
        self.movie.trailer_url = "https://evil.example/video"
        with self.assertRaises(Exception):
            self.movie.full_clean()

    def test_only_a_viewer_who_attended_can_review(self):
        self.client.force_login(self.user)
        response = self.client.post(f"/api/movies/{self.movie.id}/review/", data=json.dumps({"rating": 5, "body": "Great"}), content_type="application/json")
        self.assertEqual(response.status_code, 403)

        theater = Theater.objects.create(name="Main", city="Pune")
        show = Show.objects.create(movie=self.movie, theater=theater, starts_at=timezone.now() - timedelta(hours=2), ticket_price=10)
        reservation = reserve_seats("review-session", [Seat.objects.get(row="A", number=1).id], user=self.user)
        Booking.objects.create(user=self.user, show=show, reservation=reservation, total_amount=10)
        response = self.client.post(f"/api/movies/{self.movie.id}/review/", data=json.dumps({"rating": 5, "body": "Great"}), content_type="application/json")
        self.assertEqual(response.status_code, 200)
        self.assertTrue(Review.objects.get(movie=self.movie, user=self.user).is_verified_viewer)

