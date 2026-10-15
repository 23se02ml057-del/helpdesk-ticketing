from flask import Blueprint, render_template, request, redirect, url_for, flash, session, jsonify
from flask_babel import gettext as _
from sqlalchemy import text
from help_db import db
from datetime import datetime
import logging
from utils.notifications import notify_ticket_assigned, notify_ticket_status_changed, check_sla_breach
import os
import sys
import subprocess

support_manager_bp = Blueprint('support_manager', __name__)
logger = logging.getLogger(__name__)


def require_manager():
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

    if not role or role[0] != "Support Manager":
        flash(_("access_denied"), "danger")
        return redirect(url_for("login_page"))
    return None


@support_manager_bp.context_processor
def inject_unread_notifications():
    user_id = session.get("user_id")
    if user_id:
        unread_count = db.session.execute(
            text("SELECT COUNT(*) FROM notifications WHERE user_id = :uid AND is_read = FALSE"),
            {"uid": user_id}
        ).scalar()
        return dict(unread_count=unread_count)
    return dict(unread_count=0)


@support_manager_bp.route('/dashboard')
def dashboard():
    auth_check = require_manager()
    if auth_check:
        return auth_check

    total_tickets = db.session.execute(
        text("SELECT COUNT(*) FROM tickets")
    ).scalar()

    open_tickets = db.session.execute(
        text("SELECT COUNT(*) FROM tickets WHERE status_name = 'Open'")
    ).scalar()

    pending_tickets = db.session.execute(
        text("SELECT COUNT(*) FROM tickets WHERE status_name = 'On Hold'")
    ).scalar()

    unassigned_tickets = db.session.execute(
        text("SELECT COUNT(*) FROM tickets WHERE assigned_to IS NULL")
    ).scalar()

    assigned_tickets = db.session.execute(
        text("SELECT COUNT(*) FROM tickets WHERE assigned_to IS NOT NULL AND status_name = 'Open'")
    ).scalar()

    closed_tickets = db.session.execute(
        text("SELECT COUNT(*) FROM tickets WHERE status_name = 'Closed'")
    ).scalar()

    escalated_tickets = db.session.execute(
        text("SELECT COUNT(DISTINCT ticket_id) FROM ticket_escalations WHERE status = 'Open' OR status IS NULL")
    ).scalar() or 0

    total_agents = db.session.execute(
        text("SELECT COUNT(*) FROM users WHERE role_id = 3")
    ).scalar()

    total_customers = db.session.execute(
        text("SELECT COUNT(*) FROM users WHERE role_id = 6")
    ).scalar()

    recent_tickets = db.session.execute(
        text("""
            SELECT
                t.ticket_id,
                t.ticket_number,
                t.title,
                t.status_name,
                t.category_name,
                p.priority_name,
                t.created_at,
                t.due_date,
                a.first_name AS agent_first,
                a.last_name AS agent_last
            FROM tickets t
            LEFT JOIN priorities p ON t.priority_name = p.priority_name
            LEFT JOIN users a ON t.assigned_to = a.user_id
            ORDER BY t.ticket_id DESC
            LIMIT 10
        """)
    ).fetchall()

    status_counts = db.session.execute(
        text("""
            SELECT status_name, COUNT(*) as ticket_count
            FROM tickets
            WHERE status_name IS NOT NULL
            GROUP BY status_name
            ORDER BY ticket_count DESC
        """)
    ).fetchall()

    priority_counts = db.session.execute(
        text("""
            SELECT priority_name, COUNT(*) as ticket_count
            FROM tickets
            WHERE priority_name IS NOT NULL
            GROUP BY priority_name
            ORDER BY ticket_count DESC
        """)
    ).fetchall()

    agent_workload = db.session.execute(
        text("""
            SELECT
                u.user_id,
                u.first_name,
                u.last_name,
                COUNT(t.ticket_id) as total_assigned,
                COUNT(CASE WHEN t.status_name IN ('Open', 'In Progress') THEN 1 END) as open_tickets,
                COUNT(CASE WHEN t.status_name = 'On Hold' THEN 1 END) as pending_tickets,
                COUNT(CASE WHEN t.status_name IN ('Resolved', 'Closed') THEN 1 END) as closed_tickets
            FROM users u
            LEFT JOIN tickets t ON u.user_id = t.assigned_to
            WHERE u.role_id = 3
            GROUP BY u.user_id, u.first_name, u.last_name
            ORDER BY open_tickets DESC
            LIMIT 10
        """)
    ).fetchall()

    sla_breaches = db.session.execute(
        text("""
            SELECT t.ticket_id, t.ticket_number, t.title, t.priority_name, t.created_at
            FROM tickets t
            JOIN sla_rules s ON t.priority_name = (
                SELECT priority_name FROM priorities WHERE priority_id = s.priority_id
            ) AND s.status = 'Active'
            WHERE t.status_name IN ('Open', 'In Progress', 'On Hold')
              AND t.due_date IS NOT NULL
              AND t.due_date < NOW()
            ORDER BY t.created_at ASC
            LIMIT 10
        """)
    ).fetchall()

    # ML SLA Risk Data for Dashboard
    ml_risk_tickets = []
    try:
        ml_risk_query = db.session.execute(text("""
            SELECT DISTINCT
                t.ticket_id,
                t.ticket_number,
                t.title,
                t.priority_name,
                t.created_at,
                t.assigned_to,
                a.first_name AS agent_first,
                a.last_name AS agent_last,
                ml.predicted_resolution_minutes,
                s.resolution_time
            FROM tickets t
            JOIN ticket_ml_predictions ml ON t.ticket_id = ml.ticket_id
            LEFT JOIN sla_rules s ON t.priority_name = (
                SELECT p.priority_name FROM priorities p WHERE p.priority_id = s.priority_id
            ) AND s.status = 'Active'
            LEFT JOIN users a ON t.assigned_to = a.user_id
            WHERE t.status_name IN ('Open', 'In Progress', 'On Hold')
              AND ml.prediction_status = 'success'
              AND ml.predicted_resolution_minutes IS NOT NULL
              AND s.resolution_time IS NOT NULL
              AND ml.predicted_resolution_minutes > s.resolution_time * 0.8 * 60
            AND ml.prediction_created_at > :one_week_ago
             ORDER BY ml.predicted_resolution_minutes DESC
             LIMIT 10
         """), {"one_week_ago": datetime.utcnow()}).fetchall()
        
        from utils.ml_service import calculate_sla_breach_risk
        for row in ml_risk_query:
            sla_hours = float(row[9]) if row[9] else None
            predicted = float(row[8]) if row[8] else None
            risk = calculate_sla_breach_risk(predicted, sla_hours) if sla_hours else "unknown"
            ml_risk_tickets.append({
                "ticket_id": row[0],
                "ticket_number": row[1],
                "title": row[2],
                "priority_name": row[3],
                "created_at": row[4],
                "agent_name": f"{row[5] or ''} {row[6] or ''}".strip() if row[5] else "Unassigned",
                "predicted_minutes": round(predicted, 1) if predicted else None,
                "sla_hours": sla_hours,
                "risk_level": risk,
            })
    except Exception:
        pass

    # ML Prediction for tickets
    ml_predictions = {}
    sla_map = {}
    try:
        ml_pred_query = db.session.execute(text("""
            SELECT t.ticket_id, mp.predicted_resolution_minutes, mp.prediction_lower_minutes,
                   mp.prediction_upper_minutes, mp.model_version
            FROM ticket_ml_predictions mp
            JOIN tickets t ON t.ticket_id = mp.ticket_id
            WHERE t.status_name IN ('Open', 'In Progress', 'On Hold')
            ORDER BY mp.prediction_created_at DESC
        """)).fetchall()
        
        sla_rows = db.session.execute(text("""
            SELECT p.priority_name, s.resolution_time
            FROM sla_rules s
            JOIN priorities p ON s.priority_id = p.priority_id
            WHERE s.status = 'Active'
        """)).fetchall()
        for srow in sla_rows:
            sla_map[srow[0]] = float(srow[1]) if srow[1] else None
        
        for prow in ml_pred_query:
            ticket_id = prow[0]
            if ticket_id not in ml_predictions:
                ml_predictions[ticket_id] = {
                    "predicted_minutes": round(float(prow[1]), 1) if prow[1] else None,
                    "lower_minutes": round(float(prow[2]), 1) if prow[2] else None,
                    "upper_minutes": round(float(prow[3]), 1) if prow[3] else None,
                    "model_version": prow[4],
                }
    except Exception:
        pass

    return render_template(
        "support_manager_dashboard.html",
        total_tickets=total_tickets,
        open_tickets=open_tickets,
        pending_tickets=pending_tickets,
        unassigned_tickets=unassigned_tickets,
        assigned_tickets=assigned_tickets,
        closed_tickets=closed_tickets,
        escalated_tickets=escalated_tickets,
        total_agents=total_agents,
        total_customers=total_customers,
        recent_tickets=recent_tickets,
        status_counts=[{"status_name": r[0], "ticket_count": r[1]} for r in status_counts],
        priority_counts=[{"priority_name": r[0], "ticket_count": r[1]} for r in priority_counts],
        sla_breaches=sla_breaches,
        ml_risk_tickets=ml_risk_tickets,
        ml_predictions=ml_predictions,
        sla_map=sla_map,
        agent_workload=agent_workload
    )


@support_manager_bp.route('/tickets')
def tickets():
    auth_check = require_manager()
    if auth_check:
        return auth_check

    search = request.args.get("search", "")

    tickets = db.session.execute(
        text("""
            SELECT
                t.ticket_id,
                t.ticket_number,
                t.title,
                t.description,
                t.status_name,
                t.priority_name,
                t.category_name,
                t.created_at,
                t.assigned_to,
                t.ai_suggested_priority,
                t.issue_type_id,
                it.issue_name,
                u.first_name AS requester_first,
                u.last_name AS requester_last,
                a.first_name AS agent_first,
                a.last_name AS agent_last
            FROM tickets t
            LEFT JOIN ticket_status ts ON t.status_name = ts.status_name
            LEFT JOIN priorities p ON t.priority_name = p.priority_name
            LEFT JOIN categories c ON t.category_name = c.category_name
            LEFT JOIN users u ON t.requester_id = u.user_id
            LEFT JOIN users a ON t.assigned_to = a.user_id
            LEFT JOIN issue_types it ON t.issue_type_id = it.issue_type_id
            WHERE
                t.ticket_number ILIKE :search OR
                t.title ILIKE :search OR
                u.email ILIKE :search
            ORDER BY t.ticket_id DESC
        """),
        {"search": f"%{search}%"}
    ).fetchall()

    statuses = db.session.execute(
        text("SELECT status_name FROM ticket_status ORDER BY status_name")
    ).fetchall()

    priorities = db.session.execute(
        text("SELECT priority_name FROM priorities ORDER BY priority_name")
    ).fetchall()

    categories = db.session.execute(
        text("SELECT category_name FROM categories ORDER BY category_name")
    ).fetchall()

    agents = db.session.execute(
        text("SELECT user_id, first_name, last_name FROM users WHERE role_id = 3 AND status = 'Active' ORDER BY first_name")
    ).fetchall()

    # ML Prediction data for tickets list
    ml_predictions_map = {}
    try:
        ml_preds = db.session.execute(text("""
            SELECT ticket_id, predicted_resolution_minutes, prediction_status, model_version
            FROM ticket_ml_predictions
            WHERE ticket_id IN (SELECT ticket_id FROM tickets)
            ORDER BY prediction_created_at DESC
        """)).fetchall()
        for mp in ml_preds:
            if mp[0] not in ml_predictions_map:
                ml_predictions_map[mp[0]] = {
                    "predicted_minutes": round(float(mp[1]), 1) if mp[1] else None,
                    "prediction_status": mp[2],
                    "model_version": mp[3],
                }
    except Exception:
        pass

    return render_template(
        "manager_tickets.html",
        tickets=tickets,
        statuses=statuses,
        priorities=priorities,
        categories=categories,
        agents=agents,
        search=search,
        ml_predictions_map=ml_predictions_map
    )


@support_manager_bp.route('/ticket/<int:ticket_id>')
def ticket_detail(ticket_id):
    auth_check = require_manager()
    if auth_check:
        return auth_check

    ticket = db.session.execute(
        text("""
            SELECT
                t.ticket_id,
                t.ticket_number,
                t.title,
                t.description,
                t.status_name,
                t.priority_name,
                t.category_name,
                t.created_at,
                t.resolved_at,
                t.assigned_to,
                t.due_date,
                t.ai_summary,
                t.ai_suggested_reply,
                t.ai_suggested_category,
                t.ai_suggested_department,
                t.ai_suggested_agent,
                t.ai_confidence,
                t.ai_correction_type,
                d.department_name,
                it.issue_name,
                u.first_name AS requester_first,
                u.last_name AS requester_last,
                u.email AS requester_email,
                a.first_name AS agent_first,
                a.last_name AS agent_last
            FROM tickets t
            LEFT JOIN departments d ON t.department_id = d.department_id
            LEFT JOIN users u ON t.requester_id = u.user_id
            LEFT JOIN users a ON t.assigned_to = a.user_id
            LEFT JOIN issue_types it ON t.issue_type_id = it.issue_type_id
            WHERE t.ticket_id = :ticket_id
        """),
        {"ticket_id": ticket_id}
    ).fetchone()

    if not ticket:
        flash(_("ticket_not_found"), "danger")
        return redirect(url_for("support_manager.tickets"))

    comments = db.session.execute(
        text("""
            SELECT
                tc.comment_id,
                tc.comment_text,
                tc.created_at,
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

    status_history = []
    try:
        status_history = db.session.execute(
            text("""
                SELECT
                    th.history_id,
                    th.old_status,
                    th.new_status,
                    th.changed_at,
                    u.first_name AS changed_by_first,
                    u.last_name AS changed_by_last,
                    r.role_name AS changed_by_role
                FROM ticket_status_history th
                LEFT JOIN users u ON th.changed_by = u.user_id
                LEFT JOIN roles r ON u.role_id = r.role_id
                WHERE th.ticket_id = :ticket_id
                ORDER BY th.changed_at DESC
            """),
            {"ticket_id": ticket_id}
        ).fetchall()
    except Exception:
        pass

    sla_breach = False
    try:
        sla_breach = check_sla_breach(ticket_id)
    except Exception:
        pass

    agents = db.session.execute(
        text("SELECT user_id, first_name, last_name FROM users WHERE role_id = 3 AND status = 'Active' ORDER BY first_name")
    ).fetchall()

    # Assignment history info
    assignment_info = db.session.execute(
        text("""
            SELECT tah.match_score, tah.assignment_reason, s.skill_name
            FROM ticket_assignment_history tah
            LEFT JOIN skills s ON tah.matched_skill_id = s.skill_id
            WHERE tah.ticket_id = :ticket_id
            ORDER BY tah.history_id DESC
            LIMIT 1
        """),
        {"ticket_id": ticket_id}
    ).fetchone()

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
        "manager_ticket_detail.html",
        ticket=ticket,
        comments=comments,
        attachments=attachments,
        statuses=statuses,
        status_history=status_history,
        sla_breach=sla_breach,
        agents=agents,
        assignment_info=assignment_info,
        ml_prediction=ml_prediction,
        ml_sla_info=ml_sla_info,
    )


@support_manager_bp.route('/ticket/<int:ticket_id>/status', methods=['POST'])
def update_ticket_status(ticket_id):
    auth_check = require_manager()
    if auth_check:
        return auth_check

    new_status = request.form.get("status_name")
    if not new_status:
        flash(_("status_is_required"), "danger")
        return redirect(url_for("support_manager.ticket_detail", ticket_id=ticket_id))

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
            INSERT INTO ticket_status_history
            (ticket_id, old_status, new_status, changed_by)
            VALUES (:ticket_id, :old_status, :new_status, :changed_by)
        """),
        {
            "ticket_id": ticket_id,
            "old_status": old_status,
            "new_status": new_status,
            "changed_by": session.get("user_id")
        }
    )

    db.session.commit()

    agent_row = db.session.execute(
        text("SELECT first_name, last_name FROM users WHERE user_id = :user_id"),
        {"user_id": session.get("user_id")}
    ).fetchone()
    agent_name = f"{agent_row[0]} {agent_row[1]}".strip() if agent_row else None

    from utils.email_service import send_closed_ticket_email
    send_closed_ticket_email(ticket_id, old_status, new_status, support_agent_name=agent_name)

    ticket = db.session.execute(
        text("SELECT ticket_number, title FROM tickets WHERE ticket_id = :ticket_id"),
        {"ticket_id": ticket_id}
    ).fetchone()
    if ticket:
        notify_ticket_status_changed(ticket_id, f"{ticket[0]} - {ticket[1]}", new_status, requester_id)

    # Update ML prediction with actual resolution time
    if new_status in ('Resolved', 'Closed'):
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
    return redirect(url_for("support_manager.ticket_detail", ticket_id=ticket_id))


@support_manager_bp.route('/ticket/<int:ticket_id>/assign', methods=['POST'])
def assign_ticket(ticket_id):
    auth_check = require_manager()
    if auth_check:
        return auth_check

    new_agent_id = request.form.get("assigned_to")
    if not new_agent_id:
        flash(_("please_select_an_agent"), "danger")
        return redirect(url_for("support_manager.ticket_detail", ticket_id=ticket_id))

    current_status_row = db.session.execute(
        text("SELECT status_name FROM tickets WHERE ticket_id = :ticket_id"),
        {"ticket_id": ticket_id}
    ).fetchone()
    current_status = current_status_row[0] if current_status_row else 'Open'

    db.session.execute(
        text("UPDATE tickets SET assigned_to = :new_agent_id WHERE ticket_id = :ticket_id"),
        {"new_agent_id": new_agent_id, "ticket_id": ticket_id}
    )

    db.session.execute(
        text("""
            INSERT INTO ticket_status_history
            (ticket_id, old_status, new_status, changed_by)
            VALUES (:ticket_id, :old_status, :new_status, :changed_by)
        """),
        {"ticket_id": ticket_id, "old_status": current_status, "new_status": current_status, "changed_by": session.get("user_id")}
    )

    db.session.commit()

    ticket = db.session.execute(
        text("SELECT ticket_number, title, requester_id FROM tickets WHERE ticket_id = :ticket_id"),
        {"ticket_id": ticket_id}
    ).fetchone()
    if ticket:
        notify_ticket_assigned(ticket_id, f"{ticket[0]} - {ticket[1]}", int(new_agent_id), ticket[2])
        try:
            agent = db.session.execute(
                text("SELECT first_name, last_name, email FROM users WHERE user_id = :uid"),
                {"uid": new_agent_id}
            ).fetchone()
            if agent and agent[2]:
                manager = db.session.execute(
                    text("SELECT first_name, last_name FROM users WHERE user_id = :uid"),
                    {"uid": session.get("user_id")}
                ).fetchone()
                assigned_by = f"{manager[0]} {manager[1]}".strip() if manager else "Support Manager"
                from utils.email_service import send_ticket_assignment_email
                send_ticket_assignment_email(
                    ticket_number=ticket[0],
                    ticket_title=ticket[1],
                    recipient_email=agent[2],
                    agent_name=f"{agent[0] or ''} {agent[1] or ''}".strip() or "Agent",
                    assigned_by_name=assigned_by
                )
        except Exception as email_err:
            logger.warning("Failed to send ticket assignment email: %s", email_err)

    flash(_("ticket_assigned_successfully_1"), "success")
    return redirect(url_for("support_manager.ticket_detail", ticket_id=ticket_id))


@support_manager_bp.route('/ticket/<int:ticket_id>/priority', methods=['POST'])
def update_ticket_priority(ticket_id):
    auth_check = require_manager()
    if auth_check:
        return auth_check

    new_priority = request.form.get("priority_name")
    if not new_priority:
        flash(_("priority_is_required"), "danger")
        return redirect(url_for("support_manager.ticket_detail", ticket_id=ticket_id))

    db.session.execute(
        text("UPDATE tickets SET priority_name = :priority_name WHERE ticket_id = :ticket_id"),
        {"priority_name": new_priority, "ticket_id": ticket_id}
    )

    db.session.execute(
        text("""
            INSERT INTO ticket_status_history
            (ticket_id, old_status, new_status, changed_by)
            VALUES (:ticket_id, :old_status, :new_status, :changed_by)
        """),
        {
            "ticket_id": ticket_id,
            "old_status": "Priority Update",
            "new_status": f"Priority changed to {new_priority}",
            "changed_by": session.get("user_id")
        }
    )

    db.session.commit()

    flash(_("ticket_priority_updated_successfully"), "success")
    return redirect(url_for("support_manager.ticket_detail", ticket_id=ticket_id))


@support_manager_bp.route('/team')
def team():
    auth_check = require_manager()
    if auth_check:
        return auth_check

    search = request.args.get("search", "")

    agents = db.session.execute(
        text("""
            SELECT
                u.user_id,
                u.first_name,
                u.last_name,
                u.email,
                u.mobile,
                u.status,
                u.created_at,
                COUNT(t.ticket_id) AS total_tickets,
                COUNT(CASE WHEN t.status_name = 'Resolved' THEN 1 END) AS resolved_tickets,
                COUNT(CASE WHEN t.status_name IN ('Open', 'In Progress') THEN 1 END) AS pending_tickets
            FROM users u
            LEFT JOIN tickets t ON u.user_id = t.assigned_to
            WHERE u.role_id = 3
            AND (
                u.first_name ILIKE :search OR
                u.last_name ILIKE :search OR
                u.email ILIKE :search
            )
            GROUP BY u.user_id
            ORDER BY u.user_id
        """),
        {"search": f"%{search}%"}
    ).fetchall()

    return render_template(
        "manager_team.html",
        agents=agents,
        search=search
    )


@support_manager_bp.route('/reports')
def reports():
    auth_check = require_manager()
    if auth_check:
        return auth_check

    total_tickets = db.session.execute(
        text("SELECT COUNT(*) FROM tickets")
    ).scalar()

    open_tickets = db.session.execute(
        text("SELECT COUNT(*) FROM tickets WHERE status_name = 'Open'")
    ).scalar()

    in_progress = db.session.execute(
        text("SELECT COUNT(*) FROM tickets WHERE status_name = 'In Progress'")
    ).scalar()

    resolved = db.session.execute(
        text("SELECT COUNT(*) FROM tickets WHERE status_name = 'Resolved'")
    ).scalar()

    closed = db.session.execute(
        text("SELECT COUNT(*) FROM tickets WHERE status_name = 'Closed'")
    ).scalar()

    status_data = db.session.execute(
        text("""
            SELECT status_name, COUNT(*) as ticket_count
            FROM tickets
            GROUP BY status_name
            ORDER BY ticket_count DESC
        """)
    ).fetchall()

    priority_data = db.session.execute(
        text("""
            SELECT priority_name, COUNT(*) as ticket_count
            FROM tickets
            GROUP BY priority_name
            ORDER BY ticket_count DESC
        """)
    ).fetchall()

    category_data = db.session.execute(
        text("""
            SELECT category_name, COUNT(*) as ticket_count
            FROM tickets
            GROUP BY category_name
            ORDER BY ticket_count DESC
        """)
    ).fetchall()

    agent_performance = db.session.execute(
        text("""
            SELECT
                u.first_name,
                u.last_name,
                COUNT(t.ticket_id) as total_tickets,
                COUNT(CASE WHEN t.status_name = 'Resolved' THEN 1 END) as resolved_tickets,
                COUNT(CASE WHEN t.status_name IN ('Open', 'In Progress') THEN 1 END) as pending_tickets
            FROM users u
            LEFT JOIN tickets t ON u.user_id = t.assigned_to
            WHERE u.role_id = 3
            GROUP BY u.user_id
            ORDER BY total_tickets DESC
        """)
    ).fetchall()

    return render_template(
        "manager_reports.html",
        total_tickets=total_tickets,
        open_tickets=open_tickets,
        in_progress=in_progress,
        resolved=resolved,
        closed=closed,
        status_data=[{"status_name": r[0], "ticket_count": r[1]} for r in status_data],
        priority_data=[{"priority_name": r[0], "ticket_count": r[1]} for r in priority_data],
        category_data=[{"category_name": r[0], "ticket_count": r[1]} for r in category_data],
        agent_performance=list(agent_performance)
    )


@support_manager_bp.route('/profile', methods=['GET', 'POST'])
def profile():
    auth_check = require_manager()
    if auth_check:
        return auth_check

    user_id = session.get("user_id")

    if request.method == 'POST':
        first_name = request.form.get("first_name", "").strip()
        last_name = request.form.get("last_name", "").strip()
        email = request.form.get("email", "").strip()
        mobile = request.form.get("mobile", "").strip()

        profile_pic_filename = None
        if 'profile_pic' in request.files:
            file = request.files['profile_pic']
            import os
            from werkzeug.utils import secure_filename
            from flask import current_app
            if file and file.filename:
                ext = file.filename.rsplit('.', 1)[-1].lower()
                if ext in ['png', 'jpg', 'jpeg', 'gif', 'webp']:
                    filename = secure_filename(f"user_{user_id}_{file.filename}")
                    upload_folder = os.path.join(current_app.root_path, 'static', 'uploads', 'profiles')
                    os.makedirs(upload_folder, exist_ok=True)
                    file.save(os.path.join(upload_folder, filename))
                    profile_pic_filename = filename
                    session['profile_pic'] = profile_pic_filename

        try:
            if profile_pic_filename:
                db.session.execute(
                    text("""
                        UPDATE users
                        SET first_name = :first_name,
                            last_name = :last_name,
                            email = :email,
                            mobile = :mobile,
                            profile_pic = :profile_pic
                        WHERE user_id = :user_id
                    """),
                    {
                        "first_name": first_name,
                        "last_name": last_name,
                        "email": email,
                        "mobile": mobile,
                        "profile_pic": profile_pic_filename,
                        "user_id": user_id
                    }
                )
            else:
                db.session.execute(
                    text("""
                        UPDATE users
                        SET first_name = :first_name,
                            last_name = :last_name,
                            email = :email,
                            mobile = :mobile
                        WHERE user_id = :user_id
                    """),
                    {
                        "first_name": first_name,
                        "last_name": last_name,
                        "email": email,
                        "mobile": mobile,
                        "user_id": user_id
                    }
                )
            db.session.commit()
            flash(_('profile_updated_successfully'), "success")
        except Exception as e:
            db.session.rollback()
            logger.exception(f"Error updating manager profile: {e}")
            flash(_('failed_to_update_profile'), "danger")

        return redirect(url_for('support_manager.profile'))

    user = db.session.execute(
        text("""
            SELECT u.user_id, u.first_name, u.last_name, u.email, u.mobile, u.profile_pic,
                   r.role_name, d.department_name
            FROM users u
            JOIN roles r ON u.role_id = r.role_id
            LEFT JOIN departments d ON u.department_id = d.department_id
            WHERE u.user_id = :user_id
        """),
        {"user_id": user_id}
    ).fetchone()

    return render_template("manager_profile.html", user=user)


@support_manager_bp.route('/ml-predictions')
def ml_predictions():
    auth_check = require_manager()
    if auth_check:
        return auth_check

    search = request.args.get("search", "")

    query = """
        SELECT
            mp.prediction_id,
            t.ticket_id,
            t.ticket_number,
            t.title,
            t.priority_name,
            t.status_name,
            mp.model_version,
            mp.predicted_resolution_minutes,
            mp.prediction_lower_minutes,
            mp.prediction_upper_minutes,
            mp.prediction_created_at,
            mp.actual_resolution_minutes,
            mp.prediction_error_minutes,
            t.created_at,
            t.resolved_at,
            s.resolution_time as sla_hours
        FROM ticket_ml_predictions mp
        JOIN tickets t ON t.ticket_id = mp.ticket_id
        LEFT JOIN sla_rules s ON t.priority_name = (
            SELECT p.priority_name FROM priorities p WHERE p.priority_id = s.priority_id
        ) AND s.status = 'Active'
        WHERE (
            t.ticket_number ILIKE :search OR
            t.title ILIKE :search
        )
        ORDER BY mp.prediction_created_at DESC
        LIMIT 200
    """

    predictions = db.session.execute(text(query), {"search": f"%{search}%"}).fetchall()

    return render_template(
        "manager_ml_predictions.html",
        predictions=predictions,
        search=search
    )


@support_manager_bp.route('/notifications')
def notifications():
    auth_check = require_manager()
    if auth_check:
        return auth_check

    user_id = session.get("user_id")
    all_notifications = db.session.execute(
        text("""
            SELECT notification_id, title, message, is_read, created_at
            FROM notifications
            WHERE user_id = :user_id
            ORDER BY created_at DESC
        """),
        {"user_id": user_id}
    ).fetchall()

    unread_count = db.session.execute(
        text("SELECT COUNT(*) FROM notifications WHERE user_id = :user_id AND is_read = FALSE"),
        {"user_id": user_id}
    ).scalar()

    return render_template("manager_notifications.html", notifications=all_notifications, unread_count=unread_count)


@support_manager_bp.route('/notifications/mark-read/<int:notification_id>')
def mark_notification_read(notification_id):
    auth_check = require_manager()
    if auth_check:
        return auth_check

    user_id = session.get("user_id")
    db.session.execute(
        text("UPDATE notifications SET is_read = TRUE WHERE notification_id = :nid AND user_id = :user_id"),
        {"nid": notification_id, "user_id": user_id}
    )
    db.session.commit()
    flash(_("notification_marked_as_read"), "success")
    return redirect(url_for("support_manager.notifications"))


@support_manager_bp.route('/notifications/delete/<int:notification_id>', methods=['POST'])
def delete_notification(notification_id):
    auth_check = require_manager()
    if auth_check:
        return auth_check

    user_id = session.get("user_id")
    db.session.execute(
        text("DELETE FROM notifications WHERE notification_id = :nid AND user_id = :user_id"),
        {"nid": notification_id, "user_id": user_id}
    )
    db.session.commit()
    flash(_("notification_deleted"), "success")
    return redirect(url_for("support_manager.notifications"))


@support_manager_bp.route('/notifications/delete-all', methods=['POST'])
def delete_all_notifications():
    auth_check = require_manager()
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


@support_manager_bp.route('/ml-model')
def ml_model():
    auth_check = require_manager()
    if auth_check:
        return auth_check

    try:
        from ml.resolution_predictor import get_resolution_predictor
        predictor = get_resolution_predictor()
        predictor.initialize()
        model_info = predictor.get_model_info()
    except Exception:
        model_info = {
            "model_version": "not_trained",
            "trained_at": None,
            "training_records": 0,
            "mae_minutes": None,
            "rmse_minutes": None,
            "r2": None,
            "model_status": "not_trained",
            "dataset_status": "no_data",
            "eligible_training_records": 0,
            "sufficient_data": False,
            "warning": "Failed to load ML model info.",
        }

    try:
        from ml.model_manager import get_model_manager
        mm = get_model_manager()
        training_stats = mm.get_training_stats()
    except Exception:
        training_stats = {
            "total_tickets": 0,
            "resolved_tickets": 0,
            "eligible_for_training": 0,
        }

    return render_template(
        "manager_ml_model.html",
        model_info=model_info,
        training_stats=training_stats,
    )


@support_manager_bp.route('/ml-model/retrain', methods=['POST'])
def retrain_model():
    auth_check = require_manager()
    if auth_check:
        return jsonify({"success": False, "message": "Access Denied"}), 403

    try:
        venv_py = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "venv", "Scripts", "python.exe"
        )
        python_exe = venv_py if os.path.exists(venv_py) else sys.executable
        result = subprocess.run(
            [python_exe, "-m", "ml.train_resolution_model"],
            capture_output=True,
            text=True,
            timeout=300,
            cwd=os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        )
        output = result.stdout + result.stderr
        success = result.returncode == 0
    except Exception as e:
        output = str(e)
        success = False

    from ml.resolution_predictor import get_resolution_predictor
    predictor = get_resolution_predictor()
    predictor.refresh()
    model_info = predictor.get_model_info()

    from ml.model_manager import get_model_manager
    mm = get_model_manager()
    training_stats = mm.get_training_stats()

    if not success:
        return render_template(
            "manager_ml_model.html",
            model_info=model_info,
            training_stats=training_stats,
            retrain_result={
                "success": False,
                "output": output,
                "message": "Model training failed. The existing model has been preserved."
            }
        )

    return render_template(
        "manager_ml_model.html",
        model_info=model_info,
        training_stats=training_stats,
        retrain_result={
            "success": True,
            "output": output
        }
    )


@support_manager_bp.route('/api/ml-predictions/search')
def api_ml_predictions_search():
    auth_check = require_manager()
    if auth_check:
        return jsonify({"error": "Access Denied"}), 403

    q = request.args.get("q", "").strip()
    params = {"search": f"%{q}%"}

    predictions = db.session.execute(text("""
        SELECT
            mp.prediction_id,
            t.ticket_id,
            t.ticket_number,
            t.title,
            t.priority_name,
            t.status_name,
            mp.model_version,
            mp.predicted_resolution_minutes,
            mp.actual_resolution_minutes,
            mp.prediction_error_minutes,
            mp.prediction_created_at,
            s.resolution_time as sla_hours
        FROM ticket_ml_predictions mp
        JOIN tickets t ON t.ticket_id = mp.ticket_id
        LEFT JOIN sla_rules s ON t.priority_name = (
            SELECT p.priority_name FROM priorities p WHERE p.priority_id = s.priority_id
        ) AND s.status = 'Active'
        WHERE (
            t.ticket_number ILIKE :search
            OR t.title ILIKE :search
            OR t.priority_name ILIKE :search
            OR t.status_name ILIKE :search
            OR mp.model_version ILIKE :search
        )
        ORDER BY mp.prediction_created_at DESC
        LIMIT 50
    """), params).fetchall()

    rows = []
    for p in predictions:
        rows.append({
            "prediction_id": p.prediction_id,
            "ticket_id": p.ticket_id,
            "ticket_number": p.ticket_number,
            "title": p.title,
            "priority_name": p.priority_name,
            "status_name": p.status_name,
            "model_version": p.model_version,
            "predicted_minutes": round(float(p.predicted_resolution_minutes), 1) if p.predicted_resolution_minutes else None,
            "actual_minutes": round(float(p.actual_resolution_minutes), 1) if p.actual_resolution_minutes else None,
            "error_minutes": round(float(p.prediction_error_minutes), 1) if p.prediction_error_minutes else None,
            "prediction_created_at": p.prediction_created_at.strftime('%Y-%m-%d %H:%M') if p.prediction_created_at else 'N/A',
            "sla_hours": round(float(p.sla_hours), 1) if p.sla_hours else None
        })

    return jsonify({"rows": rows, "count": len(rows)})
