from datetime import timedelta

from django.db import transaction
from django.utils import timezone

from .models import Reservation, ReservationSeat, Seat

HOLD_DURATION = timedelta(minutes=2)


def release_expired_holds():
    expired_ids = Reservation.objects.filter(
        status=Reservation.Status.HOLD,
        expires_at__lte=timezone.now(),
    ).values_list("id", flat=True)
    ReservationSeat.objects.filter(reservation_id__in=expired_ids).delete()
    Reservation.objects.filter(id__in=expired_ids).delete()


@transaction.atomic
def reserve_seats(session_key, seat_ids, reservation=None):
    """Create or replace a hold while serializing access to every requested seat."""
    release_expired_holds()
    normalized_ids = sorted({int(seat_id) for seat_id in seat_ids})
    if not normalized_ids:
        raise ValueError("Select at least one seat.")

    locked_seats = list(Seat.objects.select_for_update().filter(id__in=normalized_ids).order_by("id"))
    if len(locked_seats) != len(normalized_ids):
        raise ValueError("One or more selected seats do not exist.")

    conflicting = ReservationSeat.objects.filter(
        seat_id__in=normalized_ids,
        reservation__status=Reservation.Status.CONFIRMED,
    ).exists()
    if not conflicting:
        conflicting = ReservationSeat.objects.filter(
            seat_id__in=normalized_ids,
            reservation__status=Reservation.Status.HOLD,
            reservation__expires_at__gt=timezone.now(),
        ).exclude(reservation=reservation).exists()
    if conflicting:
        raise ValueError("One or more seats are no longer available.")

    if reservation is None:
        reservation = Reservation.objects.create(
            session_key=session_key,
            expires_at=timezone.now() + HOLD_DURATION,
        )
    elif reservation.session_key != session_key or reservation.status != Reservation.Status.HOLD:
        raise ValueError("This reservation cannot be modified.")
    else:
        reservation.expires_at = timezone.now() + HOLD_DURATION
        reservation.save(update_fields=["expires_at", "updated_at"])
        reservation.reservationseat_set.all().delete()

    ReservationSeat.objects.bulk_create(
        [ReservationSeat(reservation=reservation, seat=seat) for seat in locked_seats]
    )
    return reservation


@transaction.atomic
def confirm_reservation(session_key, reservation_id):
    release_expired_holds()
    reservation = Reservation.objects.select_for_update().get(id=reservation_id, session_key=session_key)
    if reservation.status != Reservation.Status.HOLD or not reservation.is_active_hold:
        raise ValueError("This hold has expired.")
    reservation.status = Reservation.Status.CONFIRMED
    reservation.expires_at = None
    reservation.save(update_fields=["status", "expires_at", "updated_at"])
    return reservation