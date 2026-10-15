from flask import Blueprint, render_template, request, redirect, flash, url_for, session, jsonify, current_app
from werkzeug.utils import secure_filename
from flask_babel import gettext as _
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from help_db import db
from datetime import datetime
import os
import sys
import subprocess

super_admin_bp = Blueprint('super_admin', __name__)


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

    if not role or role[0] != "Super Admin":
        flash(_("access_denied"), "danger")
        return redirect(url_for("login_page"))
    return None


@super_admin_bp.route('/super-admin-dashboard')
def super_admin_dashboard():
    auth_check = require_super_admin()
    if auth_check:
        return auth_check

    total_users = db.session.execute(
        text("""
            SELECT COUNT(*)
            FROM users
            WHERE role_id != 6
        """)
    ).scalar()

    total_tickets = db.session.execute(
        text("""
            SELECT COUNT(*)
            FROM tickets
        """)
    ).scalar()

    recent_tickets = db.session.execute(
        text("""
            SELECT
                t.ticket_id,
                t.ticket_number,
                t.title,
                s.status_name,
                t.ai_suggested_priority,
                t.ai_suggested_category,
                t.created_at
            FROM  tickets t
            JOIN ticket_status s
            ON t.status_name = s.status_name
            ORDER BY t.ticket_id DESC
            LIMIT 10
        """)
    ).fetchall()

    open_tickets = db.session.execute(
        text("""
            SELECT COUNT(*)
            FROM tickets
            WHERE status_name = 'Open'
        """)
    ).scalar()

    closed_tickets = db.session.execute(
        text("""
            SELECT COUNT(*)
            FROM tickets
            WHERE status_name = 'Closed'
        """)
    ).scalar()

    pending_tickets = db.session.execute(
        text("""
            SELECT COUNT(*)
            FROM tickets
            WHERE status_name = 'On Hold'
        """)
    ).scalar()

    total_departments = db.session.execute(
        text("""
            SELECT COUNT(*)
            FROM departments
        """)
    ).scalar()

    total_skills = db.session.execute(
        text("""
            SELECT COUNT(*)
            FROM skills
        """)
    ).scalar()

    total_customers = db.session.execute(
        text("""
            SELECT COUNT(*)
            FROM users
            WHERE role_id = 6
        """)
    ).scalar()

    top_agents = db.session.execute(
        text("""
            SELECT
                u.first_name,
                u.last_name,
                COUNT(t.ticket_id) AS total_tickets
            FROM users u
            JOIN tickets t
                ON u.user_id = t.assigned_to
            GROUP BY
                u.user_id,
                u.first_name,
                u.last_name
            ORDER BY total_tickets DESC
            LIMIT 5
        """)
    ).fetchall()

    pie_data = db.session.execute(
        text("""
            SELECT
                c.category_name,
                COUNT(t.ticket_id) AS total_tickets
            FROM categories c
            LEFT JOIN tickets t
            ON c.category_name = t.category_name
            GROUP BY c.category_name
            ORDER BY c.category_name;
        """)
    ).fetchall()

    ticket_chart = db.session.execute(
        text("""
            SELECT
                s.status_name,
                COUNT(t.ticket_id) AS total_tickets
            FROM ticket_status s
            LEFT JOIN tickets t
            ON s.status_name = t.status_name
            GROUP BY s.status_name
            ORDER BY s.status_name
        """)
    ).fetchall()

    status_labels = []
    status_counts = []
    for row in ticket_chart:
        status_labels.append(row.status_name)
        status_counts.append(int(row.total_tickets))

    pie_labels = []
    pie_counts = []
    for row in pie_data:
        pie_labels.append(row.category_name)
        pie_counts.append(int(row.total_tickets))

    # AI Feature Counts
    ai_summary_count = db.session.execute(
        text("SELECT COUNT(*) FROM tickets WHERE ai_summary IS NOT NULL")
    ).scalar()

    ai_priority_count = db.session.execute(
        text("SELECT COUNT(*) FROM tickets WHERE ai_suggested_priority IS NOT NULL")
    ).scalar()

    ai_category_count = db.session.execute(
        text("SELECT COUNT(*) FROM tickets WHERE ai_suggested_category IS NOT NULL")
    ).scalar()

    ai_reply_count = db.session.execute(
        text("SELECT COUNT(*) FROM tickets WHERE ai_suggested_reply IS NOT NULL")
    ).scalar()

    ai_sentiment_count = db.session.execute(
        text("SELECT COUNT(*) FROM tickets WHERE ai_sentiment IS NOT NULL")
    ).scalar()

    # ML Model Info
    ml_model_info = None
    try:
        from ml.resolution_predictor import get_resolution_predictor
        predictor = get_resolution_predictor()
        ml_model_info = predictor.get_model_info()
    except Exception:
        ml_model_info = None

    return render_template("super_admin_dashboard.html",
        total_users=total_users,
        total_tickets=total_tickets,
        open_tickets=open_tickets,
        recent_tickets=recent_tickets,
        closed_tickets=closed_tickets,
        pending_tickets=pending_tickets,
        total_departments=total_departments,
        total_skills=total_skills,
        total_customers=total_customers,
        top_agents=top_agents,
        pie_data=pie_data,
        ticket_chart=ticket_chart,
        status_labels=status_labels,
        status_counts=status_counts,
        pie_labels=pie_labels,
        pie_counts=pie_counts,
        ai_summary_count=ai_summary_count,
        ai_priority_count=ai_priority_count,
        ai_category_count=ai_category_count,
        ai_reply_count=ai_reply_count,
        ai_sentiment_count=ai_sentiment_count,
        ml_model_info=ml_model_info
    )


@super_admin_bp.route('/super-admin/profile', methods=['GET', 'POST'])
def profile():
    auth_check = require_super_admin()
    if auth_check:
        return auth_check

    user_id = session.get("user_id")

    if request.method == 'POST':
        first_name = request.form.get("first_name", "").strip()
        last_name = request.form.get("last_name", "").strip()
        email = request.form.get("email", "").strip()
        mobile = request.form.get("mobile", "").strip()
        
        profile_pic_filename = None
        if 'profile_pic' in request.files:
            file = request.files['profile_pic']
            if file and file.filename:
                ext = file.filename.rsplit('.', 1)[-1].lower()
                if ext in ['png', 'jpg', 'jpeg', 'gif', 'webp']:
                    filename = secure_filename(f"user_{user_id}_{file.filename}")
                    upload_folder = os.path.join(current_app.root_path, 'static', 'uploads', 'profiles')
                    os.makedirs(upload_folder, exist_ok=True)
                    file.save(os.path.join(upload_folder, filename))
                    profile_pic_filename = filename

        try:
            if profile_pic_filename:
                db.session.execute(
                    text("""
                        UPDATE users
                        SET first_name = :first_name,
                            last_name = :last_name,
                            email = :email,
                            mobile = :mobile,
                            profile_pic = :profile_pic
                        WHERE user_id = :user_id
                    """),
                    {
                        "first_name": first_name,
                        "last_name": last_name,
                        "email": email,
                        "mobile": mobile,
                        "profile_pic": profile_pic_filename,
                        "user_id": user_id
                    }
                )
            else:
                db.session.execute(
                    text("""
                        UPDATE users
                        SET first_name = :first_name,
                            last_name = :last_name,
                            email = :email,
                            mobile = :mobile
                        WHERE user_id = :user_id
                    """),
                    {
                        "first_name": first_name,
                        "last_name": last_name,
                        "email": email,
                        "mobile": mobile,
                        "user_id": user_id
                    }
                )
            db.session.commit()
            
            if profile_pic_filename:
                session['profile_pic'] = profile_pic_filename
            
            flash(_("profile_updated_successfully"), "success")
        except IntegrityError:
            db.session.rollback()
            flash(_("email_already_exists"), "danger")
        except Exception:
            db.session.rollback()
            flash(_("error_updating_profile"), "danger")
            
        return redirect(url_for('super_admin.profile'))

    user = db.session.execute(
        text("""
            SELECT u.user_id, u.first_name, u.last_name, u.email, u.mobile, u.profile_pic,
                   r.role_name, d.department_name
            FROM users u
            JOIN roles r ON u.role_id = r.role_id
            LEFT JOIN departments d ON u.department_id = d.department_id
            WHERE u.user_id = :user_id
        """),
        {"user_id": user_id}
    ).fetchone()

    return render_template("super_admin_profile.html", user=user)


@super_admin_bp.route('/super-admin/tickets/<int:ticket_id>')
def ticket_detail(ticket_id):
    auth_check = require_super_admin()
    if auth_check:
        return auth_check

    ticket = db.session.execute(
        text("""
            SELECT
                t.ticket_id,
                t.ticket_number,
                t.title,
                t.description,
                t.status_name,
                t.priority_name,
                t.category_name,
                t.source,
                t.created_at,
                t.updated_at,
                t.assigned_at,
                t.due_date,
                t.resolved_at,
                t.rating,
                t.reopen_count,
                t.ai_summary,
                t.ai_suggested_reply,
                t.ai_suggested_category,
                t.ai_suggested_priority,
                t.ai_suggested_department,
                t.ai_suggested_agent,
                t.ai_confidence,
                t.ai_correction_type,
                t.needs_manual_review,
                t.issue_type_id,
                t.assignment_history_id,
                u.first_name AS requester_first,
                u.last_name AS requester_last,
                u.email AS requester_email,
                u.mobile AS requester_phone,
                a.first_name AS agent_first,
                a.last_name AS agent_last,
                a.email AS agent_email,
                d.department_name,
                it.issue_name
            FROM tickets t
            LEFT JOIN users u ON t.requester_id = u.user_id
            LEFT JOIN users a ON t.assigned_to = a.user_id
            LEFT JOIN departments d ON t.department_id = d.department_id
            LEFT JOIN issue_types it ON t.issue_type_id = it.issue_type_id
            WHERE t.ticket_id = :ticket_id
        """),
        {"ticket_id": ticket_id}
    ).fetchone()

    if not ticket:
        return render_template("super_admin_ticket_detail.html", ticket=None, ml_prediction=None)

    comments = db.session.execute(
        text("""
            SELECT
                tc.comment_id,
                tc.comment_text,
                tc.is_internal,
                tc.created_at,
                u.first_name,
                u.last_name,
                r.role_name
            FROM ticket_comments tc
            JOIN users u ON tc.user_id = u.user_id
            LEFT JOIN roles r ON u.role_id = r.role_id
            WHERE tc.ticket_id = :ticket_id
            ORDER BY tc.comment_id ASC
        """),
        {"ticket_id": ticket_id}
    ).fetchall()

    attachments = db.session.execute(
        text("""
            SELECT
                ta.attachment_id,
                ta.file_name,
                ta.file_path,
                ta.uploaded_at,
                u.first_name AS uploader_first,
                u.last_name AS uploader_last
            FROM ticket_attachments ta
            JOIN users u ON ta.uploaded_by = u.user_id
            WHERE ta.ticket_id = :ticket_id
            ORDER BY ta.uploaded_at DESC
        """),
        {"ticket_id": ticket_id}
    ).fetchall()

    status_history = db.session.execute(
        text("""
            SELECT
                th.history_id,
                th.old_status,
                th.new_status,
                th.changed_at,
                COALESCE(u.first_name || ' ' || u.last_name, 'System') AS changed_by_name
            FROM ticket_status_history th
            LEFT JOIN users u ON th.changed_by = u.user_id
            WHERE th.ticket_id = :ticket_id
            ORDER BY th.history_id DESC
        """),
        {"ticket_id": ticket_id}
    ).fetchall()

    ml_prediction = None
    try:
        from utils.ml_service import get_prediction_for_ticket
        ml_prediction = get_prediction_for_ticket(ticket_id)
    except Exception:
        ml_prediction = None

    return render_template(
        "super_admin_ticket_detail.html",
        ticket=ticket,
        comments=comments,
        attachments=attachments,
        status_history=status_history,
        ml_prediction=ml_prediction
    )


@super_admin_bp.route('/ml-model')
def ml_model():
    auth_check = require_super_admin()
    if auth_check:
        return auth_check

    try:
        from ml.resolution_predictor import get_resolution_predictor
        predictor = get_resolution_predictor()
        model_info = predictor.get_model_info()
    except Exception:
        model_info = {
            "model_version": "error",
            "trained_at": None,
            "training_records": 0,
            "mae_minutes": None,
            "rmse_minutes": None,
            "r2": None,
            "model_status": "error",
            "dataset_status": "unknown",
            "eligible_training_records": 0,
            "sufficient_data": False,
            "warning": "Failed to load ML model info."
        }

    try:
        from ml.model_manager import get_model_manager
        mm = get_model_manager()
        training_stats = mm.get_training_stats()
    except Exception:
        training_stats = {
            "total_tickets": 0,
            "resolved_tickets": 0,
            "eligible_for_training": 0,
        }

    return render_template(
        "ml_model.html",
        model_info=model_info,
        training_stats=training_stats
    )


@super_admin_bp.route('/ml-model/retrain', methods=['POST'])
def retrain_model():
    auth_check = require_super_admin()
    if auth_check:
        return auth_check

    try:
        import subprocess
        # Use venv Python if available, otherwise fall back to current
        venv_py = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "venv", "Scripts", "python.exe"
        )
        python_exe = venv_py if os.path.exists(venv_py) else sys.executable
        result = subprocess.run(
            [python_exe, "-m", "ml.train_resolution_model"],
            capture_output=True,
            text=True,
            timeout=300,
            cwd=os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        )
        output = result.stdout + result.stderr
        success = result.returncode == 0
    except Exception as e:
        output = str(e)
        success = False

    from ml.resolution_predictor import get_resolution_predictor
    predictor = get_resolution_predictor()
    predictor.refresh()
    model_info = predictor.get_model_info()

    try:
        from ml.model_manager import get_model_manager
        mm = get_model_manager()
        training_stats = mm.get_training_stats()
    except Exception:
        training_stats = {"total_tickets": 0, "resolved_tickets": 0, "eligible_for_training": 0}

    return render_template(
        "ml_model.html",
        model_info=model_info,
        training_stats=training_stats,
        retrain_result={
            "success": success,
            "output": output
        }
    )


@super_admin_bp.route('/ml-predictions')
def ml_predictions():
    auth_check = require_super_admin()
    if auth_check:
        return auth_check

    search = request.args.get("search", "")

    query = """
        SELECT
            mp.prediction_id,
            t.ticket_id,
            t.ticket_number,
            t.title,
            t.priority_name,
            t.status_name,
            mp.model_version,
            mp.predicted_resolution_minutes,
            mp.prediction_lower_minutes,
            mp.prediction_upper_minutes,
            mp.prediction_created_at,
            mp.actual_resolution_minutes,
            mp.prediction_error_minutes,
            t.created_at,
            t.resolved_at,
            s.resolution_time as sla_hours
        FROM ticket_ml_predictions mp
        JOIN tickets t ON t.ticket_id = mp.ticket_id
        LEFT JOIN sla_rules s ON t.priority_name = (
            SELECT p.priority_name FROM priorities p WHERE p.priority_id = s.priority_id
        ) AND s.status = 'Active'
        WHERE (
            t.ticket_number ILIKE :search OR
            t.title ILIKE :search
        )
        ORDER BY mp.prediction_created_at DESC
        LIMIT 200
    """

    predictions = db.session.execute(text(query), {"search": f"%{search}%"}).fetchall()

    return render_template(
        "ml_prediction_history.html",
        predictions=predictions,
        search=search
    )


@super_admin_bp.route('/api/ml-prediction-history/search')
def api_ml_prediction_history_search():
    auth_check = require_super_admin()
    if auth_check:
        return auth_check

    q = request.args.get("q", "").strip()
    params = {"search": f"%{q}%"}

    predictions = db.session.execute(text("""
        SELECT
            mp.prediction_id,
            t.ticket_id,
            t.ticket_number,
            t.title,
            t.priority_name,
            t.status_name,
            mp.model_version,
            mp.predicted_resolution_minutes,
            mp.actual_resolution_minutes,
            mp.prediction_error_minutes,
            mp.prediction_created_at,
            s.resolution_time as sla_hours
        FROM ticket_ml_predictions mp
        JOIN tickets t ON t.ticket_id = mp.ticket_id
        LEFT JOIN sla_rules s ON t.priority_name = (
            SELECT p.priority_name FROM priorities p WHERE p.priority_id = s.priority_id
        ) AND s.status = 'Active'
        WHERE (
            t.ticket_number ILIKE :search
            OR t.title ILIKE :search
        )
        ORDER BY mp.prediction_created_at DESC
        LIMIT 50
    """), params).fetchall()

    rows = []
    for p in predictions:
        rows.append({
            "prediction_id": p.prediction_id,
            "ticket_id": p.ticket_id,
            "ticket_number": p.ticket_number,
            "title": p.title,
            "priority_name": p.priority_name,
            "status_name": p.status_name,
            "model_version": p.model_version,
            "predicted_minutes": round(float(p.predicted_resolution_minutes), 1) if p.predicted_resolution_minutes else None,
            "actual_minutes": round(float(p.actual_resolution_minutes), 1) if p.actual_resolution_minutes else None,
            "error_minutes": round(float(p.prediction_error_minutes), 1) if p.prediction_error_minutes else None,
            "prediction_created_at": p.prediction_created_at.strftime('%Y-%m-%d %H:%M') if p.prediction_created_at else 'N/A',
            "sla_hours": round(float(p.sla_hours), 1) if p.sla_hours else None
        })

    return jsonify({"rows": rows, "count": len(rows)})
