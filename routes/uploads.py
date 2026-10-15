import os
from flask import Blueprint, redirect, request, flash, url_for, session
from werkzeug.utils import secure_filename
from sqlalchemy import text
from help_db import db

uploads_bp = Blueprint("uploads_bp", __name__)

UPLOAD_FOLDER = "static/uploads/profile"


@uploads_bp.route("/upload-photo", methods=["POST"])
def upload_photo():
    file = request.files["photo"]
    filename = secure_filename(file.filename)

    os.makedirs(UPLOAD_FOLDER, exist_ok=True)
    file.save(os.path.join(UPLOAD_FOLDER, filename))

    db.session.execute(text("""
        UPDATE users
        SET profile_image = :img
        WHERE user_id = :id
    """), {
        "img": filename,
        "id": session["user_id"]
    })
    db.session.commit()

    return redirect("/super-admin-dashboard")
