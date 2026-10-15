import app as myapp
from help_db import db
from sqlalchemy import text
from werkzeug.security import generate_password_hash
import json

def test():
    app = myapp.app
    with app.test_client() as client:
        with app.app_context():
            # Setup user
            db.session.execute(text("DELETE FROM users WHERE email='test_pwd_user@example.com'"))
            db.session.execute(text("""
                INSERT INTO users (first_name, last_name, email, password_hash, role_id, status, email_verified)
                VALUES ('Test', 'User', 'test_pwd_user@example.com', :ph, 6, 'Active', true)
            """), {"ph": generate_password_hash("Password!123")})
            db.session.commit()
            
            # Fetch user ID
            uid = db.session.execute(text("SELECT user_id FROM users WHERE email='test_pwd_user@example.com'")).scalar()
            
        print("--- Testing API ---")
        
        # 1. Login
        resp = client.post('/auth/login', json={'email': 'test_pwd_user@example.com', 'password': 'Password!123'})
        print("Login 1 Status:", resp.status_code)
        print("Login 1 JSON:", resp.get_json())
        
        access_token = resp.get_json().get("token")
        
        # 2. Change Password
        # Simulate browser session by reusing client
        resp = client.post('/auth/change-password', 
            json={
                'current_password': 'Password!123',
                'new_password': 'Password!456',
                'confirm_password': 'Password!456'
            },
            headers={'Authorization': f'Bearer {access_token}'} # Just in case it checks it
        )
        print("Change Pwd Status:", resp.status_code)
        print("Change Pwd Response:", resp.get_data(as_text=True))
        
        # 3. Login Again with new pwd
        resp = client.post('/auth/login', json={'email': 'test_pwd_user@example.com', 'password': 'Password!456'})
        print("Login 2 Status:", resp.status_code)
        print("Login 2 JSON:", resp.get_json())
            
        # Clean up
        with app.app_context():
            db.session.execute(text("DELETE FROM users WHERE email='test_pwd_user@example.com'"))
            db.session.commit()

if __name__ == '__main__':
    test()
