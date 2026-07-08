import os
import json
import logging
import urllib.request
import urllib.parse
from urllib.error import URLError

logger = logging.getLogger(__name__)

AT_API_KEY = os.getenv("AT_API_KEY", "")
AT_USERNAME = os.getenv("AT_USERNAME", "sandbox")
AT_SENDER_ID = os.getenv("AT_SENDER_ID", "")  # optional short-code; leave blank for sandbox


def send_sms(phone: str, message: str) -> bool:
    """Send an SMS via AfricasTalking. Returns True on success, False on failure."""
    if not AT_API_KEY:
        logger.warning("AT_API_KEY not set — SMS skipped for %s", phone)
        return False

    phone = phone.strip()
    if not phone.startswith("+"):
        # Assume Kenyan number; convert 07xx → +2547xx
        if phone.startswith("0"):
            phone = "+254" + phone[1:]
        else:
            phone = "+254" + phone

    payload = {
        "username": AT_USERNAME,
        "to": phone,
        "message": message,
    }
    if AT_SENDER_ID:
        payload["from"] = AT_SENDER_ID

    data = urllib.parse.urlencode(payload).encode()
    req = urllib.request.Request(
        "https://api.africastalking.com/version1/messaging",
        data=data,
        headers={
            "Accept": "application/json",
            "Content-Type": "application/x-www-form-urlencoded",
            "apiKey": AT_API_KEY,
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            body = json.loads(resp.read().decode())
            recipients = body.get("SMSMessageData", {}).get("Recipients", [])
            if recipients and recipients[0].get("status") == "Success":
                logger.info("SMS sent to %s", phone)
                return True
            logger.warning("SMS to %s returned: %s", phone, body)
            return False
    except URLError as exc:
        logger.error("SMS delivery failed for %s: %s", phone, exc)
        return False


def notify_payment(student_name: str, guardian_phone: str, amount: float,
                   term: str, receipt: str) -> None:
    """Fire-and-forget payment notification SMS."""
    if not guardian_phone:
        return
    msg = (
        f"Dear Parent/Guardian, a fee payment of KES {amount:,.0f} for {term} "
        f"has been received for {student_name}. Receipt: {receipt}. "
        f"Thank you — The Bona School."
    )
    send_sms(guardian_phone, msg)


def notify_report_card(student_name: str, guardian_phone: str, term: str) -> None:
    """Notify parent that a report card has been published."""
    if not guardian_phone:
        return
    msg = (
        f"Dear Parent/Guardian, the {term} report card for {student_name} "
        f"is now available. Please visit the school to collect it. "
        f"— The Bona School."
    )
    send_sms(guardian_phone, msg)


def notify_absence(student_name: str, guardian_phone: str, absence_date: str) -> None:
    """Notify parent that their child was marked absent."""
    if not guardian_phone:
        return
    msg = (
        f"Dear Parent/Guardian, {student_name} was marked ABSENT on {absence_date}. "
        f"Please contact the school if you have not already notified us. "
        f"— The Bona School."
    )
    send_sms(guardian_phone, msg)


def send_bulk_sms(phones: list, message: str) -> dict:
    """Send the same message to multiple phone numbers. Returns summary."""
    sent, failed = 0, 0
    for phone in phones:
        if send_sms(phone, message):
            sent += 1
        else:
            failed += 1
    return {"sent": sent, "failed": failed, "total": len(phones)}
