from flask import Blueprint, render_template, request, redirect, url_for, flash, session, jsonify
from flask_babel import gettext as _
from sqlalchemy import text
from help_db import db
from datetime import datetime
import logging
from werkzeug.utils import secure_filename
import os
from utils.notifications import notify_ticket_status_changed, create_notification, notify_ticket_assigned
from utils.socket_events import emit_ticket_status_change

support_agent_bp = Blueprint('support_agent', __name__)
logger = logging.getLogger(__name__)


@support_agent_bp.context_processor
def inject_unread_count():
    user_id = session.get("user_id")
    if user_id:
        unread_count = db.session.execute(
            text("""
                SELECT COUNT(*) FROM notifications
                WHERE user_id = :user_id AND is_read = FALSE
            """),
            {"user_id": user_id}
        ).scalar()
        return dict(unread_count=unread_count)
    return dict(unread_count=0)


def require_agent():
    user_id = session.get("user_id")
    if not user_id:
        flash(_("please_login_first"), "danger")
        return redirect(url_for("login_page"))

    role = db.session.execute(
        text("""
            SELECT r.role_name
            FROM users u
            JOIN roles r ON u.role_id = r.role_id
            WHERE u.user_id = :user_id
        """),
        {"user_id": user_id}
    ).fetchone()

    if not role or role[0] != "Support Agent":
        flash(_("access_denied"), "danger")
        return redirect(url_for("login_page"))
    return None


@support_agent_bp.route('/dashboard')
def dashboard():
    auth_check = require_agent()
    if auth_check:
        return auth_check

    user_id = session.get("user_id")

    my_total = db.session.execute(
        text("""
            SELECT COUNT(*) FROM tickets
            WHERE assigned_to = :user_id
        """),
        {"user_id": user_id}
    ).scalar()

    my_open = db.session.execute(
        text("""
            SELECT COUNT(*) FROM tickets
            WHERE assigned_to = :user_id
              AND status_name = 'Open'
        """),
        {"user_id": user_id}
    ).scalar()

    my_progress = db.session.execute(
        text("""
            SELECT COUNT(*) FROM tickets
            WHERE assigned_to = :user_id
              AND status_name = 'In Progress'
        """),
        {"user_id": user_id}
    ).scalar()

    my_resolved = db.session.execute(
        text("""
            SELECT COUNT(*) FROM tickets
            WHERE assigned_to = :user_id
              AND status_name = 'Resolved'
        """),
        {"user_id": user_id}
    ).scalar()

    my_closed = db.session.execute(
        text("""
            SELECT COUNT(*) FROM tickets
            WHERE assigned_to = :user_id
              AND status_name = 'Closed'
        """),
        {"user_id": user_id}
    ).scalar()

    recent_tickets = db.session.execute(
        text("""
            SELECT
                t.ticket_id,
                t.ticket_number,
                t.title,
                ts.status_name,
                p.priority_name,
                t.created_at
            FROM tickets t
            LEFT JOIN ticket_status ts ON t.status_name = ts.status_name
            LEFT JOIN priorities p ON t.priority_name = p.priority_name
            WHERE t.assigned_to = :user_id
            ORDER BY t.ticket_id DESC
            LIMIT 10
        """),
        {"user_id": user_id}
    ).fetchall()

    quick_tickets = db.session.execute(
        text("""
            SELECT
                t.ticket_id,
                t.ticket_number,
                t.title,
                ts.status_name,
                p.priority_name,
                t.created_at
            FROM tickets t
            LEFT JOIN ticket_status ts ON t.status_name = ts.status_name
            LEFT JOIN priorities p ON t.priority_name = p.priority_name
            WHERE t.assigned_to = :user_id
              AND t.status_name IN ('Open', 'In Progress')
            ORDER BY t.created_at DESC
            LIMIT 5
        """),
        {"user_id": user_id}
    ).fetchall()

    return render_template(
        "support_agent_dashboard.html",
        my_total=my_total,
        my_open=my_open,
        my_progress=my_progress,
        my_resolved=my_resolved,
        my_closed=my_closed,
        recent_tickets=recent_tickets,
        quick_tickets=quick_tickets
    )


@support_agent_bp.route('/tickets')
def my_tickets():
    auth_check = require_agent()
    if auth_check:
        return auth_check

    user_id = session.get("user_id")
    search = request.args.get("search", "")

    query = text("""
        SELECT
            t.ticket_id,
            t.ticket_number,
            t.title,
            t.description,
            ts.status_name,
            p.priority_name,
            c.category_name,
            t.created_at,
            t.ai_suggested_priority,
            it.issue_type_id,
            it.issue_name,
            u.first_name AS requester_first,
            u.last_name AS requester_last
        FROM tickets t
        LEFT JOIN ticket_status ts ON t.status_name = ts.status_name
        LEFT JOIN priorities p ON t.priority_name = p.priority_name
        LEFT JOIN categories c ON t.category_name = c.category_name
        LEFT JOIN users u ON t.requester_id = u.user_id
        LEFT JOIN issue_types it ON t.issue_type_id = it.issue_type_id
        WHERE t.assigned_to = :user_id
          AND (
              t.ticket_number ILIKE :search
              OR t.title ILIKE :search
          )
        ORDER BY t.ticket_id DESC
    """)

    tickets = db.session.execute(
        query,
        {"user_id": user_id, "search": f"%{search}%"}
    ).fetchall()

    return render_template(
        "agent_tickets.html",
        tickets=tickets,
        search=search
    )


@support_agent_bp.route('/ticket/<int:ticket_id>')
def ticket_detail(ticket_id):
    auth_check = require_agent()
    if auth_check:
        return auth_check

    user_id = session.get("user_id")

    ticket = db.session.execute(
        text("""
            SELECT
                t.ticket_id,
                t.ticket_number,
                t.title,
                t.description,
                ts.status_name,
                p.priority_name,
                c.category_name,
                t.created_at,
                t.ai_summary,
                t.ai_suggested_reply,
                t.ai_suggested_category,
                t.ai_suggested_department,
                t.ai_suggested_agent,
                t.ai_confidence,
                t.ai_correction_type,
                d.department_name,
                u.first_name AS requester_first,
                u.last_name AS requester_last,
                u.email AS requester_email,
                a.first_name AS agent_first,
                a.last_name AS agent_last
            FROM tickets t
            LEFT JOIN ticket_status ts ON t.status_name = ts.status_name
            LEFT JOIN priorities p ON t.priority_name = p.priority_name
            LEFT JOIN categories c ON t.category_name = c.category_name
            LEFT JOIN departments d ON t.department_id = d.department_id
            LEFT JOIN users u ON t.requester_id = u.user_id
            LEFT JOIN users a ON t.assigned_to = a.user_id
            WHERE t.ticket_id = :ticket_id
        """),
        {"ticket_id": ticket_id}
    ).fetchone()

    if not ticket:
        flash(_("ticket_not_found"), "danger")
        return redirect(url_for("support_agent.my_tickets"))

    comments = db.session.execute(
        text("""
            SELECT
                tc.comment_id,
                tc.comment_text,
                tc.created_at,
                tc.is_internal,
                u.first_name,
                u.last_name,
                r.role_name
            FROM ticket_comments tc
            JOIN users u ON tc.user_id = u.user_id
            LEFT JOIN roles r ON u.role_id = r.role_id
            WHERE tc.ticket_id = :ticket_id
            ORDER BY tc.comment_id ASC
        """),
        {"ticket_id": ticket_id}
    ).fetchall()

    attachments = db.session.execute(
        text("""
            SELECT
                ta.attachment_id,
                ta.file_name,
                ta.file_path,
                ta.uploaded_at,
                u.first_name,
                u.last_name
            FROM ticket_attachments ta
            JOIN users u ON ta.uploaded_by = u.user_id
            WHERE ta.ticket_id = :ticket_id
            ORDER BY ta.uploaded_at DESC
        """),
        {"ticket_id": ticket_id}
    ).fetchall()

    statuses = db.session.execute(
        text("SELECT status_name FROM ticket_status ORDER BY status_name")
    ).fetchall()

    sla_rule = db.session.execute(
        text("""
            SELECT response_time, resolution_time FROM sla_rules
            WHERE priority_id = (SELECT priority_id FROM priorities WHERE priority_name = (SELECT priority_name FROM tickets WHERE ticket_id = :ticket_id))
              AND status = 'Active'
            LIMIT 1
        """),
        {"ticket_id": ticket_id}
    ).fetchone()

    sla_breach = False
    try:
        from utils.notifications import check_sla_breach
        sla_breach = check_sla_breach(ticket_id)
    except Exception:
        pass

    agents = db.session.execute(
        text("SELECT user_id, first_name, last_name FROM users WHERE role_id = 3 AND status = 'Active' ORDER BY first_name")
    ).fetchall()

    # ML Prediction Data
    ml_prediction = None
    ml_sla_info = {}
    try:
        from utils.ml_service import get_prediction_for_ticket, get_sla_info_for_ticket
        ml_prediction = get_prediction_for_ticket(ticket_id)
        ml_sla_info = get_sla_info_for_ticket(ticket_id)
    except Exception:
        pass

    return render_template(
        "agent_ticket_detail.html",
        ticket=ticket,
        comments=comments,
        attachments=attachments,
        statuses=statuses,
        sla_rule=sla_rule,
        sla_breach=sla_breach,
        agents=agents,
        ml_prediction=ml_prediction,
        ml_sla_info=ml_sla_info,
    )


@support_agent_bp.route('/tickets/<int:ticket_id>/status', methods=['POST'])
def update_ticket_status(ticket_id):
    auth_check = require_agent()
    if auth_check:
        return auth_check

    user_id = session.get("user_id")

    ticket = db.session.execute(
        text("""
            SELECT ticket_id
            FROM tickets
            WHERE ticket_id = :ticket_id
              AND assigned_to = :user_id
        """),
        {"ticket_id": ticket_id, "user_id": user_id}
    ).fetchone()

    if not ticket:
        flash(_("ticket_not_found_or_not_assigned_to_you"), "danger")
        return redirect(url_for("support_agent.my_tickets"))

    new_status = request.form.get("status_name")
    if not new_status:
        flash(_("status_is_required"), "danger")
        return redirect(url_for("support_agent.ticket_detail", ticket_id=ticket_id))

    old_status_row = db.session.execute(
        text("SELECT status_name, requester_id FROM tickets WHERE ticket_id = :ticket_id"),
        {"ticket_id": ticket_id}
    ).fetchone()
    old_status = old_status_row[0] if old_status_row else None
    requester_id = old_status_row[1] if old_status_row else None

    db.session.execute(
        text("""
            UPDATE tickets
            SET status_name = :status_name,
                resolved_at = CASE
                    WHEN :new_status IN ('Resolved', 'Closed') AND resolved_at IS NULL
                    THEN :now
                    ELSE resolved_at
                END
            WHERE ticket_id = :ticket_id
        """),
        {
            "status_name": new_status,
            "new_status": new_status,
            "now": datetime.utcnow(),
            "ticket_id": ticket_id
        }
    )

    db.session.execute(
        text("""
            INSERT INTO ticket_status_history (ticket_id, old_status, new_status, changed_by)
            VALUES (:ticket_id, :old_status, :new_status, :changed_by)
        """),
        {
            "ticket_id": ticket_id,
            "old_status": old_status,
            "new_status": new_status,
            "changed_by": user_id
        }
    )

    db.session.commit()

    agent_row = db.session.execute(
        text("SELECT first_name, last_name FROM users WHERE user_id = :user_id"),
        {"user_id": user_id}
    ).fetchone()
    agent_name = f"{agent_row[0]} {agent_row[1]}".strip() if agent_row else None

    from utils.email_service import send_closed_ticket_email
    send_closed_ticket_email(ticket_id, old_status, new_status, support_agent_name=agent_name)

    ticket_info = db.session.execute(
        text("SELECT ticket_number, title, requester_id FROM tickets WHERE ticket_id = :ticket_id"),
        {"ticket_id": ticket_id}
    ).fetchone()
    if ticket_info:
        notify_ticket_status_changed(ticket_id, f"{ticket_info[0]} - {ticket_info[1]}", new_status, ticket_info[2])

    # Update ML prediction with actual resolution time
    if new_status in ('Resolved', 'Closed') and requester_id:
        try:
            from utils.ml_service import update_actual_resolution
            resolved_at = datetime.utcnow()
            created_at_row = db.session.execute(
                text("SELECT created_at FROM tickets WHERE ticket_id = :ticket_id"),
                {"ticket_id": ticket_id}
            ).fetchone()
            if created_at_row and created_at_row[0]:
                update_actual_resolution(ticket_id, resolved_at, created_at_row[0])
        except Exception:
            pass

    flash(_("ticket_status_updated_successfully"), "success")
    return redirect(url_for("support_agent.ticket_detail", ticket_id=ticket_id))


@support_agent_bp.route('/tickets/<int:ticket_id>/comment', methods=['POST'])
def add_comment(ticket_id):
    auth_check = require_agent()
    if auth_check:
        return auth_check

    user_id = session.get("user_id")

    ticket = db.session.execute(
        text("SELECT ticket_id FROM tickets WHERE ticket_id = :ticket_id AND assigned_to = :user_id"),
        {"ticket_id": ticket_id, "user_id": user_id}
    ).fetchone()

    if not ticket:
        flash(_("ticket_not_found_or_not_assigned_to_you"), "danger")
        return redirect(url_for("support_agent.my_tickets"))

    comment_text = request.form.get("comment_text")
    is_internal = request.form.get("is_internal") == "on"

    if not comment_text or not comment_text.strip():
        flash(_("comment_cannot_be_empty"), "danger")
        return redirect(url_for("support_agent.ticket_detail", ticket_id=ticket_id))

    db.session.execute(
        text("""
            INSERT INTO ticket_comments (ticket_id, user_id, comment_text, is_internal, created_at)
            VALUES (:ticket_id, :user_id, :comment_text, :is_internal, :created_at)
        """),
        {
            "ticket_id": ticket_id,
            "user_id": user_id,
            "comment_text": comment_text,
            "is_internal": is_internal,
            "created_at": datetime.utcnow()
        }
    )
    db.session.commit()

    if not is_internal:
        ticket_info = db.session.execute(
            text("SELECT ticket_number, title, requester_id FROM tickets WHERE ticket_id = :ticket_id"),
            {"ticket_id": ticket_id}
        ).fetchone()
        if ticket_info and ticket_info[2]:
            create_notification(
                ticket_info[2],
                "New Comment",
                f"New comment on ticket #{ticket_info[0]} - {ticket_info[1]}"
            )

        try:
            requester = db.session.execute(
                text("SELECT first_name, last_name, email FROM users WHERE user_id = :uid"),
                {"uid": ticket_info[2]}
            ).fetchone()
            if requester and requester[2]:
                agent_row = db.session.execute(
                    text("SELECT first_name, last_name FROM users WHERE user_id = :uid"),
                    {"uid": user_id}
                ).fetchone()
                sender_name = f"{agent_row[0]} {agent_row[1]}".strip() if agent_row else "Support Agent"
                from utils.email_service import send_ticket_reply_email
                send_ticket_reply_email(
                    ticket_number=ticket_info[0],
                    ticket_title=ticket_info[1],
                    recipient_email=requester[2],
                    customer_name=f"{requester[0] or ''} {requester[1] or ''}".strip() or "Customer",
                    reply_text=comment_text,
                    sender_name=sender_name,
                    sender_role="Support Agent"
                )
        except Exception as email_err:
            logger.warning("Failed to send ticket reply email: %s", email_err)

    flash(_("comment_added_successfully"), "success")
    return redirect(url_for("support_agent.ticket_detail", ticket_id=ticket_id))


@support_agent_bp.route('/tickets/<int:ticket_id>/upload', methods=['POST'])
def upload_attachment(ticket_id):
    auth_check = require_agent()
    if auth_check:
        return auth_check

    user_id = session.get("user_id")

    ticket = db.session.execute(
        text("SELECT ticket_id FROM tickets WHERE ticket_id = :ticket_id AND assigned_to = :user_id"),
        {"ticket_id": ticket_id, "user_id": user_id}
    ).fetchone()

    if not ticket:
        flash(_("ticket_not_found_or_not_assigned_to_you"), "danger")
        return redirect(url_for("support_agent.my_tickets"))

    if 'attachment' not in request.files:
        flash(_("no_file_selected"), "danger")
        return redirect(url_for("support_agent.ticket_detail", ticket_id=ticket_id))

    file = request.files['attachment']
    if file.filename == '':
        flash(_("no_file_selected"), "danger")
        return redirect(url_for("support_agent.ticket_detail", ticket_id=ticket_id))

    if file:
        filename = secure_filename(file.filename)
        upload_dir = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "static", "uploads", "tickets"
        )
        os.makedirs(upload_dir, exist_ok=True)
        filepath = os.path.join(upload_dir, filename)
        file.save(filepath)

        db.session.execute(
            text("""
                INSERT INTO ticket_attachments (ticket_id, file_name, file_path, uploaded_by, uploaded_at)
                VALUES (:ticket_id, :file_name, :file_path, :uploaded_by, :uploaded_at)
            """),
            {
                "ticket_id": ticket_id,
                "file_name": filename,
                "file_path": filename,
                "uploaded_by": user_id,
                "uploaded_at": datetime.utcnow()
            }
        )
        db.session.commit()

        flash(_("attachment_uploaded_successfully"), "success")

    return redirect(url_for("support_agent.ticket_detail", ticket_id=ticket_id))


@support_agent_bp.route('/tickets/<int:ticket_id>/resolve', methods=['POST'])
def resolve_ticket(ticket_id):
    auth_check = require_agent()
    if auth_check:
        return auth_check

    user_id = session.get("user_id")

    ticket = db.session.execute(
        text("""
            SELECT ticket_id, requester_id FROM tickets
            WHERE ticket_id = :ticket_id
              AND assigned_to = :user_id
        """),
        {"ticket_id": ticket_id, "user_id": user_id}
    ).fetchone()

    if not ticket:
        flash(_("ticket_not_found_or_not_assigned_to_you"), "danger")
        return redirect(url_for("support_agent.my_tickets"))

    requester_id = ticket[1]

    db.session.execute(
        text("""
            UPDATE tickets
            SET status_name = 'Resolved', resolved_at = :resolved_at
            WHERE ticket_id = :ticket_id
        """),
        {"ticket_id": ticket_id, "resolved_at": datetime.utcnow()}
    )

    db.session.execute(
        text("""
            INSERT INTO ticket_status_history (ticket_id, old_status, new_status, changed_by)
            VALUES (:ticket_id, :old_status, 'Resolved', :changed_by)
        """),
        {
            "ticket_id": ticket_id,
            "old_status": "In Progress",
            "changed_by": user_id
        }
    )

    db.session.commit()

    if requester_id:
        emit_ticket_status_change(ticket_id, 'Resolved', requester_id)

    # Update ML prediction with actual resolution time
    try:
        from utils.ml_service import update_actual_resolution
        resolved_at = datetime.utcnow()
        created_at_row = db.session.execute(
            text("SELECT created_at FROM tickets WHERE ticket_id = :ticket_id"),
            {"ticket_id": ticket_id}
        ).fetchone()
        if created_at_row and created_at_row[0]:
            update_actual_resolution(ticket_id, resolved_at, created_at_row[0])
    except Exception:
        pass

    flash(_("ticket_marked_as_resolved"), "success")
    return redirect(url_for("support_agent.ticket_detail", ticket_id=ticket_id))


@support_agent_bp.route('/tickets/<int:ticket_id>/close', methods=['POST'])
def close_ticket(ticket_id):
    auth_check = require_agent()
    if auth_check:
        return auth_check

    user_id = session.get("user_id")

    ticket = db.session.execute(
        text("""
            SELECT ticket_id, status_name, requester_id FROM tickets
            WHERE ticket_id = :ticket_id
              AND assigned_to = :user_id
        """),
        {"ticket_id": ticket_id, "user_id": user_id}
    ).fetchone()

    if not ticket:
        flash(_("ticket_not_found_or_not_assigned_to_you"), "danger")
        return redirect(url_for("support_agent.my_tickets"))

    old_status = ticket[1]
    requester_id = ticket[2]

    agent_row = db.session.execute(
        text("SELECT first_name, last_name FROM users WHERE user_id = :user_id"),
        {"user_id": user_id}
    ).fetchone()
    agent_name = f"{agent_row[0]} {agent_row[1]}".strip() if agent_row else None

    db.session.execute(
        text("""
            UPDATE tickets
            SET status_name = 'Closed', resolved_at = :resolved_at
            WHERE ticket_id = :ticket_id
        """),
        {"ticket_id": ticket_id, "resolved_at": datetime.utcnow()}
    )

    db.session.execute(
        text("""
            INSERT INTO ticket_status_history (ticket_id, old_status, new_status, changed_by)
            VALUES (:ticket_id, :old_status, 'Closed', :changed_by)
        """),
        {
            "ticket_id": ticket_id,
            "old_status": old_status,
            "changed_by": user_id
        }
    )

    db.session.commit()

    from utils.email_service import send_closed_ticket_email
    send_closed_ticket_email(ticket_id, old_status, 'Closed', support_agent_name=agent_name)

    if requester_id:
        emit_ticket_status_change(ticket_id, 'Closed', requester_id)

    # Update ML prediction with actual resolution time
    try:
        from utils.ml_service import update_actual_resolution
        resolved_at = datetime.utcnow()
        created_at_row = db.session.execute(
            text("SELECT created_at FROM tickets WHERE ticket_id = :ticket_id"),
            {"ticket_id": ticket_id}
        ).fetchone()
        if created_at_row and created_at_row[0]:
            update_actual_resolution(ticket_id, resolved_at, created_at_row[0])
    except Exception:
        pass

    flash(_("ticket_closed_successfully"), "success")
    return redirect(url_for("support_agent.ticket_detail", ticket_id=ticket_id))


@support_agent_bp.route('/tickets/<int:ticket_id>/reassign', methods=['POST'])
def reassign_ticket(ticket_id):
    auth_check = require_agent()
    if auth_check:
        return auth_check

    new_agent_id = request.form.get("assigned_to")

    if not new_agent_id:
        flash(_("please_select_an_agent"), "danger")
        return redirect(url_for("support_agent.ticket_detail", ticket_id=ticket_id))

    db.session.execute(
        text("UPDATE tickets SET assigned_to = :new_agent_id WHERE ticket_id = :ticket_id"),
        {"new_agent_id": new_agent_id, "ticket_id": ticket_id}
    )

    old_status_row = db.session.execute(
        text("SELECT status_name FROM tickets WHERE ticket_id = :ticket_id"),
        {"ticket_id": ticket_id}
    ).fetchone()
    current_status = old_status_row[0] if old_status_row else 'Open'

    db.session.execute(
        text("""
            INSERT INTO ticket_status_history (ticket_id, old_status, new_status, changed_by)
            VALUES (:ticket_id, :old_status, :new_status, :changed_by)
        """),
        {"ticket_id": ticket_id, "old_status": current_status, "new_status": current_status, "changed_by": session.get("user_id")}
    )

    db.session.commit()

    ticket = db.session.execute(
        text("SELECT ticket_number, title FROM tickets WHERE ticket_id = :ticket_id"),
        {"ticket_id": ticket_id}
    ).fetchone()
    if ticket:
        from utils.notifications import notify_ticket_assigned
        notify_ticket_assigned(ticket_id, f"{ticket[0]} - {ticket[1]}", int(new_agent_id), None)

    flash(_("ticket_reassigned_successfully"), "success")
    return redirect(url_for("support_agent.ticket_detail", ticket_id=ticket_id))


@support_agent_bp.route('/tickets/<int:ticket_id>/escalate', methods=['POST'])
def escalate_ticket(ticket_id):
    auth_check = require_agent()
    if auth_check:
        return auth_check

    reason = request.form.get("reason", "Escalated by agent")

    db.session.execute(
        text("""
            UPDATE tickets
            SET status_name = 'In Progress'
            WHERE ticket_id = :ticket_id
        """),
        {"ticket_id": ticket_id}
    )

    db.session.execute(
        text("""
            INSERT INTO ticket_status_history (ticket_id, old_status, new_status, changed_by)
            VALUES (:ticket_id, 'In Progress', 'In Progress', :changed_by)
        """),
        {"ticket_id": ticket_id, "changed_by": session.get("user_id")}
    )

    db.session.execute(
        text("""
            INSERT INTO ticket_escalations (ticket_id, escalated_by, escalated_to, reason, status)
            VALUES (:ticket_id, :escalated_by, :escalated_to, :reason, 'Active')
        """),
        {
            "ticket_id": ticket_id,
            "escalated_by": session.get("user_id"),
            "escalated_to": None,
            "reason": reason
        }
    )

    managers = db.session.execute(
        text("SELECT user_id FROM users WHERE role_id = 2 AND status = 'Active'")
    ).fetchall()

    for manager in managers:
        create_notification(
            manager[0],
            "Ticket Escalated",
            f"Ticket #{ticket_id} has been escalated."
        )

    db.session.commit()

    flash(_("ticket_escalated_successfully"), "success")
    return redirect(url_for("support_agent.ticket_detail", ticket_id=ticket_id))


@support_agent_bp.route('/profile')
def profile():
    auth_check = require_agent()
    if auth_check:
        return auth_check

    user_id = session.get("user_id")
    user = db.session.execute(
        text("""
            SELECT u.user_id, u.first_name, u.last_name, u.email, u.mobile,
                   r.role_name, d.department_name
            FROM users u
            JOIN roles r ON u.role_id = r.role_id
            LEFT JOIN departments d ON u.department_id = d.department_id
            WHERE u.user_id = :user_id
        """),
        {"user_id": user_id}
    ).fetchone()

    skills = db.session.execute(
        text("""
            SELECT s.skill_id, s.skill_name, s.category
            FROM skills s
            JOIN agent_skills ag ON s.skill_id = ag.skill_id
            WHERE ag.user_id = :user_id
            ORDER BY s.skill_name
        """),
        {"user_id": user_id}
    ).fetchall()

    return render_template("agent_profile.html", user=user, skills=skills)


@support_agent_bp.route('/notifications')
def notifications():
    auth_check = require_agent()
    if auth_check:
        return auth_check

    user_id = session.get("user_id")
    filter_type = request.args.get("filter", "all")
    search = request.args.get("search", "")

    query = """
        SELECT notification_id, title, message, is_read, created_at
        FROM notifications
        WHERE user_id = :user_id
    """
    params = {"user_id": user_id}

    if filter_type == "unread":
        query += " AND is_read = FALSE"
    elif filter_type == "read":
        query += " AND is_read = TRUE"

    if search:
        query += " AND (title ILIKE :search OR message ILIKE :search)"
        params["search"] = f"%{search}%"

    query += " ORDER BY created_at DESC"

    all_notifications = db.session.execute(text(query), params).fetchall()

    unread_count = db.session.execute(
        text("SELECT COUNT(*) FROM notifications WHERE user_id = :user_id AND is_read = FALSE"),
        {"user_id": user_id}
    ).scalar()

    return render_template(
        "agent_notifications.html",
        notifications=all_notifications,
        unread_count=unread_count,
        filter_type=filter_type,
        search=search
    )


@support_agent_bp.route('/notifications/mark-read/<int:notification_id>')
def mark_notification_read(notification_id):
    auth_check = require_agent()
    if auth_check:
        return auth_check

    user_id = session.get("user_id")
    db.session.execute(
        text("""
            UPDATE notifications
            SET is_read = TRUE
            WHERE notification_id = :notification_id
              AND user_id = :user_id
        """),
        {"notification_id": notification_id, "user_id": user_id}
    )
    db.session.commit()
    flash(_("notification_marked_as_read"), "success")
    return redirect(url_for("support_agent.notifications"))


@support_agent_bp.route('/notifications/<int:notification_id>/delete', methods=['POST'])
def delete_notification(notification_id):
    auth_check = require_agent()
    if auth_check:
        return auth_check

    user_id = session.get("user_id")
    db.session.execute(
        text("""
            DELETE FROM notifications
            WHERE notification_id = :notification_id
              AND user_id = :user_id
        """),
        {"notification_id": notification_id, "user_id": user_id}
    )
    db.session.commit()
    flash(_("notification_deleted"), "success")
    return redirect(url_for("support_agent.notifications"))


@support_agent_bp.route('/notifications/delete-all', methods=['POST'])
def delete_all_notifications():
    auth_check = require_agent()
    if auth_check:
        return jsonify({"success": False, "message": "Access Denied"}), 403

    user_id = session.get("user_id")
    try:
        result = db.session.execute(
            text("""
                DELETE FROM notifications
                WHERE user_id = :user_id
            """),
            {"user_id": user_id}
        )
        db.session.commit()
        if result.rowcount == 0:
            return jsonify({"success": True, "message": "No notifications to delete", "deleted_count": 0})
        return jsonify({"success": True, "message": "All notifications deleted successfully", "deleted_count": result.rowcount})
    except Exception:
        db.session.rollback()
        return jsonify({"success": False, "message": "Failed to delete notifications"}), 500


@support_agent_bp.route('/reports')
def reports():
    auth_check = require_agent()
    if auth_check:
        return auth_check

    user_id = session.get("user_id")

    # Status counts for the logged-in agent only
    my_total = db.session.execute(
        text("SELECT COUNT(*) FROM tickets WHERE assigned_to = :user_id"),
        {"user_id": user_id}
    ).scalar()

    my_open = db.session.execute(
        text("SELECT COUNT(*) FROM tickets WHERE assigned_to = :user_id AND status_name = 'Open'"),
        {"user_id": user_id}
    ).scalar()

    my_progress = db.session.execute(
        text("SELECT COUNT(*) FROM tickets WHERE assigned_to = :user_id AND status_name = 'In Progress'"),
        {"user_id": user_id}
    ).scalar()

    my_resolved = db.session.execute(
        text("SELECT COUNT(*) FROM tickets WHERE assigned_to = :user_id AND status_name = 'Resolved'"),
        {"user_id": user_id}
    ).scalar()

    my_closed = db.session.execute(
        text("SELECT COUNT(*) FROM tickets WHERE assigned_to = :user_id AND status_name = 'Closed'"),
        {"user_id": user_id}
    ).scalar()

    # Status chart data - query directly from tickets for agent's assigned tickets
    all_statuses = db.session.execute(
        text("SELECT status_name FROM ticket_status ORDER BY status_name")
    ).fetchall()
    status_map = {}
    for s in all_statuses:
        status_map[str(s[0])] = 0

    status_counts = db.session.execute(
        text("""
            SELECT status_name, COUNT(*) as count
            FROM tickets
            WHERE assigned_to = :user_id
              AND status_name IS NOT NULL
            GROUP BY status_name
        """),
        {"user_id": user_id}
    ).fetchall()

    for r in status_counts:
        status_map[str(r[0])] = int(r[1] or 0)

    # Include statuses with 0 count
    status_data = [[status, count] for status, count in status_map.items()]

    # Build chart data as list of [label, count] pairs
    

    # Priority chart data - query directly from tickets for agent's assigned tickets
    priority_counts = db.session.execute(
        text("""
            SELECT priority_name, COUNT(*) as count
            FROM tickets
            WHERE assigned_to = :user_id
              AND priority_name IS NOT NULL
              AND priority_name IN ('Low', 'Medium', 'High', 'Critical')
            GROUP BY priority_name
        """),
        {"user_id": user_id}
    ).fetchall()

    # Build priority map from agent's tickets only
    priority_map = {}
    for r in priority_counts:
        priority_map[str(r[0])] = int(r[1] or 0)

    # Order by priority level (Critical, High, Medium, Low)
    priority_order = ['Critical', 'High', 'Medium', 'Low']
    priority_data = []
    seen = set()
    for p in priority_order:
        if p in priority_map:
            priority_data.append([p, priority_map[p]])
            seen.add(p)
    for p, count in priority_map.items():
        if p not in seen:
            priority_data.append([p, count])

    

    # Recent assigned tickets (all statuses, sorted by created_at DESC)
    recent_tickets = db.session.execute(
        text("""
            SELECT
                t.ticket_id,
                t.ticket_number,
                t.title,
                t.priority_name,
                t.status_name,
                t.category_name,
                t.created_at,
                t.resolved_at,
                t.assigned_to,
                c.category_name AS cat_name
            FROM tickets t
            LEFT JOIN categories c ON t.category_name = c.category_name
            WHERE t.assigned_to = :user_id
            ORDER BY t.created_at DESC
            LIMIT 20
        """),
        {"user_id": user_id}
    ).fetchall()

    # Average resolution time for resolved tickets
    avg_resolution = db.session.execute(
        text("""
            SELECT AVG(EXTRACT(EPOCH FROM (resolved_at - created_at)) / 60) as avg_minutes
            FROM tickets
            WHERE assigned_to = :user_id
              AND resolved_at IS NOT NULL
              AND created_at IS NOT NULL
              AND resolved_at > created_at
        """),
        {"user_id": user_id}
    ).scalar()

    return render_template(
        "agent_reports.html",
        my_total=my_total or 0,
        my_open=my_open or 0,
        my_progress=my_progress or 0,
        my_resolved=my_resolved or 0,
        my_closed=my_closed or 0,
        status_data=status_data,
        priority_data=priority_data,
        recent_tickets=recent_tickets,
        avg_resolution=round(float(avg_resolution), 1) if avg_resolution else 0
    )
