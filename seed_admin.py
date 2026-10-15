import app
from help_db import db
from sqlalchemy import text
from werkzeug.security import generate_password_hash

with app.app.app_context():
    pwd = generate_password_hash("Admin!123")
    # Verify we have an admin
    admin = db.session.execute(text("SELECT email FROM users WHERE role_id = 5 LIMIT 1")).fetchone()
    if not admin:
        print("No admin found, creating one")
        db.session.execute(text("""
            INSERT INTO users (first_name, last_name, email, password_hash, role_id, status, email_verified)
            VALUES ('Admin', 'User', 'admin@example.com', :ph, 5, 'Active', true)
        """), {"ph": pwd})
    else:
        print("Resetting password for admin:", admin[0])
        db.session.execute(text("""
            UPDATE users SET password_hash = :ph WHERE email = :email
        """), {"ph": pwd, "email": admin[0]})
        with open("admin_email.txt", "w") as f:
            f.write(str(admin[0]))
    db.session.commit()
