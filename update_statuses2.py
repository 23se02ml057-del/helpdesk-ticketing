import sys
sys.path.insert(0, '.')
from app import app
from help_db import db
from sqlalchemy import text

# First get the actual ticket IDs
with app.app_context():
    tickets = db.session.execute(text("""
        SELECT ticket_id, ticket_number, title FROM tickets
        WHERE requester_id = 229 AND title LIKE 'TEST - Customer Dashboard%'
        ORDER BY ticket_id ASC
    """)).fetchall()
    
    print("Test tickets and their IDs:")
    for t in tickets:
        print(f"  {t[0]}: {t[1]} - {t[2]}")
    
    new_tickets = [(t[0], t[1]) for t in tickets]
    
    # Status distribution: 2 Open, 2 Pending, 2 In Progress, 3 Solved, 2 Closed
    # But I have 12 tickets, so let me distribute properly
    # First 10 with proper distribution, last 2 as Open (would be 3 Open total, adjust)
    # Actually let me just distribute all 12 properly
    status_map = {
        new_tickets[0][0]: 'Open',        # TKT202609180008
        new_tickets[1][0]: 'Pending',     # TKT202609180009
        new_tickets[2][0]: 'In Progress', # TKT202609180010
        new_tickets[3][0]: 'Open',        # TKT202609180011
        new_tickets[4][0]: 'Pending',     # TKT202609180012
        new_tickets[5][0]: 'In Progress', # TKT202609180013
        new_tickets[6][0]: 'Resolved',    # TKT202609180014
        new_tickets[7][0]: 'Resolved',    # TKT202609180015
        new_tickets[8][0]: 'Resolved',    # TKT202609180016
        new_tickets[9][0]: 'Closed',      # TKT202609180017
        new_tickets[10][0]: 'Closed',     # TKT202609180018
        new_tickets[11][0]: 'Open',       # TKT202609180019 - making this Open = 3 Open total
    }
    
    # Actually let me adjust: make last one Pending to keep 2 Open
    status_map[new_tickets[11][0]] = 'Pending'
    
    print("\nUpdating statuses via support manager route...")

with app.test_client() as client:
    # Login as support manager (user 77)
    with client.session_transaction() as sess:
        sess['user_id'] = 77
        sess['_user_id'] = '77'
        sess['_fresh'] = True
        sess['locale'] = 'en'
        sess['email'] = '23se02ie034@ppsu.ac.in'
        sess['role_id'] = 2
    
    # Get CSRF token from a page
    r = client.get('/support_manager/dashboard')
    content = r.data.decode('utf-8')
    import re
    csrf_match = re.search(r'name="csrf_token" value="([^"]+)"', content)
    csrf_token = csrf_match.group(1) if csrf_match else None
    
    if not csrf_token:
        print("ERROR: Could not get CSRF token")
        sys.exit(1)
    
    print(f"Got CSRF token")
    
    for ticket_id, new_status in status_map.items():
        r = client.post(f'/support_manager/ticket/{ticket_id}/status', data={
            'csrf_token': csrf_token,
            'status_name': new_status
        }, follow_redirects=True)
        
        if r.status_code == 200:
            print(f"  {ticket_id}: {new_status} - SUCCESS")
        else:
            print(f"  {ticket_id}: {new_status} - FAILED (status {r.status_code})")

# Verify
with app.app_context():
    print("\nVerification:")
    tickets = db.session.execute(text("""
        SELECT ticket_number, status_name FROM tickets
        WHERE requester_id = 229 AND title LIKE 'TEST - Customer Dashboard%'
        ORDER BY ticket_id ASC
    """)).fetchall()
    
    for t in tickets:
        print(f"  {t[0]}: {t[1]}")
    
    status_counts = db.session.execute(text("""
        SELECT status_name, COUNT(*) FROM tickets
        WHERE requester_id = 229 AND title LIKE 'TEST - Customer Dashboard%'
        GROUP BY status_name
        ORDER BY status_name
    """)).fetchall()
    
    print("\nStatus counts:")
    for s in status_counts:
        print(f"  {s[0]}: {s[1]}")