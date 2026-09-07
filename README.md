# Smart Seat Reservation

A Django 5 application for live, multi-seat reservation with two-minute holds.

## Run locally

```bash
python -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python manage.py migrate
.venv/bin/python manage.py runserver
```

Open `http://127.0.0.1:8000/`.

## Behavior

- Seats are displayed as available, selected, or booked.
- A selection is held for two minutes and can be replaced before payment.
- Expired holds are deleted when availability is read or a reservation operation begins.
- Reservation and confirmation operations use `transaction.atomic()` and lock requested seats with `select_for_update()` in stable ID order.
- A database constraint prevents duplicate seat positions and duplicate seat links.

SQLite is convenient for local development. Use PostgreSQL or another database with row-lock support in production so concurrent requests receive full `select_for_update()` semantics.

## Deploy

Set these environment variables in the production service:

```text
DJANGO_DEBUG=False
DJANGO_SECRET_KEY=<at least 50 random characters>
DJANGO_ALLOWED_HOSTS=example.com,www.example.com
DJANGO_CSRF_TRUSTED_ORIGINS=https://example.com,https://www.example.com
DATABASE_URL=postgresql://user:password@host:5432/database
```

Generate a secret with `python -c "import secrets; print(secrets.token_urlsafe(64))"`, then run:

```bash
python manage.py migrate
python manage.py collectstatic --noinput 
```

Serve the application with the WSGI entry point `smartseat.wsgi:application` behind an HTTPS-capable production server or platform proxy. Gunicorn is included in the requirements:

```bash
gunicorn smartseat.wsgi:application --bind 0.0.0.0:8000 --workers 3
```

Or build and run the included container:

```bash
docker build -t smartseat .
docker run --env-file .env -p 8000:8000 smartseat
```

Run `migrate` and `collectstatic` during your deployment release step before starting the container. Do not use SQLite in production.