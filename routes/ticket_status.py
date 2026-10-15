from flask import Blueprint, render_template, request, redirect, flash, url_for, jsonify, session
from flask_babel import gettext as _
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from help_db import db

ticket_status_bp = Blueprint('ticket_status', __name__)


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


@ticket_status_bp.route("/ticket-status")
def ticket_status_page():
    auth_check = require_super_admin()
    if auth_check:
        return auth_check

    search = request.args.get("search", "")
    page = int(request.args.get("page", 1))
    per_page = 10

    query = """
        SELECT status_name
        FROM ticket_status
        WHERE 1=1
    """
    params = {}

    if search:
        query += " AND status_name ILIKE :search"
        params["search"] = f"%{search}%"

    # Count total
    count_query = query.replace("SELECT status_name", "SELECT COUNT(*)")
    total = db.session.execute(text(count_query), params).scalar()

    # Pagination
    query += " ORDER BY status_name LIMIT :limit OFFSET :offset"
    params["limit"] = per_page
    params["offset"] = (page - 1) * per_page

    statuses = db.session.execute(text(query), params).fetchall()

    total_pages = (total + per_page - 1) // per_page
    has_prev = page > 1
    has_next = page < total_pages

    # Stats
    total_statuses = db.session.execute(text("SELECT COUNT(*) FROM ticket_status")).scalar()

    return render_template(
        "ticket_status.html",
        statuses=statuses,
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
        total_statuses=total_statuses,
        can_edit=is_super_admin()
    )


@ticket_status_bp.route("/api/ticket-status/search")
def api_ticket_status_search():
    auth_check = require_super_admin()
    if auth_check:
        return jsonify({"error": "Unauthorized"}), 401

    q = request.args.get("q", "").strip()
    page = int(request.args.get("page", 1))
    per_page = 10

    query = """
        SELECT status_name
        FROM ticket_status
        WHERE 1=1
    """
    params = {}

    if q:
        query += " AND status_name ILIKE :search"
        params["search"] = f"%{q}%"

    # Count total
    count_query = query.replace("SELECT status_name", "SELECT COUNT(*)")
    total = db.session.execute(text(count_query), params).scalar()

    # Pagination
    query += " ORDER BY status_name LIMIT :limit OFFSET :offset"
    params["limit"] = per_page
    params["offset"] = (page - 1) * per_page

    statuses = db.session.execute(text(query), params).fetchall()

    rows = []
    for s in statuses:
        rows.append({
            "status_name": s.status_name,
        })

    return jsonify({
        "rows": rows,
        "count": len(rows),
        "total": total,
        "page": page,
        "per_page": per_page,
        "total_pages": (total + per_page - 1) // per_page,
    })


@ticket_status_bp.route("/ticket-status/add", methods=["POST"])
def add_ticket_status():
    auth_check = require_super_admin()
    if auth_check:
        return auth_check

    if not is_super_admin():
        flash(_("access_denied"), "danger")
        return redirect(url_for("ticket_status.ticket_status_page"))

    status_name = request.form.get("status_name", "").strip()

    if not status_name:
        flash(_("status_name_required"), "danger")
        return redirect(url_for("ticket_status.ticket_status_page"))

    existing = db.session.execute(
        text("SELECT 1 FROM ticket_status WHERE LOWER(status_name) = LOWER(:status_name)"),
        {"status_name": status_name}
    ).fetchone()

    if existing:
        flash(_("status_already_exists"), "warning")
        return redirect(url_for("ticket_status.ticket_status_page"))

    try:
        db.session.execute(
            text("INSERT INTO ticket_status (status_name) VALUES (:status_name)"),
            {"status_name": status_name}
        )
        db.session.commit()
        flash(_("status_added_successfully"), "success")
    except IntegrityError:
        db.session.rollback()
        flash(_("error_adding_status"), "danger")

    return redirect(url_for("ticket_status.ticket_status_page"))


@ticket_status_bp.route("/ticket-status/update/<status_name>", methods=["POST"])
def update_ticket_status(status_name):
    auth_check = require_super_admin()
    if auth_check:
        return auth_check

    if not is_super_admin():
        flash(_("access_denied"), "danger")
        return redirect(url_for("ticket_status.ticket_status_page"))

    new_status = request.form.get("status_name", "").strip()

    if not new_status:
        flash(_("status_name_required"), "danger")
        return redirect(url_for("ticket_status.ticket_status_page"))

    existing = db.session.execute(
        text("SELECT 1 FROM ticket_status WHERE LOWER(status_name) = LOWER(:status_name) AND status_name != :old_status"),
        {"status_name": new_status, "old_status": status_name}
    ).fetchone()

    if existing:
        flash(_("another_status_with_this_name_already_exists"), "warning")
        return redirect(url_for("ticket_status.ticket_status_page"))

    try:
        db.session.execute(
            text("UPDATE ticket_status SET status_name = :new_status WHERE status_name = :old_status"),
            {"new_status": new_status, "old_status": status_name}
        )
        db.session.commit()
        flash(_("status_updated_successfully"), "success")
    except IntegrityError:
        db.session.rollback()
        flash(_("error_updating_status"), "danger")

    return redirect(url_for("ticket_status.ticket_status_page"))


@ticket_status_bp.route("/ticket-status/delete/<status_name>", methods=["POST"])
def delete_ticket_status(status_name):
    auth_check = require_super_admin()
    if auth_check:
        return auth_check

    if not is_super_admin():
        flash(_("access_denied"), "danger")
        return redirect(url_for("ticket_status.ticket_status_page"))

    # Check if status is used in tickets
    used = db.session.execute(
        text("SELECT 1 FROM tickets WHERE status_name = :status_name LIMIT 1"),
        {"status_name": status_name}
    ).fetchone()

    if used:
        flash(_("status_is_in_use_and_cannot_be_deleted"), "warning")
        return redirect(url_for("ticket_status.ticket_status_page"))

    try:
        db.session.execute(
            text("DELETE FROM ticket_status WHERE status_name = :status_name"),
            {"status_name": status_name}
        )
        db.session.commit()
        flash(_("status_deleted_successfully"), "success")
    except IntegrityError:
        db.session.rollback()
        flash(_("error_deleting_status"), "danger")

    return redirect(url_for("ticket_status.ticket_status_page"))