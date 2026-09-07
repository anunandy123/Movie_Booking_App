from django.db import migrations, models
import django.db.models.deletion
import uuid


class Migration(migrations.Migration):
    initial = True
    dependencies = []
    operations = [
        migrations.CreateModel(
            name="Seat",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("row", models.CharField(max_length=2)),
                ("number", models.PositiveSmallIntegerField()),
            ],
            options={"ordering": ["row", "number"]},
        ),
        migrations.CreateModel(
            name="Reservation",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("session_key", models.CharField(max_length=40)),
                ("status", models.CharField(choices=[("hold", "Held"), ("confirmed", "Confirmed")], default="hold", max_length=12)),
                ("expires_at", models.DateTimeField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
            options={"ordering": ["-created_at"]},
        ),
        migrations.CreateModel(
            name="ReservationSeat",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("reservation", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to="reservations.reservation")),
                ("seat", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to="reservations.seat")),
            ],
        ),
        migrations.AddField(
            model_name="reservation",
            name="seats",
            field=models.ManyToManyField(through="reservations.ReservationSeat", to="reservations.seat"),
        ),
        migrations.AddConstraint(
            model_name="seat",
            constraint=models.UniqueConstraint(fields=("row", "number"), name="unique_seat_position"),
        ),
        migrations.AddConstraint(
            model_name="reservationseat",
            constraint=models.UniqueConstraint(fields=("reservation", "seat"), name="unique_reservation_seat"),
        ),
    ]