"""
OpsPulse 360 - Notifier
Sends real notifications via Email (SMTP) or Slack incoming webhook.
Both channels are config-driven via environment variables so the
project runs safely with zero configuration (it will just log what
would have been sent and return False), and becomes a REAL, live
notification the moment credentials are supplied -- satisfying the
"at least one alert must trigger an actual automated notification"
requirement.

Environment variables:
  NOTIFY_CHANNEL          "slack" | "email" | "none" (default: "none")
  SLACK_WEBHOOK_URL        https://hooks.slack.com/services/...
  SMTP_HOST, SMTP_PORT, SMTP_USER, SMTP_PASSWORD, SMTP_FROM, SMTP_TO
"""
import json
import os
import smtplib
import urllib.request
from email.mime.text import MIMEText

NOTIFY_CHANNEL = os.environ.get("NOTIFY_CHANNEL", "none").lower()


def _send_slack(subject: str, message: str) -> bool:
    webhook_url = os.environ.get("SLACK_WEBHOOK_URL")
    if not webhook_url:
        print(f"[notifier] SLACK_WEBHOOK_URL not set. Would have sent to Slack:\n  {subject}\n  {message}")
        return False
    payload = json.dumps({"text": f"*{subject}*\n{message}"}).encode("utf-8")
    req = urllib.request.Request(webhook_url, data=payload, headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            ok = resp.status == 200
            print(f"[notifier] Slack notification sent (status={resp.status}).")
            return ok
    except Exception as e:
        print(f"[notifier] Slack send failed: {e}")
        return False


def _send_email(subject: str, message: str) -> bool:
    host = os.environ.get("SMTP_HOST")
    port = int(os.environ.get("SMTP_PORT", 587))
    user = os.environ.get("SMTP_USER")
    password = os.environ.get("SMTP_PASSWORD")
    from_addr = os.environ.get("SMTP_FROM", user)
    to_addr = os.environ.get("SMTP_TO")

    if not all([host, user, password, to_addr]):
        print(f"[notifier] SMTP not fully configured. Would have emailed:\n  Subject: {subject}\n  Body: {message}")
        return False

    msg = MIMEText(message)
    msg["Subject"] = subject
    msg["From"] = from_addr
    msg["To"] = to_addr

    try:
        with smtplib.SMTP(host, port, timeout=10) as server:
            server.starttls()
            server.login(user, password)
            server.sendmail(from_addr, [to_addr], msg.as_string())
        print(f"[notifier] Email sent to {to_addr}.")
        return True
    except Exception as e:
        print(f"[notifier] Email send failed: {e}")
        return False


def send_notification(subject: str, message: str) -> bool:
    if NOTIFY_CHANNEL == "slack":
        return _send_slack(subject, message)
    elif NOTIFY_CHANNEL == "email":
        return _send_email(subject, message)
    else:
        print(f"[notifier] NOTIFY_CHANNEL not configured (set to 'slack' or 'email'). "
              f"Alert logged only:\n  {subject}\n  {message}")
        return False


if __name__ == "__main__":
    send_notification("[OpsPulse 360] Test alert", "This is a test notification from the automation layer.")
