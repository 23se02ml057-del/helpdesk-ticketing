import os
import logging
import requests
import html
from datetime import datetime
from flask import Flask, current_app, request, url_for

logger = logging.getLogger(__name__)

BREVO_API_KEY = os.getenv("BREVO_API_KEY", "")
BREVO_SENDER_EMAIL = os.getenv("BREVO_SENDER_EMAIL", "")
BREVO_SENDER_NAME = os.getenv("BREVO_SENDER_NAME", "Help Desk Support")
BREVO_REPLY_DOMAIN = os.getenv("BREVO_REPLY_DOMAIN", "reply.yourdomain.com")
BREVO_API_URL = "https://api.brevo.com/v3/smtp/email"
BREVO_PASSWORD_RESET_TEMPLATE_ID = os.getenv("BREVO_PASSWORD_RESET_TEMPLATE_ID", "")
BREVO_TICKET_CLOSED_TEMPLATE_ID = os.getenv("BREVO_TICKET_CLOSED_TEMPLATE_ID", "")
BREVO_CUSTOMER_VERIFICATION_TEMPLATE_ID = os.getenv("BREVO_CUSTOMER_VERIFICATION_TEMPLATE_ID", "")


def _brevo_headers():
    return {
        "api-key": BREVO_API_KEY,
        "Content-Type": "application/json",
        "Accept": "application/json",
    }


def _build_brevo_payload(subject, recipient, body_text, html_content=None, reply_to=None, template_id=None, params=None):
    if template_id:
        payload = {
            "sender": {
                "name": BREVO_SENDER_NAME,
                "email": BREVO_SENDER_EMAIL,
            },
            "to": [{"email": recipient}],
            "templateId": int(template_id),
            "params": params or {},
        }
        if reply_to:
            payload["replyTo"] = {"email": reply_to}
        return payload

    payload = {
        "sender": {
            "name": BREVO_SENDER_NAME,
            "email": BREVO_SENDER_EMAIL,
        },
        "to": [{"email": recipient}],
        "subject": subject,
        "textContent": body_text or "",
    }
    if html_content:
        payload["htmlContent"] = html_content
    if reply_to:
        payload["replyTo"] = {"email": reply_to}
    return payload


def send_email(subject, recipient, body, html=None, template_id=None, params=None):
    try:
        if not BREVO_API_KEY or not BREVO_SENDER_EMAIL:
            logger.error("Brevo not configured: missing API key or sender email")
            return {"success": False, "message_id": None, "error": "Brevo not configured"}

        payload = _build_brevo_payload(subject, recipient, body, html_content=html, template_id=template_id, params=params)
        resp = requests.post(
            BREVO_API_URL,
            json=payload,
            headers=_brevo_headers(),
            timeout=30,
        )
        if resp.status_code in (200, 201):
            data = resp.json()
            message_id = data.get("messageId") or data.get("message_id")
            logger.info("Brevo email sent successfully to %s (messageId=%s)", recipient, message_id)
            return {"success": True, "message_id": message_id, "error": None}
        else:
            logger.error(
                "Brevo email failed for %s: %s %s",
                recipient, resp.status_code, resp.text[:500]
            )
            return {
                "success": False,
                "message_id": None,
                "error": f"Brevo error {resp.status_code}: {resp.text[:200]}",
            }
    except requests.exceptions.Timeout:
        logger.error("Brevo email timeout for %s", recipient)
        return {"success": False, "message_id": None, "error": "Brevo request timeout"}
    except requests.exceptions.ConnectionError:
        logger.error("Brevo email connection error for %s", recipient)
        return {"success": False, "message_id": None, "error": "Brevo connection error"}
    except Exception as e:
        logger.error("Brevo email unexpected error for %s: %s", recipient, e)
        return {"success": False, "message_id": None, "error": str(e)}


def init_mail(app):
    pass


def _build_closed_ticket_html(ticket_number, title, customer_name, old_status,
                               closing_date, support_agent_name):
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Ticket Closed - {html.escape(ticket_number)}</title>
    <style>
        body {{ font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; margin: 0; padding: 0; background-color: #f5f6fa; color: #333; }}
        .container {{ max-width: 600px; margin: 30px auto; background-color: #ffffff; border-radius: 8px; box-shadow: 0 2px 10px rgba(0,0,0,0.08); overflow: hidden; }}
        .header {{ background-color: #2563eb; color: #ffffff; padding: 24px 32px; text-align: center; }}
        .header h1 {{ margin: 0; font-size: 20px; font-weight: 600; }}
        .header .logo {{ font-size: 24px; margin-bottom: 8px; }}
        .content {{ padding: 32px; }}
        .content h2 {{ font-size: 18px; color: #1e293b; margin-top: 0; margin-bottom: 16px; }}
        .content p {{ line-height: 1.6; color: #475569; margin-bottom: 16px; }}
        .details {{ background-color: #f8fafc; border-left: 4px solid #2563eb; padding: 16px 20px; margin: 20px 0; border-radius: 0 4px 4px 0; }}
        .details table {{ width: 100%; border-collapse: collapse; }}
        .details td {{ padding: 6px 0; font-size: 14px; }}
        .details td:first-child {{ font-weight: 600; color: #64748b; width: 140px; }}
        .details td:last-child {{ color: #1e293b; }}
        .footer {{ background-color: #f8fafc; padding: 20px 32px; text-align: center; font-size: 13px; color: #94a3b8; border-top: 1px solid #e2e8f0; }}
        .button {{ display: inline-block; margin-top: 16px; padding: 10px 24px; background-color: #2563eb; color: #ffffff; text-decoration: none; border-radius: 4px; font-size: 14px; font-weight: 500; }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <div class="logo">&#128230;</div>
            <h1>Help Desk Support System</h1>
        </div>
        <div class="content">
            <h2>Ticket Closed - {html.escape(ticket_number)}</h2>
            <p>Dear {html.escape(customer_name)},</p>
            <p>Your support ticket has been successfully resolved and marked as Closed.</p>
            <div class="details">
                <table>
                    <tr><td>Ticket Number:</td><td><strong>{html.escape(ticket_number)}</strong></td></tr>
                    <tr><td>Subject:</td><td>{html.escape(title)}</td></tr>
                    <tr><td>Previous Status:</td><td>{html.escape(old_status or 'N/A')}</td></tr>
                    <tr><td>New Status:</td><td><strong style="color: #16a34a;">Closed</strong></td></tr>
                    <tr><td>Closed On:</td><td>{html.escape(closing_date)}</td></tr>
                    <tr><td>Support Agent:</td><td>{html.escape(support_agent_name or 'Support Team')}</td></tr>
                </table>
            </div>
            <p>Thank you for contacting our support team.</p>
            <p>If you continue to experience the issue or need further assistance, please create a new support ticket or contact our support team.</p>
        </div>
        <div class="footer">
            &copy; {datetime.now().year} Help Desk Support System. All rights reserved.<br>
            This is an automated message. Please do not reply to this email.
        </div>
    </div>
</body>
</html>"""


def _generate_ticket_link(ticket_id):
    try:
        return url_for("customer.ticket_detail", ticket_id=ticket_id, _external=True)
    except Exception:
        return ""


def send_closed_ticket_email(ticket_id, old_status, new_status, support_agent_name=None, ticket_link=None):
    if old_status == 'Closed' or new_status != 'Closed':
        return {"success": False, "message_id": None, "error": "No transition to Closed"}

    try:
        from help_db import db
        from sqlalchemy import text

        ticket_data = db.session.execute(
            text("""
                SELECT
                    t.ticket_number,
                    t.title,
                    u.first_name,
                    u.last_name,
                    u.email,
                    t.resolved_at,
                    t.requester_id
                FROM tickets t
                LEFT JOIN users u ON t.requester_id = u.user_id
                WHERE t.ticket_id = :ticket_id
            """),
            {"ticket_id": ticket_id}
        ).fetchone()

        if not ticket_data:
            logger.warning("send_closed_ticket_email: ticket_id=%s not found", ticket_id)
            return {"success": False, "message_id": None, "error": "Ticket not found"}

        ticket_number = ticket_data[0]
        title = ticket_data[1]
        first_name = ticket_data[2] or ''
        last_name = ticket_data[3] or ''
        recipient_email = ticket_data[4]
        resolved_at = ticket_data[5]
        requester_id = ticket_data[6]

        customer_name = f"{first_name} {last_name}".strip()
        if not customer_name:
            customer_name = "Valued Customer"

        if not recipient_email or not recipient_email.strip():
            logger.warning("send_closed_ticket_email: no email for requester of ticket_id=%s", ticket_id)
            return {"success": False, "message_id": None, "error": "No requester email"}

        closing_date = datetime.utcnow().strftime('%B %d, %Y at %I:%M %p')
        if not ticket_link:
            ticket_link = _generate_ticket_link(ticket_id) or ""

        template_id = BREVO_TICKET_CLOSED_TEMPLATE_ID
        if template_id:
            params = {
                "user_name": customer_name,
                "ticket_number": ticket_number,
                "ticket_title": title or "",
                "closed_at": closing_date,
                "ticket_link": ticket_link,
            }
            result = send_email(
                subject="Your Help Desk Ticket Has Been Closed",
                recipient=recipient_email,
                body="",
                template_id=int(template_id),
                params=params,
            )
        else:
            subject = f"Ticket Closed - {ticket_number}"
            body = f"""Hello {customer_name},

Your support ticket has been successfully resolved and marked as Closed.

Ticket Details:
- Ticket Number: {ticket_number}
- Subject: {title}
- Previous Status: {old_status or 'N/A'}
- New Status: Closed
- Closed On: {closing_date}
- Support Agent: {support_agent_name or 'Support Team'}

If you continue to experience the issue or need further assistance, please create a new support ticket or contact our support team.

Thank you for contacting our support team.

Regards,
Help Desk Support Team"""

            html_body = _build_closed_ticket_html(
                ticket_number, title, customer_name, old_status,
                closing_date, support_agent_name
            )
            result = send_email(subject, recipient_email, body, html=html_body)

        try:
            db.session.execute(
                text("""
                    INSERT INTO notifications (user_id, ticket_id, message, is_read, created_at)
                    VALUES (:user_id, :ticket_id, :message, FALSE, :created_at)
                """),
                {
                    "user_id": requester_id,
                    "ticket_id": ticket_id,
                    "message": f"Ticket {ticket_number} has been closed. Closure confirmation email sent to {recipient_email}." if result.get("success") else f"Ticket {ticket_number} has been closed. Failed to send closure email to {recipient_email}.",
                    "created_at": datetime.utcnow()
                }
            )
            db.session.commit()
        except Exception as log_err:
            db.session.rollback()
            logger.error("Failed to log email notification for ticket_id=%s: %s", ticket_id, log_err)

        return result

    except Exception as e:
        logger.error("send_closed_ticket_email error for ticket_id=%s: %s", ticket_id, e)
        try:
            from help_db import db as db3
            db3.session.rollback()
        except Exception:
            pass
        return {"success": False, "message_id": None, "error": str(e)}


def send_forgot_password_email(recipient_email, reset_link, user_name="User", expiry_minutes=15):
    template_id = BREVO_PASSWORD_RESET_TEMPLATE_ID
    if template_id:
        params = {
            "user_name": user_name,
            "reset_link": reset_link,
            "expiry_minutes": str(expiry_minutes),
        }
        return send_email(
            subject="Reset Your Help Desk Password",
            recipient=recipient_email,
            body="",
            template_id=int(template_id),
            params=params,
        )

    subject = "Password Reset Request - Help Desk System"
    body = f"""Dear {user_name},

You have requested to reset your password. Click the link below to reset your password:

{reset_link}

This link will expire in {expiry_minutes} minutes.

If you did not request this, please ignore this email.

Best regards,
Help Desk Team"""

    html_body = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Password Reset - Help Desk</title>
    <style>
        body {{ font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; margin: 0; padding: 0; background-color: #f5f6fa; color: #333; }}
        .container {{ max-width: 600px; margin: 30px auto; background-color: #ffffff; border-radius: 8px; box-shadow: 0 2px 10px rgba(0,0,0,0.08); overflow: hidden; }}
        .header {{ background-color: #2563eb; color: #ffffff; padding: 24px 32px; text-align: center; }}
        .header h1 {{ margin: 0; font-size: 20px; font-weight: 600; }}
        .content {{ padding: 32px; }}
        .content p {{ line-height: 1.6; color: #475569; margin-bottom: 16px; }}
        .button {{ display: inline-block; margin-top: 16px; padding: 10px 24px; background-color: #2563eb; color: #ffffff; text-decoration: none; border-radius: 4px; font-size: 14px; font-weight: 500; }}
        .footer {{ background-color: #f8fafc; padding: 20px 32px; text-align: center; font-size: 13px; color: #94a3b8; border-top: 1px solid #e2e8f0; }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>Help Desk Support</h1>
        </div>
        <div class="content">
            <h2>Password Reset Request</h2>
            <p>Dear {html.escape(user_name)},</p>
            <p>You have requested to reset your password. Click the button below to reset your password:</p>
            <a href="{html.escape(reset_link)}" class="button">Reset Password</a>
            <p>This link will expire in {expiry_minutes} minutes.</p>
            <p>If you did not request this, please ignore this email.</p>
        </div>
        <div class="footer">
            &copy; {datetime.now().year} Help Desk Support System. All rights reserved.<br>
            This is an automated message. Please do not reply to this email.
        </div>
    </div>
</body>
</html>"""

    return send_email(subject, recipient_email, body, html=html_body)


def send_customer_verification_email(recipient_email, user_name, verification_link):
    subject = "Verify Your Email - Help Desk Registration"
    template_id = BREVO_CUSTOMER_VERIFICATION_TEMPLATE_ID

    if template_id:
        params = {
            "user_name": user_name,
            "verification_link": verification_link,
            "expiry_minutes": "1440",
        }
        return send_email(
            subject=subject,
            recipient=recipient_email,
            body="",
            template_id=int(template_id),
            params=params,
        )

    body = f"""Dear {user_name},

Your customer account has been created successfully.

Click the link below to verify your email address and continue to the login page:

{verification_link}

This link will expire in 24 hours.

If you did not register for this account, please ignore this email.

Best regards,
Help Desk Support Team"""

    html_body = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Verify Your Email - Help Desk</title>
    <style>
        body {{ font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; margin: 0; padding: 0; background-color: #f5f6fa; color: #333; }}
        .container {{ max-width: 600px; margin: 30px auto; background-color: #ffffff; border-radius: 8px; box-shadow: 0 2px 10px rgba(0,0,0,0.08); overflow: hidden; }}
        .header {{ background-color: #2563eb; color: #ffffff; padding: 24px 32px; text-align: center; }}
        .header h1 {{ margin: 0; font-size: 20px; font-weight: 600; }}
        .content {{ padding: 32px; }}
        .content h2 {{ font-size: 18px; color: #1e293b; margin-top: 0; margin-bottom: 16px; }}
        .content p {{ line-height: 1.6; color: #475569; margin-bottom: 16px; }}
        .button {{ display: inline-block; margin-top: 16px; padding: 12px 32px; background-color: #2563eb; color: #ffffff; text-decoration: none; border-radius: 6px; font-size: 16px; font-weight: 500; }}
        .footer {{ background-color: #f8fafc; padding: 20px 32px; text-align: center; font-size: 13px; color: #94a3b8; border-top: 1px solid #e2e8f0; }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>Help Desk Support</h1>
        </div>
        <div class="content">
            <h2>Registration Successful!</h2>
            <p>Hello {html.escape(user_name)},</p>
            <p>Your customer account has been created successfully.</p>
            <p>Click the button below to verify your email address and continue to the login page:</p>
            <a href="{html.escape(verification_link)}" class="button">Verify &amp; Login</a>
            <p style="font-size: 13px; color: #94a3b8; margin-top: 20px;">This link will expire in 24 hours. If you did not register for this account, please ignore this email.</p>
        </div>
        <div class="footer">
            &copy; {datetime.now().year} Help Desk Support System. All rights reserved.<br>
            This is an automated message. Please do not reply to this email.
        </div>
    </div>
</body>
</html>"""

    return send_email(subject, recipient_email, body, html=html_body)


def send_customer_welcome_email(recipient_email, user_name, login_link):
    subject = "Welcome to Help Desk!"
    
    body = f"""Dear {user_name},

Your customer account has been created successfully.

You can now login to track and manage your support tickets using the link below:

{login_link}

Best regards,
Help Desk Support Team"""

    html_body = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Welcome - Help Desk</title>
    <style>
        body {{ font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; margin: 0; padding: 0; background-color: #f5f6fa; color: #333; }}
        .container {{ max-width: 600px; margin: 30px auto; background-color: #ffffff; border-radius: 8px; box-shadow: 0 2px 10px rgba(0,0,0,0.08); overflow: hidden; }}
        .header {{ background-color: #2563eb; color: #ffffff; padding: 24px 32px; text-align: center; }}
        .header h1 {{ margin: 0; font-size: 20px; font-weight: 600; }}
        .content {{ padding: 32px; }}
        .content h2 {{ font-size: 18px; color: #1e293b; margin-top: 0; margin-bottom: 16px; }}
        .content p {{ line-height: 1.6; color: #475569; margin-bottom: 16px; }}
        .button {{ display: inline-block; margin-top: 16px; padding: 12px 32px; background-color: #2563eb; color: #ffffff; text-decoration: none; border-radius: 6px; font-size: 16px; font-weight: 500; }}
        .footer {{ background-color: #f8fafc; padding: 20px 32px; text-align: center; font-size: 13px; color: #94a3b8; border-top: 1px solid #e2e8f0; }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>Help Desk Support</h1>
        </div>
        <div class="content">
            <h2>Registration Successful!</h2>
            <p>Hello {html.escape(user_name)},</p>
            <p>Welcome to Help Desk. Your customer account has been created successfully.</p>
            <p>Click the button below to sign in and start managing your support tickets:</p>
            <a href="{html.escape(login_link)}" class="button">Login to your Account</a>
        </div>
        <div class="footer">
            &copy; {datetime.now().year} Help Desk Support System. All rights reserved.<br>
            This is an automated message. Please do not reply to this email.
        </div>
    </div>
</body>
</html>"""

    return send_email(subject, recipient_email, body, html=html_body)


def send_ticket_reply_email(ticket_number, ticket_title, recipient_email, customer_name,
                            reply_text, sender_name, sender_role):
    subject = f"Re: {ticket_title} - {ticket_number}"
    reply_to_address = f"ticket-{ticket_number}@{BREVO_REPLY_DOMAIN}"

    body = f"""Hello {customer_name},

A new reply has been added to your support ticket.

Ticket Details:
- Ticket Number: {ticket_number}
- Subject: {ticket_title}
- From: {sender_name} ({sender_role})

Reply:
{reply_text}

If you have any further questions, please reply to this email or visit the help desk portal.

Regards,
Help Desk Support Team"""

    html_body = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Re: {html.escape(ticket_title)} - {html.escape(ticket_number)}</title>
    <style>
        body {{ font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; margin: 0; padding: 0; background-color: #f5f6fa; color: #333; }}
        .container {{ max-width: 600px; margin: 30px auto; background-color: #ffffff; border-radius: 8px; box-shadow: 0 2px 10px rgba(0,0,0,0.08); overflow: hidden; }}
        .header {{ background-color: #2563eb; color: #ffffff; padding: 24px 32px; text-align: center; }}
        .header h1 {{ margin: 0; font-size: 20px; font-weight: 600; }}
        .content {{ padding: 32px; }}
        .content h2 {{ font-size: 18px; color: #1e293b; margin-top: 0; margin-bottom: 16px; }}
        .content p {{ line-height: 1.6; color: #475569; margin-bottom: 16px; }}
        .details {{ background-color: #f8fafc; border-left: 4px solid #2563eb; padding: 16px 20px; margin: 20px 0; border-radius: 0 4px 4px 0; }}
        .details table {{ width: 100%; border-collapse: collapse; }}
        .details td {{ padding: 6px 0; font-size: 14px; }}
        .details td:first-child {{ font-weight: 600; color: #64748b; width: 140px; }}
        .details td:last-child {{ color: #1e293b; }}
        .reply-box {{ background-color: #f8fafc; padding: 16px 20px; border-radius: 4px; margin: 20px 0; white-space: pre-wrap; }}
        .footer {{ background-color: #f8fafc; padding: 20px 32px; text-align: center; font-size: 13px; color: #94a3b8; border-top: 1px solid #e2e8f0; }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>Help Desk Support</h1>
        </div>
        <div class="content">
            <h2>New Reply on Ticket {html.escape(ticket_number)}</h2>
            <p>Hello {html.escape(customer_name)},</p>
            <p>A new reply has been added to your support ticket.</p>
            <div class="details">
                <table>
                    <tr><td>Ticket Number:</td><td><strong>{html.escape(ticket_number)}</strong></td></tr>
                    <tr><td>Subject:</td><td>{html.escape(ticket_title)}</td></tr>
                    <tr><td>From:</td><td>{html.escape(sender_name)} ({html.escape(sender_role)})</td></tr>
                </table>
            </div>
            <p><strong>Reply:</strong></p>
            <div class="reply-box">{html.escape(reply_text)}</div>
            <p>If you have any further questions, please reply to this email or visit the help desk portal.</p>
        </div>
        <div class="footer">
            &copy; {datetime.now().year} Help Desk Support System. All rights reserved.<br>
            This is an automated message.
        </div>
    </div>
</body>
</html>"""

    return send_email(subject, recipient_email, body, html=html_body, reply_to=reply_to_address)


def send_ticket_assignment_email(ticket_number, ticket_title, recipient_email, agent_name,
                                 assigned_by_name="Support Manager"):
    subject = f"Ticket Assigned - {ticket_number}"

    body = f"""Hello {agent_name},

A support ticket has been assigned to you.

Ticket Details:
- Ticket Number: {ticket_number}
- Subject: {ticket_title}
- Assigned By: {assigned_by_name}

Please log in to the help desk system to review and update the ticket.

Regards,
Help Desk Support Team"""

    html_body = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Ticket Assigned - {html.escape(ticket_number)}</title>
    <style>
        body {{ font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; margin: 0; padding: 0; background-color: #f5f6fa; color: #333; }}
        .container {{ max-width: 600px; margin: 30px auto; background-color: #ffffff; border-radius: 8px; box-shadow: 0 2px 10px rgba(0,0,0,0.08); overflow: hidden; }}
        .header {{ background-color: #2563eb; color: #ffffff; padding: 24px 32px; text-align: center; }}
        .header h1 {{ margin: 0; font-size: 20px; font-weight: 600; }}
        .content {{ padding: 32px; }}
        .content h2 {{ font-size: 18px; color: #1e293b; margin-top: 0; margin-bottom: 16px; }}
        .content p {{ line-height: 1.6; color: #475569; margin-bottom: 16px; }}
        .details {{ background-color: #f8fafc; border-left: 4px solid #2563eb; padding: 16px 20px; margin: 20px 0; border-radius: 0 4px 4px 0; }}
        .details table {{ width: 100%; border-collapse: collapse; }}
        .details td {{ padding: 6px 0; font-size: 14px; }}
        .details td:first-child {{ font-weight: 600; color: #64748b; width: 140px; }}
        .details td:last-child {{ color: #1e293b; }}
        .footer {{ background-color: #f8fafc; padding: 20px 32px; text-align: center; font-size: 13px; color: #94a3b8; border-top: 1px solid #e2e8f0; }}
        .button {{ display: inline-block; margin-top: 16px; padding: 10px 24px; background-color: #2563eb; color: #ffffff; text-decoration: none; border-radius: 4px; font-size: 14px; font-weight: 500; }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>Help Desk Support</h1>
        </div>
        <div class="content">
            <h2>Ticket Assigned - {html.escape(ticket_number)}</h2>
            <p>Hello {html.escape(agent_name)},</p>
            <p>A support ticket has been assigned to you.</p>
            <div class="details">
                <table>
                    <tr><td>Ticket Number:</td><td><strong>{html.escape(ticket_number)}</strong></td></tr>
                    <tr><td>Subject:</td><td>{html.escape(ticket_title)}</td></tr>
                    <tr><td>Assigned By:</td><td>{html.escape(assigned_by_name)}</td></tr>
                </table>
            </div>
            <p>Please log in to the help desk system to review and update the ticket.</p>
        </div>
        <div class="footer">
            &copy; {datetime.now().year} Help Desk Support System. All rights reserved.<br>
            This is an automated message.
        </div>
    </div>
</body>
</html>"""

    return send_email(subject, recipient_email, body, html=html_body)
