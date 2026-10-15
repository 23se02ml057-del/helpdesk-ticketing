import sys
sys.path.insert(0, '.')
from app import app
from help_db import db
from sqlalchemy import text

with app.app_context():
    # Find support manager or admin
    users = db.session.execute(text("""
        SELECT u.user_id, u.first_name, u.last_name, u.email, r.role_name
        FROM users u
        JOIN roles r ON u.role_id = r.role_id
        WHERE r.role_name IN ('Support Manager', 'Super Admin')
        ORDER BY u.user_id
    """)).fetchall()
    
    print("Available manager/admin accounts:")
    for u in users:
        print(f"  {u[0]}: {u[1]} {u[2]} ({u[3]}) - {u[4]}")
    
    # Find agent too
    agents = db.session.execute(text("""
        SELECT u.user_id, u.first_name, u.last_name, u.email, r.role_name
        FROM users u
        JOIN roles r ON u.role_id = r.role_id
        WHERE r.role_name = 'Support Agent'
        ORDER BY u.user_id
    """)).fetchall()
    
    print("\nAvailable agent accounts:")
    for a in agents:
        print(f"  {a[0]}: {a[1]} {a[2]} ({a[3]})")