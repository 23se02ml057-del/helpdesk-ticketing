from flask import Blueprint, render_template, request, redirect, flash, url_for, jsonify, session
from flask_babel import gettext as _
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from help_db import db

escalations_bp = Blueprint('escalations', __name__)


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


@escalations_bp.route("/escalations")
def escalations():
    auth_check = require_super_admin()
    if auth_check:
        return auth_check

    search = request.args.get("search", "")
    priority_filter = request.args.get("priority_name", "")
    status_filter = request.args.get("status", "")
    page = int(request.args.get("page", 1))
    per_page = 10

    query = """
        SELECT
            e.escalation_id,
            p.priority_name,
            e.response_time,
            e.escalation_after,
            e.notify_role,
            e.status
        FROM escalations e
        JOIN priorities p ON e.priority_id = p.priority_id
        WHERE 1=1
    """
    params = {}

    if search:
        query += " AND (p.priority_name ILIKE :search OR e.notify_role ILIKE :search)"
        params["search"] = f"%{search}%"

    if priority_filter:
        query += " AND p.priority_name = :priority_name"
        params["priority_name"] = priority_filter

    if status_filter:
        query += " AND e.status = :status"
        params["status"] = status_filter

    # Count total
    count_query = query.replace(
        "SELECT\n            e.escalation_id,\n            p.priority_name,\n            e.response_time,\n            e.escalation_after,\n            e.notify_role,\n            e.status",
        "SELECT COUNT(*)"
    )
    total = db.session.execute(text(count_query), params).scalar()

    # Pagination
    query += " ORDER BY e.escalation_id DESC LIMIT :limit OFFSET :offset"
    params["limit"] = per_page
    params["offset"] = (page - 1) * per_page

    escalations = db.session.execute(text(query), params).fetchall()

    total_pages = (total + per_page - 1) // per_page
    has_prev = page > 1
    has_next = page < total_pages

    # Stats
    total_escalations = db.session.execute(text("SELECT COUNT(*) FROM escalations")).scalar()
    active_escalations = db.session.execute(text("SELECT COUNT(*) FROM escalations WHERE status='Active'")).scalar()
    inactive_escalations = db.session.execute(text("SELECT COUNT(*) FROM escalations WHERE status='Inactive'")).scalar()

    priorities = db.session.execute(
        text("SELECT priority_name FROM priorities ORDER BY priority_name")
    ).fetchall()

    roles = db.session.execute(
        text("SELECT role_name FROM roles ORDER BY role_name")
    ).fetchall()

    return render_template(
        "escalations.html",
        escalations=escalations,
        priorities=priorities,
        roles=roles,
        search=search,
        priority_filter=priority_filter,
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
        total_escalations=total_escalations,
        active_escalations=active_escalations,
        inactive_escalations=inactive_escalations,
        can_edit=is_super_admin()
    )


@escalations_bp.route("/api/escalations/search")
def api_escalations_search():
    auth_check = require_super_admin()
    if auth_check:
        return jsonify({"error": "Unauthorized"}), 401

    q = request.args.get("q", "").strip()
    priority_filter = request.args.get("priority_name", "")
    status_filter = request.args.get("status", "")
    page = int(request.args.get("page", 1))
    per_page = 10

    query = """
        SELECT
            e.escalation_id,
            p.priority_name,
            e.response_time,
            e.escalation_after,
            e.notify_role,
            e.status
        FROM escalations e
        JOIN priorities p ON e.priority_id = p.priority_id
        WHERE 1=1
    """
    params = {}

    if q:
        query += " AND (p.priority_name ILIKE :search OR e.notify_role ILIKE :search)"
        params["search"] = f"%{q}%"

    if priority_filter:
        query += " AND p.priority_name = :priority_name"
        params["priority_name"] = priority_filter

    if status_filter:
        query += " AND e.status = :status"
        params["status"] = status_filter

    # Count total
    count_query = query.replace(
        "SELECT\n            e.escalation_id,\n            p.priority_name,\n            e.response_time,\n            e.escalation_after,\n            e.notify_role,\n            e.status",
        "SELECT COUNT(*)"
    )
    total = db.session.execute(text(count_query), params).scalar()

    # Pagination
    query += " ORDER BY e.escalation_id DESC LIMIT :limit OFFSET :offset"
    params["limit"] = per_page
    params["offset"] = (page - 1) * per_page

    escalations = db.session.execute(text(query), params).fetchall()

    rows = []
    for e in escalations:
        rows.append({
            "escalation_id": e.escalation_id,
            "priority_name": e.priority_name,
            "response_time": e.response_time or 0,
            "escalation_after": e.escalation_after,
            "notify_role": e.notify_role,
            "status": e.status or "Active",
        })

    return jsonify({
        "rows": rows,
        "count": len(rows),
        "total": total,
        "page": page,
        "per_page": per_page,
        "total_pages": (total + per_page - 1) // per_page,
    })


@escalations_bp.route("/api/escalations/toggle-status", methods=["POST"])
def api_toggle_escalation_status():
    auth_check = require_super_admin()
    if auth_check:
        return jsonify({"error": "Unauthorized"}), 401

    if not is_super_admin():
        return jsonify({"error": "Access denied"}), 403

    try:
        data = request.get_json() or {}
        escalation_id = data.get("escalation_id")
        new_status = data.get("status")

        if not escalation_id or new_status not in ("Active", "Inactive"):
            return jsonify({"error": "Invalid parameters"}), 400

        db.session.execute(
            text("UPDATE escalations SET status = :status WHERE escalation_id = :escalation_id"),
            {"status": new_status, "escalation_id": escalation_id}
        )
        db.session.commit()

        return jsonify({"status": new_status, "escalation_id": escalation_id})
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": str(e)}), 500


@escalations_bp.route("/escalations/add", methods=["POST"])
def add_escalation():
    auth_check = require_super_admin()
    if auth_check:
        return auth_check

    if not is_super_admin():
        flash(_("access_denied"), "danger")
        return redirect(url_for("escalations.escalations"))

    priority_name = request.form.get("priority_name", "").strip()
    response_time = request.form.get("response_time", "").strip()
    escalation_after = request.form.get("escalation_after", "").strip()
    notify_role = request.form.get("notify_role", "").strip()
    status = request.form.get("status", "Active").strip()

    if not priority_name or not response_time or not escalation_after or not notify_role:
        flash(_("all_fields_required"), "danger")
        return redirect(url_for("escalations.escalations"))

    priority = db.session.execute(
        text("SELECT priority_id FROM priorities WHERE priority_name = :priority_name"),
        {"priority_name": priority_name}
    ).fetchone()

    if not priority:
        flash(_("priority_not_found"), "danger")
        return redirect(url_for("escalations.escalations"))

    try:
        db.session.execute(
            text("""
                INSERT INTO escalations (priority_id, response_time, escalation_after, notify_role, status)
                VALUES (:priority_id, :response_time, :escalation_after, :notify_role, :status)
            """),
            {
                "priority_id": priority.priority_id,
                "response_time": int(response_time),
                "escalation_after": int(escalation_after),
                "notify_role": notify_role,
                "status": status
            }
        )
        db.session.commit()
        flash(_("escalation_added_successfully"), "success")
    except IntegrityError:
        db.session.rollback()
        flash(_("error_adding_escalation"), "danger")

    return redirect(url_for("escalations.escalations"))


@escalations_bp.route("/escalations/update/<int:escalation_id>", methods=["POST"])
def update_escalation(escalation_id):
    auth_check = require_super_admin()
    if auth_check:
        return auth_check

    if not is_super_admin():
        flash(_("access_denied"), "danger")
        return redirect(url_for("escalations.escalations"))

    priority_name = request.form.get("priority_name", "").strip()
    response_time = request.form.get("response_time", "").strip()
    escalation_after = request.form.get("escalation_after", "").strip()
    notify_role = request.form.get("notify_role", "").strip()
    status = request.form.get("status", "Active").strip()

    if not priority_name or not response_time or not escalation_after or not notify_role:
        flash(_("all_fields_required"), "danger")
        return redirect(url_for("escalations.escalations"))

    priority = db.session.execute(
        text("SELECT priority_id FROM priorities WHERE priority_name = :priority_name"),
        {"priority_name": priority_name}
    ).fetchone()

    if not priority:
        flash(_("priority_not_found"), "danger")
        return redirect(url_for("escalations.escalations"))

    try:
        db.session.execute(
            text("""
                UPDATE escalations
                SET priority_id = :priority_id,
                    response_time = :response_time,
                    escalation_after = :escalation_after,
                    notify_role = :notify_role,
                    status = :status
                WHERE escalation_id = :escalation_id
            """),
            {
                "priority_id": priority.priority_id,
                "response_time": int(response_time),
                "escalation_after": int(escalation_after),
                "notify_role": notify_role,
                "status": status,
                "escalation_id": escalation_id
            }
        )
        db.session.commit()
        flash(_("escalation_updated_successfully"), "success")
    except IntegrityError:
        db.session.rollback()
        flash(_("error_updating_escalation"), "danger")

    return redirect(url_for("escalations.escalations"))


@escalations_bp.route("/escalations/delete/<int:escalation_id>", methods=["POST"])
def delete_escalation(escalation_id):
    auth_check = require_super_admin()
    if auth_check:
        return auth_check

    if not is_super_admin():
        flash(_("access_denied"), "danger")
        return redirect(url_for("escalations.escalations"))

    try:
        db.session.execute(
            text("DELETE FROM escalations WHERE escalation_id = :escalation_id"),
            {"escalation_id": escalation_id}
        )
        db.session.commit()
        flash(_("escalation_deleted_successfully"), "success")
    except IntegrityError:
        db.session.rollback()
        flash(_("error_deleting_escalation"), "danger")

    return redirect(url_for("escalations.escalations"))