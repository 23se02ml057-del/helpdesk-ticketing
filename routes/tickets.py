from flask import Blueprint, request, render_template, redirect, flash, url_for, session, jsonify, Response
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from help_db import db
from datetime import datetime
from urllib.parse import quote
import os
import logging
import re
from io import StringIO
import csv
from werkzeug.utils import secure_filename
from werkzeug.security import check_password_hash
from flask_jwt_extended import get_jwt_identity, verify_jwt_in_request, jwt_required
from flask_babel import gettext as _
from utils.auth_helper import get_current_user_id, get_current_role as get_current_role_name
from utils.role_check import allow_roles
from utils.notifications import notify_ticket_assigned, notify_ticket_status_changed
from utils.ai_service import AIService

tickets_bp = Blueprint('tickets', __name__)
logger = logging.getLogger(__name__)

ALLOWED_PRIORITY_ROLE_IDS = {1, 2, 5}
TICKET_PER_PAGE = 10

TICKET_LIST_QUERY = """
    SELECT
        t.ticket_id,
        t.ticket_number,
        t.title,
        t.description,
        t.created_at,
        t.requester_id,
        t.assigned_to,
        t.issue_type_id,
        t.department_id,
        c.category_name,
        p.priority_name,
        s.status_name,
        u.first_name AS requester_first,
        u.last_name AS requester_last,
        a.first_name AS agent_first,
        a.last_name AS agent_last,
        it.issue_name,
        d.department_name
    FROM tickets t
    LEFT JOIN categories c ON t.category_name = c.category_name
    LEFT JOIN priorities p ON t.priority_name = p.priority_name
    LEFT JOIN ticket_status s ON t.status_name = s.status_name
    LEFT JOIN users u ON t.requester_id = u.user_id
    LEFT JOIN users a ON t.assigned_to = a.user_id
    LEFT JOIN issue_types it ON t.issue_type_id = it.issue_type_id
    LEFT JOIN departments d ON t.department_id = d.department_id
    WHERE 1=1
"""

TICKET_COUNT_QUERY = """
    SELECT COUNT(*)
    FROM tickets t
    LEFT JOIN categories c ON t.category_name = c.category_name
    LEFT JOIN priorities p ON t.priority_name = p.priority_name
    LEFT JOIN ticket_status s ON t.status_name = s.status_name
    LEFT JOIN users u ON t.requester_id = u.user_id
    LEFT JOIN users a ON t.assigned_to = a.user_id
    LEFT JOIN issue_types it ON t.issue_type_id = it.issue_type_id
    LEFT JOIN departments d ON t.department_id = d.department_id
    WHERE 1=1
"""

SEARCH_CONDITION = """
    (
        t.ticket_number ILIKE :search OR
        t.title ILIKE :search OR
        t.description ILIKE :search OR
        u.first_name ILIKE :search OR
        u.last_name ILIKE :search OR
        u.email ILIKE :search OR
        a.first_name ILIKE :search OR
        a.last_name ILIKE :search OR
        a.email ILIKE :search OR
        c.category_name ILIKE :search OR
        it.issue_name ILIKE :search OR
        p.priority_name ILIKE :search OR
        s.status_name ILIKE :search
    )
"""


def get_session_role_id():
    return session.get("role_id")


def can_edit_priority():
    return get_session_role_id() in ALLOWED_PRIORITY_ROLE_IDS


def normalize_page(value):
    try:
        return max(int(value or 1), 1)
    except (TypeError, ValueError):
        return 1


def parse_page(value):
    if value is None or str(value).strip() == "":
        return 1
    try:
        page = int(str(value).strip())
    except (TypeError, ValueError):
        raise ValueError("Invalid page parameter")
    if page < 1:
        raise ValueError("Invalid page parameter")
    return page


def normalize_filter(value):
    return (value or "").strip()


def get_allowed_statuses():
    rows = db.session.execute(
        text("SELECT status_name FROM ticket_status ORDER BY status_name")
    ).fetchall()
    return {row.status_name for row in rows}


def build_ticket_filters(search, status):
    search = normalize_filter(search)
    status = normalize_filter(status)
    conditions = []
    params = {}

    if search:
        conditions.append(SEARCH_CONDITION)
        params["search"] = f"%{search}%"

    if status:
        if status not in get_allowed_statuses():
            raise ValueError("Invalid status filter")
        conditions.append("s.status_name = :status")
        params["status"] = status

    return search, status, conditions, params


def get_ticket_listing(search, status, page, per_page=TICKET_PER_PAGE):
    search, status, conditions, params = build_ticket_filters(search, status)
    where = "".join(f"\n        AND {condition}" for condition in conditions)
    count_query = TICKET_COUNT_QUERY + where
    total = db.session.execute(text(count_query), params).scalar() or 0
    total_pages = max((total + per_page - 1) // per_page, 1)
    page = min(normalize_page(page), total_pages)
    offset = (page - 1) * per_page
    query = TICKET_LIST_QUERY + where + "\n    ORDER BY t.ticket_id DESC"
    rows = db.session.execute(
        text(query + " LIMIT :limit OFFSET :offset"),
        {**params, "limit": per_page, "offset": offset}
    ).fetchall()
    pagination = {
        "page": page,
        "per_page": per_page,
        "total": total,
        "total_pages": total_pages,
        "has_prev": page > 1,
        "has_next": page < total_pages,
        "prev_num": page - 1,
        "next_num": page + 1,
    }
    return rows, pagination


def serialize_ticket(row):
    created_at = row.created_at
    return {
        "ticket_id": row.ticket_id,
        "ticket_number": row.ticket_number,
        "title": row.title,
        "description": row.description,
        "category_name": row.category_name,
        "priority_name": row.priority_name,
        "status_name": row.status_name,
        "requester_first": row.requester_first,
        "requester_last": row.requester_last,
        "agent_first": row.agent_first,
        "agent_last": row.agent_last,
        "issue_name": row.issue_name,
        "department_name": row.department_name,
        "requester_id": row.requester_id,
        "assigned_to": row.assigned_to,
        "issue_type_id": row.issue_type_id,
        "department_id": row.department_id,
        "created_at": created_at.isoformat() if created_at else None,
    }


def require_super_admin_html():
    user_id = get_current_user_id()
    if not user_id:
        return redirect(url_for("login_page"))
    if get_current_role_name() != "Super Admin":
        flash(_("access_denied"), "danger")
        return redirect(url_for("login_page"))
    return None


def require_super_admin_api():
    if not get_current_user_id():
        return jsonify({"error": "Authentication required"}), 401
    if get_current_role_name() != "Super Admin":
        return jsonify({"error": "Access denied"}), 403
    return None


@tickets_bp.route("/tickets", methods=["GET"])
def tickets_page():
    auth_check = require_super_admin_html()
    if auth_check:
        return auth_check

    search = normalize_filter(request.args.get("search"))
    status = normalize_filter(request.args.get("status"))
    page = normalize_page(request.args.get("page"))

    try:
        tickets, pagination = get_ticket_listing(search, status, page)
    except ValueError:
        flash(_("error_occurred"), "danger")
        return redirect(url_for("tickets.tickets_page"))

    categories = db.session.execute(
        text("SELECT category_name FROM categories ORDER BY category_name")
    ).fetchall()
    priorities = db.session.execute(
        text("SELECT priority_name FROM priorities ORDER BY priority_name")
    ).fetchall()
    statuses = db.session.execute(
        text("SELECT status_name FROM ticket_status ORDER BY status_name")
    ).fetchall()
    requesters = db.session.execute(
        text("SELECT user_id, first_name, last_name, email FROM users WHERE role_id = 6 ORDER BY first_name, last_name")
    ).fetchall()
    agents = db.session.execute(
        text("SELECT user_id, first_name, last_name, email FROM users WHERE role_id IN (3, 4) ORDER BY first_name, last_name")
    ).fetchall()
    issue_types = db.session.execute(
        text("SELECT issue_type_id, issue_name FROM issue_types WHERE status = 'Active' ORDER BY issue_name")
    ).fetchall()
    departments = db.session.execute(
        text("SELECT department_id, department_name FROM departments WHERE status = 'Active' ORDER BY department_name")
    ).fetchall()

    return render_template(
        "tickets.html",
        tickets=tickets,
        search=search,
        status=status,
        categories=categories,
        priorities=priorities,
        statuses=statuses,
        requesters=requesters,
        agents=agents,
        issue_types=issue_types,
        departments=departments,
        pagination=pagination,
    )


@tickets_bp.route("/api/tickets/search", methods=["GET"])
def api_tickets_search():
    auth_check = require_super_admin_api()
    if auth_check:
        return auth_check

    search = normalize_filter(request.args.get("search", request.args.get("q")))
    status = normalize_filter(request.args.get("status"))
    try:
        requested_page = parse_page(request.args.get("page"))
    except ValueError:
        return jsonify({"error": "Invalid page parameter"}), 400

    try:
        rows, pagination = get_ticket_listing(search, status, requested_page)
    except ValueError:
        return jsonify({"error": "Invalid status filter"}), 400

    if requested_page > pagination["total_pages"]:
        return jsonify({"error": "Page out of range"}), 400

    return jsonify({
        "tickets": [serialize_ticket(row) for row in rows],
        "page": pagination["page"],
        "per_page": pagination["per_page"],
        "total": pagination["total"],
        "total_pages": pagination["total_pages"],
        "has_prev": pagination["has_prev"],
        "has_next": pagination["has_next"],
    }), 200


@tickets_bp.route("/add-ticket", methods=["POST"])
def add_ticket():
    auth_check = require_super_admin_html()
    if auth_check:
        return auth_check

    title = request.form.get("title")
    description = request.form.get("description")
    category_name = request.form.get("category_name")
    priority_name = request.form.get("priority_name")
    status_name = request.form.get("status_name")
    requester_id = request.form.get("requester_id")
    assigned_to = request.form.get("assigned_to")

    if not title:
        flash(_("title_is_required_1"), "danger")
        return redirect("/tickets")

    if not can_edit_priority():
        priority_name = "Medium"

    last_ticket = db.session.execute(
        text("SELECT ticket_number FROM tickets ORDER BY ticket_id DESC LIMIT 1")
    ).fetchone()

    if last_ticket:
        try:
            last_number = int(last_ticket[0][-4:])
        except Exception:
            last_number = 0
        new_number = last_number + 1
    else:
        new_number = 1

    ticket_number = f"TKT{datetime.now().strftime('%Y%m%d')}{new_number:04d}"

    from utils.notifications import calculate_due_date
    due_date = calculate_due_date(priority_name, datetime.utcnow())

    db.session.execute(
        text("""
            INSERT INTO tickets
            (ticket_number, title, description, category_name, priority_name, status_name, requester_id, assigned_to, due_date)
            VALUES (:ticket_number, :title, :description, :category_name, :priority_name, :status_name, :requester_id, :assigned_to, :due_date)
        """),
        {
            "ticket_number": ticket_number,
            "title": title,
            "description": description,
            "priority_name": priority_name,
            "category_name": category_name,
            "status_name": status_name,
            "requester_id": requester_id,
            "assigned_to": assigned_to,
            "due_date": due_date
        }
    )
    db.session.commit()

    flash(_("ticket_created_successfully"), "success")
    return redirect("/tickets")


@tickets_bp.route("/edit-ticket/<int:ticket_id>", methods=["POST"])
def edit_ticket(ticket_id):
    auth_check = require_super_admin_html()
    if auth_check:
        return auth_check

    title = request.form.get("title")
    description = request.form.get("description")
    category_name = request.form.get("category_name")
    priority_name = request.form.get("priority_name")
    status_name = request.form.get("status_name")
    requester_id = request.form.get("requester_id") or None
    assigned_to = request.form.get("assigned_to") or None
    issue_type_id = request.form.get("issue_type_id") or None
    department_id = request.form.get("department_id") or None

    if not title:
        flash(_("title_is_required_1"), "danger")
        return redirect("/tickets")

    if not category_name:
        flash(_("please_select_category"), "danger")
        return redirect("/tickets")

    if not can_edit_priority():
        priority_name = db.session.execute(
            text("SELECT priority_name FROM tickets WHERE ticket_id = :id"),
            {"id": ticket_id}
        ).scalar()

    if not priority_name:
        flash(_("please_select_priority"), "danger")
        return redirect("/tickets")

    if not status_name:
        flash(_("please_select_status"), "danger")
        return redirect("/tickets")

    current_ticket = db.session.execute(
        text("SELECT status_name FROM tickets WHERE ticket_id = :id"),
        {"id": ticket_id}
    ).fetchone()

    if not current_ticket:
        flash(_("ticket_not_found"), "danger")
        return redirect("/tickets")

    old_status = current_ticket[0]
    now = datetime.utcnow()
    resolved_at = None

    if status_name in ("Resolved", "Closed") and old_status not in ("Resolved", "Closed"):
        resolved_at = now
    elif status_name not in ("Resolved", "Closed") and old_status in ("Resolved", "Closed"):
        resolved_at = None

    db.session.execute(
        text("""
            UPDATE tickets
            SET title = :title,
                description = :description,
                category_name = :category_name,
                priority_name = :priority_name,
                status_name = :status_name,
                requester_id = :requester_id,
                assigned_to = :assigned_to,
                issue_type_id = :issue_type_id,
                department_id = :department_id,
                updated_at = :updated_at,
                resolved_at = COALESCE(:resolved_at, resolved_at)
            WHERE ticket_id = :id
        """),
        {
            "title": title,
            "description": description,
            "category_name": category_name,
            "priority_name": priority_name,
            "status_name": status_name,
            "requester_id": requester_id,
            "assigned_to": assigned_to,
            "issue_type_id": issue_type_id,
            "department_id": department_id,
            "updated_at": now,
            "resolved_at": resolved_at,
            "id": ticket_id
        }
    )

    if old_status != status_name:
        changed_by = get_current_user_id()
        db.session.execute(
            text("""
                INSERT INTO ticket_status_history (ticket_id, old_status, new_status, changed_by)
                VALUES (:ticket_id, :old_status, :new_status, :changed_by)
            """),
            {
                "ticket_id": ticket_id,
                "old_status": old_status,
                "new_status": status_name,
                "changed_by": changed_by
            }
        )
        notify_ticket_status_changed(ticket_id, old_status, status_name, changed_by)

    db.session.commit()
    flash(_("ticket_updated_successfully"), "success")
    return redirect("/tickets")


@tickets_bp.route("/delete-ticket/<int:id>", methods=["POST"])
def delete_ticket(id):
    auth_check = require_super_admin_html()
    if auth_check:
        return auth_check

    try:
        db.session.execute(
            text("DELETE FROM ticket_ml_predictions WHERE ticket_id = :id"),
            {"id": id}
        )
        db.session.execute(
            text("DELETE FROM ticket_escalations WHERE ticket_id = :id"),
            {"id": id}
        )
        db.session.execute(
            text("DELETE FROM customer_feedback WHERE ticket_id = :id"),
            {"id": id}
        )
        db.session.execute(
            text("DELETE FROM ticket_status_history WHERE ticket_id = :id"),
            {"id": id}
        )
        db.session.execute(
            text("DELETE FROM ticket_comments WHERE ticket_id = :id"),
            {"id": id}
        )
        db.session.execute(
            text("DELETE FROM ticket_attachments WHERE ticket_id = :id"),
            {"id": id}
        )
        db.session.execute(
            text("DELETE FROM ticket_assignment_history WHERE ticket_id = :id"),
            {"id": id}
        )
        db.session.execute(
            text("DELETE FROM ticket_assignments WHERE ticket_id = :id"),
            {"id": id}
        )
        db.session.execute(
            text("DELETE FROM notifications WHERE ticket_id = :id"),
            {"id": id}
        )
        db.session.execute(
            text("DELETE FROM tickets WHERE ticket_id = :id"),
            {"id": id}
        )

        db.session.commit()
        flash(_("ticket_deleted_successfully"), "success")
    except Exception as e:
        db.session.rollback()
        flash(_("error_deleting_ticket_please_try_again"), "danger")
        print(f"[ERROR] Failed to delete ticket {id}: {str(e)}")

    return redirect("/tickets")


@tickets_bp.route("/update-ticket/<int:id>", methods=["POST"])
def update_ticket(id):
    auth_check = require_super_admin_html()
    if auth_check:
        return auth_check

    priority_name = request.form.get("priority_name")
    if not can_edit_priority():
        priority_name = db.session.execute(
            text("SELECT priority_name FROM tickets WHERE ticket_id = :id"),
            {"id": id}
        ).scalar()

    db.session.execute(
        text("""
            UPDATE tickets
            SET
                title=:title,
                description=:description,
                category_name=:category_name,
                priority_name=:priority_name,
                status_name=:status_name,
                requester_id=:requester_id,
                assigned_to=:assigned_to
            WHERE ticket_id=:id
        """),
        {
            "title": request.form["title"],
            "description": request.form["description"],
            "category_name": request.form["category_name"],
            "priority_name": priority_name,
            "status_name": request.form["status_name"],
            "requester_id": request.form["requester_id"],
            "assigned_to": request.form["assigned_to"],
            "id": id
        }
    )
    db.session.commit()
    return redirect("/tickets")


@tickets_bp.route("/save-ticket", methods=["POST"])
def save_ticket():
    auth_check = require_super_admin_html()
    if auth_check:
        return auth_check

    try:
        priority_name = request.form.get("priority_name")
        if not can_edit_priority():
            priority_name = "Medium"

        result = db.session.execute(
            text("""
                SELECT ticket_number
                FROM tickets
                ORDER BY ticket_id DESC
                LIMIT 1
            """)
        ).fetchone()

        if result:
            try:
                last_number = int(result[0][-4:])
            except Exception:
                last_number = 0
            new_number = last_number + 1
        else:
            new_number = 1

        ticket_number = f"TKT{datetime.now().strftime('%Y%m%d')}{new_number:04d}"

        from utils.notifications import calculate_due_date
        due_date = calculate_due_date(priority_name, datetime.utcnow())

        db.session.execute(
            text("""
                INSERT INTO tickets
                (ticket_number, title, description, category_name, priority_name, status_name, requester_id, assigned_to, due_date)
                VALUES (:ticket_number, :title, :description, :category_name, :priority_name, :status_name, :requester_id, :assigned_to, :due_date)
            """),
            {
                "ticket_number": ticket_number,
                "title": request.form["title"],
                "description": request.form["description"],
                "category_name": request.form["category_name"],
                "priority_name": priority_name,
                "status_name": request.form["status_name"],
                "requester_id": request.form.get("requester_id"),
                "assigned_to": request.form.get("assigned_to") or None,
                "due_date": due_date
            }
        )
        db.session.commit()
        return redirect("/tickets")

    except Exception as e:
        db.session.rollback()
        flash(f"Error saving ticket: {str(e)}", "danger")
        return redirect("/tickets")


# MY TICKETS

@tickets_bp.route('/my', methods=['GET'])


def get_my_tickets():

    current_user_id = get_current_user_id()


    query = text("""

        SELECT

            ticket_id,

            ticket_number,
            title,

            description,
            status_name,
            created_at

        FROM tickets

        WHERE requester_id = :user_id

        ORDER BY ticket_id DESC
    """)


    tickets = db.session.execute(

        query,

        {"user_id": current_user_id}

    ).fetchall()


    result = []


    for t in tickets:

        result.append({

            "ticket_id": t[0],

            "ticket_number": t[1],

            "title": t[2],

            "description": t[3],

            "status_name": t[4],

            "created_at": str(t[5])

        })


    return jsonify(result), 200


@tickets_bp.route('/all', methods=['GET'])


def get_all_tickets():
        

    query = text("""

        SELECT

            ticket_id,

            ticket_number,
            title,

            description,

            requester_id,
            status_name,
            created_at

        FROM tickets

        ORDER BY ticket_id DESC
    """)


    tickets = db.session.execute(query).fetchall()


    result = []


    for t in tickets:

        result.append({

            "ticket_id": t[0],

            "ticket_number": t[1],

            "title": t[2],

            "description": t[3],

            "requester_id": t[4],

            "status_name": t[5],

            "created_at": str(t[6])

        })
         

    return jsonify(result), 200


@tickets_bp.route('/<int:ticket_id>/status', methods=['PUT'])

def update_ticket_status(ticket_id):




    data = request.get_json(silent=True) or request.form
    status_name = data.get('status_name')


    # Current logged in user

    changed_by = get_current_user_id()


    # Get old status

    old_status_query = text("""

        SELECT status_name

        FROM tickets

        WHERE ticket_id = :ticket_id
    """)


    old_status = db.session.execute(

        old_status_query,

        {"ticket_id": ticket_id}

    ).fetchone()


    if old_status is None:

        return jsonify({

            "message": "Ticket Not Found"

        }), 404


    # Update ticket status

    update_query = text("""

        UPDATE tickets

        SET status_name = :status_name

        WHERE ticket_id = :ticket_id
    """)


    db.session.execute(

        update_query,

        {
            "status_name": status_name,

            "ticket_id": ticket_id

        }
    )


    # Insert into history table

    history_query = text("""

        INSERT INTO ticket_status_history
        (

            ticket_id,
            old_status,

            new_status,

            changed_by
        )

        VALUES
        (

            :ticket_id,
            :old_status,

            :new_status,

            :changed_by
        )
    """)


    db.session.execute(

        history_query,

        {

            "ticket_id": ticket_id,

            "old_status": old_status[0],

            "new_status": status_name,

            "changed_by": changed_by

        }
    )


    db.session.commit()


    return jsonify({

        "message": "Ticket Status Updated Successfully"

    }), 200
    
    

@tickets_bp.route('/<int:ticket_id>/history', methods=['GET'])

def ticket_history(ticket_id):


    query = text("""

        SELECT

            history_id,
            old_status,

            new_status,

            changed_by,

            changed_at

        FROM ticket_status_history

        WHERE ticket_id = :ticket_id

        ORDER BY history_id DESC
    """)


    history = db.session.execute(

        query,

        {"ticket_id": ticket_id}

    ).fetchall()


    result = []


    for h in history:

        result.append({

            "history_id": h[0],

            "old_status": h[1],

            "new_status": h[2],

            "changed_by": h[3],

            "changed_at": str(h[4])

        })


    return jsonify(result), 200 



@tickets_bp.route('/stats', methods=['GET'])

def ticket_stats():


    total = db.session.execute(

        text("SELECT COUNT(*) FROM tickets")

    ).scalar()


    open_count = db.session.execute(

        text("SELECT COUNT(*) FROM tickets WHERE status_name = 'Open'")

    ).scalar()


    progress_count = db.session.execute(

        text("SELECT COUNT(*) FROM tickets WHERE status_name = 'In Progress'")

    ).scalar()


    resolved_count = db.session.execute(

        text("SELECT COUNT(*) FROM tickets WHERE status_name = 'Resolved'")

    ).scalar()


    return jsonify({

        "total_tickets": total,

        "open_tickets": open_count,

        "in_progress": progress_count,

        "resolved_tickets": resolved_count

    })
    

@tickets_bp.route('/<int:ticket_id>/upload', methods=['POST'])


def upload_attachment(ticket_id):


    if 'file' not in request.files:

        return jsonify({

            "message": "No File Selected"

        }), 400


    file = request.files['file']


    if file.filename == '':

        return jsonify({

            "message": "Empty File Name"

        }), 400


    uploaded_by = get_current_user_id()


    filename = secure_filename(file.filename)


    upload_folder = "uploads"


    if not os.path.exists(upload_folder):

        os.makedirs(upload_folder)


    file_path = os.path.join(

        upload_folder,

        filename
    )


    file.save(file_path)


    query = text("""

        INSERT INTO ticket_attachments
        (

            ticket_id,

            file_name,

            file_path,

            uploaded_by
        )

        VALUES
        (

            :ticket_id,

            :file_name,

            :file_path,

            :uploaded_by
        )
    """)


    db.session.execute(

        query,

        {

            "ticket_id": ticket_id,

            "file_name": filename,

            "file_path": file_path,

            "uploaded_by": uploaded_by

        }
    )


    db.session.commit()


    return jsonify({

        "message": "File Uploaded Successfully",

        "file_name": filename

    }), 201
    

@tickets_bp.route('/<int:ticket_id>/assign', methods=['POST'])

def assign_ticket(ticket_id):


    role = get_current_role()

    if role not in ["Super Admin", "Support Manager"]:

        return jsonify({

            "message": "Access Denied"

        }), 403



    data = request.get_json(silent=True) or request.form
    assigned_to = data.get('assigned_to')


    assigned_by = get_current_user_id()


    # Check ticket exists

    ticket = db.session.execute(

        text("""

            SELECT ticket_id

            FROM tickets

            WHERE ticket_id = :ticket_id
        """),

        {"ticket_id": ticket_id}

    ).fetchone()


    if not ticket:

        return jsonify({

            "message": "Ticket Not Found"

        }), 404


    # Update assigned user

    db.session.execute(

        text("""

            UPDATE tickets

            SET assigned_to = :assigned_to

            WHERE ticket_id = :ticket_id
        """),

        {

            "assigned_to": assigned_to,

            "ticket_id": ticket_id

        }
    )

    db.session.execute(

    text("""

        INSERT INTO notifications
        (
            user_id,
            title,

            message
        )

        VALUES
        (
            :user_id,
            :title,

            :message
        )
    """),

    {

        "user_id": assigned_to,

        "title": "Ticket Assigned",

        "message": f"Ticket ID {ticket_id} has been assigned to you"

    }
)

    db.session.commit()

    try:
        agent = db.session.execute(
            text("SELECT first_name, last_name, email FROM users WHERE user_id = :uid"),
            {"uid": assigned_to}
        ).fetchone()
        if agent and agent[2]:
            from utils.email_service import send_ticket_assignment_email
            send_ticket_assignment_email(
                ticket_number=ticket_id,
                ticket_title=f"Ticket ID {ticket_id}",
                recipient_email=agent[2],
                agent_name=f"{agent[0] or ''} {agent[1] or ''}".strip() or "Agent",
                assigned_by_name="Support Manager"
            )
    except Exception as email_err:
        logger.warning("Failed to send ticket assignment email: %s", email_err)


    return jsonify({

        "message": "Ticket Assigned Successfully",

        "ticket_id": ticket_id,

        "assigned_to": assigned_to

    }), 200
    

@tickets_bp.route('/<int:ticket_id>/comment', methods=['POST'])

def add_comment(ticket_id):

   


    data = request.get_json(silent=True) or request.form
    comment = data.get('comment')


    user_id = get_current_user_id()


    query = text("""

    INSERT INTO ticket_comments
    (

        ticket_id,
        user_id,

        comment_text
    )

    VALUES
    (

        :ticket_id,
        :user_id,

        :comment_text
    )
""")


    db.session.execute(
    query,

    {

        "ticket_id": ticket_id,
        "user_id": user_id,

        "comment_text": comment

    }
)


    db.session.commit()

    try:
        ticket_info = db.session.execute(
            text("SELECT ticket_number, title, requester_id, assigned_to FROM tickets WHERE ticket_id = :ticket_id"),
            {"ticket_id": ticket_id}
        ).fetchone()
        if ticket_info and ticket_info[2]:
            from utils.notifications import create_notification
            create_notification(
                ticket_info[2],
                "New Comment",
                f"New comment on ticket #{ticket_info[0]} - {ticket_info[1]}"
            )

            if ticket_info[3]:
                create_notification(
                    ticket_info[3],
                    "New Comment",
                    f"New comment on ticket #{ticket_info[0]} - {ticket_info[1]}"
                )

            commenter_role = db.session.execute(
                text("SELECT role_id FROM users WHERE user_id = :uid"),
                {"uid": user_id}
            ).fetchone()
            if commenter_role and commenter_role[0] in (1, 2, 3, 5):
                try:
                    requester = db.session.execute(
                        text("SELECT first_name, last_name, email FROM users WHERE user_id = :uid"),
                        {"uid": ticket_info[2]}
                    ).fetchone()
                    if requester and requester[2]:
                        commenter = db.session.execute(
                            text("SELECT first_name, last_name FROM users WHERE user_id = :uid"),
                            {"uid": user_id}
                        ).fetchone()
                        sender_name = f"{commenter[0]} {commenter[1]}".strip() if commenter else "Support Team"
                        from utils.email_service import send_ticket_reply_email
                        send_ticket_reply_email(
                            ticket_number=ticket_info[0],
                            ticket_title=ticket_info[1],
                            recipient_email=requester[2],
                            customer_name=f"{requester[0] or ''} {requester[1] or ''}".strip() or "Customer",
                            reply_text=comment,
                            sender_name=sender_name,
                            sender_role="Support Team"
                        )
                except Exception as email_err:
                    logger.warning("Failed to send ticket reply email: %s", email_err)
    except Exception as notif_err:
        logger.warning("Failed to create notification for comment: %s", notif_err)


    return jsonify({

        "message": "Comment Added Successfully"

    }), 201
    

@tickets_bp.route('/<int:ticket_id>/comments', methods=['GET'])

def get_comments(ticket_id):


    query = text("""

        SELECT
            comment_id,
            user_id,
            comment_text,
            created_at

        FROM ticket_comments

        WHERE ticket_id = :ticket_id

        ORDER BY comment_id ASC
    """)


    comments = db.session.execute(

        query,

        {"ticket_id": ticket_id}

    ).fetchall()


    result = []


    for c in comments:

        result.append({

            "comment_id": c[0],

            "user_id": c[1],

            "comment": c[2],

            "created_at": str(c[3])

        })


    return jsonify(result), 200    



@tickets_bp.route('/api/notifications', methods=['GET'])
@jwt_required()


def get_notifications():


    user_id = get_current_user_id()


    notifications = db.session.execute(

        text("""

            SELECT

                notification_id,
                title,

                message,
                is_read,
                created_at

            FROM notifications

            WHERE user_id = :user_id

            ORDER BY notification_id DESC
        """),

        {"user_id": user_id}

    ).fetchall()


    result = []


    for n in notifications:

        result.append({

            "notification_id": n[0],

            "title": n[1],

            "message": n[2],

            "is_read": n[3],

            "created_at": str(n[4])

        })


    return jsonify(result),200


@tickets_bp.route('/notifications/<int:notification_id>/read', methods=['PUT'])


def mark_notification_read(notification_id):
    

    notification = db.session.execute(

        text("""

            SELECT notification_id

            FROM notifications

            WHERE notification_id = :notification_id
        """),

        {"notification_id": notification_id}

    ).fetchone()


    if not notification:

        return jsonify({

            "message": "Notification Not Found"

        }), 404


    db.session.execute(

        text("""

            UPDATE notifications

            SET is_read = TRUE

            WHERE notification_id = :notification_id
        """),

        {

            "notification_id": notification_id

        }
    )


    db.session.commit()


    return jsonify({

        "message": "Notification Marked As Read"

    }), 200
    
    
    

@tickets_bp.route('/<int:ticket_id>/feedback', methods=['POST'])


def add_feedback(ticket_id):




    data = request.get_json(silent=True) or request.form
    rating = data.get('rating')

    feedback_text = data.get('feedback_text')


    query = text("""

        INSERT INTO customer_feedback
        (

            ticket_id,

            rating,

            feedback_text
        )

        VALUES
        (

            :ticket_id,

            :rating,

            :feedback_text
        )
    """)


    db.session.execute(

        query,

        {

            "ticket_id": ticket_id,

            "rating": rating,

            "feedback_text": feedback_text

        }
    )


    db.session.commit()


    return jsonify({

        "message": "Feedback Submitted Successfully"

    }), 201 
    
    

@tickets_bp.route('/feedbacks', methods=['GET'])


def get_all_feedbacks():


    query = text("""

        SELECT

            feedback_id,

            ticket_id,

            rating,

            feedback_text,

            submitted_at

        FROM customer_feedback

        ORDER BY feedback_id DESC
    """)


    feedbacks = db.session.execute(query).fetchall()


    result = []


    for f in feedbacks:

        result.append({

            "feedback_id": f[0],

            "ticket_id": f[1],

            "rating": f[2],

            "feedback_text": f[3],

            "submitted_at": str(f[4])

        })


    return jsonify(result), 200 




@tickets_bp.route('/<int:ticket_id>/escalations', methods=['GET'])


def get_escalations(ticket_id):


    query = text("""

        SELECT
            escalation_id,
            escalated_to,
            reason,
            status,
            escalated_at

        FROM ticket_escalations

        WHERE ticket_id = :ticket_id

        ORDER BY escalation_id DESC
    """)


    escalations = db.session.execute(

        query,

        {"ticket_id": ticket_id}

    ).fetchall()


    result = []


    for e in escalations:

        result.append({

            "escalation_id": e[0],

            "escalated_to": e[1],

            "reason": e[2],

            "status": e[3],

            "escalated_at": str(e[4])

        })


    return jsonify(result), 200 




@tickets_bp.route('/sla', methods=['POST'])


def create_sla():

   


    data = request.get_json(silent=True) or request.form
    priority_name = data.get('priority_name')

    response_time_hours = data.get('response_time_hours')

    resolution_time_hours = data.get('resolution_time_hours')

    priority = db.session.execute(
        text("""
            SELECT priority_id
            FROM priorities
            WHERE priority_name = :priority_name
        """),
        {"priority_name": priority_name}
    ).fetchone()

    if not priority:
        return jsonify({"error": "Invalid priority"}), 400

    query = text("""
        INSERT INTO sla_rules
        (
            priority_id,
            response_time,
            resolution_time
        )
        VALUES
        (
            :priority_id,
            :response_time,
            :resolution_time
        )
    """)


    db.session.execute(
        query,
        {
            "priority_id": priority.priority_id,
            "response_time": response_time_hours,
            "resolution_time": resolution_time_hours
        }
    )


    db.session.commit()


    return jsonify({

        "message": "SLA Created Successfully"

    }), 201
    
    

@tickets_bp.route('/sla', methods=['GET'])


def get_sla():


    query = text("""
        SELECT
            s.sla_id,
            p.priority_name,
            s.response_time,
            s.resolution_time
        FROM sla_rules s
        JOIN priorities p ON s.priority_id = p.priority_id
    """)


    sla = db.session.execute(query).fetchall()


    result = []


    for s in sla:

        result.append({

            "sla_id": s[0],

            "priority_name": s[1],

            "response_time_hours": s[2],

            "resolution_time_hours": s[3]

        })


    return jsonify(result), 200


@tickets_bp.route("/tickets/<int:ticket_id>/reanalyze-priority", methods=["POST"])
def reanalyze_priority(ticket_id):
    """
    Manually re-analyze and update the AI-suggested priority for a ticket.
    
    This route:
    1. Fetches the ticket title and description
    2. Calls OpenRouter AI to analyze the priority
    3. Updates both ai_suggested_priority and priority_name in the database
    4. Returns JSON response with the new priority
    """
    ai_service = AIService()
    
    # Fetch ticket details from database
    ticket = db.session.execute(
        text("""
            SELECT title, description, priority_name, category_name
            FROM tickets
            WHERE ticket_id = :ticket_id
        """),
        {"ticket_id": ticket_id}
    ).fetchone()
    
    if not ticket:
        return jsonify({"success": False, "error": "Ticket not found"}), 404
    
    title = ticket[0]
    description = ticket[1]
    current_priority = ticket[2]
    current_category = ticket[3]
    
    if not title and not description:
        return jsonify({"success": False, "error": "Ticket has no content to analyze"}), 400
    
    # Generate AI priority analysis
    result = ai_service.analyze_priority(
        ticket_subject=title or "",
        ticket_description=description or "",
        category=current_category
    )
    
    if result.get("success"):
        ai_priority = result.get("priority", "Medium")
        
        # Update the ticket with AI-suggested priority
        # For admin/agent routes, we update both the suggested and actual priority
        db.session.execute(
            text("""
                UPDATE tickets
                SET ai_suggested_priority = :ai_priority,
                    priority_name = :priority_name
                WHERE ticket_id = :ticket_id
            """),
            {
                "ai_priority": ai_priority,
                "priority_name": ai_priority,
                "ticket_id": ticket_id
            }
        )
        db.session.commit()
        
        return jsonify({
            "success": True,
            "priority": ai_priority,
            "reasoning": result.get("reasoning", ""),
            "previous_priority": current_priority,
            "message": f"Priority updated to {ai_priority}"
        })
    else:
        return jsonify({
            "success": False,
            "error": "AI service is temporarily unavailable. Please try again later.",
            "fallback_priority": "Medium"
        }), 500






@tickets_bp.route('/agent-report', methods=['GET'])


def agent_report():


    query = text("""

        SELECT

            assigned_to,

            COUNT(*) as assigned_tickets,


            SUM(

                CASE

                    WHEN status_name = 'Resolved' THEN 1

                    ELSE 0

                END

            ) as resolved_tickets,


            SUM(

                CASE

                    WHEN status_name IN ('Open','In Progress') THEN 1

                    ELSE 0

                END

            ) as pending_tickets


        FROM tickets


        WHERE assigned_to IS NOT NULL


        GROUP BY assigned_to
    """)


    result = db.session.execute(query).fetchall()

    data = []

    for row in result:

        data.append({

            "agent_id": row[0],

            "assigned_tickets": row[1],

            "resolved_tickets": row[2],

            "pending_tickets": row[3]

        })


    return jsonify(data), 200


@tickets_bp.route('/lead', methods=['POST'])


def create_lead():

    data = request.get_json(silent=True) or request.form

    query = text("""

        INSERT INTO leads
        (

            company_name,

            contact_person,
            email,

            phone,

            inquiry_details,
            lead_status
        )

        VALUES
        (

            :company_name,

            :contact_person,
            :email,

            :phone,

            :inquiry_details,

            'New'
        )
    """)


    db.session.execute(

        query,

        {

            "company_name": data.get("company_name"),

            "contact_person": data.get("contact_person"),

            "email": data.get("email"),

            "phone": data.get("phone"),

            "inquiry_details": data.get("inquiry_details")

        }
    )


    db.session.commit()


    return jsonify({

        "message": "Lead Created Successfully"

    }), 201  
    
    

@tickets_bp.route('/leads', methods=['GET'])


def get_leads():


    leads = db.session.execute(

        text("""

            SELECT
                lead_id,

                company_name,

                contact_person,
                email,

                phone,
                lead_status

            FROM leads

            ORDER BY lead_id DESC
        """)

    ).fetchall()


    result = []


    for l in leads:

        result.append({

            "lead_id": l[0],

            "company_name": l[1],

            "contact_person": l[2],

            "email": l[3],

            "phone": l[4],

            "status": l[5]

        })


    return jsonify(result), 200 



@tickets_bp.route('/lead/<int:lead_id>', methods=['PUT'])


def update_lead_status(lead_id):

    data = request.get_json(silent=True) or request.form

    lead_status = data.get('lead_status')


    query = text("""

        UPDATE leads

        SET lead_status = :lead_status

        WHERE lead_id = :lead_id
    """)


    db.session.execute(

        query,

        {
            "lead_status": lead_status,
            "lead_id": lead_id

        }
    )


    db.session.commit()


    return jsonify({

        "message": "Lead Status Updated Successfully"

    }), 200
    
    

@tickets_bp.route('/lead/<int:lead_id>', methods=['DELETE'])


def delete_lead(lead_id):


    db.session.execute(

        text("""

            DELETE FROM leads

            WHERE lead_id = :lead_id
        """),

        {
            "lead_id": lead_id

        }
    )


    db.session.commit()


    return jsonify({

        "message": "Lead Deleted Successfully"

    }), 200 
    
    

@tickets_bp.route('/lead/search/<company>', methods=['GET'])


def search_lead(company):


    leads = db.session.execute(

        text("""

            SELECT
                lead_id,

                company_name,

                contact_person,
                lead_status

            FROM leads

            WHERE company_name ILIKE :company
        """),

        {

            "company": f"%{company}%"

        }

    ).fetchall()


    result = []


    for l in leads:

        result.append({

            "lead_id": l[0],

            "company_name": l[1],

            "contact_person": l[2],

            "status": l[3]

        })


    return jsonify(result), 200    



def get_current_role():


    user_id = get_current_user_id()


    query = text("""

        SELECT r.role_name

        FROM users u

        JOIN roles r

        ON u.role_id = r.role_id

        WHERE u.user_id = :user_id
    """)


    result = db.session.execute(

        query,

        {"user_id": user_id}

    ).fetchone()


    if result:

        return result[0]


    return None 


@tickets_bp.route('/department-report', methods=['GET'])


def department_report():


    query = text("""

        SELECT

            d.department_name,

            COUNT(t.ticket_id) as total_tickets

        FROM departments d

        LEFT JOIN tickets t

        ON d.department_id = t.department_id

        GROUP BY d.department_name

        ORDER BY total_tickets DESC
    """)


    data = db.session.execute(query).fetchall()


    result = []


    for row in data:

        result.append({

            "department_name": row[0],

            "total_tickets": row[1]

        })


    return jsonify(result), 200


@tickets_bp.route("/tickets/<int:ticket_id>/generate-ai-reply", methods=["POST"])
def generate_ai_reply(ticket_id):
    """
    Generate an AI-suggested reply for a ticket and store it in the database.
    
    This route:
    1. Fetches the ticket title, description, and requester name
    2. Calls OpenRouter AI to generate a professional response with troubleshooting steps
    3. Saves the reply to the ai_suggested_reply column
    4. Returns JSON with the suggestion and troubleshooting steps
    """
    ai_service = AIService()
    
    # Fetch ticket details from database
    ticket = db.session.execute(
        text("""
            SELECT t.title, t.description, u.first_name, u.last_name
            FROM tickets t
            LEFT JOIN users u ON t.requester_id = u.user_id
            WHERE t.ticket_id = :ticket_id
        """),
        {"ticket_id": ticket_id}
    ).fetchone()
    
    if not ticket:
        return jsonify({"success": False, "error": "Ticket not found"}), 404
    
    title = ticket[0]
    description = ticket[1]
    requester_first = ticket[2] or "Customer"
    requester_last = ticket[3] or ""
    customer_name = f"{requester_first} {requester_last}".strip()
    
    if not title and not description:
        return jsonify({"success": False, "error": "Ticket has no content to generate reply"}), 400
    
    # Generate AI reply
    result = ai_service.suggest_response(
        ticket_subject=title or "",
        ticket_description=description or "",
        customer_name=customer_name
    )
    
    if result.get("success"):
        suggestion = result.get("suggestion", "")
        troubleshooting = result.get("troubleshooting", "")
        
        # Store the full AI reply in the database
        # Format: REPLY + "\n\n" + TROUBLESHOOTING
        full_reply = f"REPLY:\n{suggestion}\n\nTROUBLESHOOTING:\n{troubleshooting}" if troubleshooting else suggestion
        
        db.session.execute(
            text("""
                UPDATE tickets
                SET ai_suggested_reply = :ai_reply
                WHERE ticket_id = :ticket_id
            """),
            {
                "ai_reply": full_reply,
                "ticket_id": ticket_id
            }
        )
        db.session.commit()
        
        return jsonify({
            "success": True,
            "suggestion": suggestion,
            "troubleshooting": troubleshooting,
            "message": "AI reply generated successfully"
        })
    else:
        return jsonify({
            "success": False,
            "error": "AI service is temporarily unavailable. Please try again later.",
            "suggestion": "",
            "troubleshooting": ""
        }), 500


@tickets_bp.route("/tickets/<int:ticket_id>/generate-ai-summary", methods=["POST"])
def generate_ai_summary(ticket_id):
    """
    Generate an AI summary for a ticket and store it in the database.
    
    This route:
    1. Fetches the ticket title and description
    2. Calls OpenRouter AI to generate a concise summary
    3. Saves the summary to the ai_summary column
    4. Redirects back to the referring page
    """
    ai_service = AIService()
    
    # Fetch ticket details from database
    ticket = db.session.execute(
        text("""
            SELECT t.title, t.description
            FROM tickets t
            WHERE t.ticket_id = :ticket_id
        """),
        {"ticket_id": ticket_id}
    ).fetchone()
    
    if not ticket:
        flash(_("ticket_not_found"), "danger")
        return redirect(request.referrer or "/tickets")
    
    title = ticket[0]
    description = ticket[1]
    
    if not title and not description:
        flash(_("ticket_has_no_content_to_summarize"), "danger")
        return redirect(request.referrer or "/tickets")
    
    # Generate AI summary
    result = ai_service.summarize_ticket(
        ticket_subject=title or "",
        ticket_description=description or ""
    )
    
    if result.get("success"):
        summary = result.get("summary", "")
        
        db.session.execute(
            text("""
                UPDATE tickets
                SET ai_summary = :ai_summary
                WHERE ticket_id = :ticket_id
            """),
            {
                "ai_summary": summary,
                "ticket_id": ticket_id
            }
        )
        db.session.commit()
        
        flash(_("ai_summary_generated_successfully"), "success")
    else:
        flash(f"Failed to generate summary: {result.get('error', 'Unknown error')}", "danger")
    
    return redirect(request.referrer or "/tickets")


@tickets_bp.route("/tickets/<int:ticket_id>/send-ai-reply", methods=["POST"])
def send_ai_reply(ticket_id):
    """
    Send the AI-suggested reply as a comment on the ticket.
    
    This route:
    1. Gets the edited reply from the request
    2. Validates it's not empty
    3. Inserts it as a comment in ticket_comments table
    4. Updates the ticket status to 'In Progress' if it was 'Open'
    5. Returns JSON response
    """
    user_id = session.get("user_id")
    
    if not user_id:
        return jsonify({"success": False, "error": "Unauthorized"}), 401
    
    # Get the reply text from request
    data = request.get_json(silent=True) or request.form
    reply_text = data.get("reply_text", "").strip()
    
    if not reply_text:
        return jsonify({"success": False, "error": "Reply text is required"}), 400
    
    # Verify ticket exists
    ticket = db.session.execute(
        text("SELECT ticket_id, status_name FROM tickets WHERE ticket_id = :ticket_id"),
        {"ticket_id": ticket_id}
    ).fetchone()
    
    if not ticket:
        return jsonify({"success": False, "error": "Ticket not found"}), 404
    
    # Insert the reply as a comment
    db.session.execute(
        text("""
            INSERT INTO ticket_comments (ticket_id, user_id, comment_text, is_internal)
            VALUES (:ticket_id, :user_id, :comment_text, :is_internal)
        """),
        {
            "ticket_id": ticket_id,
            "user_id": user_id,
            "comment_text": reply_text,
            "is_internal": False
        }
    )
    
    # If ticket was Open, update to In Progress
    if ticket[1] == "Open":
        db.session.execute(
            text("UPDATE tickets SET status_name = 'In Progress' WHERE ticket_id = :ticket_id"),
            {"ticket_id": ticket_id}
        )
    db.session.commit()

    try:
        ticket_info = db.session.execute(
            text("SELECT ticket_number, title, requester_id FROM tickets WHERE ticket_id = :ticket_id"),
            {"ticket_id": ticket_id}
        ).fetchone()
        if ticket_info and ticket_info[2]:
            from utils.notifications import create_notification
            create_notification(
                ticket_info[2],
                "New Comment",
                f"New comment on ticket #{ticket_info[0]} - {ticket_info[1]}"
            )
            commenter_role = db.session.execute(
                text("SELECT role_id FROM users WHERE user_id = :uid"),
                {"uid": user_id}
            ).fetchone()
            if commenter_role and commenter_role[0] in (1, 2, 3, 5):
                try:
                    requester = db.session.execute(
                        text("SELECT first_name, last_name, email FROM users WHERE user_id = :uid"),
                        {"uid": ticket_info[2]}
                    ).fetchone()
                    if requester and requester[2]:
                        commenter = db.session.execute(
                            text("SELECT first_name, last_name FROM users WHERE user_id = :uid"),
                            {"uid": user_id}
                        ).fetchone()
                        sender_name = f"{commenter[0]} {commenter[1]}".strip() if commenter else "Support Agent"
                        from utils.email_service import send_ticket_reply_email
                        send_ticket_reply_email(
                            ticket_number=ticket_info[0],
                            ticket_title=ticket_info[1],
                            recipient_email=requester[2],
                            customer_name=f"{requester[0] or ''} {requester[1] or ''}".strip() or "Customer",
                            reply_text=reply_text,
                            sender_name=sender_name,
                            sender_role="Support Agent"
                        )
                except Exception as email_err:
                    logger.warning("Failed to send AI reply email: %s", email_err)
    except Exception as notif_err:
        logger.warning("Failed to create notification for AI reply: %s", notif_err)

    return jsonify({
        "success": True,
        "message": "Reply sent successfully",
        "ticket_id": ticket_id
    })



@tickets_bp.route('/priority-report', methods=['GET'])


def priority_report():


    query = text("""

        SELECT

            p.priority_name,

            COUNT(t.ticket_id) as total_tickets

        FROM priorities p

        LEFT JOIN tickets t

        ON p.priority_name = t.priority_name

        GROUP BY p.priority_name

        ORDER BY total_tickets DESC
    """)


    data = db.session.execute(query).fetchall()


    result = []


    for row in data:

        result.append({

            "priority_name": row[0],

            "total_tickets": row[1]

        })


    return jsonify(result), 200 




@tickets_bp.route('/search', methods=['GET'])


def search_tickets():


    ticket_number = request.args.get('ticket_number')

    status_name = request.args.get('status_name')

    priority_name = request.args.get('priority_name')

    department_id = request.args.get('department_id')

    assigned_to = request.args.get('assigned_to')


    query = """

        SELECT

            ticket_id,

            ticket_number,
            title,
            status_name,

            priority_name,

            department_id,

            assigned_to

        FROM tickets

        WHERE 1=1
    """


    params = {}


    if ticket_number:

        query += " AND ticket_number = :ticket_number"

        params["ticket_number"] = ticket_number


    if status_name:

        query += " AND status_name = :status_name"

        params["status_name"] = status_name


    if priority_name:

        query += " AND priority_name = :priority_name"

        params["priority_name"] = priority_name


    if department_id:

        query += " AND department_id = :department_id"

        params["department_id"] = department_id


    if assigned_to:

        query += " AND assigned_to = :assigned_to"

        params["assigned_to"] = assigned_to


    tickets = db.session.execute(

        text(query),

        params

    ).fetchall()


    result = []


    for t in tickets:

        result.append({

            "ticket_id": t[0],

            "ticket_number": t[1],

            "title": t[2],

            "status_name": t[3],

            "priority_name": t[4],

            "department_id": t[5],

            "assigned_to": t[6]

        })


    return jsonify(result), 200 


    ######## new module started here for exporting tickets to CSV#########



@tickets_bp.route('/export', methods=['GET'])


def export_tickets():


    tickets = db.session.execute(

        text("""

            SELECT

                ticket_id,

                ticket_number,
                title,
                status_name,

                priority_name,
                created_at

            FROM tickets

            ORDER BY ticket_id DESC
        """)

    ).fetchall()


    output = StringIO()


    writer = csv.writer(output)


    writer.writerow([

        "Ticket ID",

        "Ticket Number",

        "Title",

        "Status",

        "Priority",

        "Created At"

    ])


    for ticket in tickets:


        writer.writerow([

            ticket[0],

            ticket[1],

            ticket[2],

            ticket[3],

            ticket[4],

            ticket[5]

        ])


    response = Response(

        output.getvalue(),

        mimetype="text/csv"
    )


    response.headers[

        "Content-Disposition"

    ] = "attachment; filename=tickets.csv"


    return response




@tickets_bp.route('/audit-logs', methods=['GET'])


def get_audit_logs():


    logs = db.session.execute(

        text("""

            SELECT
                audit_id,
                user_id,
                action,
                created_at

            FROM audit_logs

            ORDER BY audit_id DESC
        """)

    ).fetchall()


    result = []


    for log in logs:

        result.append({

            "audit_id": log[0],

            "user_id": log[1],

            "action": log[2],

            "created_at": str(log[3])

        })


    return jsonify(result), 200