from sqlalchemy import create_engine, text
import requests

def test():
    # Insert test user
    engine = create_engine('postgresql://postgres:postgres@localhost:5432/help_desk_db')
    try:
        with engine.connect() as conn:
            conn.execute(text("DELETE FROM users WHERE email='test_pwd_user@example.com'"))
            conn.execute(text("""
                INSERT INTO users (first_name, last_name, email, password_hash, role_id, status, email_verified)
                VALUES ('Test', 'User', 'test_pwd_user@example.com', 'scrypt:32768:8:1$BYEUC6s1oAmWf0X3$ebf3c7cb348e0bc0039c354997d83d43ef51597904703b47e3498417afa255219c200601445217ad857e44fadb1de1442a26dceb06ab05f3d7bfae0f3cb6124f', 6, 'Active', true)
            """))
            conn.commit()
    except Exception as e:
        print("Insert failed:", e)

    s = requests.Session()
    # Login
    resp = s.post('http://127.0.0.1:5000/auth/login', json={'email':'test_pwd_user@example.com', 'password':'Password!123'})
    print('Login 1:', resp.json())
    
    # Change
    resp = s.post('http://127.0.0.1:5000/auth/change-password', json={
        'current_password': 'Password!123',
        'new_password': 'Password!456',
        'confirm_password': 'Password!456'
    })
    print('Change Pwd:', resp.text)
    
    # Login again
    s2 = requests.Session()
    resp2 = s2.post('http://127.0.0.1:5000/auth/login', json={'email':'test_pwd_user@example.com', 'password':'Password!456'})
    print('Login 2:', resp2.json())
    
    try:
        with engine.connect() as conn:
            conn.execute(text("DELETE FROM users WHERE email='test_pwd_user@example.com'"))
            conn.commit()
    except:
        pass

if __name__ == '__main__':
    test()
