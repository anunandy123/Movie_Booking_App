import json

from django.http import JsonResponse
from django.shortcuts import render
from django.views.decorators.http import require_http_methods

from .models import Reservation, ReservationSeat, Seat
from .services import confirm_reservation, release_expired_holds, reserve_seats


def index(request):
    if not request.session.session_key:
        request.session.create()
    return render(request, "reservations/index.html")


def _payload(request):
    try:
        return json.loads(request.body or "{}")
    except json.JSONDecodeError:
        raise ValueError("Request body must be valid JSON.")


def _seat_payload(session_key):
    release_expired_holds()
    active_hold = ReservationSeat.objects.filter(
        reservation__session_key=session_key,
        reservation__status=Reservation.Status.HOLD,
    ).values_list("seat_id", flat=True)
    held_ids = set(active_hold)
    booked_ids = set(ReservationSeat.objects.filter(
        reservation__status=Reservation.Status.CONFIRMED,
    ).values_list("seat_id", flat=True))
    return [
        {"id": seat.id, "label": str(seat), "status": "booked" if seat.id in booked_ids else "selected" if seat.id in held_ids else "available"}
        for seat in Seat.objects.all()
    ]


def seats(request):
    if not request.session.session_key:
        request.session.create()
    return JsonResponse({"seats": _seat_payload(request.session.session_key)})


@require_http_methods(["POST"])
def create_reservation(request):
    try:
        if not request.session.session_key:
            request.session.create()
        data = _payload(request)
        reservation = reserve_seats(request.session.session_key, data.get("seat_ids", []))
        return JsonResponse({"reservation_id": str(reservation.id), "expires_at": reservation.expires_at.isoformat()})
    except (ValueError, TypeError) as error:
        return JsonResponse({"error": str(error)}, status=409)


@require_http_methods(["PATCH"])
def update_reservation(request, reservation_id):
    try:
        if not request.session.session_key:
            request.session.create()
        reservation = Reservation.objects.get(id=reservation_id)
        reservation = reserve_seats(request.session.session_key, _payload(request).get("seat_ids", []), reservation)
        return JsonResponse({"reservation_id": str(reservation.id), "expires_at": reservation.expires_at.isoformat()})
    except Reservation.DoesNotExist:
        return JsonResponse({"error": "Reservation not found."}, status=404)
    except (ValueError, TypeError) as error:
        return JsonResponse({"error": str(error)}, status=409)


@require_http_methods(["POST"])
def confirm(request, reservation_id):
    try:
        if not request.session.session_key:
            request.session.create()
        reservation = confirm_reservation(request.session.session_key, reservation_id)
        return JsonResponse({"status": reservation.Status.CONFIRMED, "reservation_id": str(reservation.id)})
    except (Reservation.DoesNotExist, ValueError) as error:
        return JsonResponse({"error": str(error)}, status=409)