"""
Thin wrapper around the Twilio client, email-to-SMS gateway, and direct
email delivery so the rest of the app never has to touch the SDK directly.
Requires TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN and TWILIO_FROM_NUMBER to
be set (see .env.example), or SMTP settings for email / email-to-SMS.
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


def send_email(smtp_server, smtp_port, sender_email, sender_password, to_email, subject, html_body):
    """
    Sends an HTML email. Returns True on success, False on failure.
    Never raises - failures are logged.
    """
    if not smtp_server or not sender_email or not sender_password:
        logger.warning("SMTP is not configured - skipping email send.")
        return False

    msg = MIMEMultipart("alternative")
    msg["From"] = f"Aurora Banff <{sender_email}>"
    msg["To"] = to_email
    msg["Subject"] = subject

    msg.attach(MIMEText(html_body, "html"))

    try:
        server = smtplib.SMTP(smtp_server, smtp_port)
        server.starttls()
        server.login(sender_email, sender_password)
        server.sendmail(sender_email, to_email, msg.as_string())
        server.quit()
        logger.info("Email sent successfully to %s", to_email)
        return True
    except Exception as exc:
        logger.warning("Failed to send email to %s: %s", to_email, exc)
        return False


def send_confirmation_email(smtp_server, smtp_port, sender_email, sender_password, to_email, unsubscribe_url):
    """
    Sends a professional confirmation email to a new subscriber.
    """
    subject = "Welcome to Aurora Tracker Banff"

    html_body = f"""\
<!DOCTYPE html>
<html lang="en">
<head><meta charset="UTF-8"></head>
<body style="margin:0;padding:0;background-color:#0a1120;font-family:'Segoe UI',Arial,Helvetica,sans-serif;">
  <table role="presentation" width="100%" cellspacing="0" cellpadding="0" style="background-color:#0a1120;">
    <tr><td align="center" style="padding:40px 20px;">
      <table role="presentation" width="560" cellspacing="0" cellpadding="0" style="background-color:#121b2e;border:1px solid rgba(232,237,245,0.09);border-radius:14px;overflow:hidden;">

        <!-- Header -->
        <tr><td style="background:linear-gradient(135deg,#45f0b3,#9b7bff);padding:32px 40px;">
          <table role="presentation" width="100%" cellspacing="0" cellpadding="0">
            <tr>
              <td>
                <span style="display:inline-block;width:10px;height:10px;border-radius:50%;background:#0a1120;margin-right:8px;vertical-align:middle;"></span>
                <span style="font-size:16px;font-weight:700;color:#0a1120;vertical-align:middle;">Aurora Banff</span>
              </td>
            </tr>
          </table>
        </td></tr>

        <!-- Body -->
        <tr><td style="padding:40px;">
          <h1 style="margin:0 0 8px;font-size:24px;font-weight:700;color:#e8edf5;">Thank You for Subscribing</h1>
          <p style="margin:0 0 24px;font-size:15px;color:#8492ac;line-height:1.6;">
            Welcome to Aurora Tracker Banff. You are now signed up to receive real-time alerts when
            geomagnetic activity and sky conditions align for aurora viewing near Banff National Park.
          </p>

          <table role="presentation" width="100%" cellspacing="0" cellpadding="0" style="background-color:#17233a;border-radius:8px;margin-bottom:24px;">
            <tr><td style="padding:20px 24px;">
              <p style="margin:0 0 12px;font-size:12px;font-weight:600;text-transform:uppercase;letter-spacing:0.08em;color:#566178;">What to expect</p>
              <table role="presentation" width="100%" cellspacing="0" cellpadding="0">
                <tr>
                  <td style="padding:6px 0;font-size:14px;color:#8492ac;" valign="top" width="24">&#8226;</td>
                  <td style="padding:6px 0;font-size:14px;color:#8492ac;">Alerts when the Kp index reaches your chosen threshold and skies are clear enough</td>
                </tr>
                <tr>
                  <td style="padding:6px 0;font-size:14px;color:#8492ac;" valign="top" width="24">&#8226;</td>
                  <td style="padding:6px 0;font-size:14px;color:#8492ac;">Notifications when cloud cover changes significantly over the Banff area</td>
                </tr>
                <tr>
                  <td style="padding:6px 0;font-size:14px;color:#8492ac;" valign="top" width="24">&#8226;</td>
                  <td style="padding:6px 0;font-size:14px;color:#8492ac;">Cooldown periods between messages so you never feel spammed</td>
                </tr>
              </table>
            </td></tr>
          </table>

          <p style="margin:0 0 24px;font-size:14px;color:#8492ac;line-height:1.6;">
            Aurora data is sourced from the NOAA Space Weather Prediction Center and weather conditions from
            Open-Meteo. We monitor conditions every few minutes so you can be among the first to know when
            the northern lights are likely.
          </p>

          <p style="margin:0;font-size:14px;color:#8492ac;">Clear skies,</p>
          <p style="margin:4px 0 0;font-size:14px;font-weight:600;color:#e8edf5;">The Aurora Banff Team</p>
        </td></tr>

        <!-- Footer -->
        <tr><td style="padding:24px 40px;border-top:1px solid rgba(232,237,245,0.09);">
          <p style="margin:0 0 8px;font-size:12px;color:#566178;">
            You received this email because you subscribed to Aurora Tracker Banff alerts.
          </p>
          <p style="margin:0;font-size:12px;">
            <a href="{unsubscribe_url}" style="color:#45f0b3;text-decoration:none;">Unsubscribe</a>
            <span style="color:#566178;"> &middot; Aurora Banff &middot; Independent aurora viewing tracker</span>
          </p>
        </td></tr>

      </table>
    </td></tr>
  </table>
</body>
</html>"""

    return send_email(smtp_server, smtp_port, sender_email, sender_password, to_email, subject, html_body)


def send_alert_email(smtp_server, smtp_port, sender_email, sender_password, to_email, subject, body_text, unsubscribe_url):
    """
    Sends an aurora or cloud alert email.
    """
    html_body = f"""\
<!DOCTYPE html>
<html lang="en">
<head><meta charset="UTF-8"></head>
<body style="margin:0;padding:0;background-color:#0a1120;font-family:'Segoe UI',Arial,Helvetica,sans-serif;">
  <table role="presentation" width="100%" cellspacing="0" cellpadding="0" style="background-color:#0a1120;">
    <tr><td align="center" style="padding:40px 20px;">
      <table role="presentation" width="560" cellspacing="0" cellpadding="0" style="background-color:#121b2e;border:1px solid rgba(232,237,245,0.09);border-radius:14px;overflow:hidden;">

        <tr><td style="background:linear-gradient(135deg,#45f0b3,#9b7bff);padding:20px 40px;">
          <span style="display:inline-block;width:10px;height:10px;border-radius:50%;background:#0a1120;margin-right:8px;vertical-align:middle;"></span>
          <span style="font-size:16px;font-weight:700;color:#0a1120;vertical-align:middle;">Aurora Banff Alert</span>
        </td></tr>

        <tr><td style="padding:32px 40px;">
          <p style="margin:0 0 24px;font-size:15px;color:#e8edf5;line-height:1.7;">{body_text}</p>
          <p style="margin:0;font-size:13px;color:#566178;">Data: NOAA SWPC &middot; Open-Meteo</p>
        </td></tr>

        <tr><td style="padding:20px 40px;border-top:1px solid rgba(232,237,245,0.09);">
          <p style="margin:0;font-size:12px;">
            <a href="{unsubscribe_url}" style="color:#45f0b3;text-decoration:none;">Unsubscribe</a>
            <span style="color:#566178;"> &middot; Aurora Banff</span>
          </p>
        </td></tr>

      </table>
    </td></tr>
  </table>
</body>
</html>"""

    return send_email(smtp_server, smtp_port, sender_email, sender_password, to_email, subject, html_body)
