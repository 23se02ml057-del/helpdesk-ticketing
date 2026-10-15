from app import app

with app.test_client() as client:
    with client.session_transaction() as sess:
        sess['user_id'] = 1
        sess['role_id'] = 1
    
    resp = client.get('/users')
    print(f'/users: {resp.status_code}')
    if resp.status_code in (301, 308):
        loc = resp.headers.get('Location')
        print(f'  Redirect to: {loc}')
    
    resp2 = client.get('/users/')
    print(f'/users/: {resp2.status_code}')
    html = resp2.get_data(as_text=True)
    if 'bhavtik' in html:
        print('  WARNING: Customer found in users page!')
    else:
        print('  OK: No customers in users page')
    
    # Also check what the /users route actually returns
    resp3 = client.get('/users', follow_redirects=True)
    print(f'/users (follow_redirects): {resp3.status_code}')
    html3 = resp3.get_data(as_text=True)
    if 'bhavtik' in html3:
        print('  WARNING: Customer found after redirect!')
    else:
        print('  OK: No customers after redirect')
