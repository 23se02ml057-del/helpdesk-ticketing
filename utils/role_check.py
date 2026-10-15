from utils.auth_helper import get_user_role_id
from flask import jsonify


def allow_roles(allowed_roles):

    role_id = get_user_role_id()

    if role_id not in allowed_roles:

        return jsonify({
            "message": "Access Denied"
        }), 403

    return None


def get_user_role():

    return get_user_role_id()
