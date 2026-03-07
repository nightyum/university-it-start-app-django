from django.core.mail import send_mail
from django.conf import settings

def send_verification_email(email, subject, message):
    send_mail(
        subject,
        message,
        settings.DEFAULT_FROM_EMAIL,
        [email],
        fail_silently=False,
    )