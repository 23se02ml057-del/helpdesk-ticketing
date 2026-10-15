from flask import Blueprint, render_template, request, jsonify, session, flash, redirect, url_for, current_app
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from help_db import db
import secrets
import hashlib
import logging
from datetime import datetime, timedelta
from utils.email_service import send_email
from utils.email_service import send_customer_verification_email
from flask_babel import gettext as _
from werkzeug.security import (
    generate_password_hash,
    check_password_hash
)
from flask_jwt_extended import (
    create_access_token,
    get_jwt_identity
)

auth_bp = Blueprint('auth', __name__)
logger = logging.getLogger(__name__)


def _hash_verification_token(token):
    return hashlib.sha256(token.encode('utf-8')).hexdigest()

PASSWORD_MIN_LENGTH = 8


def validate_password(password):
    errors = []
    if not password:
        errors.append("Password is required")
    elif len(password) < PASSWORD_MIN_LENGTH:
        errors.append(f"Password must be at least {PASSWORD_MIN_LENGTH} characters long")
    elif not any(c.isupper() for c in password):
        errors.append("Password must contain at least one uppercase letter")
    elif not any(c.islower() for c in password):
        errors.append("Password must contain at least one lowercase letter")
    elif not any(c.isdigit() for c in password):
        errors.append("Password must contain at least one number")
    return errors


def success_response(message, status_code=200):
    return jsonify({"success": True, "message": message}), status_code


def failure_response(message, status_code=400):
    return jsonify({"success": False, "message": message}), status_code


# ================= LOGIN =================
@auth_bp.route('/login', methods=['POST'])
def login():
    try:
        data = request.get_json() or {}
        email = (data.get('email') or '').strip().lower()
        password = data.get('password') or ''

        if not email or not password:
            return failure_response("Email and Password are required", 400)

        query = text("""
            SELECT user_id,
                   email,
                   password_hash,
                   role_id,
                   status,
                   email_verified,
                   profile_pic
            FROM users
            WHERE email = :email
        """)
        user = db.session.execute(query, {"email": email}).fetchone()

        if user is None:
            return failure_response("User Not Found", 404)

        user_id = user[0]
        email_db = user[1]
        password_hash = user[2]
        role_id = user[3]
        status = user[4]
        email_verified = user[5]
        profile_pic = user[6] if len(user) > 6 else None

        if status and status.lower() != "active":
            return failure_response("Account is inactive. Please contact support.", 403)

        if role_id == 6 and not email_verified:
            return failure_response("Please verify your email address before logging in.", 403)

        if not check_password_hash(password_hash, password):
            return failure_response("Invalid Password", 401)

        access_token = create_access_token(
            identity=str(user_id),
            additional_claims={
                "role_id": role_id
            }
        )
        session["user_id"] = user_id
        session["email"] = email_db
        session["role_id"] = role_id
        if profile_pic:
            session["profile_pic"] = profile_pic

        try:
            db.session.execute(
                text("UPDATE users SET last_login = :now WHERE user_id = :user_id"),
                {"now": datetime.utcnow(), "user_id": user_id}
            )
            db.session.commit()
        except Exception:
            db.session.rollback()

        if role_id == 6:
            try:
                from utils.socket_events import emit_new_customer
                user_info = db.session.execute(
                    text("""
                        SELECT u.first_name, u.last_name, u.email, u.mobile, d.department_name
                        FROM users u
                        LEFT JOIN departments d ON u.department_id = d.department_id
                        WHERE u.user_id = :user_id
                    """),
                    {"user_id": user_id}
                ).fetchone()
                if user_info:
                    emit_new_customer(
                        user_id, user_info[0], user_info[1], user_info[2],
                        user_info[3], user_info[4]
                    )
            except Exception as socket_err:
                logger.warning(f"Login socket notification failed: {socket_err}")

        return jsonify({
            "success": True,
            "message": "Login Success",
            "token": access_token,
            "user_id": user_id,
            "email": email_db,
            "role_id": role_id
        }), 200
    except Exception as e:
        db.session.rollback()
        logger.exception(f"Login error: {e}")
        return failure_response("An internal error occurred. Please try again later.", 500)


# ================= PROTECTED =================
@auth_bp.route('/protected', methods=['GET'])
def protected():
    current_user_id = get_jwt_identity()
    return jsonify({
        "success": True,
        "message": "Dashboard Access Success",
        "user_id": current_user_id
    }), 200


# ================= REGISTER =================
@auth_bp.route('/register', methods=['POST'])
def register():
    try:
        data = request.get_json() or {}
        first_name = (data.get('first_name') or '').strip()
        last_name = (data.get('last_name') or '').strip()
        email = (data.get('email') or '').strip().lower()
        mobile = (data.get('mobile') or '').strip()
        password = data.get('password') or ''
        confirm_password = data.get('confirm_password') or ''
        department_id = 6
        role_id = 6

        if not email or not password:
            return failure_response("Email and Password are required", 400)

        if password != confirm_password:
            return failure_response("Passwords do not match", 400)

        password_errors = validate_password(password)
        if password_errors:
            return failure_response(" ".join(password_errors), 400)

        check_query = text("SELECT user_id FROM users WHERE email = :email")
        existing_user = db.session.execute(check_query, {"email": email}).fetchone()

        if existing_user:
            existing_check = db.session.execute(
                text("SELECT email_verified FROM users WHERE email = :email"),
                {"email": email}
            ).fetchone()
            if existing_check and not existing_check[0]:
                return jsonify({
                    "success": True,
                    "message": "This email is already registered but not verified. Please check your email for the verification link, or request a new one.",
                    "email": email
                }), 200
            return failure_response("User with this email already exists", 400)

        hashed_password = generate_password_hash(password)

        query = text("""
            INSERT INTO users
            (first_name, last_name, email, mobile, password_hash, department_id, role_id, status, email_verified)
            VALUES (:first_name, :last_name, :email, :mobile, :password_hash, :department_id, :role_id, 'Active', TRUE)
        """)
        db.session.execute(query, {
            "first_name": first_name or None,
            "last_name": last_name or None,
            "email": email,
            "mobile": mobile or None,
            "password_hash": hashed_password,
            "department_id": department_id,
            "role_id": role_id
        })
        db.session.commit()

        user_id_row = db.session.execute(
            text("SELECT user_id FROM users WHERE email = :email ORDER BY user_id DESC LIMIT 1"),
            {"email": email}
        ).fetchone()

        try:
            if role_id == 6:
                from utils.socket_events import emit_new_customer
                emit_new_customer(
                    None, first_name, last_name, email, mobile, None
                )
        except Exception as socket_err:
            logger.warning(f"Registration socket notification failed: {socket_err}")

        email_result = {}
        if role_id == 6 and user_id_row:
            login_link = url_for("login_page", _external=True)

            user_name = f"{first_name} {last_name}".strip()
            if not user_name:
                user_name = email

            try:
                from utils.email_service import send_customer_welcome_email
                email_result = send_customer_welcome_email(
                    email, user_name, login_link
                )
                if not email_result.get("success"):
                    logger.error(
                        "Failed to send welcome email to %s: %s",
                        email, email_result.get("error")
                    )
            except Exception as email_err:
                logger.error("Welcome email send error for %s: %s", email, email_err)
                email_result = {"success": False, "error": str(email_err)}

        return jsonify({
            "success": True,
            "message": "Registration successful. A welcome email has been sent.",
            "verification_sent": email_result.get("success", False)
        }), 201

    except IntegrityError as e:
        db.session.rollback()
        logger.exception(f"Registration integrity error: {e}")
        if 'users_email_key' in str(e.orig):
            return failure_response("User with this email already exists", 400)
        return failure_response("Database constraint violation. Please try again.", 400)
    except Exception as e:
        db.session.rollback()
        logger.exception(f"Registration error: {e}")
        return failure_response("An internal error occurred. Please try again later.", 500)


# ================= VERIFY CUSTOMER =================
@auth_bp.route('/verify-customer/<token>', methods=['GET'])
def verify_customer(token):
    try:
        token_hash = _hash_verification_token(token)
        token_query = text("""
            SELECT t.id, t.user_id, t.token_hash, t.expires_at, t.used_at,
                   u.email_verified
            FROM email_verification_tokens t
            JOIN users u ON t.user_id = u.user_id
            WHERE t.token_hash = :token_hash
        """)
        token_data = db.session.execute(token_query, {"token_hash": token_hash}).fetchone()

        if not token_data:
            return render_template('verification_error.html',
                                   error_message="Invalid or unrecognized verification link.")

        token_id = token_data[0]
        user_id = token_data[1]
        expires_at = token_data[3]
        used_at = token_data[4]

        if used_at is not None:
            return render_template('verification_already_used.html')

        if datetime.utcnow() > expires_at:
            return render_template('verification_expired.html', user_id=user_id)

        db.session.execute(
            text("UPDATE users SET email_verified = TRUE WHERE user_id = :user_id"),
            {"user_id": user_id}
        )
        db.session.execute(
            text("UPDATE email_verification_tokens SET used_at = :now WHERE id = :token_id"),
            {"token_id": token_id, "now": datetime.utcnow()}
        )
        db.session.commit()

        flash(_("your_email_has_been_verified_successfully_please_login_to_continue"), "success")
        return redirect(url_for("login_page"))

    except Exception as e:
        db.session.rollback()
        logger.exception(f"Verification error: {e}")
        return render_template('verification_error.html',
                               error_message="An error occurred during verification.")


# ================= RESEND VERIFICATION =================
@auth_bp.route('/resend-verification', methods=['POST'])
def resend_verification():
    try:
        data = request.get_json() or {}
        email = (data.get('email') or '').strip().lower()

        if not email:
            return failure_response("Email is required", 400)

        user = db.session.execute(
            text("SELECT user_id, first_name, last_name, email_verified FROM users WHERE email = :email AND role_id = 6"),
            {"email": email}
        ).fetchone()

        if not user:
            return failure_response("If an account with that email exists and is unverified, a new verification email has been sent.", 200)

        user_id = user[0]
        email_verified = user[3]

        if email_verified:
            return failure_response("This email is already verified. Please login.", 400)

        verification_token = secrets.token_urlsafe(32)
        expires_at = datetime.utcnow() + timedelta(hours=24)

        new_token_result = db.session.execute(
            text("""
                INSERT INTO email_verification_tokens (user_id, token_hash, expires_at)
                VALUES (:user_id, :token_hash, :expires_at)
                RETURNING id
            """),
            {
                "user_id": user_id,
                "token_hash": _hash_verification_token(verification_token),
                "expires_at": expires_at
            }
        )
        db.session.commit()

        verification_link = url_for(
            "auth.verify_customer",
            token=verification_token,
            _external=True
        )

        user_name = f"{user[1] or ''} {user[2] or ''}".strip()
        if not user_name:
            user_name = email

        email_result = send_customer_verification_email(
            email, user_name, verification_link
        )

        if not email_result.get("success"):
            logger.error("Failed to send resend verification email to %s: %s",
                         email, email_result.get("error"))
            return failure_response("Unable to send verification email at this time. Please try again later.", 500)

        return jsonify({
            "success": True,
            "message": "A new verification email has been sent to your registered email address."
        }), 200

    except Exception as e:
        db.session.rollback()
        logger.exception(f"Resend verification error: {e}")
        return failure_response("An internal error occurred. Please try again later.", 500)


# ================= FORGOT PASSWORD =================
@auth_bp.route('/forgot-password', methods=['POST'])
def forgot_password():
    try:
        data = request.get_json() or {}
        email = (data.get('email') or '').strip().lower()

        if not email:
            return failure_response("Email is required", 400)

        cleanup_expired_tokens_silent()

        user_query = text("""
            SELECT user_id, email, first_name, last_name
            FROM users
            WHERE email = :email
        """)
        user = db.session.execute(user_query, {"email": email}).fetchone()

        if not user:
            return failure_response("Email address is not registered. Please enter your registered email address.", 404)

        token = secrets.token_urlsafe(32)
        expires_at = datetime.utcnow() + timedelta(minutes=15)

        insert_query = text("""
            INSERT INTO password_reset_tokens (user_id, token, expires_at, used)
            VALUES (:user_id, :token, :expires_at, :used)
        """)
        db.session.execute(insert_query, {
            "user_id": user[0],
            "token": token,
            "expires_at": expires_at,
            "used": False
        })
        db.session.commit()

        reset_link = url_for('auth.reset_password', token=token, _external=True)

        user_name = f"{user[2] or ''} {user[3] or ''}".strip() or "User"

        from utils.email_service import send_forgot_password_email
        email_result = send_forgot_password_email(user[1], reset_link, user_name=user_name, expiry_minutes=15)

        if not email_result.get("success"):
            logger.error("Failed to send forgot password email to %s: %s", user[1], email_result.get("error"))
            return failure_response("Unable to send the password reset email. Please try again later.", 500)

        return jsonify({
            "success": True,
            "message": "Password reset link has been sent to your email. Please check your inbox.",
            "reset_link": reset_link,
            "email_sent": True
        }), 200
    except Exception as e:
        db.session.rollback()
        logger.exception(f"Forgot password error: {e}")
        return failure_response("An internal error occurred. Please try again later.", 500)


@auth_bp.route('/cleanup-expired-tokens')
def cleanup_expired_tokens():
    try:
        deleted = db.session.execute(
            text("""
                DELETE FROM password_reset_tokens
                WHERE expires_at < :now OR used = True
            """),
            {"now": datetime.utcnow()}
        ).rowcount
        db.session.commit()
        return jsonify({"success": True, "message": f"Cleaned up {deleted} expired/used tokens"}), 200
    except Exception as e:
        db.session.rollback()
        logger.exception(f"Cleanup error: {e}")
        return failure_response("An internal error occurred.", 500)


def cleanup_expired_tokens_silent():
    try:
        db.session.execute(
            text("""
                DELETE FROM password_reset_tokens
                WHERE expires_at < :now OR used = True
            """),
            {"now": datetime.utcnow()}
        )
        db.session.commit()
    except Exception:
        db.session.rollback()


# ================= RESET PASSWORD =================
@auth_bp.route('/reset-password/<token>', methods=['GET', 'POST'])
def reset_password(token):
    cleanup_expired_tokens_silent()

    if request.method == 'GET':
        token_query = text("""
            SELECT prt.user_id, u.email, prt.expires_at, prt.used
            FROM password_reset_tokens prt
            JOIN users u ON prt.user_id = u.user_id
            WHERE prt.token = :token
        """)
        token_data = db.session.execute(token_query, {"token": token}).fetchone()

        if not token_data:
            return render_template('reset_password.html', token=token, error="Invalid or expired reset link.")

        if token_data.used:
            return render_template('reset_password.html', token=token, error="This reset link has already been used.")

        if datetime.utcnow() > token_data.expires_at:
            return render_template('reset_password.html', token=token, error="This reset link has expired. Please request a new one.")

        return render_template('reset_password.html', token=token, email=token_data.email)

    try:
        if request.is_json:
            data = request.get_json() or {}
        else:
            data = request.form

        password = data.get('password') or ''
        confirm_password = data.get('confirm_password') or ''

        if not password or not confirm_password:
            error_msg = "Password and Confirm Password are required"
            if request.is_json:
                return failure_response(error_msg, 400)
            return render_template('reset_password.html', token=token, error=error_msg)

        if password != confirm_password:
            error_msg = "Passwords do not match"
            if request.is_json:
                return failure_response(error_msg, 400)
            return render_template('reset_password.html', token=token, error=error_msg)

        password_errors = validate_password(password)
        if password_errors:
            error_msg = " ".join(password_errors)
            if request.is_json:
                return failure_response(error_msg, 400)
            return render_template('reset_password.html', token=token, error=error_msg)

        token_query = text("""
            SELECT user_id
            FROM password_reset_tokens
            WHERE token = :token AND used = False AND expires_at > :now
        """)
        token_data = db.session.execute(token_query, {
            "token": token,
            "now": datetime.utcnow()
        }).fetchone()

        if not token_data:
            error_msg = "Invalid or expired token"
            if request.is_json:
                return failure_response(error_msg, 400)
            return render_template('reset_password.html', token=token, error=error_msg)

        hashed_password = generate_password_hash(password)

        update_query = text("""
            UPDATE users
            SET password_hash = :password_hash
            WHERE user_id = :user_id
        """)
        db.session.execute(update_query, {
            "password_hash": hashed_password,
            "user_id": token_data.user_id
        })

        mark_used_query = text("""
            UPDATE password_reset_tokens
            SET used = True
            WHERE token = :token
        """)
        db.session.execute(mark_used_query, {"token": token})
        db.session.commit()

        if request.is_json:
            return jsonify({
                "success": True,
                "message": "Password reset successfully. You can now login with your new password."
            }), 200

        return render_template('reset_password.html', token=token, success="Password reset successfully! You can now login with your new password.")

    except Exception as e:
        db.session.rollback()
        logger.exception(f"Reset password error: {e}")
        if request.is_json:
            return failure_response("An internal error occurred. Please try again later.", 500)
        return render_template('reset_password.html', token=token, error="An error occurred. Please try again.")


# ================= ADMIN RESET USER PASSWORD =================
@auth_bp.route('/admin/reset-user-password', methods=['POST'])
def admin_reset_user_password():
    try:
        user_id = request.form.get('user_id')
        new_password = request.form.get('new_password')
        confirm_password = request.form.get('confirm_password')

        if not user_id or not new_password or not confirm_password:
            flash(_("all_fields_are_required"), "danger")
            return redirect(url_for("users.get_users"))

        if new_password != confirm_password:
            flash(_("passwords_do_not_match"), "danger")
            return redirect(url_for("users.get_users"))

        password_errors = validate_password(new_password)
        if password_errors:
            flash(" ".join(password_errors), "danger")
            return redirect(url_for("users.get_users"))

        user_query = text("""
            SELECT user_id, email, first_name, last_name
            FROM users
            WHERE user_id = :user_id
        """)
        user = db.session.execute(user_query, {"user_id": user_id}).fetchone()

        if not user:
            flash(_("user_not_found"), "danger")
            return redirect(url_for("users.get_users"))

        hashed_password = generate_password_hash(new_password)
        update_query = text("""
            UPDATE users
            SET password_hash = :password_hash
            WHERE user_id = :user_id
        """)
        db.session.execute(update_query, {
            "password_hash": hashed_password,
            "user_id": user_id
        })
        db.session.commit()

        verification_query = text("""
            SELECT password_hash FROM users WHERE user_id = :user_id
        """)
        verify = db.session.execute(verification_query, {"user_id": user_id}).fetchone()

        if verify and check_password_hash(verify[0], new_password):
            flash(f"Password for {user[1]} ({user[2]} {user[3]}) has been reset successfully.", "success")
        else:
            flash(_("password_reset_failed_please_try_again"), "danger")

        return redirect(url_for("users.get_users"))

    except Exception as e:
        db.session.rollback()
        logger.exception(f"Admin reset password error: {e}")
        flash(f"An error occurred: {str(e) if current_app.config.get('DEBUG') else 'Please try again later.'}", "danger")
        return redirect(url_for("users.get_users"))


# ================= CHANGE PASSWORD =================
@auth_bp.route('/change-password', methods=['GET', 'POST'])
def change_password():
    user_id = session.get("user_id")
    role_id = session.get("role_id")

    if request.method == 'GET':
        if role_id == 1:
            template = 'change_password_sa.html'
            dashboard_url = url_for('super_admin.super_admin_dashboard')
        elif role_id == 5:
            template = 'change_password_admin.html'
            dashboard_url = url_for('admin.dashboard')
        elif role_id == 2:
            template = 'change_password_manager.html'
            dashboard_url = url_for('support_manager.dashboard')
        elif role_id == 3:
            template = 'change_password_agent.html'
            dashboard_url = url_for('support_agent.dashboard')
        else:
            template = 'change_password_customer.html'
            dashboard_url = url_for('customer.dashboard')

        return render_template(template, dashboard_url=dashboard_url)

    try:
        if request.is_json:
            data = request.get_json() or {}
        else:
            data = request.form

        current_password = data.get('current_password') or ''
        new_password = data.get('new_password') or ''
        confirm_password = data.get('confirm_password') or ''

        if not current_password or not new_password or not confirm_password:
            if request.is_json:
                return failure_response("All fields are required", 400)
            flash(_("all_fields_are_required"), "danger")
            return redirect(url_for("auth.change_password"))

        if new_password != confirm_password:
            if request.is_json:
                return failure_response("New passwords do not match", 400)
            flash(_("new_passwords_do_not_match"), "danger")
            return redirect(url_for("auth.change_password"))

        user_id = session.get("user_id")
        if not user_id:
            if request.is_json:
                return failure_response("Please login first", 401)
            flash(_("please_login_first"), "danger")
            return redirect(url_for("login_page"))

        user = db.session.execute(
            text("""
                SELECT password_hash FROM users WHERE user_id = :user_id
            """),
            {"user_id": user_id}
        ).fetchone()

        if not user:
            if request.is_json:
                return failure_response("User not found", 404)
            flash(_("user_not_found"), "danger")
            session.clear()
            return redirect(url_for("login_page"))

        password_errors = validate_password(new_password)
        if password_errors:
            if request.is_json:
                return failure_response(" ".join(password_errors), 400)
            flash(" ".join(password_errors), "danger")
            return redirect(url_for("auth.change_password"))

        if check_password_hash(user[0], new_password):
            if request.is_json:
                return failure_response("New password must be different from current password", 400)
            flash(_("new_password_must_be_different_from_current_password"), "danger")
            return redirect(url_for("auth.change_password"))

        if not check_password_hash(user[0], current_password):
            if request.is_json:
                return failure_response("Current password is incorrect", 400)
            flash(_("current_password_is_incorrect"), "danger")
            return redirect(url_for("auth.change_password"))

        hashed_password = generate_password_hash(new_password)
        db.session.execute(
            text("""
                UPDATE users SET password_hash = :password_hash WHERE user_id = :user_id
            """),
            {"password_hash": hashed_password, "user_id": user_id}
        )
        db.session.commit()

        session.clear()

        if request.is_json:
            return jsonify({
                "success": True,
                "message": "Password changed successfully. Please login with your new password."
            }), 200

        flash(_("password_changed_successfully_please_login_with_your_new_password"), "success")
        return redirect(url_for("login_page"))

    except Exception as e:
        db.session.rollback()
        logger.exception(f"Change password error: {e}")
        if request.is_json:
            return failure_response("An internal error occurred. Please try again later.", 500)
        flash(_("an_error_occurred_please_try_again"), "danger")
        return redirect(url_for("auth.change_password"))
