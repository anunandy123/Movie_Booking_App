from datetime import timedelta
import uuid

from django.db import transaction
from django.utils import timezone

from .models import Booking, BookingSeat, PaymentTransaction, Reservation, ReservationSeat, Seat

HOLD_DURATION = timedelta(minutes=2)


def release_expired_holds():
    expired_ids = Reservation.objects.filter(
        status=Reservation.Status.HOLD,
        expires_at__lte=timezone.now(),
    ).values_list("id", flat=True)
    ReservationSeat.objects.filter(reservation_id__in=expired_ids).delete()
    Reservation.objects.filter(id__in=expired_ids).update(status=Reservation.Status.CANCELLED, expires_at=None)


@transaction.atomic
def reserve_seats(session_key, seat_ids, reservation=None, user=None, show=None):
    """Create or replace a hold while serializing access to every requested seat."""
    release_expired_holds()
    normalized_ids = sorted({int(seat_id) for seat_id in seat_ids})
    if not normalized_ids:
        raise ValueError("Select at least one seat.")

    locked_seats = list(Seat.objects.select_for_update().filter(id__in=normalized_ids).order_by("id"))
    if len(locked_seats) != len(normalized_ids):
        raise ValueError("One or more selected seats do not exist.")

    conflicting_query = ReservationSeat.objects.filter(
        seat_id__in=normalized_ids,
        reservation__status=Reservation.Status.CONFIRMED,
    )
    if show is not None:
        conflicting_query = conflicting_query.filter(reservation__show=show)
    conflicting = conflicting_query.exists()
    if not conflicting:
        conflicting_query = ReservationSeat.objects.filter(
            seat_id__in=normalized_ids,
            reservation__status=Reservation.Status.HOLD,
            reservation__expires_at__gt=timezone.now(),
        ).exclude(reservation=reservation)
        if show is not None:
            conflicting_query = conflicting_query.filter(reservation__show=show)
        conflicting = conflicting_query.exists()
    if conflicting:
        raise ValueError("One or more seats are no longer available.")

    if reservation is None:
        reservation = Reservation.objects.create(
            session_key=session_key,
            user=user,
            show=show,
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
def create_payment(reservation, amount=None, provider="stripe"):
    """Create one provider order for a hold; the webhook is the source of truth."""
    if not reservation.is_active_hold:
        raise ValueError("This hold has expired.")
    if amount is None:
        if not reservation.show_id:
            raise ValueError("A show is required before payment.")
        amount = reservation.show.ticket_price * reservation.seats.count()
    existing = reservation.payments.filter(status=PaymentTransaction.Status.CREATED).first()
    if existing:
        return existing
    provider_order_id = f"seat_{reservation.id}_{uuid.uuid4().hex}"
    if provider == "stripe":
        from django.conf import settings
        if settings.STRIPE_SECRET_KEY:
            import stripe
            stripe.api_key = settings.STRIPE_SECRET_KEY
            intent = stripe.PaymentIntent.create(
                amount=int(amount * 100), currency="inr",
                metadata={"reservation_id": str(reservation.id)},
            )
            provider_order_id = intent.id
    return PaymentTransaction.objects.create(
        reservation=reservation,
        provider=provider,
        provider_order_id=provider_order_id,
        provider_client_secret=getattr(locals().get("intent"), "client_secret", "") if "intent" in locals() else "",
        amount=amount,
        seat_ids=list(reservation.seats.values_list("id", flat=True)),
    )


@transaction.atomic
def retry_payment(payment):
    reservation = Reservation.objects.select_for_update().get(pk=payment.reservation_id)
    if payment.status not in {PaymentTransaction.Status.FAILED, PaymentTransaction.Status.CANCELLED}:
        raise ValueError("Only failed or cancelled payments can be retried.")
    reservation.status = Reservation.Status.HOLD
    reservation.expires_at = timezone.now() + HOLD_DURATION
    reservation.save(update_fields=["status", "expires_at", "updated_at"])
    reserve_seats(reservation.session_key, payment.seat_ids, reservation, reservation.user, reservation.show)
    return create_payment(reservation, payment.amount, payment.provider)


@transaction.atomic
def cancel_booking(booking):
    booking = Booking.objects.select_for_update().get(pk=booking.pk)
    if booking.status != Booking.Status.CONFIRMED:
        raise ValueError("Only confirmed bookings can be cancelled.")
    payment = booking.payments.filter(status=PaymentTransaction.Status.PAID).first()
    if payment:
        from django.conf import settings
        if settings.STRIPE_SECRET_KEY and payment.provider_transaction_id:
            import stripe
            stripe.api_key = settings.STRIPE_SECRET_KEY
            stripe.Refund.create(payment_intent=payment.provider_transaction_id)
        payment.status = PaymentTransaction.Status.REFUNDED
        payment.save(update_fields=["status", "updated_at"])
    booking.status = Booking.Status.REFUNDED if payment else Booking.Status.CANCELLED
    booking.cancelled_at = timezone.now()
    booking.save(update_fields=["status", "cancelled_at"])
    return booking


@transaction.atomic
def record_payment_result(order_id, status, transaction_id=None, failure_reason=""):
    """Apply a verified provider result exactly once and create at most one booking."""
    payment = PaymentTransaction.objects.select_for_update().select_related("reservation__user").get(
        provider_order_id=order_id
    )
    if payment.status == PaymentTransaction.Status.PAID:
        return payment.booking
    payment.status = status
    payment.provider_transaction_id = transaction_id or payment.provider_transaction_id
    payment.failure_reason = failure_reason
    payment.save(update_fields=["status", "provider_transaction_id", "failure_reason", "updated_at"])

    reservation = Reservation.objects.select_for_update().get(pk=payment.reservation_id)
    if status != PaymentTransaction.Status.PAID:
        reservation.reservationseat_set.all().delete()
        reservation.status = Reservation.Status.CANCELLED
        reservation.expires_at = None
        reservation.save(update_fields=["status", "expires_at", "updated_at"])
        return None
    if not reservation.user_id:
        raise ValueError("A user account is required before payment confirmation.")
    booking, created = Booking.objects.get_or_create(
        reservation=reservation,
        defaults={
            "user_id": reservation.user_id,
            "total_amount": payment.amount,
        },
    )
    if created:
        BookingSeat.objects.bulk_create(
            [BookingSeat(booking=booking, seat=seat) for seat in reservation.seats.all()]
        )
    payment.booking = booking
    payment.save(update_fields=["booking", "updated_at"])
    reservation.status = Reservation.Status.CONFIRMED
    reservation.expires_at = None
    reservation.save(update_fields=["status", "expires_at", "updated_at"])
    from .tasks import email_ticket
    transaction.on_commit(lambda: email_ticket.delay(str(booking.id)))
    return booking


@transaction.atomic
def confirm_reservation(session_key, reservation_id):
    """Reject the legacy confirmation path; only verified payments confirm bookings."""
    raise ValueError("Payment verification is required before confirmation.")