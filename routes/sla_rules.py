from flask import Blueprint, render_template, request, redirect, flash, url_for, jsonify, session
from flask_babel import gettext as _
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from help_db import db

sla_rules_bp = Blueprint('sla_rules', __name__)


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


@sla_rules_bp.route("/sla-rules")
def sla_rules():
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
            s.sla_id,
            p.priority_name,
            s.response_time,
            s.resolution_time,
            c.category_name,
            s.status
        FROM sla_rules s
        JOIN priorities p ON s.priority_id = p.priority_id
        LEFT JOIN categories c ON s.category_name = c.category_name
        WHERE 1=1
    """
    params = {}

    if search:
        query += " AND (p.priority_name ILIKE :search OR c.category_name ILIKE :search)"
        params["search"] = f"%{search}%"

    if priority_filter:
        query += " AND p.priority_name = :priority_name"
        params["priority_name"] = priority_filter

    if status_filter:
        query += " AND s.status = :status"
        params["status"] = status_filter

    # Count total
    count_query = query.replace(
        "SELECT\n            s.sla_id,\n            p.priority_name,\n            s.response_time,\n            s.resolution_time,\n            c.category_name,\n            s.status",
        "SELECT COUNT(*)"
    )
    total = db.session.execute(text(count_query), params).scalar()

    # Pagination
    query += " ORDER BY s.sla_id DESC LIMIT :limit OFFSET :offset"
    params["limit"] = per_page
    params["offset"] = (page - 1) * per_page

    sla_rules = db.session.execute(text(query), params).fetchall()

    total_pages = (total + per_page - 1) // per_page
    has_prev = page > 1
    has_next = page < total_pages

    # Stats
    total_sla_rules = db.session.execute(text("SELECT COUNT(*) FROM sla_rules")).scalar()
    active_sla_rules = db.session.execute(text("SELECT COUNT(*) FROM sla_rules WHERE status='Active'")).scalar()
    inactive_sla_rules = db.session.execute(text("SELECT COUNT(*) FROM sla_rules WHERE status='Inactive'")).scalar()

    priorities = db.session.execute(
        text("SELECT priority_name FROM priorities ORDER BY priority_name")
    ).fetchall()

    categories = db.session.execute(
        text("SELECT category_name FROM categories ORDER BY category_name")
    ).fetchall()

    return render_template(
        "sla_rules.html",
        sla_rules=sla_rules,
        priorities=priorities,
        categories=categories,
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
        total_sla_rules=total_sla_rules,
        active_sla_rules=active_sla_rules,
        inactive_sla_rules=inactive_sla_rules,
        can_edit=is_super_admin()
    )


@sla_rules_bp.route("/api/sla-rules/search")
def api_sla_rules_search():
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
            s.sla_id,
            p.priority_name,
            s.response_time,
            s.resolution_time,
            c.category_name,
            s.status
        FROM sla_rules s
        JOIN priorities p ON s.priority_id = p.priority_id
        LEFT JOIN categories c ON s.category_name = c.category_name
        WHERE 1=1
    """
    params = {}

    if q:
        query += " AND (p.priority_name ILIKE :search OR c.category_name ILIKE :search)"
        params["search"] = f"%{q}%"

    if priority_filter:
        query += " AND p.priority_name = :priority_name"
        params["priority_name"] = priority_filter

    if status_filter:
        query += " AND s.status = :status"
        params["status"] = status_filter

    # Count total
    count_query = query.replace(
        "SELECT\n            s.sla_id,\n            p.priority_name,\n            s.response_time,\n            s.resolution_time,\n            c.category_name,\n            s.status",
        "SELECT COUNT(*)"
    )
    total = db.session.execute(text(count_query), params).scalar()

    # Pagination
    query += " ORDER BY s.sla_id DESC LIMIT :limit OFFSET :offset"
    params["limit"] = per_page
    params["offset"] = (page - 1) * per_page

    sla_rules = db.session.execute(text(query), params).fetchall()

    rows = []
    for r in sla_rules:
        rows.append({
            "sla_id": r.sla_id,
            "priority_name": r.priority_name,
            "response_time": r.response_time,
            "resolution_time": r.resolution_time,
            "category_name": r.category_name or "-",
            "status": r.status or "Active",
        })

    return jsonify({
        "rows": rows,
        "count": len(rows),
        "total": total,
        "page": page,
        "per_page": per_page,
        "total_pages": (total + per_page - 1) // per_page,
    })


@sla_rules_bp.route("/api/sla-rules/toggle-status", methods=["POST"])
def api_toggle_sla_status():
    auth_check = require_super_admin()
    if auth_check:
        return jsonify({"error": "Unauthorized"}), 401

    if not is_super_admin():
        return jsonify({"error": "Access denied"}), 403

    try:
        data = request.get_json() or {}
        sla_id = data.get("sla_id")
        new_status = data.get("status")

        if not sla_id or new_status not in ("Active", "Inactive"):
            return jsonify({"error": "Invalid parameters"}), 400

        db.session.execute(
            text("UPDATE sla_rules SET status = :status WHERE sla_id = :sla_id"),
            {"status": new_status, "sla_id": sla_id}
        )
        db.session.commit()

        return jsonify({"status": new_status, "sla_id": sla_id})
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": str(e)}), 500


@sla_rules_bp.route("/sla-rules/add", methods=["POST"])
def add_sla_rule():
    auth_check = require_super_admin()
    if auth_check:
        return auth_check

    if not is_super_admin():
        flash(_("access_denied"), "danger")
        return redirect(url_for("sla_rules.sla_rules"))

    priority_name = request.form.get("priority_name", "").strip()
    response_time = request.form.get("response_time", "").strip()
    resolution_time = request.form.get("resolution_time", "").strip()
    category_name = request.form.get("category_name", "").strip()
    status = request.form.get("status", "Active").strip()

    if not priority_name or not response_time or not resolution_time:
        flash(_("all_fields_required"), "danger")
        return redirect(url_for("sla_rules.sla_rules"))

    priority = db.session.execute(
        text("SELECT priority_id FROM priorities WHERE priority_name = :priority_name"),
        {"priority_name": priority_name}
    ).fetchone()

    if not priority:
        flash(_("priority_not_found"), "danger")
        return redirect(url_for("sla_rules.sla_rules"))

    try:
        db.session.execute(
            text("""
                INSERT INTO sla_rules (priority_id, response_time, resolution_time, category_name, status)
                VALUES (:priority_id, :response_time, :resolution_time, :category_name, :status)
            """),
            {
                "priority_id": priority.priority_id,
                "response_time": int(response_time),
                "resolution_time": int(resolution_time),
                "category_name": category_name if category_name else None,
                "status": status
            }
        )
        db.session.commit()
        flash(_("sla_rule_added_successfully"), "success")
    except IntegrityError:
        db.session.rollback()
        flash(_("error_adding_sla_rule"), "danger")

    return redirect(url_for("sla_rules.sla_rules"))


@sla_rules_bp.route("/sla-rules/update/<int:sla_id>", methods=["POST"])
def update_sla_rule(sla_id):
    auth_check = require_super_admin()
    if auth_check:
        return auth_check

    if not is_super_admin():
        flash(_("access_denied"), "danger")
        return redirect(url_for("sla_rules.sla_rules"))

    priority_name = request.form.get("priority_name", "").strip()
    response_time = request.form.get("response_time", "").strip()
    resolution_time = request.form.get("resolution_time", "").strip()
    category_name = request.form.get("category_name", "").strip()
    status = request.form.get("status", "Active").strip()

    if not priority_name or not response_time or not resolution_time:
        flash(_("all_fields_required"), "danger")
        return redirect(url_for("sla_rules.sla_rules"))

    priority = db.session.execute(
        text("SELECT priority_id FROM priorities WHERE priority_name = :priority_name"),
        {"priority_name": priority_name}
    ).fetchone()

    if not priority:
        flash(_("priority_not_found"), "danger")
        return redirect(url_for("sla_rules.sla_rules"))

    try:
        db.session.execute(
            text("""
                UPDATE sla_rules
                SET priority_id = :priority_id,
                    response_time = :response_time,
                    resolution_time = :resolution_time,
                    category_name = :category_name,
                    status = :status
                WHERE sla_id = :sla_id
            """),
            {
                "priority_id": priority.priority_id,
                "response_time": int(response_time),
                "resolution_time": int(resolution_time),
                "category_name": category_name if category_name else None,
                "status": status,
                "sla_id": sla_id
            }
        )
        db.session.commit()
        flash(_("sla_rule_updated_successfully"), "success")
    except IntegrityError:
        db.session.rollback()
        flash(_("error_updating_sla_rule"), "danger")

    return redirect(url_for("sla_rules.sla_rules"))


@sla_rules_bp.route("/sla-rules/delete/<int:sla_id>", methods=["POST"])
def delete_sla_rule(sla_id):
    auth_check = require_super_admin()
    if auth_check:
        return auth_check

    if not is_super_admin():
        flash(_("access_denied"), "danger")
        return redirect(url_for("sla_rules.sla_rules"))

    try:
        db.session.execute(
            text("DELETE FROM sla_rules WHERE sla_id = :sla_id"),
            {"sla_id": sla_id}
        )
        db.session.commit()
        flash(_("sla_rule_deleted_successfully"), "success")
    except IntegrityError:
        db.session.rollback()
        flash(_("error_deleting_sla_rule"), "danger")

    return redirect(url_for("sla_rules.sla_rules"))