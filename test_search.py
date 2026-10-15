import app
import json
from sqlalchemy import text
from help_db import db

with app.app.test_client() as client:
    with app.app.app_context():
        user = db.session.execute(text("SELECT requester_id FROM tickets LIMIT 1")).fetchone()
        user_id = user[0] if user else None
    
    if user_id:
        with client.session_transaction() as sess:
            sess['user_id'] = user_id
        response = client.get('/api/customer-tickets/search?q=176&status=Closed&priority=Critical')
        print('STATUS:', response.status_code)
        try:
            print('JSON:', response.json)
        except Exception as e:
            print('ERROR:', e)
            print('DATA:', response.data.decode('utf-8'))
