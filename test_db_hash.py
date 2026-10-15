from sqlalchemy import create_engine
engine = create_engine('postgresql://postgres:postgres@localhost:5432/help_desk_db')
with engine.connect() as conn:
    result = conn.execute("SELECT user_id, email, password_hash, LENGTH(password_hash) FROM users LIMIT 3")
    for row in result:
        print(row)
