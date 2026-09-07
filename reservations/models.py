import uuid
from urllib.parse import parse_qs, urlparse

from django.conf import settings
from django.db import models
from django.utils import timezone
from django.core.exceptions import ValidationError
from django.core.validators import MaxValueValidator, MinValueValidator, URLValidator


class Seat(models.Model):
    row = models.CharField(max_length=2)
    number = models.PositiveSmallIntegerField()

    class Meta:
        ordering = ["row", "number"]
        constraints = [
            models.UniqueConstraint(fields=["row", "number"], name="unique_seat_position")
        ]

    def __str__(self):
        return f"{self.row}{self.number}"


class Reservation(models.Model):
    class Status(models.TextChoices):
        HOLD = "hold", "Held"
        CONFIRMED = "confirmed", "Confirmed"
        CANCELLED = "cancelled", "Cancelled"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL)
    show = models.ForeignKey("Show", null=True, blank=True, on_delete=models.PROTECT, related_name="reservations")
    session_key = models.CharField(max_length=40)
    status = models.CharField(max_length=12, choices=Status.choices, default=Status.HOLD)
    expires_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    seats = models.ManyToManyField(Seat, through="ReservationSeat")

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["status", "expires_at"]),
            models.Index(fields=["user", "created_at"]),
        ]

    @property
    def is_active_hold(self):
        return self.status == self.Status.HOLD and self.expires_at and self.expires_at > timezone.now()


class ReservationSeat(models.Model):
    reservation = models.ForeignKey(Reservation, on_delete=models.CASCADE)
    seat = models.ForeignKey(Seat, on_delete=models.CASCADE)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["reservation", "seat"], name="unique_reservation_seat")
        ]


class Movie(models.Model):
    title = models.CharField(max_length=200)
    genre = models.CharField(max_length=80, blank=True)
    language = models.CharField(max_length=50, blank=True)
    release_date = models.DateField(null=True, blank=True)
    rating = models.DecimalField(max_digits=3, decimal_places=1, default=0)
    popularity = models.PositiveIntegerField(default=0)
    genres = models.ManyToManyField("Genre", blank=True, related_name="movies")
    primary_language = models.ForeignKey("Language", null=True, blank=True, on_delete=models.SET_NULL, related_name="movies")
    trailer_url = models.URLField(blank=True, validators=[URLValidator()])
    age_certification = models.CharField(max_length=12, blank=True)
    duration_minutes = models.PositiveSmallIntegerField(null=True, blank=True)
    description = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-popularity", "-release_date", "title"]
        indexes = [
            models.Index(fields=["title"]),
            models.Index(fields=["genre", "language"]),
            models.Index(fields=["release_date", "rating"]),
        ]

    def __str__(self):
        return self.title

    def clean(self):
        super().clean()
        if self.trailer_url:
            parsed = urlparse(self.trailer_url)
            allowed = {"youtube.com", "www.youtube.com", "youtu.be", "youtube-nocookie.com", "www.youtube-nocookie.com"}
            if parsed.netloc.lower() not in allowed or not self.youtube_video_id:
                raise ValidationError({"trailer_url": "Trailer must be a valid YouTube video URL."})

    @property
    def youtube_video_id(self):
        parsed = urlparse(self.trailer_url) if self.trailer_url else None
        if not parsed:
            return ""
        if parsed.netloc.lower().endswith("youtu.be"):
            return parsed.path.strip("/").split("/")[0]
        return parse_qs(parsed.query).get("v", [""])[0]

    @property
    def trailer_embed_url(self):
        return f"https://www.youtube-nocookie.com/embed/{self.youtube_video_id}" if self.youtube_video_id else ""

    @property
    def average_rating(self):
        return self.reviews.filter(is_published=True).aggregate(value=models.Avg("rating"))["value"] or 0


class Genre(models.Model):
    name = models.CharField(max_length=80, unique=True)

    def __str__(self):
        return self.name


class Language(models.Model):
    name = models.CharField(max_length=50, unique=True)

    def __str__(self):
        return self.name


class CastMember(models.Model):
    name = models.CharField(max_length=160)
    biography = models.TextField(blank=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name


class MovieCast(models.Model):
    movie = models.ForeignKey(Movie, on_delete=models.CASCADE, related_name="cast_members")
    cast_member = models.ForeignKey(CastMember, on_delete=models.CASCADE, related_name="filmography")
    character_name = models.CharField(max_length=160, blank=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["movie", "cast_member"], name="unique_movie_cast")]


class MovieImage(models.Model):
    movie = models.ForeignKey(Movie, on_delete=models.CASCADE, related_name="posters")
    image_url = models.URLField(validators=[URLValidator()])
    alt_text = models.CharField(max_length=200, blank=True)
    is_primary = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)


class Review(models.Model):
    movie = models.ForeignKey(Movie, on_delete=models.CASCADE, related_name="reviews")
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="movie_reviews")
    rating = models.PositiveSmallIntegerField(validators=[MinValueValidator(1), MaxValueValidator(5)])
    body = models.TextField(max_length=4000)
    is_verified_viewer = models.BooleanField(default=False, editable=False)
    is_published = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        constraints = [models.UniqueConstraint(fields=["movie", "user"], name="unique_user_movie_review")]
        indexes = [models.Index(fields=["movie", "is_published", "created_at"])]


class ReviewReport(models.Model):
    review = models.ForeignKey(Review, on_delete=models.CASCADE, related_name="reports")
    reporter = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    reason = models.CharField(max_length=500)
    created_at = models.DateTimeField(auto_now_add=True)
    resolved_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["review", "reporter"], name="unique_review_reporter")]


class MovieView(models.Model):
    movie = models.ForeignKey(Movie, on_delete=models.CASCADE, related_name="views")
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="movie_views")
    viewed_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        indexes = [models.Index(fields=["user", "viewed_at"]), models.Index(fields=["movie", "viewed_at"])]


class Theater(models.Model):
    name = models.CharField(max_length=160)
    city = models.CharField(max_length=100, db_index=True)
    capacity = models.PositiveIntegerField(default=48)

    def __str__(self):
        return f"{self.name}, {self.city}"


class Show(models.Model):
    movie = models.ForeignKey(Movie, on_delete=models.CASCADE, related_name="shows")
    theater = models.ForeignKey(Theater, on_delete=models.CASCADE, related_name="shows")
    starts_at = models.DateTimeField(db_index=True)
    ticket_price = models.DecimalField(max_digits=8, decimal_places=2)
    screen = models.CharField(max_length=80, default="Screen 1")

    class Meta:
        ordering = ["starts_at"]
        indexes = [
            models.Index(fields=["movie", "starts_at"]),
            models.Index(fields=["theater", "starts_at"]),
            models.Index(fields=["ticket_price"]),
        ]


class Booking(models.Model):
    class Status(models.TextChoices):
        CONFIRMED = "confirmed", "Confirmed"
        CANCELLED = "cancelled", "Cancelled"
        REFUNDED = "refunded", "Refunded"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="bookings")
    show = models.ForeignKey(Show, on_delete=models.PROTECT, related_name="bookings", null=True, blank=True)
    reservation = models.OneToOneField(Reservation, on_delete=models.PROTECT, related_name="booking")
    status = models.CharField(max_length=12, choices=Status.choices, default=Status.CONFIRMED)
    total_amount = models.DecimalField(max_digits=10, decimal_places=2)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    cancelled_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["status", "created_at"]),
            models.Index(fields=["show", "status"]),
            models.Index(fields=["user", "created_at"]),
        ]


class BookingSeat(models.Model):
    booking = models.ForeignKey(Booking, on_delete=models.CASCADE, related_name="seats")
    seat = models.ForeignKey(Seat, on_delete=models.PROTECT)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["booking", "seat"], name="unique_booking_seat")
        ]


class PaymentTransaction(models.Model):
    class Status(models.TextChoices):
        CREATED = "created", "Created"
        PAID = "paid", "Paid"
        FAILED = "failed", "Failed"
        CANCELLED = "cancelled", "Cancelled"
        REFUNDED = "refunded", "Refunded"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    reservation = models.ForeignKey(Reservation, on_delete=models.PROTECT, related_name="payments")
    booking = models.ForeignKey(Booking, null=True, blank=True, on_delete=models.PROTECT, related_name="payments")
    provider = models.CharField(max_length=20, default="stripe")
    provider_order_id = models.CharField(max_length=120, unique=True)
    provider_client_secret = models.CharField(max_length=255, blank=True)
    provider_transaction_id = models.CharField(max_length=120, unique=True, null=True, blank=True)
    status = models.CharField(max_length=12, choices=Status.choices, default=Status.CREATED, db_index=True)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    seat_ids = models.JSONField(default=list)
    failure_reason = models.CharField(max_length=255, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        indexes = [models.Index(fields=["status", "created_at"]), models.Index(fields=["reservation", "status"])]