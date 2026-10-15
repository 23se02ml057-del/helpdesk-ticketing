import os
import logging

# Fix OpenBLAS memory allocation issue on Windows
os.environ['OPENBLAS_NUM_THREADS'] = '1'
os.environ['MKL_NUM_THREADS'] = '1'
os.environ['NUMEXPR_NUM_THREADS'] = '1'
os.environ['OMP_NUM_THREADS'] = '1'

from dotenv import load_dotenv
load_dotenv()

from flask import Flask, flash, redirect, render_template, request, session, jsonify, url_for, g
from config import Config
from help_db import db
from routes.auth import auth_bp
from flask_jwt_extended import JWTManager
from flask_jwt_extended import get_jwt_identity, verify_jwt_in_request, jwt_required
from flask_wtf.csrf import CSRFProtect
from flask_babel import Babel, gettext as _
import os
import logging
from sqlalchemy.exc import OperationalError, SQLAlchemyError
from sqlalchemy import text
from routes.users import users_bp
from routes.tickets import tickets_bp
from routes.support_agent import support_agent_bp
from routes.support_manager import support_manager_bp
from routes.admin import admin_bp
from routes.contact import contact_bp
from routes.settings import settings_bp
from routes.customer import customer_bp
from routes.departments import departments_bp
from routes.roles import roles_bp
from routes.categories import categories_bp
from routes.priorities import priorities_bp
from routes.issue_types import issue_types_bp
from routes.sla_rules import sla_rules_bp
from routes.escalations import escalations_bp
from routes.notifications import notifications_bp
from routes.reports import reports_bp
from routes.uploads import uploads_bp
from routes.customers import customers_bp
from routes.skills import skills_bp
from routes.super_admin import super_admin_bp
from routes.ticket_assignment import ticket_assignment_bp
from routes.ticket_status import ticket_status_bp
from routes.ai import ai_bp
from routes.chatbot import chatbot_bp
from routes.email import email_bp
from flask_socketio import SocketIO
from utils.socket_events import init_socketio

logger = logging.getLogger(__name__)

app = Flask(__name__)

# Load Config
app.config.from_object(Config)

# Flask-Babel Configuration
app.config['BABEL_DEFAULT_LOCALE'] = 'en'
app.config['BABEL_TRANSLATION_DIRECTORIES'] = 'translations'
SUPPORTED_LOCALES = ['en', 'zh', 'de', 'fr', 'tr', 'gu']
babel = Babel(app)

def get_locale():
    # Priority: 1. Session, 2. Cookie, 3. Browser accept_languages, 4. Default
    locale = session.get('locale')
    if locale and locale in SUPPORTED_LOCALES:
        return locale
    locale = request.cookies.get('locale')
    if locale and locale in SUPPORTED_LOCALES:
        return locale
    return request.accept_languages.best_match(SUPPORTED_LOCALES) or 'en'

babel.init_app(app, locale_selector=get_locale)

@app.route('/set-language/<locale>')
def set_language(locale):
    if locale in SUPPORTED_LOCALES:
        session['locale'] = locale
    response = redirect(request.referrer or url_for('dashboard'))
    if locale in SUPPORTED_LOCALES:
        response.set_cookie('locale', locale, max_age=60*60*24*365)
    return response

@app.context_processor
def inject_locale():
    return {
        'current_locale': session.get('locale', 'en'),
        'supported_locales': SUPPORTED_LOCALES
    }

@app.context_processor
def inject_nav_data():
    user_id = session.get("user_id")
    if user_id:
        user_data = db.session.execute(
            text("""
                SELECT 
                    (SELECT COUNT(*) FROM notifications WHERE user_id = :user_id AND is_read = FALSE) as unread_count,
                    profile_image
                FROM users 
                WHERE user_id = :user_id
            """),
            {"user_id": user_id}
        ).fetchone()
        if user_data:
            return dict(unread_count=user_data.unread_count, nav_profile_image=user_data.profile_image)
    return dict(unread_count=0, nav_profile_image=None)

# Register get_locale as Jinja global for templates
app.jinja_env.globals['get_locale'] = get_locale

# Register database value translation functions as Jinja globals
from utils import translations
app.jinja_env.globals['translate_value'] = translations.translate_value
app.jinja_env.globals['translate_status'] = translations.translate_status
app.jinja_env.globals['translate_priority'] = translations.translate_priority
app.jinja_env.globals['translate_category'] = translations.translate_category
app.jinja_env.globals['translate_department'] = translations.translate_department
app.jinja_env.globals['translate_role'] = translations.translate_role
app.jinja_env.globals['translate_role_description'] = translations.translate_role_description
app.jinja_env.globals['translate_skill'] = translations.translate_skill
app.jinja_env.globals['translate_user_status'] = translations.translate_user_status
app.jinja_env.globals['translate_ai_confidence'] = translations.translate_ai_confidence

# JWT
app.config["JWT_SECRET_KEY"] = os.getenv("JWT_SECRET_KEY", Config.JWT_SECRET_KEY)

# DB Init
db.init_app(app)

# JWT Init
jwt = JWTManager(app)

# CSRF Protection
csrf = CSRFProtect(app)

# Exempt public auth endpoints from CSRF
# These endpoints must be accessible without an existing session/CSRF token
csrf.exempt(auth_bp)
csrf.exempt(email_bp)

# Socket.IO Init
socketio = init_socketio(app)

# Ensure email inbound log table exists
with app.app_context():
    try:
        db.session.execute(text("""
            CREATE TABLE IF NOT EXISTS email_inbound_log (
                log_id SERIAL PRIMARY KEY,
                message_id VARCHAR(255),
                ticket_id INTEGER,
                sender_email VARCHAR(255),
                dedup_hash VARCHAR(64) UNIQUE,
                action_taken VARCHAR(100),
                processed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """))
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        logger.error("Failed to create email_inbound_log table: %s", e)

    try:
        db.session.execute(text("""
            CREATE TABLE IF NOT EXISTS ticket_escalations (
                escalation_id SERIAL PRIMARY KEY,
                ticket_id INTEGER,
                escalated_by INTEGER,
                escalated_to INTEGER,
                reason TEXT,
                status VARCHAR(50),
                escalated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """))
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        logger.error("Failed to create ticket_escalations table: %s", e)

    try:
        db.session.execute(text("""
            CREATE TABLE IF NOT EXISTS email_verification_tokens (
                id SERIAL PRIMARY KEY,
                user_id INTEGER,
                token_hash VARCHAR(255),
                expires_at TIMESTAMP,
                used_at TIMESTAMP,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """))
        db.session.execute(text("""
            CREATE INDEX IF NOT EXISTS idx_email_verification_tokens_user_id
            ON email_verification_tokens(user_id)
        """))
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        logger.error("Failed to create email_verification_tokens table: %s", e)

    try:
        db.session.execute(text("""
            CREATE TABLE IF NOT EXISTS ticket_attachments (
                attachment_id SERIAL PRIMARY KEY,
                ticket_id INTEGER REFERENCES tickets(ticket_id) ON DELETE CASCADE,
                file_name VARCHAR(255),
                file_path VARCHAR(500),
                uploaded_by INTEGER REFERENCES users(user_id),
                uploaded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """))
        db.session.execute(text("""
            CREATE INDEX IF NOT EXISTS idx_ticket_attachments_ticket_id
            ON ticket_attachments(ticket_id)
        """))
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        logger.error("Failed to create ticket_attachments table: %s", e)

    try:
        col_result = db.session.execute(text("""
            SELECT column_name FROM information_schema.columns
            WHERE table_name = 'departments' AND column_name = 'status'
        """)).fetchone()
        if not col_result:
            db.session.execute(text("ALTER TABLE departments ADD COLUMN status VARCHAR(50) DEFAULT 'Active'"))
            db.session.commit()
    except Exception as e:
        db.session.rollback()
        logger.error("Failed to add status column to departments: %s", e)

    try:
        col_result = db.session.execute(text("""
            SELECT column_name FROM information_schema.columns
            WHERE table_name = 'users' AND column_name = 'email_verified'
        """)).fetchone()
        if not col_result:
            db.session.execute(text("ALTER TABLE users ADD COLUMN email_verified BOOLEAN DEFAULT FALSE"))
            db.session.commit()
    except Exception as e:
        db.session.rollback()
        logger.error("Failed to add email_verified column: %s", e)

    try:
        col_result = db.session.execute(text("""
            SELECT column_name FROM information_schema.columns
            WHERE table_name = 'escalations' AND column_name = 'response_time'
        """)).fetchone()
        if not col_result:
            db.session.execute(text("ALTER TABLE escalations ADD COLUMN response_time INTEGER"))
            db.session.commit()
    except Exception as e:
        db.session.rollback()
        logger.error("Failed to add response_time column to escalations: %s", e)

    try:
        db.session.execute(text("""
            CREATE TABLE IF NOT EXISTS agent_reports (
                report_id SERIAL PRIMARY KEY,
                agent_id INTEGER REFERENCES users(user_id) ON DELETE SET NULL,
                report_period_start TIMESTAMP,
                report_period_end TIMESTAMP,
                total_tickets INTEGER DEFAULT 0,
                resolved_tickets INTEGER DEFAULT 0,
                closed_tickets INTEGER DEFAULT 0,
                pending_tickets INTEGER DEFAULT 0,
                in_progress_tickets INTEGER DEFAULT 0,
                new_tickets INTEGER DEFAULT 0,
                on_hold_tickets INTEGER DEFAULT 0,
                reopened_tickets INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """))
        db.session.execute(text("""
            CREATE UNIQUE INDEX IF NOT EXISTS uq_agent_report_period
            ON agent_reports(agent_id, report_period_start)
        """))
        db.session.execute(text("""
            CREATE INDEX IF NOT EXISTS idx_agent_reports_agent_id
            ON agent_reports(agent_id)
        """))
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        logger.error("Failed to create agent_reports table: %s", e)


@jwt.unauthorized_loader
def unauthorized_callback(err):
    return jsonify({
        "error": "Missing Authorization Header",
        "details": err
    }), 401

@jwt.invalid_token_loader
def invalid_token_callback(err):
    return jsonify({
        "error": "Invalid Token",
        "details": err
    }), 401

@jwt.expired_token_loader
def expired_callback(jwt_header, jwt_payload):
    return jsonify({
        "error": "Token Expired"
    }), 401

# Home Route
@app.route('/')
def home():
    return "Help Desk Running Successfully"

@app.route('/favicon.ico')
def favicon():
    return app.send_static_file('favicon.svg')

@app.errorhandler(404)
def handle_404(e):
    request_path = request.path.lower()
    image_extensions = ('.png', '.jpg', '.jpeg', '.gif', '.svg', '.webp', '.ico')
    if any(request_path.endswith(ext) for ext in image_extensions):
        return "", 204
    return render_template("error_404.html"), 404


@app.errorhandler(500)
def handle_500(e):
    logger.error("Internal server error: %s", str(e))
    return render_template("error_500.html"), 500

PUBLIC_PREFIXES = (
    '/login',
    '/register',
    '/forgot-password',
    '/reset-password/',
    '/resend-verification',
    '/verify-customer/',
    '/verify-customer',
    '/auth/',
    '/static/',
    '/socket.io/',
    '/contact',
    '/health',
    '/api/email/brevo/inbound',
)

@app.before_request
def require_login():
    path = request.path
    if path == '/api/tickets/search':
        return None
    for prefix in PUBLIC_PREFIXES:
        if path == prefix or path.startswith(prefix):
            return None
    if not session.get('user_id'):
        return redirect(url_for('login_page'))
    return None

# Login Page
@app.route('/login')
def login_page():
    return render_template("login.html")

@app.route('/register')
def register_page():
    return render_template("register.html")

# forgot Password Page
@app.route('/forgot-password')
def forgot_password_page():
    return render_template(
        'forgot_password.html'
    )

# Resend Verification Page
@app.route('/resend-verification')
def resend_verification_page():
    return render_template('resend_verification.html')


# reset Password Page
@app.route('/reset-password/<token>')
def reset_password_page(token):
    return render_template(
        'reset_password.html'
    )


#### Dashboard Route
@app.route("/dashboard")
def dashboard():
    role_id = session.get("role_id")
    if role_id == 1:
        return redirect(url_for("super_admin.super_admin_dashboard"))
    elif role_id == 2:
        return redirect(url_for("support_manager.dashboard"))
    elif role_id == 3:
        return redirect(url_for("support_agent.dashboard"))
    elif role_id == 5:
        return redirect(url_for("admin.dashboard"))
    else:
        return redirect(url_for("customer.dashboard"))

# Support Manager Dashboard
@app.route('/support_manager_dashboard')
def support_manager_dashboard():
    return redirect(url_for("support_manager.dashboard"))

@app.route('/admin-dashboard')
def admin_dashboard():
    return redirect(url_for("admin.dashboard"))

@app.route('/logout')
def logout():
    session.clear()
    return redirect('/login')


# Blueprints

app.register_blueprint(
    users_bp,
    url_prefix="/users"
)

app.register_blueprint(
    auth_bp,
    url_prefix='/auth'
)

app.register_blueprint(
    tickets_bp,
    url_prefix=''
)

app.register_blueprint(
    support_manager_bp,
    url_prefix="/support_manager"
)

app.register_blueprint(
    admin_bp,
    url_prefix="/admin"
)

app.register_blueprint(
    contact_bp,
    url_prefix=""
)

app.register_blueprint(
    support_agent_bp,
    url_prefix="/support_agent"
)

app.register_blueprint(
    customer_bp,
    url_prefix=""
)

app.register_blueprint(
    settings_bp,
    url_prefix=""
)

app.register_blueprint(
    departments_bp,
    url_prefix=""
)

app.register_blueprint(
    roles_bp,
    url_prefix=""
)

app.register_blueprint(
    categories_bp,
    url_prefix=""
)

app.register_blueprint(
    issue_types_bp,
    url_prefix=""
)

app.register_blueprint(
    priorities_bp,
    url_prefix=""
)

app.register_blueprint(
    ticket_status_bp,
    url_prefix=""
)

app.register_blueprint(
    sla_rules_bp,
    url_prefix=""
)

app.register_blueprint(
    escalations_bp,
    url_prefix=""
)

app.register_blueprint(
    notifications_bp,
    url_prefix=""
)

app.register_blueprint(
    reports_bp,
    url_prefix=""
)

app.register_blueprint(
    uploads_bp,
    url_prefix=""
)

app.register_blueprint(
    customers_bp,
    url_prefix=""
)

app.register_blueprint(
    super_admin_bp,
    url_prefix=""
)

app.register_blueprint(
    skills_bp,
    url_prefix=""
)

app.register_blueprint(
    ticket_assignment_bp,
    url_prefix=""
)

app.register_blueprint(
    ai_bp,
    url_prefix=''
)

app.register_blueprint(
    chatbot_bp,
    url_prefix=''
)

app.register_blueprint(
    email_bp,
    url_prefix=''
)


@app.route('/health')
def health_check():
    try:
        db.session.execute(text("SELECT 1"))
        return jsonify({
            "status": "healthy",
            "database": "connected"
        }), 200
    except OperationalError as e:
        logger.error("Database health check failed: %s", str(e))
        return jsonify({
            "status": "unhealthy",
            "database": "disconnected",
            "message": "PostgreSQL is not reachable or is in recovery mode. Please ensure the database server is running and recovered."
        }), 503
    except Exception as e:
        logger.error("Health check error: %s", str(e))
        return jsonify({
            "status": "unhealthy",
            "database": "error",
            "message": "An unexpected error occurred during database connectivity check."
        }), 503


@app.errorhandler(OperationalError)
def handle_db_operational_error(e):
    logger.error("Database operational error: %s", str(e))
    return jsonify({
        "success": False,
        "message": "Database connection error. Please ensure PostgreSQL is running and try again.",
        "details": "The application cannot connect to the database at this time."
    }), 503


@app.errorhandler(SQLAlchemyError)
def handle_db_error(e):
    logger.error("Database error: %s", str(e))
    return jsonify({
        "success": False,
        "message": "A database error occurred. Please try again later.",
        "details": "If the problem persists, contact the system administrator."
    }), 500


@app.after_request
def add_security_headers(response):
    response.headers['X-Content-Type-Options'] = 'nosniff'
    response.headers['X-Frame-Options'] = 'DENY'
    response.headers['X-XSS-Protection'] = '1; mode=block'
    response.headers['Referrer-Policy'] = 'strict-origin-when-cross-origin'
    response.headers['Permissions-Policy'] = 'geolocation=(), microphone=(), camera=()'
    return response


if __name__ == "__main__":
    socketio.run(app, debug=True)
