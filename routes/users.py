from help_db import db
from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify, session
from flask_babel import gettext as _
from werkzeug.security import generate_password_hash
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
import logging

logger = logging.getLogger(__name__)
from sqlalchemy.exc import IntegrityError
from utils.translations import SKILL_TRANSLATIONS

users_bp = Blueprint('users', __name__)

SUPPORT_AGENT_ROLE_ID = 3


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


@users_bp.route("/api/skills")
def api_skills():
    categories = db.session.execute(
        text("""
            SELECT c.category_name, d.department_name
            FROM categories c
            LEFT JOIN departments d ON c.department_id = d.department_id
            ORDER BY c.category_name
        """)
    ).fetchall()

    skills = db.session.execute(
        text("""
            SELECT s.skill_id, s.skill_name, s.category
            FROM skills s
            WHERE s.category IS NOT NULL AND TRIM(s.category) != ''
            ORDER BY s.category, s.skill_name
        """)
    ).fetchall()

    skills_by_category = {}
    for s in skills:
        cat = s[2]
        if cat not in skills_by_category:
            skills_by_category[cat] = []
        skills_by_category[cat].append({"skill_id": s[0], "skill_name": s[1]})

    result = []
    for cat_name, dept_name in categories:
        if cat_name in skills_by_category:
            result.append({
                "category_name": cat_name,
                "department_name": dept_name or "",
                "skills": skills_by_category[cat_name]
            })

    return jsonify(result)


@users_bp.route("/api/users/search")
def api_users_search():
    auth_check = require_super_admin()
    if auth_check:
        return jsonify({"error": "Unauthorized"}), 401

    search = request.args.get("q", "").strip()
    status = request.args.get("status", "").strip()
    page = int(request.args.get("page", 1))
    per_page = 10

    query = """
        SELECT u.user_id, u.first_name, u.last_name, u.email, u.mobile, u.status,
               r.role_name, d.department_name,
               u.role_id, u.department_id
        FROM users u
        LEFT JOIN roles r ON u.role_id = r.role_id
        LEFT JOIN departments d ON u.department_id = d.department_id
        WHERE u.role_id != 6
    """
    params = {}

    if search:
        query += """
            AND (
                u.first_name ILIKE :search OR
                u.last_name ILIKE :search OR
                u.email ILIKE :search OR
                u.mobile ILIKE :search OR
                d.department_name ILIKE :search OR
                r.role_name ILIKE :search
            )
        """
        params["search"] = f"%{search}%"

    if status:
        query += " AND u.status = :status"
        params["status"] = status

    # Count total
    count_query = query.replace("SELECT u.user_id, u.first_name, u.last_name, u.email, u.mobile, u.status, r.role_name, d.department_name, u.role_id, u.department_id", "SELECT COUNT(*)")
    total = db.session.execute(text(count_query), params).scalar()

    # Pagination
    query += " ORDER BY u.user_id LIMIT :limit OFFSET :offset"
    params["limit"] = per_page
    params["offset"] = (page - 1) * per_page

    users = db.session.execute(text(query), params).fetchall()

    rows = []
    for u in users:
        skills = db.session.execute(
            text("""
                SELECT s.skill_id
                FROM agent_skills ag
                JOIN skills s ON ag.skill_id = s.skill_id
                WHERE ag.user_id = :user_id
            """),
            {"user_id": u.user_id}
        ).fetchall()
        
        rows.append({
            "user_id": u.user_id,
            "first_name": u.first_name,
            "last_name": u.last_name,
            "email": u.email,
            "mobile": u.mobile,
            "status": u.status,
            "role_name": u.role_name,
            "department_name": u.department_name,
            "role_id": u.role_id,
            "department_id": u.department_id,
            "skills": ",".join([str(s[0]) for s in skills]) if skills else "",
        })

    return jsonify({
        "rows": rows,
        "count": len(rows),
        "total": total,
        "page": page,
        "per_page": per_page,
        "total_pages": (total + per_page - 1) // per_page,
    })


@users_bp.route("/update_user/<int:user_id>", methods=["POST"])
def update_user(user_id):
    auth_check = require_super_admin()
    if auth_check:
        return auth_check

    if not is_super_admin():
        flash(_("access_denied"), "danger")
        return redirect(url_for("users.get_users"))

    first_name = request.form.get("first_name")
    last_name = request.form.get("last_name")
    email = request.form.get("email")
    mobile = request.form.get("mobile")
    department_id = request.form.get("department_id")
    role_id = request.form.get("role_id")
    status = request.form.get("status")
    skills_raw = request.form.get("skills", "")

    db.session.execute(
        text("""
            UPDATE users
            SET
                first_name = :first_name,
                last_name = :last_name,
                email = :email,
                mobile = :mobile,
                department_id = :department_id,
                role_id = :role_id,
                status = :status
            WHERE user_id = :user_id
        """),
        {
            "first_name": first_name,
            "last_name": last_name,
            "email": email,
            "mobile": mobile,
            "department_id": department_id,
            "role_id": role_id,
            "status": status,
            "user_id": user_id
        }
    )

    selected_skill_ids = [s.strip() for s in skills_raw.split(",") if s.strip()]

    if str(role_id) == str(SUPPORT_AGENT_ROLE_ID):
        db.session.execute(
            text("DELETE FROM agent_skills WHERE user_id = :user_id"),
            {"user_id": user_id}
        )
        for skill_id in selected_skill_ids:
            try:
                db.session.execute(
                    text("""
                        INSERT INTO agent_skills (user_id, skill_id)
                        VALUES (:user_id, :skill_id)
                    """),
                    {"user_id": user_id, "skill_id": int(skill_id)}
                )
            except IntegrityError:
                db.session.rollback()
    else:
        db.session.execute(
            text("DELETE FROM agent_skills WHERE user_id = :user_id"),
            {"user_id": user_id}
        )

    db.session.commit()

    flash(_("user_updated_successfully"), "success")

    return redirect(url_for("users.get_users"))


@users_bp.route("/delete_user/<int:user_id>", methods=["POST"])
def delete_user(user_id):
    auth_check = require_super_admin()
    if auth_check:
        return auth_check

    if not is_super_admin():
        flash(_("access_denied"), "danger")
        return redirect(url_for("users.get_users"))

    try:
        db.session.execute(
            text("""
                DELETE FROM ticket_comments
                WHERE user_id = :user_id
            """),
            {"user_id": user_id}
        )

        db.session.execute(
            text("""
                DELETE FROM ticket_status_history
                WHERE changed_by = :user_id
            """),
            {"user_id": user_id}
        )

        db.session.execute(
            text("""
                DELETE FROM notifications
                WHERE user_id = :user_id
            """),
            {"user_id": user_id}
        )

        db.session.execute(
            text("""
                DELETE FROM ticket_attachments
                WHERE uploaded_by = :user_id
            """),
            {"user_id": user_id}
        )

        db.session.execute(
            text("""
                DELETE FROM password_reset_tokens
                WHERE user_id = :user_id
            """),
            {"user_id": user_id}
        )

        db.session.execute(
            text("""
                DELETE FROM audit_logs
                WHERE user_id = :user_id
            """),
            {"user_id": user_id}
        )

        db.session.execute(
            text("""
                UPDATE tickets
                SET requester_id = NULL
                WHERE requester_id = :user_id
            """),
            {"user_id": user_id}
        )

        db.session.execute(
            text("""
                DELETE FROM users
                WHERE user_id = :user_id
            """),
            {"user_id": user_id}
        )

        db.session.commit()
        flash(_("user_deleted_successfully"), "success")

    except IntegrityError:
        db.session.rollback()
        flash(_("user_cannot_be_deleted_because_this_user_is_linked_with_other_records_please_remove_all_associated_tickets_comments_and_attachments_first"), "danger")

    return redirect(url_for("users.get_users"))


@users_bp.route("/api/delete_user/<int:user_id>", methods=["POST"])
def api_delete_user(user_id):
    auth_check = require_super_admin()
    if auth_check:
        return jsonify({"error": "Unauthorized"}), 401

    if not is_super_admin():
        return jsonify({"error": "Access denied"}), 403

    try:
        db.session.execute(
            text("""
                DELETE FROM ticket_comments
                WHERE user_id = :user_id
            """),
            {"user_id": user_id}
        )

        db.session.execute(
            text("""
                DELETE FROM ticket_status_history
                WHERE changed_by = :user_id
            """),
            {"user_id": user_id}
        )

        db.session.execute(
            text("""
                DELETE FROM notifications
                WHERE user_id = :user_id
            """),
            {"user_id": user_id}
        )

        db.session.execute(
            text("""
                DELETE FROM ticket_attachments
                WHERE uploaded_by = :user_id
            """),
            {"user_id": user_id}
        )

        db.session.execute(
            text("""
                DELETE FROM password_reset_tokens
                WHERE user_id = :user_id
            """),
            {"user_id": user_id}
        )

        db.session.execute(
            text("""
                DELETE FROM audit_logs
                WHERE user_id = :user_id
            """),
            {"user_id": user_id}
        )

        db.session.execute(
            text("""
                UPDATE tickets
                SET requester_id = NULL
                WHERE requester_id = :user_id
            """),
            {"user_id": user_id}
        )

        db.session.execute(
            text("""
                DELETE FROM users
                WHERE user_id = :user_id
            """),
            {"user_id": user_id}
        )

        db.session.commit()
        return jsonify({"success": True, "message": "User deleted successfully"})

    except IntegrityError:
        db.session.rollback()
        return jsonify({"success": False, "message": "User cannot be deleted because this user is linked with other records. Please remove all associated tickets, comments, and attachments first."}), 400
    except Exception as e:
        db.session.rollback()
        return jsonify({"success": False, "message": "An error occurred while deleting the user."}), 500


@users_bp.route("/toggle-status/<int:user_id>")
def toggle_status(user_id):
    auth_check = require_super_admin()
    if auth_check:
        return auth_check

    user = db.session.execute(
        text("""
            SELECT status
            FROM users
            WHERE user_id = :user_id
        """),
        {"user_id": user_id}
    ).fetchone()

    if user.status == "Active":
        new_status = "Inactive"
    else:
        new_status = "Active"

    db.session.execute(
        text("""
            UPDATE users
            SET status = :status
            WHERE user_id = :user_id
        """),
        {
            "status": new_status,
            "user_id": user_id
        }
    )

    db.session.commit()

    flash(_("status_updated_successfully"), "success")

    return redirect(url_for("users.get_users"))


@users_bp.route("/api/toggle-status/<int:user_id>", methods=["POST"])
def api_toggle_status(user_id):
    auth_check = require_super_admin()
    if auth_check:
        return jsonify({"error": "Unauthorized"}), 401

    if not is_super_admin():
        return jsonify({"error": "Access denied"}), 403

    user = db.session.execute(
        text("""
            SELECT status
            FROM users
            WHERE user_id = :user_id
        """),
        {"user_id": user_id}
    ).fetchone()

    if not user:
        return jsonify({"error": "User not found"}), 404

    new_status = "Inactive" if user.status == "Active" else "Active"

    db.session.execute(
        text("""
            UPDATE users
            SET status = :status
            WHERE user_id = :user_id
        """),
        {
            "status": new_status,
            "user_id": user_id
        }
    )

    db.session.commit()

    return jsonify({"status": new_status, "user_id": user_id})


@users_bp.route("/add_user", methods=["POST"])
def add_user():
    auth_check = require_super_admin()
    if auth_check:
        return auth_check

    if not is_super_admin():
        flash(_("access_denied"), "danger")
        return redirect(url_for("users.get_users"))

    first_name = request.form.get("first_name")
    last_name = request.form.get("last_name")
    email = request.form.get("email")
    mobile = request.form.get("mobile")
    department_id = request.form.get("department_id")
    role_id = request.form.get("role_id")
    password = request.form.get("password")
    status = request.form.get("status", "Active")
    skills_raw = request.form.get("skills", "")

    if not email:
        flash(_("email_is_required"), "danger")
        return redirect(url_for("users.get_users"))

    existing = db.session.execute(
        text("SELECT user_id FROM users WHERE email = :email"),
        {"email": email}
    ).fetchone()

    if existing:
        flash(_("this_email_address_is_already_registered"), "danger")
        return redirect(url_for("users.get_users"))

    password_hash = generate_password_hash(password)

    try:
        result = db.session.execute(
            text("""
                INSERT INTO users
                (first_name, last_name, email, mobile, password_hash, department_id, role_id, status)
                VALUES
                (:first_name, :last_name, :email, :mobile, :password_hash, :department_id, :role_id, :status)
                RETURNING user_id
            """),
            {
                "first_name": first_name,
                "last_name": last_name,
                "email": email,
                "mobile": mobile,
                "password_hash": password_hash,
                "department_id": department_id,
                "role_id": role_id,
                "status": status
            }
        )
        user_id = result.fetchone()[0]

        if str(role_id) == str(SUPPORT_AGENT_ROLE_ID):
            selected_skill_ids = [s.strip() for s in skills_raw.split(",") if s.strip()]
            for skill_id in selected_skill_ids:
                try:
                    db.session.execute(
                        text("""
                            INSERT INTO agent_skills (user_id, skill_id)
                            VALUES (:user_id, :skill_id)
                        """),
                        {"user_id": user_id, "skill_id": int(skill_id)}
                    )
                except IntegrityError:
                    db.session.rollback()

        db.session.commit()
        flash(_("user_added_successfully"), "success")
        return redirect(url_for("users.get_users"))

    except Exception as e:
        db.session.rollback()
        logger.error("Error adding user: %s", str(e))
        flash(_("error_adding_user"), "danger")
        return redirect(url_for("users.get_users"))


@users_bp.route("/")
def get_users():
    auth_check = require_super_admin()
    if auth_check:
        return auth_check

    search = request.args.get("search", "")
    status = request.args.get("status", "")
    page = int(request.args.get("page", 1))
    per_page = 10

    query = """
        SELECT u.user_id, u.first_name, u.last_name, u.email, u.mobile, u.status,
               r.role_name, d.department_name,
               u.role_id, u.department_id
        FROM users u
        LEFT JOIN roles r ON u.role_id = r.role_id
        LEFT JOIN departments d ON u.department_id = d.department_id
        WHERE u.role_id != 6
    """
    params = {}

    if search:
        query += """
            AND (
                u.first_name ILIKE :search OR
                u.last_name ILIKE :search OR
                u.email ILIKE :search OR
                u.mobile ILIKE :search OR
                d.department_name ILIKE :search OR
                r.role_name ILIKE :search
            )
        """
        params["search"] = f"%{search}%"

    if status:
        query += " AND u.status = :status"
        params["status"] = status

    # Count total
    count_query = query.replace("SELECT u.user_id, u.first_name, u.last_name, u.email, u.mobile, u.status, r.role_name, d.department_name, u.role_id, u.department_id", "SELECT COUNT(*)")
    total = db.session.execute(text(count_query), params).scalar()

    # Pagination
    query += " ORDER BY u.user_id LIMIT :limit OFFSET :offset"
    params["limit"] = per_page
    params["offset"] = (page - 1) * per_page

    users = db.session.execute(text(query), params).fetchall()

    total_pages = (total + per_page - 1) // per_page
    has_prev = page > 1
    has_next = page < total_pages

    # Stats
    total_users = db.session.execute(text("SELECT COUNT(*) FROM users WHERE role_id != 6")).scalar()
    active_users = db.session.execute(text("SELECT COUNT(*) FROM users WHERE role_id != 6 AND status='Active'")).scalar()
    inactive_users = db.session.execute(text("SELECT COUNT(*) FROM users WHERE role_id != 6 AND status='Inactive'")).scalar()

    roles = db.session.execute(text("SELECT * FROM roles")).fetchall()
    departments = db.session.execute(text("SELECT * FROM departments")).fetchall()
    all_skills = db.session.execute(text("SELECT skill_id, skill_name, category FROM skills ORDER BY category, skill_name")).fetchall()

    users_with_skills = []
    for user in users:
        skills = db.session.execute(
            text("""
                SELECT s.skill_id, s.skill_name
                FROM skills s
                JOIN agent_skills ag ON s.skill_id = ag.skill_id
                WHERE ag.user_id = :user_id
                ORDER BY s.skill_name
            """),
            {"user_id": user.user_id}
        ).fetchall()
        users_with_skills.append({
            'user': user,
            'skills': skills
        })

    return render_template(
        "users.html",
        users_with_skills=users_with_skills,
        roles=roles,
        departments=departments,
        all_skills=all_skills,
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
        total_users=total_users,
        active_users=active_users,
        inactive_users=inactive_users,
        skill_translations=SKILL_TRANSLATIONS,
        can_edit=is_super_admin()
    )