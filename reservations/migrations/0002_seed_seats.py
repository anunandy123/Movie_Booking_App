from django.db import migrations


def seed_seats(apps, schema_editor):
    Seat = apps.get_model("reservations", "Seat")
    Seat.objects.bulk_create(
        [Seat(row=row, number=number) for row in "ABCDEF" for number in range(1, 9)]
    )


class Migration(migrations.Migration):
    dependencies = [("reservations", "0001_initial")]
    operations = [migrations.RunPython(seed_seats, migrations.RunPython.noop)]