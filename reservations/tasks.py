from io import BytesIO

import qrcode
from celery import shared_task
from django.core.files.base import ContentFile
from django.core.mail import EmailMessage
from django.conf import settings
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas

from .models import Booking


def build_ticket(booking):
    buffer = BytesIO()
    pdf = canvas.Canvas(buffer, pagesize=letter)
    pdf.setTitle(f"Ticket {booking.id}")
    pdf.drawString(72, 740, "Smart Seat Ticket")
    pdf.drawString(72, 710, f"Booking: {booking.id}")
    pdf.drawString(72, 690, f"Payment: {booking.payments.filter(provider_transaction_id__isnull=False).values_list('provider_transaction_id', flat=True).first() or 'Pending'}")
    if booking.show_id:
        pdf.drawString(72, 670, f"Movie: {booking.show.movie.title}")
        pdf.drawString(72, 650, f"Theater: {booking.show.theater.name}")
        pdf.drawString(72, 630, f"Screen: {booking.show.screen}")
        pdf.drawString(72, 610, f"Show: {booking.show.starts_at.isoformat()}")
    pdf.drawString(72, 590, f"Seats: {', '.join(str(item.seat) for item in booking.seats.select_related('seat'))}")
    qr = qrcode.make(str(booking.id))
    qr_buffer = BytesIO()
    qr.save(qr_buffer, format="PNG")
    from reportlab.lib.utils import ImageReader
    pdf.drawImage(ImageReader(BytesIO(qr_buffer.getvalue())), 72, 450, width=120, height=120)
    pdf.save()
    return buffer.getvalue()


@shared_task(bind=True, autoretry_for=(Exception,), retry_backoff=True, max_retries=5)
def email_ticket(self, booking_id):
    booking = Booking.objects.select_related("user", "show__movie", "show__theater").get(id=booking_id)
    attachment = build_ticket(booking)
    message = EmailMessage(
        subject=f"Your Smart Seat ticket {booking.id}",
        body="Your payment is confirmed. Your ticket is attached.",
        to=[booking.user.email],
    )
    message.attach(f"ticket-{booking.id}.pdf", attachment, "application/pdf")
    message.send(fail_silently=False)
