from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify, session
from flask_babel import gettext as _
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from help_db import db

issue_types_bp = Blueprint('issue_types', __name__)


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


@issue_types_bp.route("/issue-types", methods=["GET", "POST"])
def issue_types_page():
    if request.method == "POST":
        flash(_("Action could not be interpreted. Please hard refresh your browser (Ctrl+Shift+R)."), "warning")
        return redirect(url_for("issue_types.issue_types_page"))
    auth_check = require_super_admin()
    if auth_check:
        return auth_check

    search = request.args.get("search", "")
    category_filter = request.args.get("category_name", "")
    status_filter = request.args.get("status", "")
    page = int(request.args.get("page", 1))
    per_page = 10

    query = """
        SELECT it.issue_type_id, it.issue_name, it.category_name, it.description, it.status, it.created_at,
               c.department_id, d.department_name
        FROM issue_types it
        JOIN categories c ON it.category_name = c.category_name
        LEFT JOIN departments d ON c.department_id = d.department_id
        WHERE 1=1
    """
    params = {}

    if search:
        query += " AND (it.issue_name ILIKE :search OR it.description ILIKE :search)"
        params["search"] = f"%{search}%"

    if category_filter:
        query += " AND it.category_name = :category_name"
        params["category_name"] = category_filter

    if status_filter:
        query += " AND it.status = :status"
        params["status"] = status_filter

    # Count total
    count_query = query.replace("SELECT it.issue_type_id, it.issue_name, it.category_name, it.description, it.status, it.created_at, c.department_id, c.department_name", "SELECT COUNT(*)")
    total = db.session.execute(text(count_query), params).scalar() or 0

    # Pagination
    query += " ORDER BY it.category_name, it.issue_name LIMIT :limit OFFSET :offset"
    params["limit"] = per_page
    params["offset"] = (page - 1) * per_page

    issue_types = db.session.execute(text(query), params).fetchall()

    total = total or 0
    total_pages = (total + per_page - 1) // per_page
    has_prev = page > 1
    has_next = page < total_pages

    # Stats
    total_issue_types = db.session.execute(text("SELECT COUNT(*) FROM issue_types")).scalar()
    active_issue_types = db.session.execute(text("SELECT COUNT(*) FROM issue_types WHERE status='Active'")).scalar()
    inactive_issue_types = db.session.execute(text("SELECT COUNT(*) FROM issue_types WHERE status='Inactive'")).scalar()

    categories = db.session.execute(
        text("SELECT category_name, department_id FROM categories ORDER BY category_name")
    ).fetchall()

    layout_template = "layout.html" if is_super_admin() else "layout_admin.html"

    return render_template(
        "issue_types.html",
        layout_template=layout_template,
        issue_types=issue_types,
        categories=categories,
        search=search,
        category_filter=category_filter,
        status_filter=status_filter,
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
        total_issue_types=total_issue_types,
        active_issue_types=active_issue_types,
        inactive_issue_types=inactive_issue_types,
        can_edit=True
    )


@issue_types_bp.route("/api/issue-types/search")
def api_issue_types_search():
    auth_check = require_super_admin()
    if auth_check:
        return jsonify({"error": "Unauthorized"}), 401

    q = request.args.get("q", "").strip()
    category_filter = request.args.get("category_name", "")
    status_filter = request.args.get("status", "")
    page = int(request.args.get("page", 1))
    per_page = 10

    query = """
        SELECT it.issue_type_id, it.issue_name, it.category_name, it.description, it.status, it.created_at,
               c.department_id, d.department_name
        FROM issue_types it
        JOIN categories c ON it.category_name = c.category_name
        LEFT JOIN departments d ON c.department_id = d.department_id
        WHERE 1=1
    """
    params = {}

    if q:
        query += " AND (it.issue_name ILIKE :search OR it.description ILIKE :search)"
        params["search"] = f"%{q}%"

    if category_filter:
        query += " AND it.category_name = :category_name"
        params["category_name"] = category_filter

    if status_filter:
        query += " AND it.status = :status"
        params["status"] = status_filter

    # Count total
    count_query = query.replace("SELECT it.issue_type_id, it.issue_name, it.category_name, it.description, it.status, it.created_at, c.department_id, d.department_name", "SELECT COUNT(*)")
    total = db.session.execute(text(count_query), params).scalar()

    # Pagination
    query += " ORDER BY it.category_name, it.issue_name LIMIT :limit OFFSET :offset"
    params["limit"] = per_page
    params["offset"] = (page - 1) * per_page

    issue_types = db.session.execute(text(query), params).fetchall()

    rows = []
    for it in issue_types:
        rows.append({
            "issue_type_id": it.issue_type_id,
            "issue_name": it.issue_name,
            "category_name": it.category_name,
            "description": it.description or "-",
            "status": it.status or "Active",
            "created_at": str(it.created_at) if it.created_at else "-",
            "department_name": it.department_name or "-",
        })

    total = total or 0
    return jsonify({
        "rows": rows,
        "count": len(rows),
        "total": total,
        "page": page,
        "per_page": per_page,
        "total_pages": (total + per_page - 1) // per_page,
    })


@issue_types_bp.route("/api/toggle-status", methods=["POST"])
def api_toggle_status():
    auth_check = require_super_admin()
    if auth_check:
        return jsonify({"error": "Unauthorized"}), 401

    try:
        data = request.get_json() or {}
        issue_type_id = data.get("issue_type_id")
        new_status = data.get("status")

        if not issue_type_id or new_status not in ("Active", "Inactive"):
            return jsonify({"error": "Invalid parameters"}), 400

        db.session.execute(
            text("UPDATE issue_types SET status = :status WHERE issue_type_id = :issue_type_id"),
            {"status": new_status, "issue_type_id": issue_type_id}
        )
        db.session.commit()

        return jsonify({"status": new_status, "issue_type_id": issue_type_id})
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": str(e)}), 500


@issue_types_bp.route("/issue-types/add", methods=["POST"])
def add_issue_type():
    auth_check = require_super_admin()
    if auth_check:
        return auth_check

    issue_name = request.form.get("issue_name", "").strip()
    category_name = request.form.get("category_name", "").strip()
    description = request.form.get("description", "").strip()
    status = request.form.get("status", "Active").strip()

    if not issue_name or not category_name:
        flash(_("issue_type_name_and_category_are_required"), "danger")
        return redirect(url_for("issue_types.issue_types_page"))

    existing = db.session.execute(
        text("SELECT 1 FROM issue_types WHERE LOWER(issue_name) = LOWER(:issue_name)"),
        {"issue_name": issue_name}
    ).fetchone()

    if existing:
        flash(_("issue_type_already_exists"), "warning")
        return redirect(url_for("issue_types.issue_types_page"))

    try:
        db.session.execute(
            text("""
                INSERT INTO issue_types (issue_name, category_name, description, status)
                VALUES (:issue_name, :category_name, :description, :status)
            """),
            {
                "issue_name": issue_name,
                "category_name": category_name,
                "description": description,
                "status": status
            }
        )
        db.session.commit()
        flash(_("issue_type_added_successfully"), "success")
    except IntegrityError:
        db.session.rollback()
        flash(_("error_adding_issue_type"), "danger")

    return redirect(url_for("issue_types.issue_types_page"))


@issue_types_bp.route("/issue-types/edit/<int:issue_type_id>", methods=["POST"])
def edit_issue_type(issue_type_id):
    auth_check = require_super_admin()
    if auth_check:
        return auth_check

    issue_name = request.form.get("issue_name", "").strip()
    category_name = request.form.get("category_name", "").strip()
    description = request.form.get("description", "").strip()
    status = request.form.get("status", "Active").strip()

    if not issue_name or not category_name:
        flash(_("issue_type_name_and_category_are_required"), "danger")
        return redirect(url_for("issue_types.issue_types_page"))

    existing = db.session.execute(
        text("SELECT 1 FROM issue_types WHERE LOWER(issue_name) = LOWER(:issue_name) AND issue_type_id != :issue_type_id"),
        {"issue_name": issue_name, "issue_type_id": issue_type_id}
    ).fetchone()

    if existing:
        flash(_("another_issue_type_with_this_name_already_exists"), "warning")
        return redirect(url_for("issue_types.issue_types_page"))

    try:
        db.session.execute(
            text("""
                UPDATE issue_types
                SET issue_name = :issue_name,
                    category_name = :category_name,
                    description = :description,
                    status = :status,
                    updated_at = CURRENT_TIMESTAMP
                WHERE issue_type_id = :issue_type_id
            """),
            {
                "issue_name": issue_name,
                "category_name": category_name,
                "description": description,
                "status": status,
                "issue_type_id": issue_type_id
            }
        )
        db.session.commit()
        flash(_("issue_type_updated_successfully"), "success")
    except IntegrityError:
        db.session.rollback()
        flash(_("error_updating_issue_type"), "danger")

    return redirect(url_for("issue_types.issue_types_page"))


@issue_types_bp.route("/issue-types/delete/<int:issue_type_id>", methods=["POST"])
def delete_issue_type(issue_type_id):
    auth_check = require_super_admin()
    if auth_check:
        return auth_check

    try:
        # Nullify foreign key references in tickets to allow clean deletion
        db.session.execute(
            text("UPDATE tickets SET issue_type_id = NULL WHERE issue_type_id = :issue_type_id"),
            {"issue_type_id": issue_type_id}
        )
        # Perform permanent hard deletion
        db.session.execute(
            text("DELETE FROM issue_types WHERE issue_type_id = :issue_type_id"),
            {"issue_type_id": issue_type_id}
        )
        db.session.commit()
        flash(_("issue_type_deleted_successfully"), "success")
    except Exception as e:
        db.session.rollback()
        flash(f"Error: {str(e)}", "danger")

    return redirect(url_for("issue_types.issue_types_page"))


@issue_types_bp.route("/api/issue-types")
def api_issue_types():
    category_name = request.args.get("category_name", "")

    if category_name:
        issue_types = db.session.execute(
            text("""
                SELECT issue_type_id, issue_name
                FROM issue_types
                WHERE category_name = :category_name AND status = 'Active'
                ORDER BY issue_name
            """),
            {"category_name": category_name}
        ).fetchall()
    else:
        issue_types = db.session.execute(
            text("""
                SELECT issue_type_id, issue_name
                FROM issue_types
                WHERE status = 'Active'
                ORDER BY issue_name
            """)
        ).fetchall()

    return jsonify([
        {"issue_type_id": r[0], "issue_name": r[1]}
        for r in issue_types
    ])