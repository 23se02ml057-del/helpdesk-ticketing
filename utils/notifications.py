from help_db import db
from sqlalchemy import text
from datetime import datetime
import json

try:
    from utils.socket_events import emit_notification, emit_sla_breach, emit_ticket_status_change
except ImportError:
    emit_notification = None
    emit_sla_breach = None
    emit_ticket_status_change = None


def create_notification(user_id, title, message):
    """Create a notification for a specific user."""
    db.session.execute(
        text("""
            INSERT INTO notifications (user_id, title, message, is_read, created_at)
            VALUES (:user_id, :title, :message, FALSE, :created_at)
        """),
        {
            "user_id": user_id,
            "title": title,
            "message": message,
            "created_at": datetime.utcnow()
        }
    )
    db.session.commit()

    if emit_notification:
        emit_notification(user_id, title, message)


def notify_ticket_created(ticket_id, ticket_title, requester_id):
    """Notify assigned agent and managers when a new ticket is created."""
    ticket = db.session.execute(
        text("SELECT assigned_to FROM tickets WHERE ticket_id = :ticket_id"),
        {"ticket_id": ticket_id}
    ).fetchone()

    assigned_agent_id = ticket[0] if ticket else None

    message = f"New ticket #{ticket_id} - {ticket_title} has been created."

    if assigned_agent_id:
        create_notification(assigned_agent_id, "New Ticket Created", f"You have been assigned ticket #{ticket_id} - {ticket_title}.")

    managers = db.session.execute(
        text("SELECT user_id FROM users WHERE role_id = 2 AND status = 'Active'")
    ).fetchall()
    for manager in managers:
        create_notification(manager[0], "New Ticket Created", message)

    if requester_id:
        create_notification(
            requester_id,
            "Ticket Submitted",
            f"Your ticket #{ticket_id} - {ticket_title} has been submitted successfully."
        )


def notify_ticket_assigned(ticket_id, ticket_title, agent_id, requester_id):
    """Notify the assigned agent and requester when a ticket is assigned."""
    agent = db.session.execute(
        text("SELECT first_name, last_name FROM users WHERE user_id = :uid"),
        {"uid": agent_id}
    ).fetchone()

    agent_name = f"{agent[0]} {agent[1]}" if agent else "an agent"

    message = f"Ticket #{ticket_id} - {ticket_title} has been assigned to {agent_name}."
    create_notification(agent_id, "Ticket Assigned", f"You have been assigned ticket #{ticket_id} - {ticket_title}.")

    if requester_id:
        create_notification(
            requester_id,
            "Ticket Assigned",
            f"Your ticket #{ticket_id} has been assigned to {agent_name}."
        )

    managers = db.session.execute(
        text("SELECT user_id FROM users WHERE role_id = 2 AND status = 'Active'")
    ).fetchall()
    for manager in managers:
        create_notification(manager[0], "Ticket Assigned", message)


def notify_ticket_status_changed(ticket_id, ticket_title, new_status, requester_id):
    """Notify requester and assigned agent when ticket status changes."""
    message = f"Ticket #{ticket_id} - {ticket_title} status updated to {new_status}."

    if requester_id:
        create_notification(
            requester_id,
            "Status Updated",
            message
        )

    assigned_agent = db.session.execute(
        text("SELECT assigned_to FROM tickets WHERE ticket_id = :ticket_id"),
        {"ticket_id": ticket_id}
    ).fetchone()

    if assigned_agent and assigned_agent[0]:
        create_notification(
            assigned_agent[0],
            "Status Updated",
            message
        )

    if emit_ticket_status_change:
        emit_ticket_status_change(ticket_id, new_status, requester_id)


def calculate_due_date(priority_name, created_at):
    """Calculate SLA due date based on priority resolution time."""
    if not priority_name or not created_at:
        return None
    rule = db.session.execute(
        text("""
            SELECT resolution_time
            FROM sla_rules
            WHERE priority_id = (SELECT priority_id FROM priorities WHERE priority_name = :priority)
              AND status = 'Active'
            ORDER BY sla_id DESC
            LIMIT 1
        """),
        {"priority": priority_name}
    ).fetchone()
    if rule and rule[0]:
        from datetime import timedelta
        return created_at + timedelta(hours=rule[0])
    return None


def check_sla_breach(ticket_id):
    """Check if a ticket has breached its SLA and notify."""
    ticket = db.session.execute(
        text("""
            SELECT t.ticket_number, t.title, t.priority_name, t.created_at,
                   t.assigned_at, t.requester_id, t.assigned_to,
                   s.resolution_time
            FROM tickets t
            LEFT JOIN sla_rules s ON t.priority_name = (
                SELECT priority_name FROM priorities WHERE priority_id = s.priority_id
            ) AND s.status = 'Active'
            WHERE t.ticket_id = :ticket_id
        """),
        {"ticket_id": ticket_id}
    ).fetchone()

    if not ticket:
        return False

    if not ticket[7]:
        return False

    created_at = ticket[3]
    if not created_at:
        return False

    resolution_time_hours = ticket[7]
    due_date = datetime.utcnow()
    hours_since_created = (due_date - created_at).total_seconds() / 3600

    if hours_since_created > resolution_time_hours:
        if emit_sla_breach:
            emit_sla_breach(ticket_id, ticket[3], ticket[5])

        message = f"SLA Breach: Ticket {ticket[0]} - {ticket[1]} has exceeded SLA deadline."

        if ticket[5]:
            create_notification(ticket[5], "SLA Breach", message)

        if ticket[6]:
            create_notification(ticket[6], "SLA Breach", message)

        managers = db.session.execute(
            text("SELECT user_id FROM users WHERE role_id = 2 AND status = 'Active'")
        ).fetchall()
        for manager in managers:
            create_notification(manager[0], "SLA Breach", message)

        escalation = db.session.execute(
            text("""
                SELECT e.escalation_after, e.notify_role
                FROM escalations e
                WHERE e.priority_id = (SELECT priority_id FROM priorities WHERE priority_name = :priority)
                  AND e.status = 'Active'
            """),
            {"priority": ticket[2]}
        ).fetchone()

        if escalation:
            escalated_to = None
            if escalation[1] == "Support Manager":
                manager = db.session.execute(
                    text("SELECT user_id FROM users WHERE role_id = 2 AND status = 'Active' ORDER BY created_at ASC LIMIT 1")
                ).fetchone()
                if manager:
                    escalated_to = manager[0]
            elif escalation[1] == "Support Agent":
                agent = db.session.execute(
                    text("SELECT user_id FROM users WHERE role_id = 3 AND status = 'Active' ORDER BY created_at ASC LIMIT 1")
                ).fetchone()
                if agent:
                    escalated_to = agent[0]
            elif escalation[1] == "Super Admin":
                admin = db.session.execute(
                    text("SELECT user_id FROM users WHERE role_id = 1 AND status = 'Active' ORDER BY created_at ASC LIMIT 1")
                ).fetchone()
                if admin:
                    escalated_to = admin[0]

            db.session.execute(
                text("""
                    INSERT INTO ticket_escalations (ticket_id, escalated_by, escalated_to, reason, status)
                    VALUES (:ticket_id, :escalated_by, :escalated_to, :reason, 'Active')
                """),
                {
                    "ticket_id": ticket_id,
                    "escalated_by": ticket[5],
                    "escalated_to": escalated_to,
                    "reason": "SLA Breach - Automatic escalation"
                }
            )

            if escalated_to:
                create_notification(
                    escalated_to,
                    "Ticket Escalated",
                    f"Ticket {ticket[0]} - {ticket[1]} has been automatically escalated due to SLA breach."
                )

            db.session.execute(
                text("UPDATE tickets SET status_name = 'In Progress' WHERE ticket_id = :ticket_id"),
                {"ticket_id": ticket_id}
            )
            db.session.commit()

        return True

    return False


def auto_notify_on_event(event_type, **kwargs):
    """Generic event handler for auto-notifications on ticket events."""
    if event_type == "ticket_created":
        notify_ticket_created(
            kwargs.get("ticket_id"),
            kwargs.get("ticket_title"),
            kwargs.get("requester_id")
        )

    elif event_type == "ticket_assigned":
        notify_ticket_assigned(
            kwargs.get("ticket_id"),
            kwargs.get("ticket_title"),
            kwargs.get("agent_id"),
            kwargs.get("requester_id")
        )

    elif event_type == "status_changed":
        notify_ticket_status_changed(
            kwargs.get("ticket_id"),
            kwargs.get("ticket_title"),
            kwargs.get("new_status"),
            kwargs.get("requester_id")
        )

    elif event_type == "sla_check":
        check_sla_breach(kwargs.get("ticket_id"))
