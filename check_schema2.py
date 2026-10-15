import app
from sqlalchemy import text
from help_db import db

with app.app.app_context():
    indexes = db.session.execute(text("""
        SELECT indexname, indexdef 
        FROM pg_indexes 
        WHERE tablename = 'users'
    """)).fetchall()
    
    with open('indexes.txt', 'w') as f:
        for idx in indexes:
            f.write(f"{idx[0]}: {idx[1]}\n")
            
    # Also check if there are duplicate emails
    dupes = db.session.execute(text("""
        SELECT email, COUNT(*) 
        FROM users 
        GROUP BY email 
        HAVING COUNT(*) > 1
    """)).fetchall()
    
    with open('dupes.txt', 'w') as f:
        for d in dupes:
            f.write(f"{d[0]}: {d[1]}\n")
