from flask import Blueprint, render_template, request, redirect, url_for, flash, session
from flask_babel import gettext as _
from sqlalchemy import text
from help_db import db
from datetime import datetime
from utils.notifications import notify_ticket_created, calculate_due_date

contact_bp = Blueprint('contact', __name__)


@contact_bp.route('/contact', methods=['GET', 'POST'])
def contact_form():
    if request.method == 'POST':
        first_name = request.form.get("first_name")
        last_name = request.form.get("last_name")
        email = request.form.get("email")
        mobile = request.form.get("mobile")
        subject = request.form.get("subject")
        description = request.form.get("description")
        category = request.form.get("category", "Technical")
        priority = request.form.get("priority", "Medium")

        if not all([first_name, last_name, email, subject, description]):
            flash(_("all_required_fields_must_be_filled"), "danger")
            return redirect(url_for("contact.contact_form"))

        check = db.session.execute(
            text("SELECT user_id FROM users WHERE email = :email"),
            {"email": email}
        ).fetchone()

        if check:
            requester_id = check[0]
        else:
            hashed_pw = "contact_form_" + datetime.utcnow().strftime("%Y%m%d%H%M%S")
            from werkzeug.security import generate_password_hash
            db.session.execute(
                text("""
                    INSERT INTO users (first_name, last_name, email, mobile, password_hash, role_id, status)
                    VALUES (:first_name, :last_name, :email, :mobile, :password_hash, 6, 'Active')
                """),
                {
                    "first_name": first_name,
                    "last_name": last_name,
                    "email": email,
                    "mobile": mobile,
                    "password_hash": generate_password_hash(hashed_pw)
                }
            )
            db.session.commit()
            requester_id = db.session.execute(
                text("SELECT user_id FROM users WHERE email = :email"),
                {"email": email}
            ).fetchone()[0]

        last_ticket = db.session.execute(
            text("SELECT ticket_number FROM tickets ORDER BY ticket_id DESC LIMIT 1")
        ).fetchone()

        if last_ticket:
            last_num = last_ticket[0]
            if last_num.startswith('TKT'):
                try:
                    seq = int(last_num[3:]) + 1
                except ValueError:
                    seq = 1
            else:
                seq = 1
        else:
            seq = 1
        ticket_number = f"TKT{seq:03d}"

        while db.session.execute(
            text("SELECT ticket_id FROM tickets WHERE ticket_number = :tn"),
            {"tn": ticket_number}
        ).fetchone():
            seq += 1
            ticket_number = f"TKT{seq:03d}"

        db.session.execute(
            text("""
                INSERT INTO tickets (
                    ticket_number, title, description, category_name, priority_name,
                    status_name, requester_id, source, created_at, updated_at, due_date
                ) VALUES (
                    :ticket_number, :title, :description, :category_name, :priority_name,
                    'New', :requester_id, 'Contact Form', :created_at, :updated_at, :due_date
                )
            """),
            {
                "ticket_number": ticket_number,
                "title": subject,
                "description": description,
                "category_name": category,
                "priority_name": priority,
                "requester_id": requester_id,
                "created_at": datetime.utcnow(),
                "updated_at": datetime.utcnow(),
                "due_date": calculate_due_date(priority, datetime.utcnow())
            }
        )
        db.session.commit()

        ticket_id = db.session.execute(
            text("SELECT ticket_id FROM tickets WHERE ticket_number = :ticket_number"),
            {"ticket_number": ticket_number}
        ).fetchone()[0]

        notify_ticket_created(ticket_id, subject, requester_id)

        flash(_("thank_you_your_message_has_been_sent_a_support_ticket_has_been_created_and_our_team_will_respond_shortly"), "success")
        return redirect(url_for("contact.contact_form"))

    categories = db.session.execute(
        text("SELECT category_name FROM categories ORDER BY category_name")
    ).fetchall()

    return render_template("contact_us.html", categories=categories)
