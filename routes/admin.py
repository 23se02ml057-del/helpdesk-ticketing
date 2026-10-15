from flask import Blueprint, render_template, request, redirect, url_for, flash, session, jsonify
from flask_babel import gettext as _
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from help_db import db
import logging
from datetime import datetime
from utils.notifications import notify_ticket_assigned, notify_ticket_status_changed

admin_bp = Blueprint('admin', __name__)
logger = logging.getLogger(__name__)


def require_admin():
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

    if not role or (role[0] != "Admin" and role[0] != "Super Admin"):
        flash(_("access_denied"), "danger")
        return redirect(url_for("login_page"))
    return None


@admin_bp.context_processor
def inject_unread_notifications():
    user_id = session.get("user_id")
    if user_id:
        unread_count = db.session.execute(
            text("SELECT COUNT(*) FROM notifications WHERE user_id = :uid AND is_read = FALSE"),
            {"uid": user_id}
        ).scalar()
        return dict(unread_count=unread_count)
    return dict(unread_count=0)


@admin_bp.route('/dashboard')
def dashboard():
    auth_check = require_admin()
    if auth_check:
        return auth_check

    total_tickets = db.session.execute(
        text("SELECT COUNT(*) FROM tickets")
    ).scalar()

    open_tickets = db.session.execute(
        text("SELECT COUNT(*) FROM tickets WHERE status_name = 'Open'")
    ).scalar()

    closed = db.session.execute(
        text("SELECT COUNT(*) FROM tickets WHERE status_name = 'Closed'")
    ).scalar()

    pending = db.session.execute(
        text("SELECT COUNT(*) FROM tickets WHERE status_name = 'On Hold'")
    ).scalar()

    total_customers = db.session.execute(
        text("SELECT COUNT(*) FROM users WHERE role_id = 6")
    ).scalar()

    total_agents = db.session.execute(
        text("SELECT COUNT(*) FROM users WHERE role_id = 3")
    ).scalar()

    recent_tickets = db.session.execute(
        text("""
            SELECT
                t.ticket_id,
                t.ticket_number,
                t.title,
                t.status_name,
                t.priority_name,
                t.created_at,
                u.first_name AS requester_first,
                u.last_name AS requester_last
            FROM tickets t
            LEFT JOIN users u ON t.requester_id = u.user_id
            ORDER BY t.ticket_id DESC
            LIMIT 10
        """)
    ).fetchall()

    status_counts = db.session.execute(
        text("""
            SELECT status_name, COUNT(*) as ticket_count
            FROM tickets
            GROUP BY status_name
            ORDER BY ticket_count DESC
        """)
    ).fetchall()

    priority_counts = db.session.execute(
        text("""
            SELECT priority_name, COUNT(*) as ticket_count
            FROM tickets
            GROUP BY priority_name
            ORDER BY ticket_count DESC
        """)
    ).fetchall()

    # ML Risk Ticket Data
    ml_risk_count = 0
    try:
        from datetime import datetime as dt
        ml_risk_count = db.session.execute(text("""
            SELECT COUNT(DISTINCT t.ticket_id)
            FROM tickets t
            JOIN ticket_ml_predictions ml ON t.ticket_id = ml.ticket_id
            LEFT JOIN sla_rules s ON t.priority_name = (
                SELECT p.priority_name FROM priorities p WHERE p.priority_id = s.priority_id
            ) AND s.status = 'Active'
            WHERE t.status_name IN ('Open', 'In Progress', 'On Hold')
              AND ml.prediction_status = 'success'
              AND ml.predicted_resolution_minutes IS NOT NULL
              AND s.resolution_time IS NOT NULL
              AND ml.predicted_resolution_minutes > s.resolution_time * 60
              AND ml.prediction_created_at > :one_week_ago
        """) , {"one_week_ago": dt.utcnow() - __import__("datetime").timedelta(days=7)}).scalar() or 0
    except Exception:
        ml_risk_count = 0

    return render_template(
        "admin_dashboard.html",
        total_tickets=total_tickets,
        open_tickets=open_tickets,
        closed=closed,
        pending=pending,
        total_customers=total_customers,
        total_agents=total_agents,
        recent_tickets=recent_tickets,
        status_counts=[{"status_name": r[0], "ticket_count": r[1]} for r in status_counts],
        priority_counts=[{"priority_name": r[0], "ticket_count": r[1]} for r in priority_counts],
        ml_high_risk_count=ml_risk_count
    )


@admin_bp.route('/tickets')
def tickets():
    auth_check = require_admin()
    if auth_check:
        return auth_check

    search = request.args.get("search", "")
    page = request.args.get("page", 1, type=int)
    per_page = 10

    base_query = """
        SELECT
            t.ticket_id,
            t.ticket_number,
            t.title,
            t.status_name,
            t.priority_name,
            t.category_name,
            t.created_at,
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
    """
    count_query = """
        SELECT COUNT(*) FROM tickets t
        LEFT JOIN users u ON t.requester_id = u.user_id
        WHERE t.ticket_number ILIKE :search OR t.title ILIKE :search OR u.email ILIKE :search
    """

    total = db.session.execute(text(count_query), {"search": f"%{search}%"}).scalar()
    total_pages = max((total + per_page - 1) // per_page, 1)
    page = max(1, min(page, total_pages))
    offset = (page - 1) * per_page

    all_tickets = db.session.execute(
        text(base_query + " LIMIT :limit OFFSET :offset"),
        {"search": f"%{search}%", "limit": per_page, "offset": offset}
    ).fetchall()

    ml_predictions_map = {}
    try:
        ml_preds = db.session.execute(text("""
            SELECT ticket_id, predicted_resolution_minutes, prediction_status, model_version
            FROM ticket_ml_predictions
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
        "admin_tickets.html",
        tickets=all_tickets,
        search=search,
        ml_predictions_map=ml_predictions_map,
        pagination={
            "page": page,
            "per_page": per_page,
            "total": total,
            "total_pages": total_pages,
            "has_prev": page > 1,
            "has_next": page < total_pages,
            "prev_num": page - 1,
            "next_num": page + 1,
        },
    )


@admin_bp.route('/ticket/<int:ticket_id>')
def ticket_detail(ticket_id):
    auth_check = require_admin()
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
                t.ai_summary,
                t.ai_suggested_reply,
                t.ai_suggested_category,
                t.ai_suggested_department,
                t.ai_suggested_agent,
                t.ai_confidence,
                t.ai_correction_type,
                t.issue_type_id,
                it.issue_name,
                d.department_name,
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
        return redirect(url_for("admin.tickets"))

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

    sla_breach = False
    try:
        from utils.notifications import check_sla_breach
        sla_breach = check_sla_breach(ticket_id)
    except Exception:
        pass

    agents = db.session.execute(
        text("SELECT user_id, first_name, last_name FROM users WHERE role_id = 3 AND status = 'Active' ORDER BY first_name")
    ).fetchall()

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
        "admin_ticket_detail.html",
        ticket=ticket,
        comments=comments,
        attachments=attachments,
        statuses=statuses,
        sla_breach=sla_breach,
        agents=agents,
        ticket_assignment_info=assignment_info,
        ml_prediction=ml_prediction,
        ml_sla_info=ml_sla_info
    )


@admin_bp.route('/ticket/<int:ticket_id>/status', methods=['POST'])
def update_ticket_status(ticket_id):
    auth_check = require_admin()
    if auth_check:
        return auth_check

    new_status = request.form.get("status_name")
    if not new_status:
        flash(_("status_is_required"), "danger")
        return redirect(url_for("admin.ticket_detail", ticket_id=ticket_id))

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
        text("SELECT ticket_number, title, requester_id FROM tickets WHERE ticket_id = :ticket_id"),
        {"ticket_id": ticket_id}
    ).fetchone()
    if ticket:
        notify_ticket_status_changed(ticket_id, f"{ticket[0]} - {ticket[1]}", new_status, ticket[2])

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
    return redirect(url_for("admin.ticket_detail", ticket_id=ticket_id))


@admin_bp.route('/ticket/<int:ticket_id>/assign', methods=['POST'])
def assign_ticket(ticket_id):
    auth_check = require_admin()
    if auth_check:
        return auth_check

    new_agent_id = request.form.get("assigned_to")

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
                admin = db.session.execute(
                    text("SELECT first_name, last_name FROM users WHERE user_id = :uid"),
                    {"uid": session.get("user_id")}
                ).fetchone()
                assigned_by = f"{admin[0]} {admin[1]}".strip() if admin else "Admin"
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
    return redirect(url_for("admin.ticket_detail", ticket_id=ticket_id))


@admin_bp.route('/ticket/<int:ticket_id>/priority', methods=['POST'])
def update_ticket_priority(ticket_id):
    auth_check = require_admin()
    if auth_check:
        return auth_check

    new_priority = request.form.get("priority_name")
    if not new_priority:
        flash(_("priority_is_required"), "danger")
        return redirect(url_for("admin.ticket_detail", ticket_id=ticket_id))

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
    return redirect(url_for("admin.ticket_detail", ticket_id=ticket_id))


@admin_bp.route('/customers')
def customers():
    auth_check = require_admin()
    if auth_check:
        return auth_check

    search = request.args.get("search", "")
    page = request.args.get("page", 1, type=int)
    per_page = 10

    base_query = """
        SELECT
            u.user_id,
            u.first_name,
            u.last_name,
            u.email,
            u.mobile,
            u.department_id,
            u.status,
            u.created_at,
            COUNT(t.ticket_id) AS total_tickets
        FROM users u
        LEFT JOIN tickets t ON u.user_id = t.requester_id
        WHERE u.role_id = 6
        AND (
            u.first_name ILIKE :search OR
            u.last_name ILIKE :search OR
            u.email ILIKE :search
        )
        GROUP BY u.user_id
        ORDER BY u.user_id
    """
    count_query = """
        SELECT COUNT(*) FROM users u
        WHERE u.role_id = 6
        AND (
            u.first_name ILIKE :search OR
            u.last_name ILIKE :search OR
            u.email ILIKE :search
        )
    """

    total = db.session.execute(text(count_query), {"search": f"%{search}%"}).scalar()
    total_pages = max((total + per_page - 1) // per_page, 1)
    page = max(1, min(page, total_pages))
    offset = (page - 1) * per_page

    customers = db.session.execute(
        text(base_query + " LIMIT :limit OFFSET :offset"),
        {"search": f"%{search}%", "limit": per_page, "offset": offset}
    ).fetchall()

    departments = db.session.execute(
        text("SELECT department_id, department_name FROM departments ORDER BY department_name")
    ).fetchall()

    return render_template(
        "admin_customers.html",
        customers=customers,
        departments=departments,
        search=search,
        pagination={
            "page": page,
            "per_page": per_page,
            "total": total,
            "total_pages": total_pages,
            "has_prev": page > 1,
            "has_next": page < total_pages,
            "prev_num": page - 1,
            "next_num": page + 1,
        },
    )


@admin_bp.route('/agents')
def agents():
    auth_check = require_admin()
    if auth_check:
        return auth_check

    search = request.args.get("search", "")
    page = request.args.get("page", 1, type=int)
    per_page = 10

    base_query = """
        SELECT
            u.user_id,
            u.first_name,
            u.last_name,
            u.email,
            u.mobile,
            u.status,
            u.department_id,
            u.created_at,
            (SELECT STRING_AGG(CAST(skill_id AS TEXT), ',') FROM agent_skills WHERE user_id = u.user_id) AS skill_ids,
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
    """
    count_query = """
        SELECT COUNT(*) FROM users u
        WHERE u.role_id = 3
        AND (
            u.first_name ILIKE :search OR
            u.last_name ILIKE :search OR
            u.email ILIKE :search
        )
    """

    total = db.session.execute(text(count_query), {"search": f"%{search}%"}).scalar()
    total_pages = max((total + per_page - 1) // per_page, 1)
    page = max(1, min(page, total_pages))
    offset = (page - 1) * per_page

    all_agents = db.session.execute(
        text(base_query + " LIMIT :limit OFFSET :offset"),
        {"search": f"%{search}%", "limit": per_page, "offset": offset}
    ).fetchall()

    departments = db.session.execute(
        text("SELECT department_id, department_name FROM departments ORDER BY department_name")
    ).fetchall()

    return render_template(
        "admin_agents.html",
        agents=all_agents,
        departments=departments,
        search=search,
        pagination={
            "page": page,
            "per_page": per_page,
            "total": total,
            "total_pages": total_pages,
            "has_prev": page > 1,
            "has_next": page < total_pages,
            "prev_num": page - 1,
            "next_num": page + 1,
        },
    )


@admin_bp.route('/agents/edit/<int:agent_id>')
def edit_agent(agent_id):
    auth_check = require_admin()
    if auth_check:
        return auth_check

    agent = db.session.execute(
        text("""
            SELECT u.user_id, u.first_name, u.last_name, u.email, u.mobile,
                   u.department_id, u.status
            FROM users u
            WHERE u.user_id = :agent_id AND u.role_id = 3
        """),
        {"agent_id": agent_id}
    ).fetchone()

    if not agent:
        flash(_("agent_not_found"), "danger")
        return redirect(url_for("admin.agents"))

    departments = db.session.execute(
        text("SELECT department_id, department_name FROM departments ORDER BY department_name")
    ).fetchall()

    agent_skills = db.session.execute(
        text("""
            SELECT s.skill_id, s.skill_name
            FROM skills s
            JOIN agent_skills ag ON s.skill_id = ag.skill_id
            WHERE ag.user_id = :agent_id
            ORDER BY s.skill_name
        """),
        {"agent_id": agent_id}
    ).fetchall()

    agent_skills_list = [{"skill_id": s[0], "skill_name": s[1]} for s in agent_skills]

    return render_template(
        "admin_edit_agent.html",
        agent=agent,
        departments=departments,
        agent_skills=agent_skills_list
    )


@admin_bp.route('/agents/update/<int:agent_id>', methods=['POST'])
def update_agent(agent_id):
    auth_check = require_admin()
    if auth_check:
        return auth_check

    first_name = request.form.get("first_name")
    last_name = request.form.get("last_name")
    email = request.form.get("email")
    mobile = request.form.get("mobile")
    department_id = request.form.get("department_id")
    status = request.form.get("status")
    skills_raw = request.form.get("skills", "")

    db.session.execute(
        text("""
            UPDATE users
            SET first_name = :first_name,
                last_name = :last_name,
                email = :email,
                mobile = :mobile,
                department_id = :department_id,
                status = :status
            WHERE user_id = :agent_id AND role_id = 3
        """),
        {
            "first_name": first_name,
            "last_name": last_name,
            "email": email,
            "mobile": mobile,
            "department_id": department_id,
            "status": status,
            "agent_id": agent_id
        }
    )

    selected_skill_ids = [s.strip() for s in skills_raw.split(",") if s.strip()]
    db.session.execute(
        text("DELETE FROM agent_skills WHERE user_id = :agent_id"),
        {"agent_id": agent_id}
    )
    for skill_id in selected_skill_ids:
        try:
            db.session.execute(
                text("""
                    INSERT INTO agent_skills (user_id, skill_id)
                    VALUES (:agent_id, :skill_id)
                """),
                {"agent_id": agent_id, "skill_id": int(skill_id)}
            )
        except IntegrityError:
            db.session.rollback()

    db.session.commit()

    flash(_("agent_updated_successfully"), "success")
    return redirect(url_for("admin.agents"))


@admin_bp.route('/agents/delete/<int:agent_id>', methods=['POST'])
def delete_agent(agent_id):
    auth_check = require_admin()
    if auth_check:
        return auth_check

    try:
        db.session.execute(
            text("""
                DELETE FROM ticket_comments
                WHERE user_id = :agent_id
            """),
            {"agent_id": agent_id}
        )

        db.session.execute(
            text("""
                DELETE FROM ticket_status_history
                WHERE changed_by = :agent_id
            """),
            {"agent_id": agent_id}
        )

        db.session.execute(
            text("""
                DELETE FROM notifications
                WHERE user_id = :agent_id
            """),
            {"agent_id": agent_id}
        )

        db.session.execute(
            text("""
                DELETE FROM ticket_attachments
                WHERE uploaded_by = :agent_id
            """),
            {"agent_id": agent_id}
        )

        db.session.execute(
            text("""
                DELETE FROM password_reset_tokens
                WHERE user_id = :agent_id
            """),
            {"agent_id": agent_id}
        )

        db.session.execute(
            text("""
                DELETE FROM audit_logs
                WHERE user_id = :agent_id
            """),
            {"agent_id": agent_id}
        )

        db.session.execute(
            text("""
                UPDATE tickets
                SET assigned_to = NULL
                WHERE assigned_to = :agent_id
            """),
            {"agent_id": agent_id}
        )

        db.session.execute(
            text("""
                DELETE FROM users
                WHERE user_id = :agent_id AND role_id = 3
            """),
            {"agent_id": agent_id}
        )

        db.session.commit()
        flash(_("agent_deleted_successfully"), "success")

    except IntegrityError:
        db.session.rollback()
        flash(_("agent_cannot_be_deleted_because_they_are_linked_with_other_records_please_reassign_their_tickets_first"), "success")

    return redirect(url_for("admin.agents"))


@admin_bp.route('/customers/edit/<int:customer_id>')
def edit_customer(customer_id):
    auth_check = require_admin()
    if auth_check:
        return auth_check

    customer = db.session.execute(
        text("""
            SELECT u.user_id, u.first_name, u.last_name, u.email, u.mobile,
                   u.department_id, u.status
            FROM users u
            WHERE u.user_id = :customer_id AND u.role_id = 6
        """),
        {"customer_id": customer_id}
    ).fetchone()

    if not customer:
        flash(_("customer_not_found"), "danger")
        return redirect(url_for("admin.customers"))

    departments = db.session.execute(
        text("SELECT department_id, department_name FROM departments ORDER BY department_name")
    ).fetchall()

    return render_template(
        "admin_edit_customer.html",
        customer=customer,
        departments=departments
    )


@admin_bp.route('/customers/update/<int:customer_id>', methods=['POST'])
def update_customer(customer_id):
    auth_check = require_admin()
    if auth_check:
        return auth_check

    first_name = request.form.get("first_name")
    last_name = request.form.get("last_name")
    email = request.form.get("email")
    mobile = request.form.get("mobile")
    department_id = request.form.get("department_id")
    status = request.form.get("status")

    db.session.execute(
        text("""
            UPDATE users
            SET first_name = :first_name,
                last_name = :last_name,
                email = :email,
                mobile = :mobile,
                department_id = :department_id,
                status = :status
            WHERE user_id = :customer_id AND role_id = 6
        """),
        {
            "first_name": first_name,
            "last_name": last_name,
            "email": email,
            "mobile": mobile,
            "department_id": department_id,
            "status": status,
            "customer_id": customer_id
        }
    )
    db.session.commit()

    flash(_("customer_updated_successfully"), "success")
    return redirect(url_for("admin.customers"))


@admin_bp.route('/customers/delete/<int:customer_id>', methods=['POST'])
def delete_customer(customer_id):
    auth_check = require_admin()
    if auth_check:
        return auth_check

    try:
        db.session.execute(
            text("""
                DELETE FROM ticket_comments
                WHERE user_id = :customer_id
            """),
            {"customer_id": customer_id}
        )

        db.session.execute(
            text("""
                DELETE FROM ticket_status_history
                WHERE changed_by = :customer_id
            """),
            {"customer_id": customer_id}
        )

        db.session.execute(
            text("""
                DELETE FROM notifications
                WHERE user_id = :customer_id
            """),
            {"customer_id": customer_id}
        )

        db.session.execute(
            text("""
                DELETE FROM ticket_attachments
                WHERE uploaded_by = :customer_id
            """),
            {"customer_id": customer_id}
        )

        db.session.execute(
            text("""
                DELETE FROM password_reset_tokens
                WHERE user_id = :customer_id
            """),
            {"customer_id": customer_id}
        )

        db.session.execute(
            text("""
                DELETE FROM audit_logs
                WHERE user_id = :customer_id
            """),
            {"customer_id": customer_id}
        )

        db.session.execute(
            text("""
                UPDATE tickets
                SET requester_id = NULL
                WHERE requester_id = :customer_id
            """),
            {"customer_id": customer_id}
        )

        db.session.execute(
            text("""
                DELETE FROM users
                WHERE user_id = :customer_id AND role_id = 6
            """),
            {"customer_id": customer_id}
        )

        db.session.commit()
        flash(_("customer_deleted_successfully"), "success")

    except IntegrityError:
        db.session.rollback()
        flash(_("customer_cannot_be_deleted_because_they_are_linked_with_other_records_please_remove_all_associated_tickets_first"), "success")

    return redirect(url_for("admin.customers"))


@admin_bp.route('/reports')
def reports():
    auth_check = require_admin()
    if auth_check:
        return auth_check

    total_tickets = db.session.execute(
        text("SELECT COUNT(*) FROM tickets")
    ).scalar()

    total_customers = db.session.execute(
        text("SELECT COUNT(*) FROM users WHERE role_id = 6")
    ).scalar()

    total_agents = db.session.execute(
        text("SELECT COUNT(*) FROM users WHERE role_id = 3")
    ).scalar()

    total_employees = db.session.execute(
        text("SELECT COUNT(*) FROM users WHERE role_id = 4")
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
        "admin_reports.html",
        total_tickets=total_tickets,
        total_customers=total_customers,
        total_agents=total_agents,
        total_employees=total_employees,
        status_data=[{"status_name": r[0], "ticket_count": r[1]} for r in status_data],
        priority_data=[{"priority_name": r[0], "ticket_count": r[1]} for r in priority_data],
        category_data=[{"category_name": r[0], "ticket_count": r[1]} for r in category_data],
        agent_performance=list(agent_performance)
    )


@admin_bp.route('/profile', methods=['GET', 'POST'])
def profile():
    auth_check = require_admin()
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
            flash(_("profile_updated_successfully"), "success")
        except IntegrityError:
            db.session.rollback()
            flash(_("email_already_exists"), "danger")
        except Exception:
            db.session.rollback()
            flash(_("error_updating_profile"), "danger")
            
        return redirect(url_for('admin.profile'))

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

    return render_template("admin_profile.html", user=user)


@admin_bp.route('/notifications')
def notifications():
    auth_check = require_admin()
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
        "admin_notifications.html",
        notifications=all_notifications,
        unread_count=unread_count,
        filter_type=filter_type,
        search=search
    )


@admin_bp.route('/notifications/mark-read/<int:notification_id>')
def mark_notification_read(notification_id):
    auth_check = require_admin()
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
    return redirect(url_for("admin.notifications"))


@admin_bp.route('/notifications/<int:notification_id>/delete', methods=['POST'])
def delete_notification(notification_id):
    auth_check = require_admin()
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
    return redirect(url_for("admin.notifications"))


@admin_bp.route('/notifications/mark-all-read', methods=['POST'])
def mark_all_notifications_read():
    auth_check = require_admin()
    if auth_check:
        return auth_check

    user_id = session.get("user_id")
    db.session.execute(
        text("""
            UPDATE notifications
            SET is_read = TRUE
            WHERE user_id = :user_id AND is_read = FALSE
        """),
        {"user_id": user_id}
    )
    db.session.commit()
    flash(_("all_notifications_marked_as_read"), "success")
    return redirect(url_for("admin.notifications"))


@admin_bp.route('/notifications/delete-all-read', methods=['POST'])
def delete_all_read_notifications():
    auth_check = require_admin()
    if auth_check:
        return auth_check

    user_id = session.get("user_id")
    try:
        result = db.session.execute(
            text("""
                DELETE FROM notifications
                WHERE user_id = :user_id AND is_read = TRUE
            """),
            {"user_id": user_id}
        )
        db.session.commit()
        flash(f"{result.rowcount} read notifications deleted", "success")
    except Exception:
        db.session.rollback()
        flash(_("failed_to_delete_notifications"), "danger")
    return redirect(url_for("admin.notifications"))


@admin_bp.route('/notifications/delete-all', methods=['POST'])
def delete_all_notifications():
    auth_check = require_admin()
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


@admin_bp.route('/settings')
def settings():
    auth_check = require_admin()
    if auth_check:
        return auth_check

    all_settings = db.session.execute(
        text("SELECT * FROM settings WHERE setting_id = 1")
    ).fetchone()

    config = db.session.execute(
        text("SELECT * FROM settings LIMIT 1")
    ).fetchone()

    return render_template("admin_settings.html", config=config)


@admin_bp.route('/settings', methods=['POST'])
def update_settings():
    company_name = request.form.get("company_name", "").strip()
    company_email = request.form.get("company_email", "").strip()
    company_phone = request.form.get("company_phone", "").strip()
    company_address = request.form.get("company_address", "").strip()
    smtp_server = request.form.get("smtp_server", "").strip()
    smtp_port = request.form.get("smtp_port", "587")
    smtp_username = request.form.get("smtp_username", "").strip()
    smtp_password = request.form.get("smtp_password", "").strip()
    smtp_use_tls = request.form.get("smtp_use_tls") == "on"
    default_priority = request.form.get("default_priority", "Medium").strip()
    auto_assign_tickets = request.form.get("auto_assign_tickets") == "on"
    items_per_page = request.form.get("items_per_page", "25").strip()
    timezone = request.form.get("timezone", "UTC").strip()

    try:
        smtp_port_int = int(smtp_port)
        items_per_page_int = int(items_per_page)
    except ValueError:
        flash(_("invalid_port_or_items_per_page_value"), "danger")
        return redirect(url_for("admin.settings"))

    db.session.execute(text("""
        UPDATE settings SET
            company_name = :company_name,
            company_email = :company_email,
            company_phone = :company_phone,
            company_address = :company_address,
            smtp_server = :smtp_server,
            smtp_port = :smtp_port,
            smtp_username = :smtp_username,
            smtp_password = :smtp_password,
            smtp_use_tls = :smtp_use_tls,
            default_priority = :default_priority,
            auto_assign_tickets = :auto_assign_tickets,
            items_per_page = :items_per_page,
            timezone = :timezone,
            updated_at = CURRENT_TIMESTAMP
    """),
    {
        "company_name": company_name,
        "company_email": company_email,
        "company_phone": company_phone,
        "company_address": company_address,
        "smtp_server": smtp_server,
        "smtp_port": smtp_port_int,
        "smtp_username": smtp_username,
        "smtp_password": smtp_password,
        "smtp_use_tls": smtp_use_tls,
        "default_priority": default_priority,
        "auto_assign_tickets": auto_assign_tickets,
        "items_per_page": items_per_page_int,
        "timezone": timezone
    })
    db.session.commit()
    flash(_("settings_updated_successfully"), "success")
    return redirect(url_for("admin.settings"))


@admin_bp.route('/types-of-issue')
def admin_types_of_issue():
    auth_check = require_admin()
    if auth_check:
        return auth_check

    search = request.args.get("search", "")
    category_filter = request.args.get("category_name", "")

    query = """
        SELECT it.issue_type_id, it.issue_name, it.category_name, it.description, it.status, it.created_at,
               c.category_name as category_display
        FROM issue_types it
        JOIN categories c ON it.category_name = c.category_name
        WHERE 1=1
    """
    params = {}

    if search:
        query += " AND (it.issue_name ILIKE :search OR it.description ILIKE :search)"
        params["search"] = f"%{search}%"

    if category_filter:
        query += " AND it.category_name = :category_name"
        params["category_name"] = category_filter

    query += " ORDER BY it.category_name, it.issue_name"

    issue_types = db.session.execute(text(query), params).fetchall()

    categories = db.session.execute(
        text("SELECT category_name FROM categories ORDER BY category_name")
    ).fetchall()

    return render_template(
        "admin/types_of_issue.html",
        issue_types=issue_types,
        categories=categories,
        search=search,
        category_filter=category_filter
    )


# ===========================
# Admin Categories Management
# ===========================

@admin_bp.route('/categories')
def admin_categories():
    auth_check = require_admin()
    if auth_check:
        return auth_check

    search = request.args.get("search", "")

    query = """
        SELECT category_name, created_at
        FROM categories
        WHERE 1=1
    """
    params = {}

    if search:
        query += " AND category_name ILIKE :search"
        params["search"] = f"%{search}%"

    query += " ORDER BY category_name"

    categories = db.session.execute(text(query), params).fetchall()

    return render_template(
        "admin/categories.html",
        categories=categories,
        search=search
    )


# ===========================
# Admin Skills Management
# ===========================

@admin_bp.route('/skills')
def admin_skills():
    auth_check = require_admin()
    if auth_check:
        return auth_check

    search = request.args.get("search", "")
    department_filter = request.args.get("department_id", "")
    category_filter = request.args.get("category_name", "")
    status_filter = request.args.get("status", "")

    query = """
        SELECT s.skill_id, s.skill_name, s.category, s.status, s.created_at,
               d.department_name, c.category_name as category_display
        FROM skills s
        LEFT JOIN categories c ON s.category = c.category_name
        LEFT JOIN departments d ON c.department_id = d.department_id
        WHERE 1=1
    """
    params = {}

    if search:
        query += " AND (s.skill_name ILIKE :search OR s.category ILIKE :search OR d.department_name ILIKE :search)"
        params["search"] = f"%{search}%"

    if department_filter:
        query += " AND d.department_id = :department_id"
        params["department_id"] = department_filter

    if category_filter:
        query += " AND s.category = :category_name"
        params["category_name"] = category_filter

    if status_filter:
        query += " AND s.status = :status"
        params["status"] = status_filter

    query += " ORDER BY s.skill_id DESC"

    skills = db.session.execute(text(query), params).fetchall()

    total_skills = db.session.execute(
        text("SELECT COUNT(*) FROM skills")
    ).scalar()

    active_skills = db.session.execute(
        text("SELECT COUNT(*) FROM skills WHERE status='Active'")
    ).scalar()

    departments = db.session.execute(
        text("SELECT department_id, department_name FROM departments ORDER BY department_name")
    ).fetchall()

    categories = db.session.execute(
        text("SELECT category_name, department_id FROM categories ORDER BY category_name")
    ).fetchall()

    return render_template(
        "admin_skills.html",
        skills=skills,
        total_skills=total_skills,
        active_skills=active_skills,
        departments=departments,
        categories=categories,
        search=search,
        department_filter=department_filter,
        category_filter=category_filter,
        status_filter=status_filter,
        can_edit=True
    )


@admin_bp.route('/skills/add')
def admin_add_skill():
    auth_check = require_admin()
    if auth_check:
        return auth_check

    departments = db.session.execute(
        text("SELECT department_id, department_name FROM departments ORDER BY department_name")
    ).fetchall()

    return render_template("admin_add_skill.html", departments=departments)


@admin_bp.route('/skills/save', methods=['POST'])
def admin_save_skill():
    auth_check = require_admin()
    if auth_check:
        return auth_check

    skill_name = request.form.get("skill_name", "").strip()
    category = request.form.get("category_name", "").strip()
    status = request.form.get("status", "Active").strip()

    if not skill_name or not category:
        flash(_("skill_name_and_category_are_required"), "danger")
        return redirect(url_for("admin.admin_add_skill"))

    existing = db.session.execute(
        text("SELECT 1 FROM skills WHERE LOWER(skill_name) = LOWER(:skill_name)"),
        {"skill_name": skill_name}
    ).fetchone()

    if existing:
        flash(_("skill_already_exists"), "warning")
        return redirect(url_for("admin.admin_skills"))

    try:
        db.session.execute(
            text("""
                INSERT INTO skills (skill_name, category, status)
                VALUES (:skill_name, :category, :status)
            """),
            {
                "skill_name": skill_name,
                "category": category,
                "status": status
            }
        )
        db.session.commit()
        flash(_("skill_added_successfully"), "success")
    except IntegrityError:
        db.session.rollback()
        flash(_("error_adding_skill"), "danger")

    return redirect(url_for("admin.admin_skills"))


@admin_bp.route('/skills/edit/<int:id>')
def admin_edit_skill(id):
    auth_check = require_admin()
    if auth_check:
        return auth_check

    skill = db.session.execute(
        text("""
            SELECT s.skill_id, s.skill_name, s.category, s.status, c.department_id
            FROM skills s
            LEFT JOIN categories c ON s.category = c.category_name
            WHERE s.skill_id = :id
        """),
        {"id": id}
    ).fetchone()

    if not skill:
        flash(_("skill_not_found"), "danger")
        return redirect(url_for("admin.admin_skills"))

    departments = db.session.execute(
        text("SELECT department_id, department_name FROM departments ORDER BY department_name")
    ).fetchall()

    categories = db.session.execute(
        text("SELECT category_name, department_id FROM categories ORDER BY category_name")
    ).fetchall()

    return render_template(
        "admin_edit_skill.html",
        skill=skill,
        departments=departments,
        categories=categories
    )


@admin_bp.route('/skills/update/<int:id>', methods=['POST'])
def admin_update_skill(id):
    auth_check = require_admin()
    if auth_check:
        return auth_check

    skill_name = request.form.get("skill_name", "").strip()
    category = request.form.get("category_name", "").strip()
    status = request.form.get("status", "Active").strip()

    if not skill_name or not category:
        flash(_("skill_name_and_category_are_required"), "danger")
        return redirect(url_for("admin.admin_edit_skill", id=id))

    existing = db.session.execute(
        text("""
            SELECT 1 FROM skills
            WHERE LOWER(skill_name) = LOWER(:skill_name)
            AND skill_id != :id
        """),
        {"skill_name": skill_name, "id": id}
    ).fetchone()

    if existing:
        flash(_("another_skill_with_this_name_already_exists"), "warning")
        return redirect(url_for("admin.admin_edit_skill", id=id))

    try:
        db.session.execute(
            text("""
                UPDATE skills
                SET skill_name = :skill_name,
                    category = :category,
                    status = :status
                WHERE skill_id = :id
            """),
            {
                "skill_name": skill_name,
                "category": category,
                "status": status,
                "id": id
            }
        )
        db.session.commit()
        flash(_("skill_updated_successfully"), "success")
    except IntegrityError:
        db.session.rollback()
        flash(_("error_updating_skill"), "danger")

    return redirect(url_for("admin.admin_skills"))


@admin_bp.route('/skills/delete/<int:id>', methods=['POST'])
def admin_delete_skill(id):
    auth_check = require_admin()
    if auth_check:
        return auth_check

    try:
        db.session.execute(
            text("DELETE FROM agent_skills WHERE skill_id = :id"),
            {"id": id}
        )
        db.session.execute(
            text("DELETE FROM skills WHERE skill_id = :id"),
            {"id": id}
        )
        db.session.commit()
        flash(_("skill_deleted_successfully"), "success")
    except IntegrityError:
        db.session.rollback()
        flash(_("error_deleting_skill"), "danger")

    return redirect(url_for("admin.admin_skills"))


# ===========================
# Admin Live Search API
# ===========================

@admin_bp.route('/api/tickets/search')
def api_tickets_search():
    auth_check = require_admin()
    if auth_check:
        return jsonify({"error": "Access Denied"}), 403

    q = request.args.get("q", "").strip()
    params = {"search": f"%{q}%"}

    query = text("""
        SELECT
            t.ticket_id,
            t.ticket_number,
            t.title,
            t.status_name,
            t.priority_name,
            t.category_name,
            t.created_at,
            it.issue_name,
            u.first_name AS requester_first,
            u.last_name AS requester_last,
            a.first_name AS agent_first,
            a.last_name AS agent_last
        FROM tickets t
        LEFT JOIN issue_types it ON t.issue_type_id = it.issue_type_id
        LEFT JOIN users u ON t.requester_id = u.user_id
        LEFT JOIN users a ON t.assigned_to = a.user_id
        WHERE
            t.ticket_number ILIKE :search
            OR t.title ILIKE :search
            OR u.first_name ILIKE :search
            OR u.last_name ILIKE :search
            OR u.email ILIKE :search
            OR t.category_name ILIKE :search
            OR t.status_name ILIKE :search
            OR t.priority_name ILIKE :search
        ORDER BY t.ticket_id DESC
        LIMIT 50
    """)

    tickets = db.session.execute(query, params).fetchall()

    ml_map = {}
    try:
        ml_preds = db.session.execute(text("""
            SELECT ticket_id, predicted_resolution_minutes, model_version
            FROM ticket_ml_predictions
            ORDER BY prediction_created_at DESC
        """)).fetchall()
        for mp in ml_preds:
            if mp[0] not in ml_map:
                ml_map[mp[0]] = {
                    "ml_minutes": round(float(mp[1]), 1) if mp[1] else None,
                    "ml_model": mp[2]
                }
    except Exception:
        pass

    rows = []
    for t in tickets:
        ml = ml_map.get(t.ticket_id, {})
        rows.append({
            "ticket_id": t.ticket_id,
            "ticket_number": t.ticket_number,
            "title": t.title,
            "status_name": t.status_name,
            "priority_name": t.priority_name,
            "category_name": t.category_name,
            "created_at": t.created_at.strftime('%Y-%m-%d') if t.created_at else 'N/A',
            "issue_name": t.issue_name,
            "requester_first": t.requester_first,
            "requester_last": t.requester_last,
            "agent_first": t.agent_first,
            "agent_last": t.agent_last,
            "ml_minutes": ml.get("ml_minutes"),
            "ml_model": ml.get("ml_model")
        })

    return jsonify({"rows": rows, "count": len(rows)})


@admin_bp.route('/api/customers/search')
def api_customers_search():
    auth_check = require_admin()
    if auth_check:
        return jsonify({"error": "Access Denied"}), 403

    q = request.args.get("q", "").strip()
    status = request.args.get("status", "").strip()
    
    query = """
        SELECT
            u.user_id,
            u.first_name,
            u.last_name,
            u.email,
            u.mobile,
            u.status,
            u.created_at,
            COUNT(t.ticket_id) AS total_tickets
        FROM users u
        LEFT JOIN tickets t ON u.user_id = t.requester_id
        WHERE u.role_id = 6
    """
    params = {}

    if q:
        query += """
            AND (
                u.first_name ILIKE :search
                OR u.last_name ILIKE :search
                OR u.email ILIKE :search
                OR u.mobile ILIKE :search
            )
        """
        params["search"] = f"%{q}%"

    if status:
        query += " AND u.status = :status"
        params["status"] = status

    query += """
        GROUP BY u.user_id
        ORDER BY u.user_id
        LIMIT 50
    """

    customers = db.session.execute(text(query), params).fetchall()

    rows = []
    for c in customers:
        rows.append({
            "user_id": c.user_id,
            "first_name": c.first_name,
            "last_name": c.last_name,
            "email": c.email,
            "mobile": c.mobile,
            "status": c.status,
            "total_tickets": c.total_tickets or 0,
            "created_at": c.created_at.strftime('%Y-%m-%d') if c.created_at else 'N/A'
        })

    return jsonify({"rows": rows, "count": len(rows)})


@admin_bp.route('/api/agents/search')
def api_agents_search():
    auth_check = require_admin()
    if auth_check:
        return jsonify({"error": "Access Denied"}), 403

    q = request.args.get("q", "").strip()
    params = {"search": f"%{q}%"}

    agents = db.session.execute(text("""
        SELECT
            u.user_id,
            u.first_name,
            u.last_name,
            u.email,
            u.mobile,
            u.status,
            u.department_id,
            u.created_at,
            (SELECT STRING_AGG(CAST(skill_id AS TEXT), ',') FROM agent_skills WHERE user_id = u.user_id) AS skill_ids,
            COUNT(t.ticket_id) AS total_tickets,
            COUNT(CASE WHEN t.status_name = 'Resolved' THEN 1 END) AS resolved_tickets,
            COUNT(CASE WHEN t.status_name IN ('Open', 'In Progress') THEN 1 END) AS pending_tickets
        FROM users u
        LEFT JOIN tickets t ON u.user_id = t.assigned_to
        WHERE u.role_id = 3
          AND (
              u.first_name ILIKE :search
              OR u.last_name ILIKE :search
              OR u.email ILIKE :search
              OR u.mobile ILIKE :search
          )
        GROUP BY u.user_id
        ORDER BY u.user_id
        LIMIT 50
    """), params).fetchall()

    rows = []
    for a in agents:
        rows.append({
            "user_id": a.user_id,
            "first_name": a.first_name,
            "last_name": a.last_name,
            "email": a.email,
            "mobile": a.mobile,
            "status": a.status,
            "department_id": a.department_id,
            "skill_ids": a.skill_ids,
            "total_tickets": a.total_tickets or 0,
            "resolved_tickets": a.resolved_tickets or 0,
            "pending_tickets": a.pending_tickets or 0,
            "created_at": a.created_at.strftime('%Y-%m-%d') if a.created_at else 'N/A'
        })

    return jsonify({"rows": rows, "count": len(rows)})


@admin_bp.route('/api/skills/search')
def api_skills_search():
    auth_check = require_admin()
    if auth_check:
        return jsonify({"error": "Access Denied"}), 403

    q = request.args.get("q", "").strip()
    status_filter = request.args.get("status", "")
    department_filter = request.args.get("department_id", "")
    category_filter = request.args.get("category_name", "")

    params = {"search": f"%{q}%"}

    query = """
        SELECT s.skill_id, s.skill_name, s.category, s.status, s.created_at,
               d.department_name, c.category_name as category_display
        FROM skills s
        LEFT JOIN categories c ON s.category = c.category_name
        LEFT JOIN departments d ON c.department_id = d.department_id
        WHERE 1=1
    """

    if q:
        query += " AND (s.skill_name ILIKE :search OR s.category ILIKE :search OR d.department_name ILIKE :search)"
    if status_filter:
        query += " AND s.status = :status"
        params["status"] = status_filter
    if department_filter:
        query += " AND d.department_id = :department_id"
        params["department_id"] = department_filter
    if category_filter:
        query += " AND s.category = :category_name"
        params["category_name"] = category_filter

    query += " ORDER BY s.skill_id DESC"

    skills = db.session.execute(text(query), params).fetchall()

    rows = []
    for s in skills:
        rows.append({
            "skill_id": s.skill_id,
            "skill_name": s.skill_name,
            "category": s.category,
            "status": s.status,
            "created_at": s.created_at.strftime('%d %b %Y, %I:%M %p') if s.created_at else '-',
            "department_name": s.department_name,
            "category_display": s.category_display
        })

    return jsonify({"rows": rows, "count": len(rows)})


@admin_bp.route('/api/types-of-issue/search')
def api_types_of_issue_search():
    auth_check = require_admin()
    if auth_check:
        return jsonify({"error": "Access Denied"}), 403

    q = request.args.get("q", "").strip()
    params = {"search": f"%{q}%"}

    issue_types = db.session.execute(text("""
        SELECT it.issue_type_id, it.issue_name, it.category_name, it.description, it.status,
               c.category_name as category_display
        FROM issue_types it
        JOIN categories c ON it.category_name = c.category_name
        WHERE it.issue_name ILIKE :search
           OR it.description ILIKE :search
           OR c.category_name ILIKE :search
        ORDER BY it.issue_type_id DESC
        LIMIT 50
    """), params).fetchall()

    rows = []
    for it in issue_types:
        rows.append({
            "issue_type_id": it.issue_type_id,
            "issue_name": it.issue_name,
            "category_name": it.category_name,
            "description": it.description,
            "status": it.status,
            "category_display": it.category_display
        })

    return jsonify({"rows": rows, "count": len(rows)})


@admin_bp.route('/api/notifications/search')
def api_notifications_search():
    auth_check = require_admin()
    if auth_check:
        return jsonify({"error": "Access Denied"}), 403

    q = request.args.get("q", "").strip()
    user_id = session.get("user_id")
    params = {"user_id": user_id, "search": f"%{q}%"}

    notifications = db.session.execute(text("""
        SELECT notification_id, title, message, is_read, created_at
        FROM notifications
        WHERE user_id = :user_id
          AND (title ILIKE :search OR message ILIKE :search)
        ORDER BY created_at DESC
        LIMIT 50
    """), params).fetchall()

    rows = []
    for n in notifications:
        rows.append({
            "notification_id": n.notification_id,
            "title": n.title,
            "message": n.message,
            "is_read": n.is_read,
            "created_at": n.created_at.strftime('%Y-%m-%d %H:%M') if n.created_at else 'N/A'
        })

    return jsonify({"rows": rows, "count": len(rows)})
