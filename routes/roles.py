from flask import Blueprint, render_template, request, redirect, flash, jsonify, session, url_for
from flask_babel import gettext as _
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from help_db import db

roles_bp = Blueprint('roles', __name__)


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


@roles_bp.route("/roles")
def roles_page():
    auth_check = require_super_admin()
    if auth_check:
        return auth_check

    search = request.args.get("search", "")
    page = int(request.args.get("page", 1))
    per_page = 10

    query = """
        SELECT role_id, role_name, description
        FROM roles
        WHERE 1=1
    """
    params = {}

    if search:
        query += " AND (role_name ILIKE :search OR description ILIKE :search)"
        params["search"] = f"%{search}%"

    # Count total
    count_query = query.replace("SELECT role_id, role_name, description", "SELECT COUNT(*)")
    total = db.session.execute(text(count_query), params).scalar()

    # Pagination
    query += " ORDER BY role_id LIMIT :limit OFFSET :offset"
    params["limit"] = per_page
    params["offset"] = (page - 1) * per_page

    roles = db.session.execute(text(query), params).fetchall()

    total_pages = (total + per_page - 1) // per_page
    has_prev = page > 1
    has_next = page < total_pages

    return render_template(
        "roles.html",
        roles=roles,
        search=search,
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
        can_edit=is_super_admin()
    )


@roles_bp.route("/api/roles/search")
def api_roles_search():
    auth_check = require_super_admin()
    if auth_check:
        return jsonify({"error": "Unauthorized"}), 401

    q = request.args.get("q", "").strip()
    page = int(request.args.get("page", 1))
    per_page = 10

    query = """
        SELECT role_id, role_name, description
        FROM roles
        WHERE 1=1
    """
    params = {}

    if q:
        query += " AND (role_name ILIKE :search OR description ILIKE :search)"
        params["search"] = f"%{q}%"

    # Count total
    count_query = query.replace("SELECT role_id, role_name, description", "SELECT COUNT(*)")
    total = db.session.execute(text(count_query), params).scalar()

    # Pagination
    query += " ORDER BY role_id LIMIT :limit OFFSET :offset"
    params["limit"] = per_page
    params["offset"] = (page - 1) * per_page

    roles = db.session.execute(text(query), params).fetchall()

    rows = []
    for r in roles:
        rows.append({
            "role_id": r.role_id,
            "role_name": r.role_name,
            "description": r.description or "-",
        })

    return jsonify({
        "rows": rows,
        "count": len(rows),
        "total": total,
        "page": page,
        "per_page": per_page,
        "total_pages": (total + per_page - 1) // per_page,
    })


@roles_bp.route("/add-role", methods=["POST"])
def add_role():
    auth_check = require_super_admin()
    if auth_check:
        return auth_check

    if not is_super_admin():
        flash(_("access_denied"), "danger")
        return redirect(url_for("roles.roles_page"))

    role_name = request.form.get("role_name")
    description = request.form.get("description")

    if not role_name:
        flash(_("role_name_required"), "danger")
        return redirect(url_for("roles.roles_page"))

    existing = db.session.execute(
        text("SELECT 1 FROM roles WHERE LOWER(role_name) = LOWER(:role_name)"),
        {"role_name": role_name}
    ).fetchone()

    if existing:
        flash(_("role_already_exists"), "warning")
        return redirect(url_for("roles.roles_page"))

    try:
        db.session.execute(
            text("""
                INSERT INTO roles (role_name, description)
                VALUES (:role_name, :description)
            """),
            {"role_name": role_name, "description": description}
        )
        db.session.commit()
        flash(_("role_added_successfully"), "success")
    except IntegrityError:
        db.session.rollback()
        flash(_("error_adding_role"), "danger")

    return redirect(url_for("roles.roles_page"))


@roles_bp.route("/edit-role/<int:id>", methods=["POST"])
def edit_role(id):
    auth_check = require_super_admin()
    if auth_check:
        return auth_check

    if not is_super_admin():
        flash(_("access_denied"), "danger")
        return redirect(url_for("roles.roles_page"))

    role_name = request.form.get("role_name")
    description = request.form.get("description")

    if not role_name:
        flash(_("role_name_required"), "danger")
        return redirect(url_for("roles.roles_page"))

    existing = db.session.execute(
        text("SELECT 1 FROM roles WHERE LOWER(role_name) = LOWER(:role_name) AND role_id != :id"),
        {"role_name": role_name, "id": id}
    ).fetchone()

    if existing:
        flash(_("another_role_with_this_name_already_exists"), "warning")
        return redirect(url_for("roles.roles_page"))

    try:
        db.session.execute(
            text("""
                UPDATE roles
                SET role_name = :role_name,
                    description = :description
                WHERE role_id = :id
            """),
            {"role_name": role_name, "description": description, "id": id}
        )
        db.session.commit()
        flash(_("role_updated_successfully"), "success")
    except IntegrityError:
        db.session.rollback()
        flash(_("error_updating_role"), "danger")

    return redirect(url_for("roles.roles_page"))


@roles_bp.route("/delete-role/<int:id>", methods=["POST"])
def delete_role(id):
    auth_check = require_super_admin()
    if auth_check:
        return auth_check

    if not is_super_admin():
        flash(_("access_denied"), "danger")
        return redirect(url_for("roles.roles_page"))

    # Check if role is assigned to any user
    user_count = db.session.execute(
        text("SELECT COUNT(*) FROM users WHERE role_id = :id"),
        {"id": id}
    ).scalar()

    if user_count > 0:
        flash(_("role_cannot_be_deleted_because_users_are_assigned"), "danger")
        return redirect(url_for("roles.roles_page"))

    try:
        db.session.execute(
            text("DELETE FROM roles WHERE role_id = :id"),
            {"id": id}
        )
        db.session.commit()
        flash(_("role_deleted_successfully"), "success")
    except IntegrityError:
        db.session.rollback()
        flash(_("error_deleting_role"), "danger")

    return redirect(url_for("roles.roles_page"))