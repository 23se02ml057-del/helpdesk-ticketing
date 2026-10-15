import json
from flask import Blueprint, render_template, request, jsonify, session, flash, redirect
from flask_jwt_extended import jwt_required, get_jwt_identity
from flask_babel import gettext as _
from utils.ai_service import ai_service

ai_bp = Blueprint("ai", __name__)


@ai_bp.route("/ai-assistant")
def ai_assistant_page():
    """
    Render the AI Assistant chat page.
    Only accessible to logged-in users.
    """
    if not session.get("user_id"):
        flash(_("please_log_in_to_access_the_ai_assistant"), "info")
        return redirect("/login")
    
    user_name = session.get("name", "User")
    return render_template("ai_assistant.html", user_name=user_name)


@ai_bp.route("/api/ai/chat", methods=["POST"])
def ai_chat_api():
    """
    API endpoint for the AI chat feature.
    Expects JSON: { "message": "user message", "history": [...] }
    Returns JSON: { "response": "AI response", "success": true/false, "error": "..." }
    """
    if not session.get("user_id"):
        return jsonify({"success": False, "error": "Unauthorized. Please log in."}), 401
    
    data = request.get_json(silent=True)
    
    if not data or "message" not in data:
        return jsonify({"success": False, "error": "Missing 'message' field in request body"}), 400
    
    user_message = data.get("message", "").strip()
    conversation_history = data.get("history", [])
    
    if not user_message:
        return jsonify({"success": False, "error": "Message cannot be empty"}), 400
    
    # Call the AI service
    response = ai_service.chat_with_ai(
        user_message=user_message,
        conversation_history=conversation_history,
    )
    
    # Check if it's an error response
    if not response.get("success"):
        return jsonify({
            "success": False,
            "error": response.get("response", "AI service is temporarily unavailable. Please try again later.")
        }), 500
    
    return jsonify({
        "success": True,
        "response": response.get("response", "")
    })


@ai_bp.route("/api/ai/summarize-ticket", methods=["POST"])
def summarize_ticket_api():
    """
    API endpoint to summarize a ticket using AI.
    Expects JSON: { "subject": "...", "description": "..." }
    Returns JSON: { "summary": "...", "success": true/false }
    """
    if not session.get("user_id"):
        return jsonify({"success": False, "error": "Unauthorized. Please log in."}), 401
    
    data = request.get_json(silent=True)
    
    if not data or "subject" not in data or "description" not in data:
        return jsonify({"success": False, "error": "Missing 'subject' or 'description' field"}), 400
    
    subject = data.get("subject", "").strip()
    description = data.get("description", "").strip()
    
    if not subject or not description:
        return jsonify({"success": False, "error": "Subject and description cannot be empty"}), 400
    
    summary = ai_service.summarize_ticket(
        ticket_subject=subject,
        ticket_description=description,
    )
    
    if not summary.get("success"):
        return jsonify({
            "success": False,
            "error": "AI service is temporarily unavailable. Please try again later."
        }), 500
    
    return jsonify({
        "success": True,
        "summary": summary.get("summary", "")
    })


@ai_bp.route("/api/ai/suggest-response", methods=["POST"])
def suggest_response_api():
    """
    API endpoint to get an AI-suggested response for a ticket.
    Expects JSON: { "subject": "...", "description": "...", "customer_name": "..." }
    Returns JSON: { "suggestion": "...", "success": true/false }
    """
    if not session.get("user_id"):
        return jsonify({"success": False, "error": "Unauthorized. Please log in."}), 401
    
    data = request.get_json(silent=True)
    
    if not data or "subject" not in data or "description" not in data:
        return jsonify({"success": False, "error": "Missing 'subject' or 'description' field"}), 400
    
    subject = data.get("subject", "").strip()
    description = data.get("description", "").strip()
    customer_name = data.get("customer_name", "Customer").strip()
    
    if not subject or not description:
        return jsonify({"success": False, "error": "Subject and description cannot be empty"}), 400
    
    suggestion = ai_service.suggest_response(
        ticket_subject=subject,
        ticket_description=description,
        customer_name=customer_name,
    )
    
    if not suggestion.get("success"):
        return jsonify({
            "success": False,
            "error": "AI service is temporarily unavailable. Please try again later."
        }), 500
    
    return jsonify({
        "success": True,
        "suggestion": suggestion.get("suggestion", ""),
        "troubleshooting": suggestion.get("troubleshooting", "")
    })


@ai_bp.route("/api/ai/analyze-sentiment", methods=["POST"])
def analyze_sentiment_api():
    """
    API endpoint to analyze sentiment of ticket text.
    Expects JSON: { "text": "..." }
    Returns JSON: { "sentiment": "...", "confidence": "...", "reasoning": "...", "success": true/false }
    """
    if not session.get("user_id"):
        return jsonify({"success": False, "error": "Unauthorized. Please log in."}), 401
    
    data = request.get_json(silent=True)
    
    if not data or "text" not in data:
        return jsonify({"success": False, "error": "Missing 'text' field"}), 400
    
    text = data.get("text", "").strip()
    
    if not text:
        return jsonify({"success": False, "error": "Text cannot be empty"}), 400
    
    result = ai_service.analyze_sentiment(text=text)
    
    if not result.get("success") or result.get("sentiment") == "unknown":
        return jsonify({
            "success": False,
            "error": "AI service is temporarily unavailable. Please try again later."
        }), 500
    
    return jsonify({"success": True, **result})


@ai_bp.route("/api/ai/health", methods=["GET"])
def ai_health_check():
    """
    Health check endpoint for the AI service.
    Returns whether OpenRouter is configured and reachable.
    """
    if not ai_service.is_configured():
        return jsonify({
            "success": False,
            "status": "not_configured",
            "message": "OPENROUTER_API_KEY is not set in environment variables.",
        }), 503
    
    # Try a minimal request to verify connectivity
    result = ai_service.chat(
        messages=[{"role": "user", "content": "Say 'OK' only."}],
        max_tokens=10,
    )
    
    if result["success"]:
        return jsonify({
            "success": True,
            "status": "healthy",
            "model": result.get("model"),
            "message": "OpenRouter API is working correctly.",
        })
    else:
        return jsonify({
            "success": False,
            "status": "error",
            "message": result.get("error", "Unknown error"),
        }), 500
