"""
Authentication helper utilities for hybrid session/JWT auth.

This module provides helper functions that work with both session-based
authentication (for HTML pages) and JWT-based authentication (for API endpoints).
"""

from flask import session
from flask_jwt_extended import get_jwt_identity, verify_jwt_in_request
from sqlalchemy import text
from help_db import db


def get_current_user_id():
    """
    Get the current user ID from either JWT or session.
    Falls back to session if JWT is not available.
    """
    try:
        verify_jwt_in_request(optional=True)
        jwt_user_id = get_jwt_identity()
        if jwt_user_id:
            return int(jwt_user_id)
    except Exception:
        pass
    return session.get("user_id")


def get_current_role():
    """
    Get the current user's role name from either JWT or session.
    Falls back to session if JWT is not available.
    """
    user_id = get_current_user_id()
    if not user_id:
        return None

    try:
        result = db.session.execute(
            text("""
                SELECT r.role_name
                FROM users u
                JOIN roles r ON u.role_id = r.role_id
                WHERE u.user_id = :user_id
            """),
            {"user_id": user_id}
        ).fetchone()
        if result:
            return result[0]
    except Exception:
        pass
    return None


def get_user_role_id():
    """
    Get the current user's role ID from either JWT or session.
    Falls back to session if JWT is not available.
    """
    user_id = get_current_user_id()
    if not user_id:
        return None

    try:
        result = db.session.execute(
            text("""
                SELECT role_id
                FROM users
                WHERE user_id = :user_id
            """),
            {"user_id": user_id}
        ).fetchone()
        if result:
            return result[0]
    except Exception:
        pass
    return None
