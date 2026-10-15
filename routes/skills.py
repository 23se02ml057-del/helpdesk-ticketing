from flask import Blueprint, render_template, request, redirect, flash, url_for, session, jsonify
from flask_babel import gettext as _
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from help_db import db

skills_bp = Blueprint('skills', __name__)


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


@skills_bp.route("/skills")
def skills_page():
    auth_check = require_super_admin()
    if auth_check:
        return auth_check

    search = request.args.get("search", "")
    department_filter = request.args.get("department_id", "")
    category_filter = request.args.get("category_name", "")

    query = """
        SELECT s.skill_id, s.skill_name, s.category, s.status, s.created_at,
               d.department_name, c.category_name as category_display
        FROM skills s
        LEFT JOIN categories c ON s.category = c.category_name
        LEFT JOIN departments d ON c.department_id = d.department_id
        WHERE 1=1
    """
    params = {}

    if search:
        query += " AND (s.skill_name ILIKE :search OR s.category ILIKE :search OR d.department_name ILIKE :search)"
        params["search"] = f"%{search}%"

    if department_filter:
        query += " AND d.department_id = :department_id"
        params["department_id"] = department_filter

    if category_filter:
        query += " AND s.category = :category_name"
        params["category_name"] = category_filter

    query += " ORDER BY s.skill_id DESC"

    skills = db.session.execute(text(query), params).fetchall()

    total_skills = db.session.execute(
        text("SELECT COUNT(*) FROM skills")
    ).scalar()

    active_skills = db.session.execute(
        text("SELECT COUNT(*) FROM skills WHERE status='Active'")
    ).scalar()

    departments = db.session.execute(
        text("SELECT department_id, department_name FROM departments ORDER BY department_name")
    ).fetchall()

    categories = db.session.execute(
        text("SELECT category_name, department_id FROM categories ORDER BY category_name")
    ).fetchall()

    return render_template(
        "skills.html",
        skills=skills,
        total_skills=total_skills,
        active_skills=active_skills,
        departments=departments,
        categories=categories,
        search=search,
        department_filter=department_filter,
        category_filter=category_filter,
        can_edit=is_super_admin()
    )


@skills_bp.route("/api/skills/search")
def api_skills_search():
    auth_check = require_super_admin()
    if auth_check:
        return auth_check

    q = request.args.get("q", "").strip()
    department_id = request.args.get("department_id", "")
    category_name = request.args.get("category_name", "")

    query = """
        SELECT s.skill_id, s.skill_name, s.category, s.status,
               d.department_name, c.category_name as category_display
        FROM skills s
        LEFT JOIN categories c ON s.category = c.category_name
        LEFT JOIN departments d ON c.department_id = d.department_id
        WHERE 1=1
    """
    params = {}

    if q:
        query += " AND (s.skill_name ILIKE :search OR s.category ILIKE :search OR d.department_name ILIKE :search)"
        params["search"] = f"%{q}%"

    if department_id:
        query += " AND d.department_id = :department_id"
        params["department_id"] = department_id

    if category_name:
        query += " AND s.category = :category_name"
        params["category_name"] = category_name

    query += " ORDER BY s.skill_id DESC LIMIT 50"

    skills = db.session.execute(text(query), params).fetchall()

    rows = []
    for s in skills:
        rows.append({
            "skill_id": s.skill_id,
            "skill_name": s.skill_name,
            "category": s.category,
            "status": s.status,
            "department_name": s.department_name or '-',
            "category_display": s.category_display or '-',
        })

    return jsonify({"rows": rows, "count": len(rows)})


@skills_bp.route("/api/categories")
def api_categories():
    department_id = request.args.get("department_id", "")
    if department_id:
        categories = db.session.execute(
            text("SELECT category_name, category_name FROM categories WHERE department_id = :dept_id ORDER BY category_name"),
            {"dept_id": department_id}
        ).fetchall()
    else:
        categories = db.session.execute(
            text("SELECT category_name, category_name FROM categories ORDER BY category_name")
        ).fetchall()
    return jsonify([{"category_name": c[0]} for c in categories])


@skills_bp.route("/api/skills")
def api_skills():
    category = request.args.get("category", "")
    if category:
        skills = db.session.execute(
            text("SELECT skill_id, skill_name, category FROM skills WHERE category = :cat ORDER BY skill_name"),
            {"cat": category}
        ).fetchall()
    else:
        skills = db.session.execute(
            text("SELECT skill_id, skill_name, category FROM skills ORDER BY skill_name")
        ).fetchall()
    return jsonify([
        {"skill_id": s[0], "skill_name": s[1], "category": s[2]}
        for s in skills
    ])


@skills_bp.route("/add-skill")
def add_skill():
    auth_check = require_super_admin()
    if auth_check:
        return auth_check

    if not is_super_admin():
        flash(_("access_denied"), "danger")
        return redirect(url_for("skills.skills_page"))

    departments = db.session.execute(
        text("SELECT department_id, department_name FROM departments ORDER BY department_name")
    ).fetchall()

    return render_template("add_skill.html", departments=departments)


@skills_bp.route("/save-skill", methods=["POST"])
def save_skill():
    auth_check = require_super_admin()
    if auth_check:
        return auth_check

    if not is_super_admin():
        flash(_("access_denied"), "danger")
        return redirect(url_for("skills.skills_page"))

    skill_name = request.form.get("skill_name", "").strip()
    category = request.form.get("category_name", "").strip()
    status = request.form.get("status", "Active").strip()

    if not skill_name or not category:
        flash(_("skill_name_and_category_are_required"), "danger")
        return redirect(url_for("skills.add_skill"))

    existing = db.session.execute(
        text("SELECT 1 FROM skills WHERE LOWER(skill_name) = LOWER(:skill_name)"),
        {"skill_name": skill_name}
    ).fetchone()

    if existing:
        flash(_("skill_already_exists"), "warning")
        return redirect(url_for("skills.skills_page"))

    try:
        db.session.execute(
            text("""
                INSERT INTO skills (skill_name, category, status)
                VALUES (:skill_name, :category, :status)
            """),
            {
                "skill_name": skill_name,
                "category": category,
                "status": status
            }
        )
        db.session.commit()
        flash(_("skill_added_successfully"), "success")
    except IntegrityError:
        db.session.rollback()
        flash(_("error_adding_skill"), "danger")

    return redirect(url_for("skills.skills_page"))


@skills_bp.route("/edit-skill/<int:id>")
def edit_skill(id):
    auth_check = require_super_admin()
    if auth_check:
        return auth_check

    if not is_super_admin():
        flash(_("access_denied"), "danger")
        return redirect(url_for("skills.skills_page"))

    skill = db.session.execute(
        text("""
            SELECT s.skill_id, s.skill_name, s.category, s.status, c.department_id
            FROM skills s
            LEFT JOIN categories c ON s.category = c.category_name
            WHERE s.skill_id = :id
        """),
        {"id": id}
    ).fetchone()

    if not skill:
        flash(_("skill_not_found"), "danger")
        return redirect(url_for("skills.skills_page"))

    departments = db.session.execute(
        text("SELECT department_id, department_name FROM departments ORDER BY department_name")
    ).fetchall()

    categories = db.session.execute(
        text("SELECT category_name, department_id FROM categories ORDER BY category_name")
    ).fetchall()

    return render_template(
        "edit_skill.html",
        skill=skill,
        departments=departments,
        categories=categories
    )


@skills_bp.route("/update-skill/<int:id>", methods=["POST"])
def update_skill(id):
    auth_check = require_super_admin()
    if auth_check:
        return auth_check

    if not is_super_admin():
        flash(_("access_denied"), "danger")
        return redirect(url_for("skills.skills_page"))

    skill_name = request.form.get("skill_name", "").strip()
    category = request.form.get("category_name", "").strip()
    status = request.form.get("status", "Active").strip()

    if not skill_name or not category:
        flash(_("skill_name_and_category_are_required"), "danger")
        return redirect(url_for("skills.edit_skill", id=id))

    existing = db.session.execute(
        text("""
            SELECT 1 FROM skills
            WHERE LOWER(skill_name) = LOWER(:skill_name)
            AND skill_id != :id
        """),
        {"skill_name": skill_name, "id": id}
    ).fetchone()

    if existing:
        flash(_("another_skill_with_this_name_already_exists"), "warning")
        return redirect(url_for("skills.edit_skill", id=id))

    try:
        db.session.execute(
            text("""
                UPDATE skills
                SET skill_name = :skill_name,
                    category = :category,
                    status = :status
                WHERE skill_id = :id
            """),
            {
                "skill_name": skill_name,
                "category": category,
                "status": status,
                "id": id
            }
        )
        db.session.commit()
        flash(_("skill_updated_successfully"), "success")
    except IntegrityError:
        db.session.rollback()
        flash(_("error_updating_skill"), "danger")

    return redirect(url_for("skills.skills_page"))


@skills_bp.route("/delete-skill/<int:id>", methods=["POST"])
def delete_skill(id):
    auth_check = require_super_admin()
    if auth_check:
        return auth_check

    if not is_super_admin():
        flash(_("access_denied"), "danger")
        return redirect(url_for("skills.skills_page"))

    try:
        db.session.execute(
            text("DELETE FROM agent_skills WHERE skill_id = :id"),
            {"id": id}
        )
        db.session.execute(
            text("DELETE FROM skills WHERE skill_id = :id"),
            {"id": id}
        )
        db.session.commit()
        flash(_("skill_deleted_successfully"), "success")
    except IntegrityError:
        db.session.rollback()
        flash(_("error_deleting_skill"), "danger")

    return redirect(url_for("skills.skills_page"))


@skills_bp.route("/api/toggle-status/<int:id>", methods=["POST"])
def api_toggle_status(id):
    auth_check = require_super_admin()
    if auth_check:
        return jsonify({"error": "Unauthorized"}), 401

    if not is_super_admin():
        return jsonify({"error": "Access denied"}), 403

    try:
        data = request.get_json() or {}
        new_status = data.get("status")
        
        if new_status not in ("Active", "Inactive"):
            return jsonify({"error": "Invalid status"}), 400

        db.session.execute(
            text("UPDATE skills SET status = :status WHERE skill_id = :id"),
            {"status": new_status, "id": id}
        )
        db.session.commit()

        return jsonify({"status": new_status, "skill_id": id})
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": str(e)}), 500
