import os
import logging
import hashlib
from flask import Blueprint, request, jsonify
from sqlalchemy import text
from help_db import db
from datetime import datetime

email_bp = Blueprint('email', __name__)
logger = logging.getLogger(__name__)

BREVO_INBOUND_WEBHOOK_TOKEN = os.getenv("BREVO_INBOUND_WEBHOOK_TOKEN", "")


def _clean_quoted_text(body):
    if not body:
        return ""
    lines = body.splitlines()
    cleaned = []
    for line in lines:
        stripped = line.strip()
        if stripped.startswith(">") or stripped.startswith("----") or stripped.startswith("Original Message") or stripped.startswith("On ") and " wrote:" in stripped:
            break
        cleaned.append(line)
    return "\n".join(cleaned).strip()


def _extract_ticket_number(recipient_email):
    if not recipient_email:
        return None
    local_part = recipient_email.split("@")[0]
    if local_part.startswith("ticket-"):
        return local_part[len("ticket-"):]
    return None


@email_bp.route('/api/email/brevo/inbound', methods=['POST'])
def brevo_inbound():
    try:
        webhook_token = request.headers.get("X-Brevo-Token", "") or request.form.get("token", "")
        if not BREVO_INBOUND_WEBHOOK_TOKEN or webhook_token != BREVO_INBOUND_WEBHOOK_TOKEN:
            logger.warning("Inbound Brevo webhook rejected: invalid token")
            return jsonify({"success": False, "message": "Invalid token"}), 403

        data = request.get_json(silent=True) or request.form.to_dict()

        sender_email = data.get("From", "")
        recipient_email = data.get("To", "")
        subject = data.get("Subject", "")
        text_body = data.get("text", "") or data.get("Text", "")
        html_body = data.get("html", "") or data.get("Html", "")
        message_id = data.get("MessageID", "") or data.get("message-id", "")
        in_reply_to = data.get("In-Reply-To", "") or data.get("in-reply-to", "")
        references = data.get("References", "") or data.get("references", "")

        logger.info("Inbound Brevo webhook received: from=%s to=%s subject=%s message_id=%s", sender_email, recipient_email, subject, message_id)

        ticket_number = _extract_ticket_number(recipient_email)
        if not ticket_number:
            logger.warning("Inbound email: could not extract ticket number from recipient=%s", recipient_email)
            return jsonify({"success": False, "message": "Cannot identify ticket"}), 400

        ticket = db.session.execute(
            text("""
                SELECT ticket_id, requester_id, status_name
                FROM tickets
                WHERE ticket_number = :ticket_number
            """),
            {"ticket_number": ticket_number}
        ).fetchone()

        if not ticket:
            logger.warning("Inbound email: ticket not found for ticket_number=%s", ticket_number)
            return jsonify({"success": False, "message": "Ticket not found"}), 404

        ticket_id = ticket[0]
        requester_id = ticket[1]
        current_status = ticket[2]

        sender = db.session.execute(
            text("""
                SELECT user_id, first_name, last_name, role_id
                FROM users
                WHERE email = :email
            """),
            {"email": sender_email}
        ).fetchone()

        if not sender or sender[0] != requester_id:
            logger.warning("Inbound email: unauthorized sender=%s for ticket_id=%s", sender_email, ticket_id)
            return jsonify({"success": False, "message": "Unauthorized sender"}), 403

        dedup_hash = hashlib.sha256(
            f"{message_id}:{ticket_id}:{sender_email}".encode()
        ).hexdigest()

        existing = db.session.execute(
            text("""
                SELECT log_id FROM email_inbound_log
                WHERE dedup_hash = :dedup_hash
            """),
            {"dedup_hash": dedup_hash}
        ).fetchone()

        if existing:
            logger.info("Inbound email: duplicate ignored for ticket_id=%s dedup_hash=%s", ticket_id, dedup_hash)
            return jsonify({"success": True, "message": "Duplicate email ignored"}), 200

        clean_body = _clean_quoted_text(text_body or html_body or "")
        if not clean_body:
            logger.info("Inbound email: empty body after cleaning for ticket_id=%s", ticket_id)
            return jsonify({"success": True, "message": "Empty body ignored"}), 200

        db.session.execute(
            text("""
                INSERT INTO ticket_comments (ticket_id, user_id, comment_text, is_internal, created_at)
                VALUES (:ticket_id, :user_id, :comment_text, FALSE, :created_at)
            """),
            {
                "ticket_id": ticket_id,
                "user_id": requester_id,
                "comment_text": clean_body,
                "created_at": datetime.utcnow()
            }
        )

        if current_status == 'Closed':
            db.session.execute(
                text("""
                    UPDATE tickets
                    SET status_name = 'Open', reopen_count = COALESCE(reopen_count, 0) + 1
                    WHERE ticket_id = :ticket_id
                """),
                {"ticket_id": ticket_id}
            )

        db.session.execute(
            text("""
                INSERT INTO email_inbound_log (message_id, ticket_id, sender_email, dedup_hash, action_taken, processed_at)
                VALUES (:message_id, :ticket_id, :sender_email, :dedup_hash, :action_taken, :processed_at)
            """),
            {
                "message_id": message_id,
                "ticket_id": ticket_id,
                "sender_email": sender_email,
                "dedup_hash": dedup_hash,
                "action_taken": "comment_added" + ("_reopened" if current_status == 'Closed' else ""),
                "processed_at": datetime.utcnow()
            }
        )

        db.session.commit()

        ticket_info = db.session.execute(
            text("SELECT ticket_number, title, assigned_to FROM tickets WHERE ticket_id = :ticket_id"),
            {"ticket_id": ticket_id}
        ).fetchone()

        if ticket_info:
            from utils.notifications import create_notification
            if ticket_info[2]:
                create_notification(
                    ticket_info[2],
                    "New Customer Reply",
                    f"Customer replied to ticket #{ticket_info[0]} - {ticket_info[1]}"
                )

        logger.info("Inbound email: comment added to ticket_id=%s", ticket_id)
        return jsonify({"success": True, "message": "Comment added"}), 200

    except Exception as e:
        db.session.rollback()
        logger.error("Inbound Brevo webhook error: %s", e)
        return jsonify({"success": False, "message": "Internal error"}), 500
