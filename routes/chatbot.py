from flask import Blueprint, render_template, request, jsonify, session, redirect
from sqlalchemy import text
from help_db import db
from utils.ai_service import AIService
import logging

chatbot_bp = Blueprint("chatbot", __name__)
logger = logging.getLogger(__name__)


@chatbot_bp.route("/chatbot")
def chatbot_page():
    if not session.get("user_id"):
        return redirect("/login")
    return render_template("chatbot.html")


@chatbot_bp.route("/api/chatbot/send", methods=["POST"])
def chatbot_send():
    if not session.get("user_id"):
        return jsonify({"success": False, "error": "Unauthorized"}), 401

    data = request.get_json(silent=True)
    if not data or "message" not in data:
        return jsonify({"success": False, "error": "Missing message"}), 400

    user_message = data.get("message", "").strip()
    if not user_message:
        return jsonify({"success": False, "error": "Empty message"}), 400

    user_id = session.get("user_id")

    # Check for duplicate recent messages to prevent duplicates
    recent_dup = db.session.execute(
        text("""
            SELECT 1 FROM chat_history
            WHERE user_id = :user_id AND role = 'user' AND message = :message
            AND created_at > NOW() - INTERVAL '5 seconds'
            LIMIT 1
        """),
        {"user_id": user_id, "message": user_message}
    ).fetchone()
    
    if recent_dup:
        return jsonify({"success": False, "error": "Duplicate message"}), 409

    # Save user message to history
    db.session.execute(
        text("""
            INSERT INTO chat_history (user_id, role, message)
            VALUES (:user_id, 'user', :message)
        """),
        {"user_id": user_id, "message": user_message}
    )
    db.session.commit()

    # Get recent conversation history (last 10 messages, most recent first then reverse)
    history_rows = db.session.execute(
        text("""
            SELECT role, message FROM chat_history
            WHERE user_id = :user_id
            ORDER BY created_at DESC
            LIMIT 10
        """),
        {"user_id": user_id}
    ).fetchall()

    history_rows = list(reversed(history_rows))
    conversation_history = [
        {"role": row[0], "content": row[1]} for row in history_rows
    ]

    ai_service = AIService()
    result = ai_service.chat_with_ai(
        user_message=user_message,
        conversation_history=conversation_history[:-1]
    )

    if result.get("success"):
        ai_response = result.get("response", "")
        db.session.execute(
            text("""
                INSERT INTO chat_history (user_id, role, message)
                VALUES (:user_id, 'assistant', :message)
            """),
            {"user_id": user_id, "message": ai_response}
        )
        db.session.commit()
        return jsonify({"success": True, "response": ai_response}), 200
    else:
        logger.error(f"[Chatbot] AI service failed: {result.get('error')}")
        return jsonify({
            "success": False,
            "response": "AI service is temporarily unavailable. Please try again later.",
            "error": "AI service is temporarily unavailable. Please try again later."
        }), 503


@chatbot_bp.route("/api/chatbot/history", methods=["GET"])
def chatbot_history():
    if not session.get("user_id"):
        return jsonify({"success": False, "error": "Unauthorized"}), 401

    user_id = session.get("user_id")
    rows = db.session.execute(
        text("""
            SELECT role, message, created_at FROM chat_history
            WHERE user_id = :user_id
            ORDER BY created_at ASC
            LIMIT 50
        """),
        {"user_id": user_id}
    ).fetchall()

    history = [
        {
            "role": row[0],
            "message": row[1],
            "created_at": row[2].strftime("%Y-%m-%d %H:%M") if row[2] else ""
        }
        for row in rows
    ]

    return jsonify({"success": True, "history": history})


@chatbot_bp.route("/api/chatbot/clear", methods=["POST"])
def chatbot_clear():
    if not session.get("user_id"):
        return jsonify({"success": False, "error": "Unauthorized"}), 401

    user_id = session.get("user_id")
    db.session.execute(
        text("DELETE FROM chat_history WHERE user_id = :user_id"),
        {"user_id": user_id}
    )
    db.session.commit()

    return jsonify({"success": True, "message": "Chat history cleared"})
