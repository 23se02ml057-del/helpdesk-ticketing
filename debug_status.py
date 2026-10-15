import sys
sys.path.insert(0, '.')
from app import app

with app.test_client() as client:
    with client.session_transaction() as sess:
        sess['user_id'] = 77
        sess['_user_id'] = '77'
        sess['_fresh'] = True
        sess['locale'] = 'en'
        sess['email'] = '23se02ie034@ppsu.ac.in'
        sess['role_id'] = 2
    
    # Debug: check response
    r = client.post('/support_manager/ticket/1084/status', data={
        'status_name': 'Open'
    }, follow_redirects=False)
    
    print(f"Status: {r.status_code}")
    print(f"Location: {r.headers.get('Location', 'None')}")
    print(f"Response body (first 500 chars):")
    try:
        print(r.data.decode('utf-8', errors='ignore')[:500])
    except:
        print("Cannot decode")