import uuid

from django.db import models
from django.utils import timezone


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

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    session_key = models.CharField(max_length=40)
    status = models.CharField(max_length=12, choices=Status.choices, default=Status.HOLD)
    expires_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    seats = models.ManyToManyField(Seat, through="ReservationSeat")

    class Meta:
        ordering = ["-created_at"]

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