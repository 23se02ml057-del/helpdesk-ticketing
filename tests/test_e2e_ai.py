"""
End-to-end test for AI ticket classification, priority, and agent assignment.
"""
import json
from app import app
from help_db import db
from sqlalchemy import text
import re

with app.app_context():
    client = app.test_client()
    results = {"passed": 0, "failed": 0}

    def assert_test(condition, message):
        if condition:
            results["passed"] += 1
            print(f"  [PASS] {message}")
        else:
            results["failed"] += 1
            print(f"  [FAIL] {message}")

    def get_csrf(path='/login'):
        resp = client.get(path)
        html = resp.data.decode()
        match = re.search(r'name="csrf-token"\s+content="([^"]+)"', html)
        if not match:
            match = re.search(r'content="([^"]+)"\s+name="csrf-token"', html)
        return match.group(1) if match else ''

    # Login as customer
    csrf = get_csrf()
    client.post('/auth/login', 
        data=json.dumps({'email': 'khushi12@gmail.com', 'password': 'password'}),
        content_type='application/json',
        headers={'X-CSRFToken': csrf},
        follow_redirects=False)
    with client.session_transaction() as sess:
        sess['role_id'] = 6
        sess['user_id'] = 79

    test_cases = [
        ("mouse is not proper working", "Hardware", "Low", "Hardware"),
        ("internet is very slow", "Network", "Medium", "Networking"),
        ("payment is not successfully", "Financial", "High", "Financial"),
        ("wifi password hacking issue", "Network", "High", "Networking"),
        ("keyboard is not working", "Hardware", "Low", "Hardware"),
        ("software is not opening", "Software", "Medium", "Software"),
        ("internet is not working", "Network", "High", "Networking"),
        ("critical server outage", "Network", "Critical", "Networking"),
    ]

    ticket_ids = []
    for title, expected_cat, expected_pri, expected_dept in test_cases:
        print(f"\n=== Testing: {title} ===")
        csrf = get_csrf('/submit-ticket')
        resp = client.post('/submit-ticket', data={
            'title': title,
            'description': '',
            'csrf_token': csrf
        }, follow_redirects=False)
        
        if resp.status_code in [200, 302]:
            ticket = db.session.execute(text("""
                SELECT ticket_id, category_name, priority_name, department_id, assigned_to
                FROM tickets WHERE title = :title ORDER BY ticket_id DESC LIMIT 1
            """), {"title": title}).fetchone()
            
            if ticket:
                tid, cat, pri, dept, assigned = ticket
                ticket_ids.append(tid)
                
                # Get department name
                dept_name = db.session.execute(text(
                    "SELECT department_name FROM departments WHERE department_id = :id"
                ), {"id": dept}).scalar()
                
                # Get agent name
                agent_name = None
                if assigned:
                    agent = db.session.execute(text("""
                        SELECT first_name, last_name FROM users WHERE user_id = :id
                    """), {"id": assigned}).fetchone()
                    if agent:
                        agent_name = f"{agent[0]} {agent[1]}"
                
                assert_test(cat == expected_cat, f"Category: {cat} (expected {expected_cat})")
                assert_test(pri == expected_pri, f"Priority: {pri} (expected {expected_pri})")
                assert_test((dept_name or '').strip() == expected_dept, f"Department: {dept_name} (expected {expected_dept})")
                assert_test(assigned is not None, f"Agent assigned: {agent_name} (expected: assigned)")
            else:
                assert_test(False, "Ticket not found in database")
        else:
            assert_test(False, f"Ticket creation failed: {resp.status_code}")

    print(f"\n=== SUMMARY: {results['passed']} passed, {results['failed']} failed ===")
    if results["failed"] == 0:
        print("ALL TESTS PASSED!")
    else:
        print("SOME TESTS FAILED!")

    # Cleanup
    for tid in ticket_ids:
        db.session.execute(text("DELETE FROM ticket_status_history WHERE ticket_id = :id"), {"id": tid})
        db.session.execute(text("DELETE FROM ticket_assignment_history WHERE ticket_id = :id"), {"id": tid})
        db.session.execute(text("DELETE FROM ticket_ml_predictions WHERE ticket_id = :id"), {"id": tid})
        db.session.execute(text("DELETE FROM tickets WHERE ticket_id = :id"), {"id": tid})
    db.session.commit()
    print(f"\nCleaned up {len(ticket_ids)} test tickets")
