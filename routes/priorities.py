from flask import Blueprint, render_template, request, redirect, flash, url_for, jsonify, session
from flask_babel import gettext as _
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from help_db import db

priorities_bp = Blueprint('priorities', __name__)


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


@priorities_bp.route("/priorities")
def priorities_page():
    auth_check = require_super_admin()
    if auth_check:
        return auth_check

    search = request.args.get("search", "")
    page = int(request.args.get("page", 1))
    per_page = 10

    query = """
        SELECT priority_name
        FROM priorities
        WHERE 1=1
    """
    params = {}

    if search:
        query += " AND priority_name ILIKE :search"
        params["search"] = f"%{search}%"

    # Count total
    count_query = query.replace("SELECT priority_name", "SELECT COUNT(*)")
    total = db.session.execute(text(count_query), params).scalar()

    # Pagination
    query += " ORDER BY priority_name LIMIT :limit OFFSET :offset"
    params["limit"] = per_page
    params["offset"] = (page - 1) * per_page

    priorities = db.session.execute(text(query), params).fetchall()

    total_pages = (total + per_page - 1) // per_page
    has_prev = page > 1
    has_next = page < total_pages

    # Stats
    total_priorities = db.session.execute(text("SELECT COUNT(*) FROM priorities")).scalar()

    return render_template(
        "priorities.html",
        priorities=priorities,
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
        total_priorities=total_priorities,
        can_edit=is_super_admin()
    )


@priorities_bp.route("/api/priorities/search")
def api_priorities_search():
    auth_check = require_super_admin()
    if auth_check:
        return jsonify({"error": "Unauthorized"}), 401

    q = request.args.get("q", "").strip()
    page = int(request.args.get("page", 1))
    per_page = 10

    query = """
        SELECT priority_name
        FROM priorities
        WHERE 1=1
    """
    params = {}

    if q:
        query += " AND priority_name ILIKE :search"
        params["search"] = f"%{q}%"

    # Count total
    count_query = query.replace("SELECT priority_name", "SELECT COUNT(*)")
    total = db.session.execute(text(count_query), params).scalar()

    # Pagination
    query += " ORDER BY priority_name LIMIT :limit OFFSET :offset"
    params["limit"] = per_page
    params["offset"] = (page - 1) * per_page

    priorities = db.session.execute(text(query), params).fetchall()

    rows = []
    for p in priorities:
        rows.append({
            "priority_name": p.priority_name,
        })

    return jsonify({
        "rows": rows,
        "count": len(rows),
        "total": total,
        "page": page,
        "per_page": per_page,
        "total_pages": (total + per_page - 1) // per_page,
    })


@priorities_bp.route("/priorities/add", methods=["POST"])
def add_priority():
    auth_check = require_super_admin()
    if auth_check:
        return auth_check

    if not is_super_admin():
        flash(_("access_denied"), "danger")
        return redirect(url_for("priorities.priorities_page"))

    priority_name = request.form.get("priority_name", "").strip()

    if not priority_name:
        flash(_("priority_name_required"), "danger")
        return redirect(url_for("priorities.priorities_page"))

    existing = db.session.execute(
        text("SELECT 1 FROM priorities WHERE LOWER(priority_name) = LOWER(:priority_name)"),
        {"priority_name": priority_name}
    ).fetchone()

    if existing:
        flash(_("priority_already_exists"), "warning")
        return redirect(url_for("priorities.priorities_page"))

    try:
        db.session.execute(
            text("INSERT INTO priorities (priority_name) VALUES (:priority_name)"),
            {"priority_name": priority_name}
        )
        db.session.commit()
        flash(_("priority_added_successfully"), "success")
    except IntegrityError:
        db.session.rollback()
        flash(_("error_adding_priority"), "danger")

    return redirect(url_for("priorities.priorities_page"))


@priorities_bp.route("/priorities/update/<priority_name>", methods=["POST"])
def update_priority(priority_name):
    auth_check = require_super_admin()
    if auth_check:
        return auth_check

    if not is_super_admin():
        flash(_("access_denied"), "danger")
        return redirect(url_for("priorities.priorities_page"))

    new_priority = request.form.get("priority_name", "").strip()

    if not new_priority:
        flash(_("priority_name_required"), "danger")
        return redirect(url_for("priorities.priorities_page"))

    existing = db.session.execute(
        text("SELECT 1 FROM priorities WHERE LOWER(priority_name) = LOWER(:priority_name) AND priority_name != :old_priority"),
        {"priority_name": new_priority, "old_priority": priority_name}
    ).fetchone()

    if existing:
        flash(_("another_priority_with_this_name_already_exists"), "warning")
        return redirect(url_for("priorities.priorities_page"))

    try:
        db.session.execute(
            text("UPDATE priorities SET priority_name = :new_priority WHERE priority_name = :old_priority"),
            {"new_priority": new_priority, "old_priority": priority_name}
        )
        db.session.commit()
        flash(_("priority_updated_successfully"), "success")
    except IntegrityError:
        db.session.rollback()
        flash(_("error_updating_priority"), "danger")

    return redirect(url_for("priorities.priorities_page"))


@priorities_bp.route("/priorities/delete/<priority_name>", methods=["POST"])
def delete_priority(priority_name):
    auth_check = require_super_admin()
    if auth_check:
        return auth_check

    if not is_super_admin():
        flash(_("access_denied"), "danger")
        return redirect(url_for("priorities.priorities_page"))

    # Check if priority is used in tickets
    used = db.session.execute(
        text("SELECT 1 FROM tickets WHERE priority_name = :priority_name LIMIT 1"),
        {"priority_name": priority_name}
    ).fetchone()

    if used:
        flash(_("priority_is_in_use_and_cannot_be_deleted"), "warning")
        return redirect(url_for("priorities.priorities_page"))

    try:
        db.session.execute(
            text("DELETE FROM priorities WHERE priority_name = :priority_name"),
            {"priority_name": priority_name}
        )
        db.session.commit()
        flash(_("priority_deleted_successfully"), "success")
    except IntegrityError:
        db.session.rollback()
        flash(_("error_deleting_priority"), "danger")

    return redirect(url_for("priorities.priorities_page"))