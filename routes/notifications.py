import logging
from flask import Blueprint, render_template, request, redirect, flash, url_for, session, jsonify
from flask_babel import gettext as _
from sqlalchemy import text
from help_db import db

notifications_bp = Blueprint('notifications', __name__)

logger = logging.getLogger(__name__)


def require_super_admin_notification():
    """Check if the current user is a Super Admin. Returns redirect if not authorized."""
    user_id = session.get("user_id")
    if not user_id:
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

    if not role or role[0] != "Super Admin":
        return redirect(url_for("login_page"))
    return None


@notifications_bp.route("/notifications")
def notifications():
    auth_check = require_super_admin_notification()
    if auth_check:
        return auth_check

    search = request.args.get("search", "").strip()
    status_filter = request.args.get("status", "").strip()
    user_id = session.get("user_id")

    query = """
        SELECT
            n.notification_id,
            u.first_name,
            u.last_name,
            n.title,
            n.message,
            n.is_read,
            n.created_at,
            u.user_id
        FROM notifications n
        JOIN users u ON n.user_id = u.user_id
        WHERE n.user_id = :current_user_id
    """
    params = {"current_user_id": user_id}

    if search:
        query += " AND (n.title ILIKE :search OR n.message ILIKE :search)"
        params["search"] = f"%{search}%"

    if status_filter:
        query += " AND n.is_read = :is_read"
        params["is_read"] = status_filter == "read"

    query += " ORDER BY n.notification_id DESC"

    notifications = db.session.execute(text(query), params).fetchall()

    total_count = len(notifications)
    unread_count = sum(1 for n in notifications if not n.is_read)
    read_count = sum(1 for n in notifications if n.is_read)

    return render_template(
        "notifications.html",
        notifications=notifications,
        users=[],
        total_count=total_count,
        unread_count=unread_count,
        read_count=read_count,
        search=search,
        status_filter=status_filter,
    )

@notifications_bp.route("/add-notification")
def add_notification():
    users = db.session.execute(text("""
        SELECT user_id, first_name, last_name FROM users ORDER BY first_name
    """)).fetchall()

    return render_template(
        "add_notification.html",
        users=users
    )

@notifications_bp.route("/save-notification", methods=["POST"])
def save_notification():
    user_id = request.form.get("user_id")
    title = request.form.get("title")
    message = request.form.get("message")
    is_read = request.form.get("is_read") == "True"

    db.session.execute(
        text("""
            INSERT INTO notifications (user_id, title, message, is_read)
            VALUES (:user_id, :title, :message, :is_read)
        """),
        {
            "user_id": user_id,
            "title": title,
            "message": message,
            "is_read": is_read
        }
    )
    db.session.commit()

    flash(_("notification_added_successfully"), "success")
    return redirect("/notifications")

@notifications_bp.route("/edit-notification/<int:notification_id>")
def edit_notification(notification_id):
    notification = db.session.execute(
        text("""
            SELECT *
            FROM notifications
            WHERE notification_id = :notification_id
        """),
        {"notification_id": notification_id}
    ).fetchone()

    users = db.session.execute(text("""
        SELECT user_id, first_name, last_name FROM users ORDER BY first_name
    """)).fetchall()

    return render_template(
        "edit_notification.html",
        notification=notification,
        users=users
    )

@notifications_bp.route("/update-notification/<int:notification_id>", methods=["POST"])
def update_notification(notification_id):
    user_id = request.form.get("user_id")
    title = request.form.get("title")
    message = request.form.get("message")
    is_read = request.form.get("is_read") == "True"

    db.session.execute(
        text("""
            UPDATE notifications
            SET user_id = :user_id,
                title = :title,
                message = :message,
                is_read = :is_read
            WHERE notification_id = :notification_id
        """),
        {
            "user_id": user_id,
            "title": title,
            "message": message,
            "is_read": is_read,
            "notification_id": notification_id
        }
    )
    db.session.commit()

    flash(_("notification_updated_successfully"), "success")
    return redirect("/notifications")

@notifications_bp.route("/delete-notification/<int:notification_id>")
def delete_notification(notification_id):
    auth_check = require_super_admin_notification()
    if auth_check:
        return auth_check

    user_id = session.get("user_id")
    try:
        db.session.execute(
            text("""
                DELETE FROM notifications
                WHERE notification_id = :notification_id AND user_id = :user_id
            """),
            {"notification_id": notification_id, "user_id": user_id}
        )
        db.session.commit()
        flash(_("notification_deleted_successfully"), "success")
    except Exception:
        db.session.rollback()
        flash(_("failed_to_delete_notification"), "danger")
    return redirect("/notifications")


@notifications_bp.route("/notifications/delete-all", methods=["POST"])
def delete_all_notifications():
    auth_check = require_super_admin_notification()
    if auth_check:
        return jsonify({"success": False, "message": "Unauthorized"}), 403

    user_id = session.get("user_id")
    if not user_id:
        return jsonify({"success": False, "message": "Please login first"}), 401

    try:
        result = db.session.execute(
            text("""
                DELETE FROM notifications
                WHERE user_id = :user_id
            """),
            {"user_id": user_id}
        )
        db.session.commit()
        if result.rowcount == 0:
            return jsonify({"success": True, "message": "No notifications to delete", "deleted_count": 0})
        return jsonify({"success": True, "message": "All notifications deleted successfully", "deleted_count": result.rowcount})
    except Exception as e:
        db.session.rollback()
        logger.exception(f"Failed to delete notifications for user {user_id}")
        return jsonify({"success": False, "message": "Failed to delete notifications"}), 500
