from flask import Blueprint, flash, redirect, render_template, request, url_for, jsonify
from flask_babel import gettext as _
from help_db import db
from sqlalchemy import text

ticket_assignment_bp = Blueprint('ticket_assignment', __name__)


@ticket_assignment_bp.route("/ticket-assignment")
def ticket_assignment():

    search = request.args.get("search", "")

    assignments = db.session.execute(

        text("""

        SELECT

            t.ticket_id,

            t.ticket_number,

            t.title,

            u.first_name,

            u.last_name

        FROM tickets t

        LEFT JOIN users u

        ON t.assigned_to = u.user_id

        WHERE

            t.ticket_number ILIKE :search

            OR

            t.title ILIKE :search

        ORDER BY t.ticket_id DESC

        """),

        {

            "search": f"%{search}%"

        }

    ).fetchall()
    
     # Support Agents Only
    users = db.session.execute(
        text("""
            SELECT
                user_id,
                first_name,
                last_name
            FROM users
            WHERE role_id = 3
              AND status = 'Active'
            ORDER BY first_name
        """)
    ).fetchall()
    
    return render_template(

        "ticket_assignment.html",

        assignments=assignments,
        
        users=users,

        search=search

    )


@ticket_assignment_bp.route('/api/ticket-assignment/search')
def api_ticket_assignment_search():
    q = request.args.get("q", "").strip()
    params = {}

    where_clauses = [
        "t.ticket_number ILIKE :search",
        "t.title ILIKE :search",
        "t.ticket_id::text ILIKE :search",
        "t.category_name ILIKE :search",
        "t.status_name ILIKE :search",
        "t.priority_name ILIKE :search",
        """COALESCE(r.first_name || ' ' || r.last_name, '') ILIKE :search""",
        "r.email ILIKE :search",
        """COALESCE(u.first_name || ' ' || u.last_name, '') ILIKE :search""",
        "COALESCE(d.department_name, '') ILIKE :search",
    ]
    params["search"] = f"%{q}%" if q else "%%"

    sql = """
        SELECT
            t.ticket_id,
            t.ticket_number,
            t.title,
            u.first_name,
            u.last_name
        FROM tickets t
        LEFT JOIN users u ON t.assigned_to = u.user_id
        LEFT JOIN users r ON t.requester_id = r.user_id
        LEFT JOIN departments d ON t.department_id = d.department_id
        WHERE {where}
        ORDER BY t.ticket_id DESC
    """.format(where=" OR ".join(where_clauses))

    if q:
        sql += " LIMIT 50"

    assignments = db.session.execute(text(sql), params).fetchall()

    rows = []
    for a in assignments:
        rows.append({
            "ticket_id": a.ticket_id,
            "ticket_number": a.ticket_number,
            "title": a.title,
            "first_name": a.first_name or '',
            "last_name": a.last_name or ''
        })

    return jsonify({"rows": rows, "count": len(rows)})


### assign ticket###
    
@ticket_assignment_bp.route("/assign-ticket", methods=["POST"])
def assign_ticket():

    ticket_id = request.form.get("ticket_id")
    assigned_to = request.form.get("assigned_to")

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

    db.session.commit()

    flash(_("ticket_assigned_successfully"), "success")

    return redirect("/ticket-assignment")
### save assign ticket ###

@ticket_assignment_bp.route("/save_ticket_assignment", methods=["POST"])
def save_ticket_assignment():

    ticket_id = request.form["ticket_id"]

    assigned_to = request.form["assigned_to"]

    db.session.execute(
        text("""
            UPDATE tickets
            SET assigned_to=:assigned_to
            WHERE ticket_id=:ticket_id
        """),
        {
            "assigned_to": assigned_to,
            "ticket_id": ticket_id
        }
    )

    db.session.commit()

    return redirect("/ticket-assignment")
