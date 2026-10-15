import sys
sys.path.insert(0, 'C:\\Users\\kikan\\OneDrive\\Desktop\\HELP_DESK&TICKET')
from app import app
with app.app_context():
    from help_db import db
    from sqlalchemy import text
    
    for user_id in [244, 78, 79, 238, 239]:
        result = db.session.execute(text('''
            SELECT COUNT(*) FROM tickets WHERE requester_id = :user_id
        '''), {'user_id': user_id}).scalar()
        print(f'Customer ID {user_id} has {result} tickets')