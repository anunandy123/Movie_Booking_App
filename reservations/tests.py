from datetime import timedelta
import json

from django.test import TestCase
from django.utils import timezone

from .models import Reservation, ReservationSeat, Seat
from .services import confirm_reservation, reserve_seats


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

    def test_confirmation_is_permanent(self):
        reservation = reserve_seats("session-one", [self.seats[0].id])
        confirmed = confirm_reservation("session-one", reservation.id)
        self.assertEqual(confirmed.status, Reservation.Status.CONFIRMED)
        with self.assertRaisesMessage(ValueError, "no longer available"):
            reserve_seats("session-two", [self.seats[0].id])


class ReservationViewTests(TestCase):
    def test_index_and_seat_api_are_available(self):
        self.assertEqual(self.client.get("/").status_code, 200)
        response = self.client.get("/api/seats/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.json()["seats"]), 48)

    def test_reservation_can_be_created_and_confirmed(self):
        seat = Seat.objects.get(row="A", number=1)
        response = self.client.post(
            "/api/reservations/",
            data=json.dumps({"seat_ids": [seat.id]}),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)
        reservation_id = response.json()["reservation_id"]

        response = self.client.post(f"/api/reservations/{reservation_id}/confirm/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["status"], Reservation.Status.CONFIRMED)

    def test_reservation_cannot_be_confirmed_by_another_session(self):
        seat = Seat.objects.get(row="A", number=1)
        response = self.client.post(
            "/api/reservations/",
            data=json.dumps({"seat_ids": [seat.id]}),
            content_type="application/json",
        )
        reservation_id = response.json()["reservation_id"]

        other_client = self.client_class()
        response = other_client.post(f"/api/reservations/{reservation_id}/confirm/")
        self.assertEqual(response.status_code, 409)

