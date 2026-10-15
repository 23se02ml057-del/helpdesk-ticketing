from flask import Blueprint, render_template, request, redirect, flash, url_for, session, Response, jsonify
from flask_babel import gettext as _
from sqlalchemy import text
from help_db import db
import csv
from datetime import datetime, timedelta
import io
from io import StringIO
from flask import Blueprint, render_template, request, flash, redirect, url_for, Response, send_file
from fpdf import FPDF
reports_bp = Blueprint('reports', __name__)


def require_login():
    user_id = session.get("user_id")
    if not user_id:
        flash(_("please_login_first"), "danger")
        return redirect(url_for("login_page"))
    return None


def generate_agent_reports(period_start: datetime, period_end: datetime, role_filter: str = 'Support Agent', status_filter: str = 'Active'):
    agents = db.session.execute(text("""
        SELECT u.user_id, u.first_name, u.last_name
        FROM users u
        JOIN roles r ON u.role_id = r.role_id
        WHERE r.role_name = :role_filter AND u.status = :status_filter
        ORDER BY u.user_id
    """), {'role_filter': role_filter, 'status_filter': status_filter}).fetchall()

    for agent in agents:
        agent_id = agent[0]

        existing = db.session.execute(text("""
            SELECT report_id FROM agent_reports
            WHERE agent_id = :agent_id
              AND report_period_start = :period_start
        """), {
            'agent_id': agent_id,
            'period_start': period_start
        }).fetchone()

        if existing:
            continue

        stats = db.session.execute(text("""
            SELECT
                COUNT(*) as total_tickets,
                SUM(CASE WHEN status_name = 'Resolved' THEN 1 ELSE 0 END) as resolved_tickets,
                SUM(CASE WHEN status_name = 'Closed' THEN 1 ELSE 0 END) as closed_tickets,
                SUM(CASE WHEN status_name IN ('Open', 'In Progress') THEN 1 ELSE 0 END) as pending_tickets,
                SUM(CASE WHEN status_name = 'In Progress' THEN 1 ELSE 0 END) as in_progress_tickets,
                SUM(CASE WHEN status_name = 'New' THEN 1 ELSE 0 END) as new_tickets,
                SUM(CASE WHEN status_name = 'On Hold' THEN 1 ELSE 0 END) as on_hold_tickets,
                SUM(CASE WHEN reopen_count > 0 THEN 1 ELSE 0 END) as reopened_tickets
            FROM tickets
            WHERE assigned_to = :agent_id
              AND created_at >= :period_start
              AND created_at <= :period_end
        """), {
            'agent_id': agent_id,
            'period_start': period_start,
            'period_end': period_end
        }).fetchone()

        db.session.execute(text("""
            INSERT INTO agent_reports (
                agent_id, report_period_start, report_period_end,
                total_tickets, resolved_tickets, closed_tickets,
                pending_tickets, in_progress_tickets, new_tickets,
                on_hold_tickets, reopened_tickets, created_at
            ) VALUES (
                :agent_id, :period_start, :period_end,
                :total, :resolved, :closed,
                :pending, :in_progress, :new,
                :on_hold, :reopened, :created_at
            )
        """), {
            'agent_id': agent_id,
            'period_start': period_start,
            'period_end': period_end,
            'total': stats[0] or 0,
            'resolved': stats[1] or 0,
            'closed': stats[2] or 0,
            'pending': stats[3] or 0,
            'in_progress': stats[4] or 0,
            'new': stats[5] or 0,
            'on_hold': stats[6] or 0,
            'reopened': stats[7] or 0,
            'created_at': datetime.utcnow()
        })

    db.session.commit()


@reports_bp.route("/reports")
def reports():
    auth_check = require_login()
    if auth_check:
        return auth_check

    total_users = db.session.execute(text("""
        SELECT COUNT(*) FROM users WHERE role_id != 6
    """)).scalar()

    total_tickets = db.session.execute(text("""
        SELECT COUNT(*) FROM tickets
    """)).scalar()

    open_tickets = db.session.execute(text("""
        SELECT COUNT(*) FROM tickets WHERE status_name = 'Open'
    """)).scalar()

    closed_tickets = db.session.execute(text("""
        SELECT COUNT(*) FROM tickets WHERE status_name = 'Closed'
    """)).scalar()

    total_sla = db.session.execute(text("""
        SELECT COUNT(*) FROM sla_rules
    """)).scalar()

    total_escalation = db.session.execute(text("""
        SELECT COUNT(*) FROM escalations
    """)).scalar()

    total_notifications = db.session.execute(text("""
        SELECT COUNT(*) FROM notifications
    """)).scalar()

    return render_template(
        "reports.html",
        total_users=total_users,
        total_tickets=total_tickets,
        open_tickets=open_tickets,
        closed_tickets=closed_tickets,
        total_sla=total_sla,
        total_escalation=total_escalation,
        total_notifications=total_notifications,
    )


@reports_bp.route("/reports/agent-performance")
def agent_performance_report():
    auth_check = require_login()
    if auth_check:
        return auth_check

    period_days = request.args.get("period", "30")
    try:
        period_days = int(period_days)
    except ValueError:
        period_days = 30

    user_status = request.args.get("status", "Active")
    role_filter = request.args.get("role", "Support Agent")

    period_end = datetime.utcnow()
    period_start = period_end - timedelta(days=period_days)
    period_key = period_start.replace(hour=0, minute=0, second=0, microsecond=0)

    generate_agent_reports(period_start=period_key, period_end=period_end, role_filter=role_filter, status_filter=user_status)

    agent_reports = db.session.execute(text("""
        SELECT
            ar.report_id,
            u.user_id,
            u.first_name,
            u.last_name,
            ar.total_tickets,
            ar.resolved_tickets,
            ar.closed_tickets,
            ar.pending_tickets,
            ar.in_progress_tickets,
            ar.new_tickets,
            ar.on_hold_tickets,
            ar.reopened_tickets,
            ar.report_period_start,
            ar.report_period_end
        FROM agent_reports ar
        JOIN users u ON ar.agent_id = u.user_id
        JOIN roles r ON u.role_id = r.role_id
        WHERE ar.report_period_start = :period_key
          AND u.status = :user_status
          AND r.role_name = :role_filter
        ORDER BY ar.total_tickets DESC
    """), {
        'period_key': period_key,
        'user_status': user_status,
        'role_filter': role_filter
    }).fetchall()

    return render_template(
        "agent_performance_report.html",
        agent_reports=agent_reports,
        report_period_start=period_key,
        report_period_end=period_end,
    )


@reports_bp.route("/ticket-report")
def ticket_report():
    auth_check = require_login()
    if auth_check:
        return auth_check

    status = request.args.get("status", "").strip()
    priority = request.args.get("priority", "").strip()
    category = request.args.get("category", "").strip()
    date_from = request.args.get("date_from", "").strip()
    date_to = request.args.get("date_to", "").strip()

    query = """
        SELECT
            t.ticket_id,
            t.ticket_number,
            t.title,
            s.status_name,
            p.priority_name,
            c.category_name,
            u.first_name AS requester,
            t.created_at
        FROM tickets t
        LEFT JOIN ticket_status s ON t.status_name = s.status_name
        LEFT JOIN priorities p ON t.priority_name = p.priority_name
        LEFT JOIN categories c ON t.category_name = c.category_name
        LEFT JOIN users u ON t.requester_id = u.user_id
        WHERE 1=1
    """
    params = {}

    if status:
        query += " AND t.status_name = :status"
        params["status"] = status

    if priority:
        query += " AND t.priority_name = :priority"
        params["priority"] = priority

    if category:
        query += " AND t.category_name = :category"
        params["category"] = category

    if date_from:
        query += " AND DATE(t.created_at) >= :date_from"
        params["date_from"] = date_from

    if date_to:
        query += " AND DATE(t.created_at) <= :date_to"
        params["date_to"] = date_to

    query += " ORDER BY t.ticket_id DESC"

    report_data = db.session.execute(text(query), params).fetchall()

    statuses = db.session.execute(text("SELECT status_name FROM ticket_status ORDER BY status_name")).fetchall()
    priorities = db.session.execute(text("SELECT priority_name FROM priorities ORDER BY priority_name")).fetchall()
    categories = db.session.execute(text("SELECT category_name FROM categories ORDER BY category_name")).fetchall()

    return render_template(
        "ticket_report.html",
        report_data=report_data,
        statuses=statuses,
        priorities=priorities,
        categories=categories,
        filters={
            "status": status,
            "priority": priority,
            "category": category,
            "date_from": date_from,
            "date_to": date_to,
        },
    )

@reports_bp.route("/user-report")
def user_report():
    auth_check = require_login()
    if auth_check:
        return auth_check

    role = request.args.get("role", "").strip()
    status = request.args.get("status", "").strip()
    date_from = request.args.get("date_from", "").strip()
    date_to = request.args.get("date_to", "").strip()

    query = """
        SELECT
            u.user_id,
            u.first_name,
            u.last_name,
            u.email,
            r.role_name,
            d.department_name,
            u.status,
            u.created_at
        FROM users u
        LEFT JOIN roles r ON u.role_id = r.role_id
        LEFT JOIN departments d ON u.department_id = d.department_id
        WHERE u.role_id != 6
    """
    params = {}

    if role:
        query += " AND r.role_name = :role"
        params["role"] = role

    if status:
        query += " AND u.status = :status"
        params["status"] = status

    if date_from:
        query += " AND DATE(u.created_at) >= :date_from"
        params["date_from"] = date_from

    if date_to:
        query += " AND DATE(u.created_at) <= :date_to"
        params["date_to"] = date_to

    query += " ORDER BY u.user_id DESC"

    report_data = db.session.execute(text(query), params).fetchall()

    roles = db.session.execute(text("SELECT role_name FROM roles WHERE role_name != 'Customer' ORDER BY role_name")).fetchall()

    return render_template(
        "user_report.html",
        report_data=report_data,
        roles=roles,
        filters={
            "role": role,
            "status": status,
            "date_from": date_from,
            "date_to": date_to,
        },
    )

@reports_bp.route("/notification-report")
def notification_report():
    auth_check = require_login()
    if auth_check:
        return auth_check

    search = request.args.get("search", "").strip()
    is_read = request.args.get("is_read", "").strip()
    date_from = request.args.get("date_from", "").strip()
    date_to = request.args.get("date_to", "").strip()

    query = """
        SELECT
            n.notification_id,
            u.first_name,
            u.last_name,
            n.title,
            n.message,
            n.is_read,
            n.created_at
        FROM notifications n
        JOIN users u ON n.user_id = u.user_id
        WHERE 1=1
    """
    params = {}

    if search:
        query += " AND (n.title ILIKE :search OR n.message ILIKE :search)"
        params["search"] = f"%{search}%"

    if is_read:
        query += " AND n.is_read = :is_read"
        params["is_read"] = is_read == "read"

    if date_from:
        query += " AND DATE(n.created_at) >= :date_from"
        params["date_from"] = date_from

    if date_to:
        query += " AND DATE(n.created_at) <= :date_to"
        params["date_to"] = date_to

    query += " ORDER BY n.notification_id DESC"

    report_data = db.session.execute(text(query), params).fetchall()

    return render_template(
        "notification_report.html",
        report_data=report_data,
        filters={
            "search": search,
            "is_read": is_read,
            "date_from": date_from,
            "date_to": date_to,
        },
    )


@reports_bp.route("/api/notification-report/search")
def api_notification_report_search():
    auth_check = require_login()
    if auth_check:
        return auth_check

    q = request.args.get("q", "").strip()
    is_read = request.args.get("is_read", "").strip()
    date_from = request.args.get("date_from", "").strip()
    date_to = request.args.get("date_to", "").strip()

    query = """
        SELECT
            n.notification_id,
            u.first_name,
            u.last_name,
            n.title,
            n.message,
            n.is_read,
            n.created_at
        FROM notifications n
        JOIN users u ON n.user_id = u.user_id
        WHERE 1=1
    """
    params = {}

    if q:
        query += " AND (n.title ILIKE :search OR n.message ILIKE :search)"
        params["search"] = f"%{q}%"

    if is_read:
        query += " AND n.is_read = :is_read"
        params["is_read"] = is_read == "read"

    if date_from:
        query += " AND DATE(n.created_at) >= :date_from"
        params["date_from"] = date_from

    if date_to:
        query += " AND DATE(n.created_at) <= :date_to"
        params["date_to"] = date_to

    query += " ORDER BY n.notification_id DESC LIMIT 50"

    notifications = db.session.execute(text(query), params).fetchall()

    rows = []
    for n in notifications:
        rows.append({
            "notification_id": n.notification_id,
            "first_name": n.first_name,
            "last_name": n.last_name,
            "title": n.title,
            "message": n.message,
            "is_read": n.is_read,
            "created_at": n.created_at.strftime('%Y-%m-%d %H:%M') if n.created_at else 'N/A',
        })

    return jsonify({"rows": rows, "count": len(rows)})


@reports_bp.route("/sla-report")
def sla_report():
    auth_check = require_login()
    if auth_check:
        return auth_check

    status = request.args.get("status", "").strip()
    priority = request.args.get("priority", "").strip()

    query = """
        SELECT
            s.sla_id,
            p.priority_name,
            s.response_time,
            s.resolution_time,
            s.status,
            s.created_at
        FROM sla_rules s
        JOIN priorities p ON s.priority_id = p.priority_id
        WHERE 1=1
    """
    params = {}

    if status:
        query += " AND s.status = :status"
        params["status"] = status

    if priority:
        query += " AND p.priority_name = :priority"
        params["priority"] = priority

    query += " ORDER BY s.sla_id DESC"

    report_data = db.session.execute(text(query), params).fetchall()

    priorities = db.session.execute(text("SELECT priority_name FROM priorities ORDER BY priority_name")).fetchall()

    return render_template(
        "sla_report.html",
        report_data=report_data,
        priorities=priorities,
        filters={
            "status": status,
            "priority": priority,
        },
    )

@reports_bp.route("/escalation-report")
def escalation_report():
    auth_check = require_login()
    if auth_check:
        return auth_check

    status = request.args.get("status", "").strip()
    notify_role = request.args.get("notify_role", "").strip()

    query = """
        SELECT
            e.escalation_id,
            p.priority_name,
            e.escalation_after,
            e.notify_role,
            e.status,
            e.created_at
        FROM escalations e
        JOIN priorities p ON e.priority_id = p.priority_id
        WHERE 1=1
    """
    params = {}

    if status:
        query += " AND e.status = :status"
        params["status"] = status

    if notify_role:
        query += " AND e.notify_role = :notify_role"
        params["notify_role"] = notify_role

    query += " ORDER BY e.escalation_id DESC"

    report_data = db.session.execute(text(query), params).fetchall()

    return render_template(
        "escalation_report.html",
        report_data=report_data,
        filters={
            "status": status,
            "notify_role": notify_role,
        },
    )

@reports_bp.route("/export/ticket-report")
def export_ticket_report():
    report_data = db.session.execute(text("""
        SELECT
            t.ticket_id,
            t.ticket_number,
            t.title,
            s.status_name,
            p.priority_name,
            c.category_name,
            u.first_name AS requester,
            t.created_at
        FROM tickets t
        LEFT JOIN ticket_status s ON t.status_name = s.status_name
        LEFT JOIN priorities p ON t.priority_name = p.priority_name
        LEFT JOIN categories c ON t.category_name = c.category_name
        LEFT JOIN users u ON t.requester_id = u.user_id
        ORDER BY t.ticket_id DESC
    """)).fetchall()

    output = StringIO()
    writer = csv.writer(output)
    writer.writerow([
        "Ticket ID", "Ticket Number", "Title", "Status",
        "Priority", "Category", "Requester", "Created At"
    ])

    for row in report_data:
        writer.writerow([
            row[0], row[1], row[2], row[3],
            row[4], row[5], row[6], row[7]
        ])

    response = Response(
        output.getvalue(),
        mimetype="text/csv"
    )
    response.headers["Content-Disposition"] = "attachment; filename=ticket_report.csv"
    return response

@reports_bp.route("/export/user-report")
def export_user_report():
    report_data = db.session.execute(text("""
        SELECT
            u.user_id,
            u.first_name,
            u.last_name,
            u.email,
            r.role_name,
            d.department_name,
            u.status,
            u.created_at
        FROM users u
        LEFT JOIN roles r ON u.role_id = r.role_id
        LEFT JOIN departments d ON u.department_id = d.department_id
        WHERE u.role_id != 6
        ORDER BY u.user_id DESC
    """)).fetchall()

    output = StringIO()
    writer = csv.writer(output)
    writer.writerow([
        "User ID", "First Name", "Last Name", "Email",
        "Role", "Department", "Status", "Created At"
    ])

    for row in report_data:
        writer.writerow([
            row[0], row[1], row[2], row[3],
            row[4], row[5], row[6], row[7]
        ])

    response = Response(
        output.getvalue(),
        mimetype="text/csv"
    )
    response.headers["Content-Disposition"] = "attachment; filename=user_report.csv"
    return response

@reports_bp.route("/export/notification-report")
def export_notification_report():
    report_data = db.session.execute(text("""
        SELECT
            n.notification_id,
            u.first_name,
            u.last_name,
            n.title,
            n.message,
            n.is_read,
            n.created_at
        FROM notifications n
        JOIN users u ON n.user_id = u.user_id
        ORDER BY n.notification_id DESC
    """)).fetchall()

    output = StringIO()
    writer = csv.writer(output)
    writer.writerow([
        "Notification ID", "First Name", "Last Name",
        "Title", "Message", "Is Read", "Created At"
    ])

    for row in report_data:
        writer.writerow([
            row[0], row[1], row[2], row[3],
            row[4], row[5], row[6]
        ])

    response = Response(
        output.getvalue(),
        mimetype="text/csv"
    )
    response.headers["Content-Disposition"] = "attachment; filename=notification_report.csv"
    return response

@reports_bp.route("/export/sla-report")
def export_sla_report():
    report_data = db.session.execute(text("""
        SELECT
            s.sla_id,
            p.priority_name,
            s.response_time,
            s.resolution_time,
            s.status,
            s.created_at
        FROM sla_rules s
        JOIN priorities p ON s.priority_id = p.priority_id
        ORDER BY s.sla_id DESC
    """)).fetchall()

    output = StringIO()
    writer = csv.writer(output)
    writer.writerow([
        "SLA ID", "Priority", "Response Time",
        "Resolution Time", "Status", "Created At"
    ])

    for row in report_data:
        writer.writerow([
            row[0], row[1], row[2], row[3],
            row[4], row[5]
        ])

    response = Response(
        output.getvalue(),
        mimetype="text/csv"
    )
    response.headers["Content-Disposition"] = "attachment; filename=sla_report.csv"
    return response

@reports_bp.route("/export/escalation-report")
def export_escalation_report():
    report_data = db.session.execute(text("""
        SELECT
            e.escalation_id,
            p.priority_name,
            e.escalation_after,
            e.notify_role,
            e.status,
            e.created_at
        FROM escalations e
        JOIN priorities p ON e.priority_id = p.priority_id
        ORDER BY e.escalation_id DESC
    """)).fetchall()

    output = StringIO()
    writer = csv.writer(output)
    writer.writerow([
        "Escalation ID", "Priority", "Escalation After",
        "Notify Role", "Status", "Created At"
    ])

    for row in report_data:
        writer.writerow([
            row[0], row[1], row[2], row[3],
            row[4], row[5]
        ])

    response = Response(
        output.getvalue(),
        mimetype="text/csv"
    )
    response.headers["Content-Disposition"] = "attachment; filename=escalation_report.csv"
    return response


@reports_bp.route("/reports/agent/<int:agent_id>")
def agent_report_detail(agent_id):
    auth_check = require_login()
    if auth_check:
        return auth_check

    period_end = datetime.utcnow()
    period_start = period_end - timedelta(days=30)
    period_key = period_start.replace(hour=0, minute=0, second=0, microsecond=0)

    agent = db.session.execute(text("""
        SELECT u.user_id, u.first_name, u.last_name, u.email, d.department_name
        FROM users u
        LEFT JOIN departments d ON u.department_id = d.department_id
        WHERE u.user_id = :agent_id
    """), {"agent_id": agent_id}).fetchone()

    if not agent:
        flash(_("agent_not_found"), "danger")
        return redirect(url_for("reports.reports"))

    report = db.session.execute(text("""
        SELECT * FROM agent_reports
        WHERE agent_id = :agent_id AND report_period_start = :period_key
    """), {"agent_id": agent_id, "period_key": period_key}).fetchone()

    if not report:
        generate_agent_reports(period_start=period_key, period_end=period_end)
        report = db.session.execute(text("""
            SELECT * FROM agent_reports
            WHERE agent_id = :agent_id AND report_period_start = :period_key
        """), {"agent_id": agent_id, "period_key": period_key}).fetchone()

    if not report:
        flash(_("report_not_found"), "danger")
        return redirect(url_for("reports.reports"))

    # Get ticket details for this agent in the period
    tickets = db.session.execute(text("""
        SELECT
            t.ticket_id, t.ticket_number, t.title, t.status_name,
            t.priority_name, t.category_name, t.created_at,
            t.resolved_at, t.assigned_at, t.reopen_count,
            EXTRACT(EPOCH FROM (t.resolved_at - t.created_at)) / 3600.0 AS resolution_hours
        FROM tickets t
        WHERE t.assigned_to = :agent_id
          AND t.created_at >= :period_start
          AND t.created_at <= :period_end
        ORDER BY t.created_at DESC
    """), {
        "agent_id": agent_id,
        "period_start": period_key,
        "period_end": period_end
    }).fetchall()

    # Calculate SLA compliance
    sla_met = 0
    sla_breached = 0
    for t in tickets:
        if t[9] and t[8]:
            sla_rule = db.session.execute(text("""
                SELECT resolution_time FROM sla_rules
                WHERE priority_id = (SELECT priority_id FROM priorities WHERE priority_name = :priority)
                  AND status = 'Active'
                ORDER BY sla_id DESC LIMIT 1
            """), {"priority": t[5]}).fetchone()
            if sla_rule and sla_rule[0]:
                actual_hours = float(t[10]) if t[10] else 0
                if actual_hours <= sla_rule[0]:
                    sla_met += 1
                else:
                    sla_breached += 1

    resolution_rate = 0
    if report.total_tickets and report.total_tickets > 0:
        resolution_rate = round((report.resolved_tickets or 0) / report.total_tickets * 100, 1)

    return render_template(
        "agent_report_detail.html",
        agent=agent,
        report=report,
        tickets=tickets,
        sla_met=sla_met,
        sla_breached=sla_breached,
        resolution_rate=resolution_rate,
        report_period_start=period_key,
        report_period_end=period_end,
    )


@reports_bp.route("/reports/regenerate/<int:agent_id>", methods=["POST"])
def regenerate_agent_report(agent_id):
    auth_check = require_login()
    if auth_check:
        return auth_check

    period_end = datetime.utcnow()
    period_start = period_end - timedelta(days=30)
    period_key = period_start.replace(hour=0, minute=0, second=0, microsecond=0)

    # Delete existing report for this agent and period
    db.session.execute(text("""
        DELETE FROM agent_reports
        WHERE agent_id = :agent_id AND report_period_start = :period_key
    """), {"agent_id": agent_id, "period_key": period_key})

    generate_agent_reports(period_start=period_key, period_end=period_end)

    flash(_("report_regenerated_successfully"), "success")
    return redirect(url_for("reports.agent_report_detail", agent_id=agent_id))


@reports_bp.route("/reports/export/agent/<int:agent_id>")
def export_agent_report(agent_id):
    auth_check = require_login()
    if auth_check:
        return auth_check

    period_end = datetime.utcnow()
    period_start = period_end - timedelta(days=30)
    period_key = period_start.replace(hour=0, minute=0, second=0, microsecond=0)

    report = db.session.execute(text("""
        SELECT * FROM agent_reports
        WHERE agent_id = :agent_id AND report_period_start = :period_key
    """), {"agent_id": agent_id, "period_key": period_key}).fetchone()

    agent = db.session.execute(text("""
        SELECT first_name, last_name, email FROM users WHERE user_id = :agent_id
    """), {"agent_id": agent_id}).fetchone()

    if not report or not agent:
        flash(_("report_not_found"), "danger")
        return redirect(url_for("reports.reports"))

    pdf = FPDF()
    pdf.add_page()
    
    # Title
    pdf.set_font('Helvetica', 'B', 18)
    pdf.set_text_color(13, 110, 253)
    pdf.cell(0, 12, 'AGENT PERFORMANCE REPORT', 0, 1, 'C')
    pdf.set_draw_color(13, 110, 253)
    pdf.set_line_width(0.8)
    pdf.line(10, pdf.get_y(), 200, pdf.get_y())
    pdf.ln(8)

    # Info
    pdf.set_font('Helvetica', 'B', 12)
    pdf.set_text_color(0, 0, 0)
    pdf.cell(0, 8, f"Agent: {agent[0]} {agent[1]} ({agent[2]})", 0, 1)
    
    pdf.set_font('Helvetica', '', 11)
    pdf.cell(0, 6, f"Period: {report.report_period_start.strftime('%Y-%m-%d')} to {report.report_period_end.strftime('%Y-%m-%d')}", 0, 1)
    pdf.ln(8)

    # Table Header
    pdf.set_fill_color(240, 240, 240)
    pdf.set_font('Helvetica', 'B', 11)
    pdf.cell(100, 10, 'Metric', border=1, align='L', fill=True)
    pdf.cell(40, 10, 'Count', border=1, align='C', fill=True)
    pdf.ln(10)

    # Table Body
    pdf.set_font('Helvetica', '', 11)
    
    metrics = [
        ("Total Tickets", report.total_tickets),
        ("Resolved Tickets", report.resolved_tickets),
        ("Closed Tickets", report.closed_tickets),
        ("Pending Tickets", report.pending_tickets),
        ("In Progress Tickets", report.in_progress_tickets),
        ("New Tickets", report.new_tickets),
        ("On Hold Tickets", report.on_hold_tickets),
        ("Reopened Tickets", report.reopened_tickets),
    ]

    for label, count in metrics:
        pdf.cell(100, 10, str(label), border=1, align='L')
        pdf.cell(40, 10, str(count) if count is not None else "0", border=1, align='C')
        pdf.ln(10)

    # Output
    pdf_bytes = pdf.output()
    if isinstance(pdf_bytes, bytearray):
        pdf_bytes = bytes(pdf_bytes)
    pdf_buffer = io.BytesIO(pdf_bytes)
    
    filename = f"agent_{agent_id}_report.pdf"
    
    return send_file(
        pdf_buffer,
        mimetype='application/pdf',
        as_attachment=True,
        download_name=filename
    )


@reports_bp.route("/reports/generate-now", methods=["POST"])
def generate_reports_now():
    auth_check = require_login()
    if auth_check:
        return auth_check

    period_end = datetime.utcnow()
    period_start = period_end - timedelta(days=30)
    period_key = period_start.replace(hour=0, minute=0, second=0, microsecond=0)

    generate_agent_reports(period_start=period_key, period_end=period_end)

    flash(_("agent_reports_generated_successfully"), "success")
    return redirect(url_for("reports.reports"))
