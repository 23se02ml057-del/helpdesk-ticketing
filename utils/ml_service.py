"""
ML Service Integration Layer

Integrates ML prediction into the ticket creation workflow and provides
SLA breach risk calculation based on ML predictions.
"""

import logging
from datetime import datetime
from typing import Dict, Any, Optional

from help_db import db
from sqlalchemy import text

from ml.resolution_predictor import get_resolution_predictor
from utils.notifications import create_notification

logger = logging.getLogger(__name__)

SLA_RISK_THRESHOLDS = {
    "high": 1.0,
    "medium": 0.8,
    "low": 0.0,
}


def get_sla_resolution_time(priority_name: str) -> Optional[float]:
    try:
        result = db.session.execute(
            text("""
                SELECT s.resolution_time
                FROM sla_rules s
                JOIN priorities p ON s.priority_id = p.priority_id
                WHERE p.priority_name = :priority
                  AND s.status = 'Active'
            """),
            {"priority": priority_name}
        ).fetchone()
        if result and result[0] is not None:
            return float(result[0])
        return None
    except Exception as e:
        logger.error("Failed to fetch SLA resolution time: %s", str(e))
        return None


def calculate_sla_breach_risk(predicted_minutes: float, sla_resolution_hours: float) -> str:
    if predicted_minutes is None or sla_resolution_hours is None:
        return "unknown"
    sla_minutes = sla_resolution_hours * 60
    if sla_minutes <= 0:
        return "low"
    ratio = predicted_minutes / sla_minutes
    if ratio >= SLA_RISK_THRESHOLDS["high"]:
        return "high"
    elif ratio >= SLA_RISK_THRESHOLDS["medium"]:
        return "medium"
    else:
        return "low"


def store_prediction(ticket_id: int, prediction_result: Dict[str, Any]) -> Optional[int]:
    try:
        db.session.execute(text("""
            INSERT INTO ticket_ml_predictions (
                ticket_id, model_version, predicted_resolution_minutes,
                prediction_lower_minutes, prediction_upper_minutes,
                prediction_status, prediction_created_at
            ) VALUES (
                :ticket_id, :model_version, :predicted_minutes,
                :lower_minutes, :upper_minutes, :status, :created_at
            )
        """), {
            "ticket_id": ticket_id,
            "model_version": prediction_result.get("model_version", "none"),
            "predicted_minutes": prediction_result.get("predicted_minutes"),
            "lower_minutes": prediction_result.get("lower_bound_minutes"),
            "upper_minutes": prediction_result.get("upper_bound_minutes"),
            "status": "success" if prediction_result.get("success") else "unavailable",
            "created_at": datetime.utcnow()
        })
        db.session.commit()
        
        pred_id = db.session.execute(
            text("SELECT MAX(prediction_id) FROM ticket_ml_predictions WHERE ticket_id = :tid"),
            {"tid": ticket_id}
        ).scalar()
        return pred_id
    except Exception as e:
        logger.error("Failed to store ML prediction for ticket %d: %s", ticket_id, str(e))
        db.session.rollback()
        return None


def get_prediction_for_ticket(ticket_id: int) -> Optional[Dict[str, Any]]:
    try:
        result = db.session.execute(text("""
            SELECT
                prediction_id, ticket_id, model_version,
                predicted_resolution_minutes,
                prediction_lower_minutes,
                prediction_upper_minutes,
                prediction_status,
                prediction_created_at,
                actual_resolution_minutes,
                prediction_error_minutes
            FROM ticket_ml_predictions
            WHERE ticket_id = :ticket_id
            ORDER BY prediction_created_at DESC
            LIMIT 1
        """), {"ticket_id": ticket_id}).fetchone()
        
        if not result:
            return None

        predicted = float(result[3]) if result[3] else None

        sla_breach_risk = "unknown"
        try:
            sla_hours = get_sla_resolution_time_from_ticket(ticket_id)
            if predicted is not None and sla_hours is not None:
                sla_breach_risk = calculate_sla_breach_risk(predicted, sla_hours)
        except Exception:
            pass

        return {
            "prediction_id": result[0],
            "ticket_id": result[1],
            "model_version": result[2],
            "predicted_resolution_minutes": predicted,
            "prediction_lower_minutes": result[4],
            "prediction_upper_minutes": result[5],
            "lower_bound_minutes": result[4],
            "upper_bound_minutes": result[5],
            "prediction_status": result[6],
            "prediction_created_at": result[7],
            "actual_resolution_minutes": result[8],
            "prediction_error_minutes": result[9],
            "sla_breach_risk": sla_breach_risk,
        }
    except Exception as e:
        logger.error("Failed to fetch ML prediction: %s", str(e))
        return None


def get_sla_resolution_time_from_ticket(ticket_id: int) -> Optional[float]:
    try:
        result = db.session.execute(text("""
            SELECT s.resolution_time
            FROM tickets t
            LEFT JOIN sla_rules s ON t.priority_name = (
                SELECT p.priority_name FROM priorities p WHERE p.priority_id = s.priority_id
            ) AND s.status = 'Active'
            WHERE t.ticket_id = :ticket_id
        """), {"ticket_id": ticket_id}).fetchone()
        if result and result[0] is not None:
            return float(result[0])
        return None
    except Exception:
        return None


def get_sla_info_for_ticket(ticket_id: int) -> Dict[str, Any]:
    try:
        result = db.session.execute(text("""
            SELECT
                t.priority_name,
                t.created_at,
                t.resolved_at,
                s.resolution_time,
                s.response_time
            FROM tickets t
            LEFT JOIN sla_rules s ON t.priority_name = (
                SELECT p.priority_name FROM priorities p WHERE p.priority_id = s.priority_id
            ) AND s.status = 'Active'
            WHERE t.ticket_id = :ticket_id
        """), {"ticket_id": ticket_id}).fetchone()
        
        if not result:
            return {}
        sla_resolution_hours = float(result[3]) if result[3] else None
        sla_response_hours = float(result[4]) if result[4] else None
        return {
            "priority_name": result[0],
            "created_at": result[1],
            "resolved_at": result[2],
            "sla_resolution_hours": sla_resolution_hours,
            "sla_response_hours": sla_response_hours,
        }
    except Exception as e:
        logger.error("Failed to fetch SLA info for ticket %d: %s", ticket_id, str(e))
        return {}


def update_actual_resolution(ticket_id: int, resolved_at, created_at) -> bool:
    try:
        actual_minutes = (resolved_at - created_at).total_seconds() / 60.0
        db.session.execute(text("""
            UPDATE ticket_ml_predictions
            SET actual_resolution_minutes = :actual_minutes,
                prediction_error_minutes = ABS(predicted_resolution_minutes - :actual_minutes)
            WHERE ticket_id = :ticket_id
              AND prediction_status = 'success'
              AND actual_resolution_minutes IS NULL
        """), {
            "actual_minutes": actual_minutes,
            "ticket_id": ticket_id
        })
        db.session.commit()
        return True
    except Exception as e:
        logger.error("Failed to update actual resolution for ticket %d: %s", ticket_id, str(e))
        db.session.rollback()
        return False


def notify_sla_risk_alert(ticket_id: int, ticket_number: str, title: str,
                          predicted_minutes: float, sla_hours: float, risk_level: str):
    """Send SLA breach risk notification for high-risk tickets."""
    try:
        requester_result = db.session.execute(
            text("SELECT requester_id FROM tickets WHERE ticket_id = :tid"),
            {"tid": ticket_id}
        ).fetchone()
        requester_id = requester_result[0] if requester_result else None
        
        message = (
            f"SLA Risk Alert (ML): Ticket #{ticket_number} - {title}\n"
            f"ML Estimate: {_format_minutes(predicted_minutes)}\n"
            f"SLA Limit: {_format_hours(sla_hours)}\n"
            f"Risk Level: {risk_level}\n"
            f"ML predicts this ticket may exceed the SLA deadline."
        )
        
        managers = db.session.execute(
            text("SELECT user_id FROM users WHERE role_id = 2 AND status = 'Active'")
        ).fetchall()
        for manager in managers:
            create_notification(manager[0], "ML SLA Risk Alert", message)
        
        agent_result = db.session.execute(
            text("SELECT assigned_to FROM tickets WHERE ticket_id = :tid"),
            {"tid": ticket_id}
        ).fetchone()
        if agent_result and agent_result[0]:
            create_notification(
                agent_result[0],
                "ML SLA Risk Alert",
                f"Ticket #{ticket_number} has high SLA breach risk. "
                f"ML estimate: {_format_minutes(predicted_minutes)}, "
                f"SLA: {_format_hours(sla_hours)}"
            )
    except Exception as e:
        logger.error("Failed to send SLA risk notification: %s", str(e))


def predict_and_store_for_ticket(ticket_id: int, title: str, description: str,
                                  category: str = None, priority: str = None,
                                  department: str = None, issue_type: str = None,
                                  priority_name: str = None) -> Dict[str, Any]:
    """Main entry point: called after ticket creation. Runs ML prediction,
    stores it, calculates SLA risk, and notifies if needed."""
    predictor = get_resolution_predictor()
    predictor.initialize()
    
    result = predictor.predict(
        title=title,
        description=description,
        category=category,
        priority=priority,
        department=department,
        issue_type=issue_type
    )
    
    store_prediction(ticket_id, result)
    
    risk_level = "unknown"
    sla_hours = None
    
    if result.get("success") and result.get("predicted_minutes") is not None:
        priority_to_use = priority_name or priority
        if priority_to_use:
            sla_hours = get_sla_resolution_time(priority_to_use)
            if sla_hours is not None:
                risk_level = calculate_sla_breach_risk(
                    result["predicted_minutes"], sla_hours
                )
                if risk_level == "high":
                    try:
                        ticket = db.session.execute(
                            text("SELECT ticket_number FROM tickets WHERE ticket_id = :tid"),
                            {"tid": ticket_id}
                        ).fetchone()
                        ticket_number = ticket[0] if ticket else str(ticket_id)
                        notify_sla_risk_alert(
                            ticket_id, ticket_number, title,
                            result["predicted_minutes"], sla_hours, risk_level
                        )
                    except Exception as e:
                        logger.error("Failed to send risk notification: %s", str(e))
    
    result["sla_breach_risk"] = risk_level
    result["sla_resolution_hours"] = sla_hours
    return result


def _format_minutes(minutes: float) -> str:
    if minutes is None:
        return "N/A"
    hours = int(minutes // 60)
    mins = int(round(minutes % 60))
    if hours == 0:
        return f"{mins}m"
    return f"{hours}h {mins}m"


def _format_hours(hours: float) -> str:
    if hours is None:
        return "N/A"
    h = int(hours)
    m = int(round((hours - h) * 60))
    if m == 0:
        return f"{h}h"
    return f"{h}h {m}m"
