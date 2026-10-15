from flask import Blueprint, flash, redirect, render_template, request, url_for
from flask_babel import gettext as _
from sqlalchemy import text
from help_db import db

settings_bp = Blueprint("settings", __name__)


@settings_bp.route("/settings", methods=["GET", "POST"])
def settings():
    if request.method == "POST":
        company_name = request.form.get("company_name", "").strip()
        company_email = request.form.get("company_email", "").strip()
        company_phone = request.form.get("company_phone", "").strip()
        company_address = request.form.get("company_address", "").strip()
        smtp_server = request.form.get("smtp_server", "").strip()
        smtp_port = request.form.get("smtp_port", "587")
        smtp_username = request.form.get("smtp_username", "").strip()
        smtp_password = request.form.get("smtp_password", "").strip()
        smtp_use_tls = request.form.get("smtp_use_tls") == "on"
        default_priority = request.form.get("default_priority", "Medium").strip()
        auto_assign_tickets = request.form.get("auto_assign_tickets") == "on"
        items_per_page = request.form.get("items_per_page", "25").strip()
        timezone = request.form.get("timezone", "UTC").strip()

        try:
            smtp_port_int = int(smtp_port)
            items_per_page_int = int(items_per_page)
        except ValueError:
            flash(_("invalid_port_or_items_per_page_value"), "danger")
            return redirect(url_for("settings.settings"))

        db.session.execute(text("""
            UPDATE settings SET
                company_name = :company_name,
                company_email = :company_email,
                company_phone = :company_phone,
                company_address = :company_address,
                smtp_server = :smtp_server,
                smtp_port = :smtp_port,
                smtp_username = :smtp_username,
                smtp_password = :smtp_password,
                smtp_use_tls = :smtp_use_tls,
                default_priority = :default_priority,
                auto_assign_tickets = :auto_assign_tickets,
                items_per_page = :items_per_page,
                timezone = :timezone,
                updated_at = CURRENT_TIMESTAMP
        """),
        {
            "company_name": company_name,
            "company_email": company_email,
            "company_phone": company_phone,
            "company_address": company_address,
            "smtp_server": smtp_server,
            "smtp_port": smtp_port_int,
            "smtp_username": smtp_username,
            "smtp_password": smtp_password,
            "smtp_use_tls": smtp_use_tls,
            "default_priority": default_priority,
            "auto_assign_tickets": auto_assign_tickets,
            "items_per_page": items_per_page_int,
            "timezone": timezone
        })
        db.session.commit()
        flash(_("settings_saved_successfully"), "success")
        return redirect(url_for("settings.settings"))

    settings_data = db.session.execute(text("""
        SELECT * FROM settings ORDER BY setting_id DESC LIMIT 1
    """)).fetchone()

    priorities = db.session.execute(text("""
        SELECT priority_name FROM priorities ORDER BY priority_name
    """)).fetchall()

    return render_template(
        "settings.html",
        settings=settings_data,
        priorities=priorities
    )
