from flask import Blueprint, render_template, request, redirect, flash, jsonify, session
from flask_babel import gettext as _
from help_db import db
from sqlalchemy import text

departments_bp = Blueprint('departments', __name__)


def require_super_admin():
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

    if not role or role[0] not in ("Super Admin", "Admin"):
        flash(_("access_denied"), "danger")
        return redirect(url_for("login_page"))
    return None


def is_super_admin():
    user_id = session.get("user_id")
    if not user_id:
        return False
    role = db.session.execute(
        text("""
            SELECT r.role_name
            FROM users u
            JOIN roles r ON u.role_id = r.role_id
            WHERE u.user_id = :user_id
        """),
        {"user_id": user_id}
    ).fetchone()
    return bool(role and role[0] == "Super Admin")


@departments_bp.route("/departments")
def departments_page():
    auth_check = require_super_admin()
    if auth_check:
        return auth_check

    search = request.args.get("search", "")
    status = request.args.get("status", "")
    page = int(request.args.get("page", 1))
    per_page = 10

    query = """
        SELECT department_id, department_name, description, status, created_at
        FROM departments
        WHERE 1=1
    """
    params = {}

    if search:
        query += " AND (department_name ILIKE :search OR description ILIKE :search)"
        params["search"] = f"%{search}%"

    if status:
        query += " AND status = :status"
        params["status"] = status

    # Count total
    count_query = query.replace("SELECT department_id, department_name, description, status, created_at", "SELECT COUNT(*)")
    total = db.session.execute(text(count_query), params).scalar()

    # Pagination
    query += " ORDER BY department_id LIMIT :limit OFFSET :offset"
    params["limit"] = per_page
    params["offset"] = (page - 1) * per_page

    departments = db.session.execute(text(query), params).fetchall()

    total_pages = (total + per_page - 1) // per_page
    has_prev = page > 1
    has_next = page < total_pages

    # Stats
    total_departments = db.session.execute(text("SELECT COUNT(*) FROM departments")).scalar()
    active_departments = db.session.execute(text("SELECT COUNT(*) FROM departments WHERE status='Active'")).scalar()
    inactive_departments = db.session.execute(text("SELECT COUNT(*) FROM departments WHERE status='Inactive'")).scalar()

    return render_template(
        "departments.html",
        departments=departments,
        search=search,
        status=status,
        pagination={
            "page": page,
            "per_page": per_page,
            "total": total,
            "total_pages": total_pages,
            "has_prev": has_prev,
            "has_next": has_next,
            "prev_num": page - 1,
            "next_num": page + 1,
        },
        total_departments=total_departments,
        active_departments=active_departments,
        inactive_departments=inactive_departments,
        can_edit=is_super_admin()
    )


@departments_bp.route("/api/departments/search")
def api_departments_search():
    auth_check = require_super_admin()
    if auth_check:
        return jsonify({"error": "Unauthorized"}), 401

    q = request.args.get("q", "").strip()
    status = request.args.get("status", "")
    page = int(request.args.get("page", 1))
    per_page = 10

    query = """
        SELECT department_id, department_name, description, status, created_at
        FROM departments
        WHERE 1=1
    """
    params = {}

    if q:
        query += " AND (department_name ILIKE :search OR description ILIKE :search)"
        params["search"] = f"%{q}%"

    if status:
        query += " AND status = :status"
        params["status"] = status

    # Count total
    count_query = query.replace("SELECT department_id, department_name, description, status, created_at", "SELECT COUNT(*)")
    total = db.session.execute(text(count_query), params).scalar()

    # Pagination
    query += " ORDER BY department_id LIMIT :limit OFFSET :offset"
    params["limit"] = per_page
    params["offset"] = (page - 1) * per_page

    departments = db.session.execute(text(query), params).fetchall()

    rows = []
    for d in departments:
        rows.append({
            "department_id": d.department_id,
            "department_name": d.department_name,
            "description": d.description or "-",
            "status": d.status or "Active",
            "created_at": str(d.created_at) if d.created_at else "-",
        })

    return jsonify({
        "rows": rows,
        "count": len(rows),
        "total": total,
        "page": page,
        "per_page": per_page,
        "total_pages": (total + per_page - 1) // per_page,
    })


@departments_bp.route("/api/departments/toggle-status", methods=["POST"])
def api_toggle_status():
    auth_check = require_super_admin()
    if auth_check:
        return jsonify({"error": "Unauthorized"}), 401

    if not is_super_admin():
        return jsonify({"error": "Access denied"}), 403

    try:
        data = request.get_json() or {}
        department_id = data.get("department_id")
        new_status = data.get("status")

        if not department_id or new_status not in ("Active", "Inactive"):
            return jsonify({"error": "Invalid parameters"}), 400

        db.session.execute(
            text("UPDATE departments SET status = :status WHERE department_id = :department_id"),
            {"status": new_status, "department_id": department_id}
        )
        db.session.commit()

        return jsonify({"status": new_status, "department_id": department_id})
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": str(e)}), 500


@departments_bp.route("/add-department")
def add_department():
    auth_check = require_super_admin()
    if auth_check:
        return auth_check

    if not is_super_admin():
        flash(_("access_denied"), "danger")
        return redirect(url_for("departments.departments_page"))
    
    return render_template("add_department.html")


@departments_bp.route("/save-department", methods=["POST"])
def save_department():
    auth_check = require_super_admin()
    if auth_check:
        return auth_check

    if not is_super_admin():
        flash(_("access_denied"), "danger")
        return redirect(url_for("departments.departments_page"))

    department_name = request.form.get("department_name")
    description = request.form.get("description", "")
    status = request.form.get("status", "Active")

    check_query = text("""
        SELECT department_id
        FROM departments
        WHERE department_name = :department_name
    """)

    department = db.session.execute(
        check_query,
        {"department_name": department_name}
    ).fetchone()

    if department:
        flash(_("department_already_exists"), "warning")
        return redirect("/departments")

    insert_query = text("""
        INSERT INTO departments (department_name, description, status)
        VALUES (:department_name, :description, :status)
    """)

    db.session.execute(
        insert_query,
        {"department_name": department_name, "description": description, "status": status}
    )
    db.session.commit()

    flash(_("department_added_successfully"), "success")
    return redirect("/departments")


@departments_bp.route("/edit-department/<int:id>")
def edit_department(id):
    auth_check = require_super_admin()
    if auth_check:
        return auth_check

    department = db.session.execute(
        text("""
            SELECT *
            FROM departments
            WHERE department_id=:id
        """),
        {"id": id}
    ).fetchone()

    if not department:
        flash(_("department_not_found"), "danger")
        return redirect(url_for("departments.departments_page"))

    return render_template(
        "edit_department.html",
        department=department
    )


@departments_bp.route("/update-department/<int:id>", methods=["POST"])
def update_department(id):
    auth_check = require_super_admin()
    if auth_check:
        return auth_check

    if not is_super_admin():
        flash(_("access_denied"), "danger")
        return redirect(url_for("departments.departments_page"))

    department_name = request.form["department_name"]
    description = request.form.get("description", "")
    status = request.form["status"]

    db.session.execute(
        text("""
            UPDATE departments
            SET department_name=:department_name,
                description=:description,
                status=:status
            WHERE department_id=:id
        """),
        {
            "department_name": department_name,
            "description": description,
            "status": status,
            "id": id
        }
    )
    db.session.commit()

    flash(_("department_updated_successfully"), "success")
    return redirect("/departments")


@departments_bp.route("/delete-department/<int:id>", methods=["POST"])
def delete_department(id):
    auth_check = require_super_admin()
    if auth_check:
        return auth_check

    if not is_super_admin():
        flash(_("access_denied"), "danger")
        return redirect(url_for("departments.departments_page"))

    # Check for references in users table
    user_count = db.session.execute(
        text("""
            SELECT COUNT(*)
            FROM users
            WHERE department_id = :id
        """),
        {"id": id}
    ).scalar()

    if user_count > 0:
        flash(_("department_cannot_be_deleted_because_users_are_assigned_to_it"), "danger")
        return redirect("/departments")

    # Check for references in skills table
    skill_count = db.session.execute(
        text("""
            SELECT COUNT(*)
            FROM skills
            WHERE department_id = :id
        """),
        {"id": id}
    ).scalar()

    if skill_count > 0:
        flash(_("department_cannot_be_deleted_because_skills_are_assigned_to_it"), "danger")
        return redirect("/departments")

    # Check for references in tickets table
    ticket_count = db.session.execute(
        text("""
            SELECT COUNT(*)
            FROM tickets
            WHERE department_id = :id
        """),
        {"id": id}
    ).scalar()

    if ticket_count > 0:
        flash(_("department_cannot_be_deleted_because_tickets_are_assigned_to_it"), "danger")
        return redirect("/departments")

    # Check for references in categories table (if department_id column exists)
    try:
        category_count = db.session.execute(
            text("""
                SELECT COUNT(*)
                FROM categories
                WHERE department_id = :id
            """),
            {"id": id}
        ).scalar()

        if category_count > 0:
            flash(_("department_cannot_be_deleted_because_categories_are_assigned_to_it"), "danger")
            return redirect("/departments")
    except Exception:
        # department_id column might not exist in categories table
        pass

    try:
        db.session.execute(
            text("""
                DELETE FROM departments
                WHERE department_id = :id
            """),
            {"id": id}
        )
        db.session.commit()

        flash(_("department_deleted_successfully"), "success")
    except Exception as e:
        db.session.rollback()
        # Handle foreign key constraint violations
        if "foreign key constraint" in str(e).lower() or "violates foreign key" in str(e).lower():
            flash(_("department_cannot_be_deleted_because_it_is_referenced_by_other_records"), "danger")
        else:
            flash(_("an_error_occurred"), "danger")
        return redirect("/departments")

    return redirect("/departments")