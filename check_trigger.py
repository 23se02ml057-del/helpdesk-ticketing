import app
from sqlalchemy import text
from help_db import db

with app.app.app_context():
    triggers = db.session.execute(text("""
        SELECT trigger_name, action_statement 
        FROM information_schema.triggers 
        WHERE event_object_table = 'users'
    """)).fetchall()
    
    with open('triggers.txt', 'w') as f:
        if not triggers:
            f.write("None\n")
        else:
            for t in triggers:
                f.write(f"{t[0]}: {t[1]}\n")
