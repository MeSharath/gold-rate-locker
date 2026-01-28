"""Email notification via Gmail SMTP."""

import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import date
from typing import Optional
import logging

from app.config import settings

logger = logging.getLogger(__name__)


class NotificationError(Exception):
    """Custom exception for notification operations."""
    pass


def is_email_configured() -> bool:
    """Check if email configuration is available."""
    return bool(
        settings.SMTP_USER and
        settings.SMTP_PASSWORD and
        settings.EMAIL_TO
    )


def send_email(subject: str, body: str, html_body: Optional[str] = None) -> bool:
    """Send an email notification.

    Args:
        subject: Email subject
        body: Plain text body
        html_body: Optional HTML body

    Returns:
        True if sent successfully, False otherwise

    Raises:
        NotificationError: If email fails and we want to propagate the error
    """
    if not is_email_configured():
        logger.info("Email not configured, skipping notification")
        return False

    try:
        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"] = settings.SMTP_USER
        msg["To"] = settings.EMAIL_TO

        # Attach plain text
        msg.attach(MIMEText(body, "plain"))

        # Attach HTML if provided
        if html_body:
            msg.attach(MIMEText(html_body, "html"))

        with smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT) as server:
            server.starttls()
            server.login(settings.SMTP_USER, settings.SMTP_PASSWORD)
            server.send_message(msg)

        logger.info(f"Email sent: {subject}")
        return True

    except smtplib.SMTPAuthenticationError as e:
        logger.error(f"SMTP authentication failed: {e}")
        return False
    except smtplib.SMTPException as e:
        logger.error(f"SMTP error: {e}")
        return False
    except Exception as e:
        logger.error(f"Email failed: {e}")
        return False


def send_daily_summary(
    rate_date: date,
    ibja_rate: float,
    rate_with_gst: float,
    reference_price: Optional[float] = None,
    moving_average: Optional[float] = None,
    month_low: Optional[float] = None
) -> bool:
    """Send daily rate summary email.

    Args:
        rate_date: Date of the rate
        ibja_rate: Raw IBJA rate
        rate_with_gst: Rate with GST applied
        reference_price: Last month reference price
        moving_average: 20-day moving average
        month_low: Current month low

    Returns:
        True if sent successfully
    """
    subject = f"Gold Rate Update - {rate_date.strftime('%B %d, %Y')}"

    # Calculate differentials if we have reference data
    diff_text = ""
    if reference_price:
        diff = ((rate_with_gst - reference_price) / reference_price) * 100
        diff_text = f"vs Reference: {diff:+.1f}%\n"
    if moving_average:
        diff = ((rate_with_gst - moving_average) / moving_average) * 100
        diff_text += f"vs 20-Day MA: {diff:+.1f}%\n"
    if month_low:
        diff = ((rate_with_gst - month_low) / month_low) * 100
        diff_text += f"vs Month Low: {diff:+.1f}%\n"

    body = f"""
Gold Rate Update for {rate_date.strftime('%B %d, %Y')}
{'='*50}

IBJA 916 Rate: Rs. {ibja_rate:,.2f}/gram
With GST (3%): Rs. {rate_with_gst:,.2f}/gram

Reference Points:
{'-'*30}
Last Month Reference: Rs. {reference_price:,.2f}/gram if reference_price else 'N/A'
20-Day Moving Avg: Rs. {moving_average:,.2f}/gram if moving_average else 'N/A'
Month Low So Far: Rs. {month_low:,.2f}/gram if month_low else 'N/A'

Comparison:
{'-'*30}
{diff_text if diff_text else 'Insufficient data for comparison'}

Check your jeweller's price at: {settings.APP_URL}
"""

    html_body = f"""
<!DOCTYPE html>
<html>
<head>
    <style>
        body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; }}
        .container {{ max-width: 600px; margin: 0 auto; padding: 20px; }}
        .header {{ background: linear-gradient(135deg, #D4AF37, #FFD700); padding: 20px; border-radius: 8px; text-align: center; }}
        .header h1 {{ color: #fff; margin: 0; text-shadow: 1px 1px 2px rgba(0,0,0,0.3); }}
        .rate-box {{ background: #f8f9fa; padding: 20px; border-radius: 8px; margin: 20px 0; text-align: center; }}
        .rate {{ font-size: 2em; color: #D4AF37; font-weight: bold; }}
        .stats {{ display: grid; gap: 10px; margin: 20px 0; }}
        .stat {{ background: #fff; padding: 15px; border-radius: 8px; border: 1px solid #e0e0e0; }}
        .stat-label {{ color: #666; font-size: 0.9em; }}
        .stat-value {{ font-size: 1.2em; font-weight: bold; }}
        .positive {{ color: #28a745; }}
        .negative {{ color: #dc3545; }}
        .cta {{ text-align: center; margin-top: 20px; }}
        .cta a {{ background: #D4AF37; color: #fff; padding: 12px 24px; text-decoration: none; border-radius: 5px; font-weight: bold; }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>Gold Rate Update</h1>
            <p style="color: #fff; margin: 10px 0 0 0;">{rate_date.strftime('%B %d, %Y')}</p>
        </div>

        <div class="rate-box">
            <div class="stat-label">IBJA 916 Rate (with 3% GST)</div>
            <div class="rate">Rs. {rate_with_gst:,.2f}/g</div>
            <div style="color: #666; font-size: 0.9em;">Base: Rs. {ibja_rate:,.2f}/g</div>
        </div>

        <div class="stats">
            <div class="stat">
                <div class="stat-label">Last Month Reference</div>
                <div class="stat-value">{f'Rs. {reference_price:,.2f}/g' if reference_price else 'N/A'}</div>
            </div>
            <div class="stat">
                <div class="stat-label">20-Day Moving Average</div>
                <div class="stat-value">{f'Rs. {moving_average:,.2f}/g' if moving_average else 'N/A'}</div>
            </div>
            <div class="stat">
                <div class="stat-label">Month Low So Far</div>
                <div class="stat-value">{f'Rs. {month_low:,.2f}/g' if month_low else 'N/A'}</div>
            </div>
        </div>

        <div class="cta">
            <a href="{settings.APP_URL}">Check Your Jeweller's Price</a>
        </div>
    </div>
</body>
</html>
"""

    return send_email(subject, body, html_body)


def send_buy_alert(price: float, reason: str, rate_date: date = None) -> bool:
    """Send a BUY recommendation alert.

    Args:
        price: The price that triggered the alert
        reason: Reason for the recommendation
        rate_date: Date of the recommendation

    Returns:
        True if sent successfully
    """
    if rate_date is None:
        rate_date = date.today()

    subject = f"BUY Alert - Gold at Rs. {price:,.2f}/g"

    body = f"""
BUY RECOMMENDATION
{'='*50}

Date: {rate_date.strftime('%B %d, %Y')}
Price: Rs. {price:,.2f}/gram

Reason:
{reason}

This is an automated alert from Gold Investment Timing Optimizer.
Visit {settings.APP_URL} for more details.
"""

    return send_email(subject, body)
