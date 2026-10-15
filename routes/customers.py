from flask import Blueprint, render_template, request, redirect, url_for, flash, session, jsonify
from flask_babel import gettext as _
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from werkzeug.security import generate_password_hash
from help_db import db

customers_bp = Blueprint('customers', __name__)

_cached_departments = None


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


@customers_bp.route('/customers')
def customers_page():
    auth_check = require_super_admin()
    if auth_check:
        return auth_check

    search = request.args.get("search", "")
    status = request.args.get("status", "")
    page = int(request.args.get("page", 1))
    per_page = 10

    query = """
        SELECT
            u.user_id,
            u.first_name,
            u.last_name,
            u.email,
            u.mobile,
            u.department_id,
            d.department_name,
            u.status,
            u.created_at
        FROM users u
        LEFT JOIN departments d ON u.department_id = d.department_id
        WHERE u.role_id = 6
    """
    params = {}

    if search:
        query += """
            AND (
                u.first_name ILIKE :search OR
                u.last_name ILIKE :search OR
                u.email ILIKE :search OR
                u.mobile ILIKE :search
            )
        """
        params["search"] = f"%{search}%"

    if status:
        query += " AND u.status = :status"
        params["status"] = status

    # Count total
    count_query = query.replace("SELECT u.user_id, u.first_name, u.last_name, u.email, u.mobile, u.department_id, d.department_name, u.status, u.created_at", "SELECT COUNT(*)")
    total = db.session.execute(text(count_query), params).scalar()

    # Pagination
    query += " ORDER BY u.user_id DESC LIMIT :limit OFFSET :offset"
    params["limit"] = per_page
    params["offset"] = (page - 1) * per_page

    customers = db.session.execute(text(query), params).fetchall()

    total_pages = (total + per_page - 1) // per_page
    has_prev = page > 1
    has_next = page < total_pages

    # Stats
    total_customers = db.session.execute(text("SELECT COUNT(*) FROM users WHERE role_id = 6")).scalar()
    active_customers = db.session.execute(text("SELECT COUNT(*) FROM users WHERE role_id = 6 AND status='Active'")).scalar()
    inactive_customers = db.session.execute(text("SELECT COUNT(*) FROM users WHERE role_id = 6 AND status='Inactive'")).scalar()

    global _cached_departments
    if _cached_departments is None:
        _cached_departments = db.session.execute(text("""
            SELECT department_id, department_name
            FROM departments
            ORDER BY department_name
        """)).fetchall()

    return render_template(
        "customers.html",
        customers=customers,
        departments=_cached_departments,
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
        total_customers=total_customers,
        active_customers=active_customers,
        inactive_customers=inactive_customers,
        can_edit=is_super_admin()
    )


@customers_bp.route('/api/customers/search')
def api_customers_search():
    auth_check = require_super_admin()
    if auth_check:
        return jsonify({"error": "Unauthorized"}), 401

    search = request.args.get("q", "").strip()
    status = request.args.get("status", "").strip()
    page = int(request.args.get("page", 1))
    per_page = 10

    query = """
        SELECT
            u.user_id,
            u.first_name,
            u.last_name,
            u.email,
            u.mobile,
            u.department_id,
            d.department_name,
            u.status,
            u.created_at
        FROM users u
        LEFT JOIN departments d ON u.department_id = d.department_id
        WHERE u.role_id = 6
    """
    params = {}

    if search:
        query += """
            AND (
                u.first_name ILIKE :search OR
                u.last_name ILIKE :search OR
                u.email ILIKE :search OR
                u.mobile ILIKE :search
            )
        """
        params["search"] = f"%{search}%"

    if status:
        query += " AND u.status = :status"
        params["status"] = status

    # Count total
    count_query = query.replace("SELECT u.user_id, u.first_name, u.last_name, u.email, u.mobile, u.department_id, d.department_name, u.status, u.created_at", "SELECT COUNT(*)")
    total = db.session.execute(text(count_query), params).scalar()

    # Pagination
    query += " ORDER BY u.user_id DESC LIMIT :limit OFFSET :offset"
    params["limit"] = per_page
    params["offset"] = (page - 1) * per_page

    customers = db.session.execute(text(query), params).fetchall()

    rows = []
    for c in customers:
        rows.append({
            "user_id": c.user_id,
            "first_name": c.first_name,
            "last_name": c.last_name,
            "email": c.email,
            "mobile": c.mobile,
            "department_id": c.department_id,
            "department_name": c.department_name,
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


@customers_bp.route('/customers/add', methods=['POST'])
def add_customer():
    auth_check = require_super_admin()
    if auth_check:
        return auth_check

    if not is_super_admin():
        flash(_("access_denied"), "danger")
        return redirect(url_for("customers.customers_page"))

    first_name = request.form.get("first_name")
    last_name = request.form.get("last_name")
    email = request.form.get("email")
    password = request.form.get("password")
    mobile = request.form.get("mobile")
    department_id = request.form.get("department_id")
    status = request.form.get("status", "Active")

    if not first_name or not last_name or not email or not password:
        flash(_("first_name_last_name_email_and_password_are_required"), "danger")
        return redirect(url_for("customers.customers_page"))

    existing = db.session.execute(
        text("SELECT user_id FROM users WHERE email = :email"),
        {"email": email}
    ).fetchone()

    if existing:
        flash(_("this_email_address_is_already_registered"), "danger")
        return redirect(url_for("customers.customers_page"))

    password_hash = generate_password_hash(password)

    db.session.execute(
        text("""
            INSERT INTO users
            (first_name, last_name, email, password_hash, mobile, department_id, role_id, status)
            VALUES (:first_name, :last_name, :email, :password_hash, :mobile, :department_id, 6, :status)
        """),
        {
            "first_name": first_name,
            "last_name": last_name,
            "email": email,
            "password_hash": password_hash,
            "mobile": mobile,
            "department_id": department_id or None,
            "status": status
        }
    )
    db.session.commit()

    flash(_("customer_added_successfully"), "success")
    return redirect(url_for("customers.customers_page"))


@customers_bp.route('/customers/edit/<int:customer_id>')
def edit_customer(customer_id):
    auth_check = require_super_admin()
    if auth_check:
        return auth_check

    customer = db.session.execute(
        text("""
            SELECT u.user_id, u.first_name, u.last_name, u.email, u.mobile,
                   u.department_id, u.status
            FROM users u
            WHERE u.user_id = :customer_id AND u.role_id = 6
        """),
        {"customer_id": customer_id}
    ).fetchone()

    if not customer:
        return jsonify({"error": "Customer not found"}), 404

    return jsonify({
        "user_id": customer[0],
        "first_name": customer[1],
        "last_name": customer[2],
        "email": customer[3],
        "mobile": customer[4],
        "department_id": customer[5],
        "status": customer[6]
    })


@customers_bp.route('/customers/update/<int:customer_id>', methods=['POST'])
def update_customer(customer_id):
    auth_check = require_super_admin()
    if auth_check:
        return auth_check

    if not is_super_admin():
        flash(_("access_denied"), "danger")
        return redirect(url_for("customers.customers_page"))

    first_name = request.form.get("first_name")
    last_name = request.form.get("last_name")
    email = request.form.get("email")
    mobile = request.form.get("mobile")
    department_id = request.form.get("department_id")
    status = request.form.get("status")

    if not department_id:
        department_id = None

    db.session.execute(
        text("""
            UPDATE users
            SET first_name = :first_name,
                last_name = :last_name,
                email = :email,
                mobile = :mobile,
                department_id = :department_id,
                status = :status
            WHERE user_id = :customer_id AND role_id = 6
        """),
        {
            "first_name": first_name,
            "last_name": last_name,
            "email": email,
            "mobile": mobile,
            "department_id": department_id,
            "status": status,
            "customer_id": customer_id
        }
    )
    db.session.commit()

    flash(_("customer_updated_successfully"), "success")
    return redirect(url_for("customers.customers_page"))


@customers_bp.route('/customers/delete/<int:customer_id>', methods=['POST'])
def delete_customer(customer_id):
    auth_check = require_super_admin()
    if auth_check:
        return auth_check

    if not is_super_admin():
        flash(_("access_denied"), "danger")
        return redirect(url_for("customers.customers_page"))

    try:
        db.session.execute(
            text("""
                DELETE FROM ticket_comments
                WHERE user_id = :customer_id
            """),
            {"customer_id": customer_id}
        )

        db.session.execute(
            text("""
                DELETE FROM ticket_status_history
                WHERE changed_by = :customer_id
            """),
            {"customer_id": customer_id}
        )

        db.session.execute(
            text("""
                DELETE FROM notifications
                WHERE user_id = :customer_id
            """),
            {"customer_id": customer_id}
        )

        db.session.execute(
            text("""
                DELETE FROM ticket_attachments
                WHERE uploaded_by = :customer_id
            """),
            {"customer_id": customer_id}
        )

        db.session.execute(
            text("""
                DELETE FROM password_reset_tokens
                WHERE user_id = :customer_id
            """),
            {"customer_id": customer_id}
        )

        db.session.execute(
            text("""
                DELETE FROM audit_logs
                WHERE user_id = :customer_id
            """),
            {"customer_id": customer_id}
        )

        db.session.execute(
            text("""
                UPDATE tickets
                SET requester_id = NULL
                WHERE requester_id = :customer_id
            """),
            {"customer_id": customer_id}
        )

        db.session.execute(
            text("""
                DELETE FROM users
                WHERE user_id = :customer_id AND role_id = 6
            """),
            {"customer_id": customer_id}
        )

        db.session.commit()
        flash(_("customer_deleted_successfully"), "success")

    except IntegrityError:
        db.session.rollback()
        flash(_("customer_cannot_be_deleted_because_they_are_linked_with_other_records_please_remove_all_associated_tickets_first"), "danger")

    return redirect(url_for("customers.customers_page"))


@customers_bp.route("/api/toggle-status/<int:customer_id>", methods=["POST"])
def api_toggle_status(customer_id):
    auth_check = require_super_admin()
    if auth_check:
        return jsonify({"error": "Unauthorized"}), 401

    if not is_super_admin():
        return jsonify({"error": "Access denied"}), 403

    customer = db.session.execute(
        text("""
            SELECT status
            FROM users
            WHERE user_id = :customer_id AND role_id = 6
        """),
        {"customer_id": customer_id}
    ).fetchone()

    if not customer:
        return jsonify({"error": "Customer not found"}), 404

    new_status = "Inactive" if customer.status == "Active" else "Active"

    db.session.execute(
        text("""
            UPDATE users
            SET status = :status
            WHERE user_id = :customer_id AND role_id = 6
        """),
        {
            "status": new_status,
            "customer_id": customer_id
        }
    )

    db.session.commit()

    return jsonify({"status": new_status, "customer_id": customer_id})