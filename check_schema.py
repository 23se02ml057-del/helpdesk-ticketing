import app
from sqlalchemy import text
from help_db import db

with app.app.app_context():
    cols = db.session.execute(text("SELECT column_name FROM information_schema.columns WHERE table_name = 'users'")).fetchall()
    with open('cols.txt', 'w') as f:
        f.write(','.join([c[0] for c in cols]))
