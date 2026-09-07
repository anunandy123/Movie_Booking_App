import json
import csv
from datetime import datetime, time, timedelta
from decimal import Decimal, InvalidOperation

from django.contrib.auth.decorators import login_required, user_passes_test
from django.db.models import Count, Q, Sum
from django.db.models.functions import TruncDay, TruncMonth, TruncWeek, TruncYear
from django.http import HttpResponse, JsonResponse
from django.shortcuts import render
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods

from .models import Booking, Movie, MovieView, PaymentTransaction, Reservation, ReservationSeat, Review, ReviewReport, Seat, Show, Theater
from .services import cancel_booking, create_payment, confirm_reservation, record_payment_result, release_expired_holds, reserve_seats, retry_payment


def index(request):
    if not request.session.session_key:
        request.session.create()
    return render(request, "reservations/index.html")


def _payload(request):
    try:
        return json.loads(request.body or "{}")
    except json.JSONDecodeError:
        raise ValueError("Request body must be valid JSON.")


def _seat_payload(session_key, show_id=None):
    release_expired_holds()
    active_hold = ReservationSeat.objects.filter(
        reservation__session_key=session_key,
        reservation__status=Reservation.Status.HOLD,
    ).values_list("seat_id", flat=True)
    if show_id:
        active_hold = ReservationSeat.objects.filter(
            reservation__session_key=session_key,
            reservation__status=Reservation.Status.HOLD,
            reservation__show_id=show_id,
        ).values_list("seat_id", flat=True)
    held_ids = set(active_hold)
    booked_ids = set(ReservationSeat.objects.filter(
        reservation__status=Reservation.Status.CONFIRMED,
        **({"reservation__show_id": show_id} if show_id else {}),
    ).values_list("seat_id", flat=True))
    return [
        {"id": seat.id, "label": str(seat), "status": "booked" if seat.id in booked_ids else "selected" if seat.id in held_ids else "available"}
        for seat in Seat.objects.all()
    ]


def seats(request):
    if not request.session.session_key:
        request.session.create()
    return JsonResponse({"seats": _seat_payload(request.session.session_key, request.GET.get("show_id"))})


@require_http_methods(["POST"])
def create_reservation(request):
    try:
        if not request.session.session_key:
            request.session.create()
        data = _payload(request)
        show = Show.objects.get(id=data["show_id"]) if data.get("show_id") else None
        reservation = reserve_seats(request.session.session_key, data.get("seat_ids", []), user=request.user if request.user.is_authenticated else None, show=show)
        return JsonResponse({"reservation_id": str(reservation.id), "expires_at": reservation.expires_at.isoformat()})
    except (ValueError, TypeError, KeyError, Show.DoesNotExist) as error:
        return JsonResponse({"error": str(error)}, status=409)


@require_http_methods(["PATCH"])
def update_reservation(request, reservation_id):
    try:
        if not request.session.session_key:
            request.session.create()
        reservation = Reservation.objects.get(id=reservation_id)
        reservation = reserve_seats(request.session.session_key, _payload(request).get("seat_ids", []), reservation, show=reservation.show)
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
        payment = PaymentTransaction.objects.select_related("booking").filter(
            reservation_id=reservation_id,
            reservation__session_key=request.session.session_key,
            status=PaymentTransaction.Status.PAID,
        ).first()
        if not payment or not payment.booking_id:
            return JsonResponse({"error": "Payment verification is required before confirmation."}, status=402)
        return JsonResponse({"status": Booking.Status.CONFIRMED, "reservation_id": str(reservation_id), "booking_id": str(payment.booking_id)})
    except Reservation.DoesNotExist as error:
        return JsonResponse({"error": str(error)}, status=409)


@login_required
@require_http_methods(["POST"])
def create_payment_order(request, reservation_id):
    try:
        try:
            reservation = Reservation.objects.get(id=reservation_id, session_key=request.session.session_key, user=request.user)
        except Reservation.DoesNotExist:
            reservation = Reservation.objects.get(id=reservation_id, session_key=request.session.session_key, user__isnull=True)
            reservation.user = request.user
            reservation.save(update_fields=["user", "updated_at"])
        payment = create_payment(reservation)
        return JsonResponse({"order_id": payment.provider_order_id, "client_secret": payment.provider_client_secret, "amount": str(payment.amount), "currency": "INR"})
    except (Reservation.DoesNotExist, InvalidOperation, TypeError, ValueError) as error:
        return JsonResponse({"error": str(error)}, status=409)


@login_required
@require_http_methods(["POST"])
def retry_payment_order(request, payment_id):
    try:
        payment = PaymentTransaction.objects.get(id=payment_id, reservation__user=request.user)
        retry = retry_payment(payment)
        return JsonResponse({"order_id": retry.provider_order_id, "amount": str(retry.amount), "currency": "INR"})
    except (PaymentTransaction.DoesNotExist, ValueError) as error:
        return JsonResponse({"error": str(error)}, status=409)


@csrf_exempt
@require_http_methods(["POST"])
def payment_webhook(request):
    """Verify Stripe's signature before accepting a payment result."""
    try:
        import stripe
        event = stripe.Webhook.construct_event(
            request.body,
            request.META.get("HTTP_STRIPE_SIGNATURE", ""),
            __import__("django.conf", fromlist=["settings"]).settings.STRIPE_WEBHOOK_SECRET,
        )
    except Exception:
        return JsonResponse({"error": "Invalid webhook signature."}, status=400)
    event_type = event.get("type")
    payload = event.get("data", {}).get("object", {})
    order_id = payload.get("metadata", {}).get("order_id") or payload.get("id")
    try:
        if event_type == "payment_intent.succeeded":
            record_payment_result(order_id, PaymentTransaction.Status.PAID, payload.get("id"))
        elif event_type in {"payment_intent.payment_failed", "payment_intent.canceled"}:
            status = PaymentTransaction.Status.FAILED if "failed" in event_type else PaymentTransaction.Status.CANCELLED
            record_payment_result(order_id, status, payload.get("id"), payload.get("last_payment_error", {}).get("message", ""))
    except PaymentTransaction.DoesNotExist:
        return JsonResponse({"error": "Unknown payment order."}, status=400)
    return JsonResponse({"received": True})


@login_required
def booking_history(request):
    bookings = Booking.objects.filter(user=request.user).select_related("show__movie", "show__theater").prefetch_related("seats__seat", "payments")
    return JsonResponse({"bookings": [{
        "id": str(booking.id), "status": booking.status, "amount": str(booking.total_amount),
        "created_at": booking.created_at.isoformat(), "movie": booking.show.movie.title if booking.show_id else None,
        "theater": booking.show.theater.name if booking.show_id else None,
        "seats": [str(item.seat) for item in booking.seats.all()],
        "payment_reference": next((payment.provider_transaction_id for payment in booking.payments.all() if payment.provider_transaction_id), None),
        "payments": [{"status": payment.status, "provider": payment.provider, "transaction_id": payment.provider_transaction_id, "amount": str(payment.amount)} for payment in booking.payments.all()],
    } for booking in bookings]})


@login_required
def profile(request):
    bookings = Booking.objects.filter(user=request.user).select_related("show__movie", "show__theater").prefetch_related("seats__seat", "payments")
    return render(request, "reservations/profile.html", {"bookings": bookings})


@login_required
def download_ticket(request, booking_id):
    from .tasks import build_ticket
    try:
        booking = Booking.objects.select_related("user", "show__movie", "show__theater").get(id=booking_id, user=request.user)
    except Booking.DoesNotExist:
        return JsonResponse({"error": "Booking not found."}, status=404)
    response = HttpResponse(build_ticket(booking), content_type="application/pdf")
    response["Content-Disposition"] = f'attachment; filename="ticket-{booking.id}.pdf"'
    return response


@login_required
@require_http_methods(["POST"])
def cancel_booking_view(request, booking_id):
    try:
        booking = Booking.objects.get(id=booking_id, user=request.user)
        booking = cancel_booking(booking)
        return JsonResponse({"status": booking.status, "booking_id": str(booking.id)})
    except (Booking.DoesNotExist, ValueError) as error:
        return JsonResponse({"error": str(error)}, status=409)


def movie_discovery(request):
    movies = Movie.objects.all()
    query = request.GET.get("q")
    if query:
        movies = movies.filter(title__icontains=query)
    for field in ("genre", "language"):
        value = request.GET.get(field)
        if value:
            movies = movies.filter(**{f"{field}__iexact": value})
    if request.GET.get("city"):
        movies = movies.filter(shows__theater__city__iexact=request.GET["city"])
    if request.GET.get("theater"):
        movies = movies.filter(shows__theater_id=request.GET["theater"])
    if request.GET.get("release_from"):
        movies = movies.filter(release_date__gte=request.GET["release_from"])
    if request.GET.get("release_to"):
        movies = movies.filter(release_date__lte=request.GET["release_to"])
    if request.GET.get("show_after"):
        movies = movies.filter(shows__starts_at__gte=request.GET["show_after"])
    if request.GET.get("show_before"):
        movies = movies.filter(shows__starts_at__lte=request.GET["show_before"])
    if request.GET.get("min_rating"):
        movies = movies.filter(rating__gte=request.GET["min_rating"])
    sort = request.GET.get("sort", "popularity")
    movies = movies.order_by({"newest": "-release_date", "rating": "-rating", "price": "shows__ticket_price"}.get(sort, "-popularity"))
    movies = movies.distinct()
    count = movies.count()
    page = max(int(request.GET.get("page", 1)), 1)
    page_size = min(max(int(request.GET.get("page_size", 20)), 1), 100)
    start = (page - 1) * page_size
    recommendations = Movie.objects.none()
    if request.user.is_authenticated:
        booked_genres = Movie.objects.filter(shows__bookings__user=request.user).values_list("genre", flat=True).distinct()
        viewed_genres = Movie.objects.filter(views__user=request.user).values_list("genre", flat=True).distinct()
        recommendations = Movie.objects.filter(genre__in=booked_genres.union(viewed_genres)).exclude(views__user=request.user).order_by("-popularity").values("id", "title", "genre", "rating")[:6]
    return JsonResponse({"count": count, "page": page, "page_size": page_size, "movies": list(movies.values("id", "title", "genre", "language", "release_date", "rating", "popularity")[start:start + page_size]), "recommended": list(recommendations)})


def movie_detail(request, movie_id):
    try:
        movie = Movie.objects.prefetch_related("genres", "posters", "cast_members__cast_member", "reviews__user").get(id=movie_id)
    except Movie.DoesNotExist:
        return JsonResponse({"error": "Movie not found."}, status=404)
    if request.user.is_authenticated:
        MovieView.objects.create(movie=movie, user=request.user)
    similar = Movie.objects.filter(genres__in=movie.genres.all(), primary_language=movie.primary_language).exclude(id=movie.id).distinct().order_by("-popularity")[:6]
    trending = Movie.objects.exclude(id=movie.id).order_by("-popularity")[:6]
    recent = Movie.objects.exclude(id=movie.id).order_by("-release_date")[:6]
    return JsonResponse({
        "movie": {"id": movie.id, "title": movie.title, "genre": movie.genre, "genres": list(movie.genres.values_list("name", flat=True)), "language": movie.language, "release_date": movie.release_date, "rating": movie.average_rating, "age_certification": movie.age_certification, "duration_minutes": movie.duration_minutes, "description": movie.description, "trailer_embed_url": movie.trailer_embed_url, "posters": list(movie.posters.values("image_url", "alt_text", "is_primary")), "cast": list(movie.cast_members.values("cast_member__name", "character_name"))},
        "reviews": list(movie.reviews.filter(is_published=True).values("id", "user__username", "rating", "body", "is_verified_viewer", "created_at")),
        "similar": list(similar.values("id", "title", "rating", "release_date")),
        "trending": list(trending.values("id", "title", "rating")),
        "recent": list(recent.values("id", "title", "release_date")),
    })


def movie_page(request, movie_id):
    try:
        movie = Movie.objects.prefetch_related("genres", "posters", "cast_members__cast_member", "reviews__user").get(id=movie_id)
    except Movie.DoesNotExist:
        return HttpResponse("Movie not found.", status=404)
    if request.user.is_authenticated:
        MovieView.objects.create(movie=movie, user=request.user)
    similar = Movie.objects.filter(genres__in=movie.genres.all(), primary_language=movie.primary_language).exclude(id=movie.id).distinct().order_by("-popularity")[:6]
    return render(request, "reservations/movie_detail.html", {"movie": movie, "similar": similar, "reviews": movie.reviews.filter(is_published=True)})


@login_required
@require_http_methods(["POST", "PATCH"])
def movie_review(request, movie_id):
    try:
        movie = Movie.objects.get(id=movie_id)
        watched = Booking.objects.filter(user=request.user, show__movie=movie, status=Booking.Status.CONFIRMED, show__starts_at__lte=timezone.now()).exists()
        if not watched:
            return JsonResponse({"error": "You can review a movie after attending a confirmed show."}, status=403)
        data = _payload(request)
        review, _ = Review.objects.get_or_create(movie=movie, user=request.user, defaults={"rating": data.get("rating"), "body": data.get("body", "")})
        if request.method == "PATCH":
            review.rating = data.get("rating", review.rating)
            review.body = data.get("body", review.body)
        review.is_verified_viewer = True
        review.full_clean()
        review.save()
        return JsonResponse({"id": review.id, "rating": review.rating, "body": review.body, "verified": review.is_verified_viewer})
    except (Movie.DoesNotExist, ValueError, TypeError) as error:
        return JsonResponse({"error": str(error)}, status=409)


@login_required
@require_http_methods(["POST"])
def report_review(request, review_id):
    try:
        review = Review.objects.get(id=review_id)
        report, _ = ReviewReport.objects.get_or_create(review=review, reporter=request.user, defaults={"reason": _payload(request).get("reason", "Inappropriate content")})
        return JsonResponse({"reported": True, "report_id": report.id})
    except Review.DoesNotExist:
        return JsonResponse({"error": "Review not found."}, status=404)


def _is_staff(request):
    return request.user.is_authenticated and request.user.is_staff


@user_passes_test(_is_staff)
def admin_dashboard(request):
    start = request.GET.get("start")
    end = request.GET.get("end")
    bookings = Booking.objects.filter(status=Booking.Status.CONFIRMED)
    if start:
        bookings = bookings.filter(created_at__date__gte=start)
    if end:
        bookings = bookings.filter(created_at__date__lte=end)
    revenue = bookings.aggregate(total=Sum("total_amount"))["total"] or Decimal("0")
    all_bookings = Booking.objects.all()
    if start:
        all_bookings = all_bookings.filter(created_at__date__gte=start)
    if end:
        all_bookings = all_bookings.filter(created_at__date__lte=end)
    theater_capacity = {item["id"]: item["capacity"] for item in Theater.objects.values("id", "capacity")}
    occupied = bookings.values("show__theater_id").annotate(seats=Count("reservation__seats"))
    occupancy = [{"theater_id": item["show__theater_id"], "percentage": round((item["seats"] / theater_capacity.get(item["show__theater_id"], 1)) * 100, 2)} for item in occupied]
    dashboard = {
        "revenue": str(revenue), "bookings": bookings.count(),
        "revenue_periods": {
            "daily": list(bookings.annotate(period=TruncDay("created_at")).values("period").annotate(revenue=Sum("total_amount")).order_by("period")),
            "weekly": list(bookings.annotate(period=TruncWeek("created_at")).values("period").annotate(revenue=Sum("total_amount")).order_by("period")),
            "monthly": list(bookings.annotate(period=TruncMonth("created_at")).values("period").annotate(revenue=Sum("total_amount")).order_by("period")),
            "yearly": list(bookings.annotate(period=TruncYear("created_at")).values("period").annotate(revenue=Sum("total_amount")).order_by("period")),
        },
        "booking_trends": list(bookings.values("created_at__date").annotate(count=Count("id")).order_by("created_at__date")),
        "movies": list(bookings.values("show__movie__title").annotate(count=Count("id")).order_by("-count")[:10]),
        "theaters": list(bookings.values("show__theater__name").annotate(count=Count("id"), revenue=Sum("total_amount")).order_by("-revenue")[:10]),
        "payment_status": list(PaymentTransaction.objects.values("status").annotate(count=Count("id"), amount=Sum("amount"))),
        "occupancy": occupancy,
        "peak_booking_hours": list(bookings.values("created_at__hour").annotate(count=Count("id")).order_by("-count")[:24]),
        "cancellations": all_bookings.filter(status=Booking.Status.CANCELLED).count(),
        "refunds": PaymentTransaction.objects.filter(status=PaymentTransaction.Status.REFUNDED, **({"created_at__date__gte": start} if start else {}), **({"created_at__date__lte": end} if end else {})).aggregate(count=Count("id"), amount=Sum("amount")),
        "user_growth": list(__import__("django.contrib.auth", fromlist=["get_user_model"]).get_user_model().objects.values("date_joined__date").annotate(count=Count("id")).order_by("date_joined__date")),
    }
    if request.GET.get("format") == "json":
        return JsonResponse(dashboard)
    return render(request, "reservations/admin_dashboard.html", {"dashboard": dashboard})


@user_passes_test(_is_staff)
def admin_report_csv(request):
    response = HttpResponse(content_type="text/csv")
    response["Content-Disposition"] = 'attachment; filename="booking-report.csv"'
    writer = csv.writer(response)
    writer.writerow(["booking_id", "status", "amount", "created_at", "user_id"])
    bookings = Booking.objects.select_related("user").order_by("created_at")
    if request.GET.get("start"):
        bookings = bookings.filter(created_at__date__gte=request.GET["start"])
    if request.GET.get("end"):
        bookings = bookings.filter(created_at__date__lte=request.GET["end"])
    for booking in bookings.iterator():
        writer.writerow([booking.id, booking.status, booking.total_amount, booking.created_at.isoformat(), booking.user_id])
    return response