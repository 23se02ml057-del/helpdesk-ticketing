from datetime import datetime
from help_db import db
from werkzeug.security import generate_password_hash, check_password_hash


class User(db.Model):
    __tablename__ = "users"

    user_id = db.Column(db.Integer, primary_key=True)
    first_name = db.Column(db.String(100), nullable=True)
    last_name = db.Column(db.String(100), nullable=True)
    email = db.Column(db.String(255), unique=True, nullable=True)
    mobile = db.Column(db.String(20), unique=True, nullable=True)
    password_hash = db.Column(db.String(255), nullable=True)
    department_id = db.Column(db.Integer, nullable=True)
    role_id = db.Column(db.Integer, nullable=True)
    status = db.Column(db.String(50), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    last_login = db.Column(db.DateTime, nullable=True)
    profile_image = db.Column(db.String(255), nullable=True)
    email_verified = db.Column(db.Boolean, default=False, nullable=False)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)


class Department(db.Model):
    __tablename__ = "departments"

    department_id = db.Column(db.Integer, primary_key=True)
    department_name = db.Column(db.String(100), nullable=True)
    description = db.Column(db.Text, nullable=True)
    status = db.Column(db.String(50), nullable=True, default="Active")
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class Category(db.Model):
    __tablename__ = "categories"

    category_id = db.Column(db.Integer, primary_key=True)
    category_name = db.Column(db.String(100), unique=True, nullable=False)
    description = db.Column(db.Text, nullable=True)
    status = db.Column(db.String(50), nullable=True, default="Active")
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class Skill(db.Model):
    __tablename__ = "skills"

    skill_id = db.Column(db.Integer, primary_key=True)
    skill_name = db.Column(db.String(100), nullable=False)
    category = db.Column(db.String(100), nullable=True)
    department_id = db.Column(db.Integer, db.ForeignKey("departments.department_id"), nullable=True)
    status = db.Column(db.String(50), nullable=True, default="Active")
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class Priority(db.Model):
    __tablename__ = "priorities"

    priority_id = db.Column(db.Integer, primary_key=True)
    priority_name = db.Column(db.String(50), unique=True, nullable=False)
    description = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class TicketStatus(db.Model):
    __tablename__ = "ticket_status"

    status_id = db.Column(db.Integer, primary_key=True)
    status_name = db.Column(db.String(50), unique=True, nullable=False)


class Ticket(db.Model):
    __tablename__ = "tickets"

    ticket_id = db.Column(db.Integer, primary_key=True)
    ticket_number = db.Column(db.String(30), unique=True, nullable=True)
    title = db.Column(db.String(255), nullable=True)
    description = db.Column(db.Text, nullable=True)
    category_name = db.Column(db.String(100), db.ForeignKey("categories.category_name"), nullable=True)
    priority_name = db.Column(db.String(50), db.ForeignKey("priorities.priority_name"), nullable=True)
    status_name = db.Column(db.String(50), db.ForeignKey("ticket_status.status_name"), nullable=True)
    requester_id = db.Column(db.Integer, db.ForeignKey("users.user_id"), nullable=True)
    assigned_to = db.Column(db.Integer, db.ForeignKey("users.user_id"), nullable=True)
    department_id = db.Column(db.Integer, db.ForeignKey("departments.department_id"), nullable=True)
    source = db.Column(db.String(50), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, nullable=True)
    assigned_at = db.Column(db.DateTime, nullable=True)
    due_date = db.Column(db.DateTime, nullable=True)
    resolved_at = db.Column(db.DateTime, nullable=True)
    rating = db.Column(db.Integer, nullable=True)
    reopen_count = db.Column(db.Integer, default=0)
    ai_summary = db.Column(db.Text, nullable=True)
    ai_suggested_priority = db.Column(db.String(50), nullable=True)
    ai_suggested_category = db.Column(db.String(100), nullable=True)
    ai_suggested_reply = db.Column(db.Text, nullable=True)
    ai_sentiment = db.Column(db.String(50), nullable=True)
    ai_suggested_department = db.Column(db.String(100), nullable=True)
    ai_suggested_agent = db.Column(db.Integer, nullable=True)
    ai_confidence = db.Column(db.String(50), nullable=True)
    ai_correction_type = db.Column(db.String(50), nullable=True)
    needs_manual_review = db.Column(db.Boolean, nullable=True)
    issue_type_id = db.Column(db.Integer, nullable=True)
    assignment_history_id = db.Column(db.Integer, nullable=True)

    requester = db.relationship("User", foreign_keys=[requester_id], backref="requested_tickets")
    assignee = db.relationship("User", foreign_keys=[assigned_to], backref="assigned_tickets")
    department = db.relationship("Department", backref="tickets")
    category = db.relationship("Category", backref="tickets")
    priority = db.relationship("Priority", backref="tickets")
    status = db.relationship("TicketStatus", backref="tickets")


class TicketAssignment(db.Model):
    __tablename__ = "ticket_assignments"

    assignment_id = db.Column(db.Integer, primary_key=True)
    ticket_id = db.Column(db.Integer, db.ForeignKey("tickets.ticket_id"), nullable=True)
    assigned_to = db.Column(db.Integer, db.ForeignKey("users.user_id"), nullable=True)
    assigned_by = db.Column(db.Integer, db.ForeignKey("users.user_id"), nullable=True)
    assigned_date = db.Column(db.DateTime, default=datetime.utcnow)


class TicketAssignmentHistory(db.Model):
    __tablename__ = "ticket_assignment_history"

    history_id = db.Column(db.Integer, primary_key=True)
    ticket_id = db.Column(db.Integer, db.ForeignKey("tickets.ticket_id"), nullable=True)
    agent_id = db.Column(db.Integer, db.ForeignKey("users.user_id"), nullable=True)
    department_id = db.Column(db.Integer, nullable=True)
    category_id = db.Column(db.Integer, nullable=True)
    matched_skill_id = db.Column(db.Integer, nullable=True)
    match_score = db.Column(db.Integer, nullable=True)
    assignment_reason = db.Column(db.Text, nullable=True)
    assigned_at = db.Column(db.DateTime, default=datetime.utcnow)


class TicketComment(db.Model):
    __tablename__ = "ticket_comments"

    comment_id = db.Column(db.Integer, primary_key=True)
    ticket_id = db.Column(db.Integer, db.ForeignKey("tickets.ticket_id"), nullable=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.user_id"), nullable=True)
    comment_text = db.Column(db.Text, nullable=True)
    is_internal = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class Notification(db.Model):
    __tablename__ = "notifications"

    notification_id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.user_id"), nullable=True)
    ticket_id = db.Column(db.Integer, db.ForeignKey("tickets.ticket_id"), nullable=True)
    title = db.Column(db.String(255), nullable=True)
    message = db.Column(db.Text, nullable=True)
    is_read = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class SLARule(db.Model):
    __tablename__ = "sla_rules"

    sla_id = db.Column(db.Integer, primary_key=True)
    priority_id = db.Column(db.Integer, nullable=True)
    response_time = db.Column(db.Integer, nullable=True)
    resolution_time = db.Column(db.Integer, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    status = db.Column(db.String(50), nullable=True)
    category_name = db.Column(db.String(100), nullable=True)


class EscalationRule(db.Model):
    __tablename__ = "escalations"

    escalation_id = db.Column(db.Integer, primary_key=True)
    priority_id = db.Column(db.Integer, nullable=True)
    response_time = db.Column(db.Integer, nullable=True)
    escalation_after = db.Column(db.Integer, nullable=True)
    notify_role = db.Column(db.String(50), nullable=True)
    status = db.Column(db.String(50), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class TicketEscalation(db.Model):
    __tablename__ = "ticket_escalations"

    escalation_id = db.Column(db.Integer, primary_key=True)
    ticket_id = db.Column(db.Integer, db.ForeignKey("tickets.ticket_id"), nullable=True)
    escalated_by = db.Column(db.Integer, db.ForeignKey("users.user_id"), nullable=True)
    escalated_to = db.Column(db.Integer, db.ForeignKey("users.user_id"), nullable=True)
    reason = db.Column(db.Text, nullable=True)
    status = db.Column(db.String(50), nullable=True)
    escalated_at = db.Column(db.DateTime, default=datetime.utcnow)


class TicketStatusHistory(db.Model):
    __tablename__ = "ticket_status_history"

    history_id = db.Column(db.Integer, primary_key=True)
    ticket_id = db.Column(db.Integer, db.ForeignKey("tickets.ticket_id"), nullable=True)
    old_status = db.Column(db.String(50), nullable=True)
    new_status = db.Column(db.String(50), nullable=True)
    changed_by = db.Column(db.Integer, db.ForeignKey("users.user_id"), nullable=True)
    changed_at = db.Column(db.DateTime, default=datetime.utcnow)


class CustomerFeedback(db.Model):
    __tablename__ = "customer_feedback"

    feedback_id = db.Column(db.Integer, primary_key=True)
    ticket_id = db.Column(db.Integer, db.ForeignKey("tickets.ticket_id"), nullable=True)
    rating = db.Column(db.Integer, nullable=True)
    feedback_text = db.Column(db.Text, nullable=True)
    submitted_at = db.Column(db.DateTime, default=datetime.utcnow)


class AuditLog(db.Model):
    __tablename__ = "audit_logs"

    audit_id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.user_id"), nullable=True)
    action = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class ChatHistory(db.Model):
    __tablename__ = "chat_history"

    chat_id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.user_id"), nullable=True)
    role = db.Column(db.String(20), nullable=False)
    message = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    user = db.relationship("User", backref="chat_messages")


class PasswordResetToken(db.Model):
    __tablename__ = "password_reset_tokens"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.user_id"), nullable=True)
    token = db.Column(db.String(255), nullable=True)
    expires_at = db.Column(db.DateTime, nullable=True)
    used = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class Setting(db.Model):
    __tablename__ = "settings"

    setting_id = db.Column(db.Integer, primary_key=True)
    company_name = db.Column(db.String(255), nullable=True)
    company_email = db.Column(db.String(255), nullable=True)
    company_phone = db.Column(db.String(50), nullable=True)
    company_address = db.Column(db.Text, nullable=True)
    smtp_server = db.Column(db.String(255), nullable=True)
    smtp_port = db.Column(db.Integer, nullable=True)
    smtp_username = db.Column(db.String(255), nullable=True)
    smtp_password = db.Column(db.String(255), nullable=True)
    smtp_use_tls = db.Column(db.Boolean, default=True)
    default_priority = db.Column(db.String(50), nullable=True)
    auto_assign_tickets = db.Column(db.Boolean, default=False)
    items_per_page = db.Column(db.Integer, default=10)
    timezone = db.Column(db.String(50), default="UTC")
    updated_at = db.Column(db.DateTime, default=datetime.utcnow)


class AgentSkill(db.Model):
    __tablename__ = "agent_skills"

    agent_skill_id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.user_id"), nullable=True)
    skill_id = db.Column(db.Integer, db.ForeignKey("skills.skill_id"), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class UserCategory(db.Model):
    __tablename__ = "user_categories"

    user_id = db.Column(db.Integer, db.ForeignKey("users.user_id"), nullable=True)
    category_name = db.Column(db.String(100), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    __table_args__ = (
        db.PrimaryKeyConstraint('user_id', 'category_name'),
    )


class IssueType(db.Model):
    __tablename__ = "issue_types"

    issue_type_id = db.Column(db.Integer, primary_key=True)
    issue_name = db.Column(db.String(100), nullable=True)
    category_name = db.Column(db.String(100), nullable=True)
    description = db.Column(db.Text, nullable=True)
    status = db.Column(db.String(50), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, nullable=True)


class Lead(db.Model):
    __tablename__ = "leads"

    lead_id = db.Column(db.Integer, primary_key=True)
    company_name = db.Column(db.String(255), nullable=True)
    contact_person = db.Column(db.String(100), nullable=True)
    email = db.Column(db.String(255), nullable=True)
    phone = db.Column(db.String(20), nullable=True)
    inquiry_details = db.Column(db.Text, nullable=True)
    assigned_sales_exec = db.Column(db.String(100), nullable=True)
    lead_status = db.Column(db.String(50), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class Role(db.Model):
    __tablename__ = "roles"

    role_id = db.Column(db.Integer, primary_key=True)
    role_name = db.Column(db.String(50), unique=True, nullable=False)
    description = db.Column(db.Text, nullable=True)


class TicketAttachment(db.Model):
    __tablename__ = "ticket_attachments"

    attachment_id = db.Column(db.Integer, primary_key=True)
    ticket_id = db.Column(db.Integer, db.ForeignKey("tickets.ticket_id"), nullable=True)
    file_name = db.Column(db.String(255), nullable=True)
    file_path = db.Column(db.String(500), nullable=True)
    uploaded_by = db.Column(db.Integer, db.ForeignKey("users.user_id"), nullable=True)
    uploaded_at = db.Column(db.DateTime, default=datetime.utcnow)


class TicketMLPrediction(db.Model):
    __tablename__ = "ticket_ml_predictions"

    prediction_id = db.Column(db.Integer, primary_key=True)
    ticket_id = db.Column(db.Integer, db.ForeignKey("tickets.ticket_id"), nullable=True)
    model_version = db.Column(db.String(50), nullable=True)
    predicted_resolution_minutes = db.Column(db.Integer, nullable=True)
    prediction_lower_minutes = db.Column(db.Integer, nullable=True)
    prediction_upper_minutes = db.Column(db.Integer, nullable=True)
    prediction_status = db.Column(db.String(50), nullable=True)
    prediction_created_at = db.Column(db.DateTime, default=datetime.utcnow)
    actual_resolution_minutes = db.Column(db.Integer, nullable=True)
    prediction_error_minutes = db.Column(db.Integer, nullable=True)


class EmailInboundLog(db.Model):
    __tablename__ = "email_inbound_log"

    log_id = db.Column(db.Integer, primary_key=True)
    message_id = db.Column(db.String(255), nullable=True)
    ticket_id = db.Column(db.Integer, nullable=True)
    sender_email = db.Column(db.String(255), nullable=True)
    dedup_hash = db.Column(db.String(64), unique=True, nullable=True)
    action_taken = db.Column(db.String(100), nullable=True)
    processed_at = db.Column(db.DateTime, default=datetime.utcnow)


class AgentReport(db.Model):
    __tablename__ = "agent_reports"

    report_id = db.Column(db.Integer, primary_key=True)
    agent_id = db.Column(db.Integer, db.ForeignKey("users.user_id"), nullable=True)
    report_period_start = db.Column(db.DateTime, nullable=True)
    report_period_end = db.Column(db.DateTime, nullable=True)
    total_tickets = db.Column(db.Integer, default=0)
    resolved_tickets = db.Column(db.Integer, default=0)
    closed_tickets = db.Column(db.Integer, default=0)
    pending_tickets = db.Column(db.Integer, default=0)
    in_progress_tickets = db.Column(db.Integer, default=0)
    new_tickets = db.Column(db.Integer, default=0)
    on_hold_tickets = db.Column(db.Integer, default=0)
    reopened_tickets = db.Column(db.Integer, default=0)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class EmailVerificationToken(db.Model):
    __tablename__ = "email_verification_tokens"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.user_id"), nullable=True)
    token_hash = db.Column(db.String(255), nullable=True)
    expires_at = db.Column(db.DateTime, nullable=True)
    used_at = db.Column(db.DateTime, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
