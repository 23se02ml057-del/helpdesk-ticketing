from app import app
from app import db
from sqlalchemy import text
from werkzeug.security import generate_password_hash

with app.app_context():
    test_pw = 'AgentTest123!'
    hashed = generate_password_hash(test_pw)
    db.session.execute(text('UPDATE users SET password_hash = :hash WHERE email = :email'), 
                      {'hash': hashed, 'email': 'test.agent@example.com'})
    db.session.commit()
    print(f'Set password for test.agent@example.com to: {test_pw}')

print('=== Testing Agent Change Password Flow ===\n')

with app.test_client() as client:
    print('1. Login as agent...')
    resp = client.post('/auth/login', json={
        'email': 'test.agent@example.com',
        'password': 'AgentTest123!'
    })
    print(f'   Status: {resp.status_code}')
    print(f'   Body: {resp.data.decode()[:500]}')
    
    if resp.status_code == 200:
        print('\n2. Access profile page...')
        resp = client.get('/support_agent/profile')
        print(f'   Status: {resp.status_code}')
        
        print('\n3. Submit change password form...')
        resp = client.post('/auth/change-password', data={
            'current_password': 'AgentTest123!',
            'new_password': 'NewAgentPass123!',
            'confirm_password': 'NewAgentPass123!'
        })
        print(f'   Status: {resp.status_code}')
        location = resp.headers.get('Location', 'None')
        print(f'   Redirect: {location}')
        
        with client.session_transaction() as sess:
            flashes = sess.get('_flashes', [])
            for cat, msg in flashes:
                print(f'   Flash: [{cat}] {msg}')
        
        print('\n4. Test login with new password...')
        resp = client.post('/auth/login', json={
            'email': 'test.agent@example.com',
            'password': 'NewAgentPass123!'
        })
        print(f'   Status: {resp.status_code}')
        if resp.status_code == 200:
            print('   SUCCESS: Password changed and login works')
        else:
            print(f'   FAIL: {resp.get_json()}')
    else:
        print('   Login failed, stopping test')

print('\n=== Test Complete ===')
