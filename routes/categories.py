from flask import Blueprint, render_template, request, redirect, flash, url_for, jsonify, session
from flask_babel import gettext as _
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from help_db import db

categories_bp = Blueprint('categories', __name__)


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


@categories_bp.route("/categories")
def categories_page():
    auth_check = require_super_admin()
    if auth_check:
        return auth_check

    search = request.args.get("search", "")
    status_filter = request.args.get("status", "")
    page = int(request.args.get("page", 1))
    per_page = 10

    query = """
        SELECT category_name, department_id, description, status, created_at
        FROM categories
        WHERE 1=1
    """
    params = {}

    if search:
        query += " AND (category_name ILIKE :search OR description ILIKE :search)"
        params["search"] = f"%{search}%"

    if status_filter:
        query += " AND status = :status"
        params["status"] = status_filter

    # Count total
    count_query = query.replace("SELECT category_name, department_id, description, status, created_at", "SELECT COUNT(*)")
    total = db.session.execute(text(count_query), params).scalar()

    # Pagination
    query += " ORDER BY category_name LIMIT :limit OFFSET :offset"
    params["limit"] = per_page
    params["offset"] = (page - 1) * per_page

    categories = db.session.execute(text(query), params).fetchall()

    total_pages = (total + per_page - 1) // per_page
    has_prev = page > 1
    has_next = page < total_pages

    # Stats
    total_categories = db.session.execute(text("SELECT COUNT(*) FROM categories")).scalar()
    active_categories = db.session.execute(text("SELECT COUNT(*) FROM categories WHERE status='Active'")).scalar()
    inactive_categories = db.session.execute(text("SELECT COUNT(*) FROM categories WHERE status='Inactive'")).scalar()

    departments = db.session.execute(
        text("SELECT department_id, department_name FROM departments ORDER BY department_name")
    ).fetchall()

    return render_template(
        "categories.html",
        categories=categories,
        departments=departments,
        search=search,
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
        total_categories=total_categories,
        active_categories=active_categories,
        inactive_categories=inactive_categories,
        can_edit=is_super_admin()
    )


@categories_bp.route("/api/categories/search")
def api_categories_search():
    auth_check = require_super_admin()
    if auth_check:
        return jsonify({"error": "Unauthorized"}), 401

    q = request.args.get("q", "").strip()
    status = request.args.get("status", "")
    page = int(request.args.get("page", 1))
    per_page = 10

    query = """
        SELECT category_name, department_id, description, status, created_at
        FROM categories
        WHERE 1=1
    """
    params = {}

    if q:
        query += " AND (category_name ILIKE :search OR description ILIKE :search)"
        params["search"] = f"%{q}%"

    if status:
        query += " AND status = :status"
        params["status"] = status

    # Count total
    count_query = query.replace("SELECT category_name, department_id, description, status, created_at", "SELECT COUNT(*)")
    total = db.session.execute(text(count_query), params).scalar()

    # Pagination
    query += " ORDER BY category_name LIMIT :limit OFFSET :offset"
    params["limit"] = per_page
    params["offset"] = (page - 1) * per_page

    categories = db.session.execute(text(query), params).fetchall()

    rows = []
    for c in categories:
        rows.append({
            "category_name": c.category_name,
            "department_id": c.department_id,
            "description": c.description or "-",
            "status": c.status or "Active",
            "created_at": str(c.created_at) if c.created_at else "-",
        })

    return jsonify({
        "rows": rows,
        "count": len(rows),
        "total": total,
        "page": page,
        "per_page": per_page,
        "total_pages": (total + per_page - 1) // per_page,
    })


@categories_bp.route("/api/toggle-status", methods=["POST"])
def api_toggle_status():
    auth_check = require_super_admin()
    if auth_check:
        return jsonify({"error": "Unauthorized"}), 401

    try:
        data = request.get_json() or {}
        category_name = data.get("category_name")
        new_status = data.get("status")

        if not category_name or new_status not in ("Active", "Inactive"):
            return jsonify({"error": "Invalid parameters"}), 400

        db.session.execute(
            text("UPDATE categories SET status = :status WHERE category_name = :category_name"),
            {"status": new_status, "category_name": category_name}
        )
        db.session.commit()

        return jsonify({"status": new_status, "category_name": category_name})
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": str(e)}), 500


@categories_bp.route("/add-category", methods=["POST"])
def add_category():
    auth_check = require_super_admin()
    if auth_check:
        return auth_check

    category_name = request.form.get("category_name", "").strip()
    department_id = request.form.get("department_id", "").strip()
    description = request.form.get("description", "").strip()
    status = request.form.get("status", "Active").strip()

    if not category_name:
        flash(_("category_name_required"), "danger")
        return redirect(url_for("categories.categories_page"))

    existing = db.session.execute(
        text("SELECT 1 FROM categories WHERE LOWER(category_name) = LOWER(:category_name)"),
        {"category_name": category_name}
    ).fetchone()

    if existing:
        flash(_("category_already_exists"), "warning")
        return redirect(url_for("categories.categories_page"))

    try:
        db.session.execute(
            text("""
                INSERT INTO categories (category_name, department_id, description, status)
                VALUES (:category_name, :department_id, :description, :status)
            """),
            {
                "category_name": category_name,
                "department_id": department_id if department_id else None,
                "description": description,
                "status": status
            }
        )
        db.session.commit()
        flash(_("category_added_successfully"), "success")
    except IntegrityError:
        db.session.rollback()
        flash(_("error_adding_category"), "danger")

    return redirect(url_for("categories.categories_page"))


@categories_bp.route("/update-category", methods=["POST"])
def update_category():
    auth_check = require_super_admin()
    if auth_check:
        return auth_check

    old_category = request.form.get("old_category")
    new_category = request.form.get("category_name", "").strip()
    department_id = request.form.get("department_id", "").strip()
    description = request.form.get("description", "").strip()
    status = request.form.get("status", "Active").strip()

    if not old_category or not new_category:
        flash(_("category_name_required"), "danger")
        return redirect(url_for("categories.categories_page"))

    existing = db.session.execute(
        text("""
            SELECT 1 FROM categories
            WHERE LOWER(category_name) = LOWER(:category_name)
            AND category_name != :old_category
        """),
        {"category_name": new_category, "old_category": old_category}
    ).fetchone()

    if existing:
        flash(_("another_category_with_this_name_already_exists"), "warning")
        return redirect(url_for("categories.categories_page"))

    try:
        db.session.execute(
            text("""
                UPDATE categories
                SET category_name = :new_category,
                    department_id = :department_id,
                    description = :description,
                    status = :status
                WHERE category_name = :old_category
            """),
            {
                "new_category": new_category,
                "department_id": department_id if department_id else None,
                "description": description,
                "status": status,
                "old_category": old_category
            }
        )
        db.session.commit()
        flash(_("category_updated_successfully"), "success")
    except IntegrityError:
        db.session.rollback()
        flash(_("error_updating_category"), "danger")

    return redirect(url_for("categories.categories_page"))


@categories_bp.route("/delete-category", methods=["POST"])
def delete_category():
    auth_check = require_super_admin()
    if auth_check:
        return auth_check

    category_name = request.form.get("category_name")

    if not category_name:
        return redirect(url_for("categories.categories_page"))

    try:
        # First cascade: nullify tickets that depend on issue_types which belong to this category
        db.session.execute(
            text("""
                UPDATE tickets SET issue_type_id = NULL
                WHERE issue_type_id IN (
                    SELECT issue_type_id FROM issue_types WHERE category_name = :category_name
                )
            """),
            {"category_name": category_name}
        )

        db.session.execute(
            text("""
                UPDATE skills
                SET category = NULL
                WHERE category = :category_name
            """),
            {"category_name": category_name}
        )

        db.session.execute(
            text("""
                DELETE FROM user_categories
                WHERE category_name = :category_name
            """),
            {"category_name": category_name}
        )

        db.session.execute(
            text("""
                DELETE FROM issue_types
                WHERE category_name = :category_name
            """),
            {"category_name": category_name}
        )

        db.session.execute(
            text("""
                DELETE FROM categories
                WHERE category_name = :category_name
            """),
            {"category_name": category_name}
        )
        db.session.commit()
        flash(_("category_deleted_successfully"), "success")
    except IntegrityError:
        db.session.rollback()
        flash(_("error_deleting_category"), "danger")
    except Exception as e:
        db.session.rollback()
        flash(f"Error: {str(e)}", "danger")

    # Use request context referrer to redirect cleanly to whoever requested it
    return redirect(request.referrer or url_for("categories.categories_page"))


@categories_bp.route("/save-category", methods=["POST"])
def save_category():
    auth_check = require_super_admin()
    if auth_check:
        return auth_check

    category_name = request.form["category_name"]
    department_id = request.form.get("department_id", "")
    description = request.form.get("description", "")
    status = request.form.get("status", "Active")

    db.session.execute(
        text("""
            INSERT INTO categories (category_name, department_id, description, status)
            VALUES (:category_name, :department_id, :description, :status)
        """),
        {
            "category_name": category_name,
            "department_id": department_id if department_id else None,
            "description": description,
            "status": status
        }
    )
    db.session.commit()

    return redirect("/categories")