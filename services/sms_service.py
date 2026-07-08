"""
Thin wrapper around the Twilio client and email-to-SMS gateway so the rest of the app never has to
touch the SDK directly. Requires TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN and
TWILIO_FROM_NUMBER to be set (see .env.example), or SMTP settings for email-to-SMS.
"""

import logging
import smtplib

from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from twilio.base.exceptions import TwilioRestException
from twilio.rest import Client

logger = logging.getLogger(__name__)


def send_sms(account_sid, auth_token, from_number, to_number, body):
    """
    Sends a single SMS. Returns True on success, False on failure.
    Never raises - failures are logged so a bad number can't crash the
    background scheduler.
    """
    if not account_sid or not auth_token or not from_number:
        logger.warning("Twilio is not configured - skipping SMS send.")
        return False

    try:
        client = Client(account_sid, auth_token)
        client.messages.create(to=to_number, from_=from_number, body=body)
        return True
    except TwilioRestException as exc:
        logger.warning("Twilio failed to send SMS to %s: %s", to_number, exc)
        return False


def send_sms_via_email(
    smtp_server, smtp_port, sender_email, sender_password, to_number, carrier_domain, body
):
    """
    Sends SMS via email-to-SMS gateway. Returns True on success, False on failure.
    Never raises - failures are logged so a bad number can't crash the
    background scheduler.
    """
    if not smtp_server or not sender_email or not sender_password:
        logger.warning("Email-to-SMS is not configured - skipping SMS send.")
        return False

    to_address = f"{to_number}@{carrier_domain}"

    msg = MIMEMultipart()
    msg["From"] = sender_email
    msg["To"] = to_address
    msg["Subject"] = ""  # Leave subject blank for standard text layout

    msg.attach(MIMEText(body, "plain"))

    try:
        server = smtplib.SMTP(smtp_server, smtp_port)
        server.starttls()
        server.login(sender_email, sender_password)
        server.sendmail(sender_email, to_address, msg.as_string())
        server.quit()
        logger.info("Email-to-SMS sent successfully to %s", to_address)
        return True
    except Exception as exc:
        logger.warning("Email-to-SMS failed to send to %s: %s", to_address, exc)
        return False
