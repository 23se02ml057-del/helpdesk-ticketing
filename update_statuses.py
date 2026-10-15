import sys
sys.path.insert(0, '.')
from app import app
from help_db import db
from sqlalchemy import text

with app.test_client() as client:
    # Login as support manager
    with client.session_transaction() as sess:
        sess['user_id'] = 77
        sess['_user_id'] = '77'
        sess['_fresh'] = True
        sess['locale'] = 'en'
        sess['email'] = '23se02ie034@ppsu.ac.in'
        sess['role_id'] = 2
    
    # Define ticket status updates
    # Using ticket IDs from the created tickets
    status_updates = [
        (1077 + 0, 'Open'),        # TKT202609180008 - Internet Connection
        (1077 + 1, 'Pending'),     # TKT202609180009 - Billing Problem
        (1077 + 2, 'In Progress'), # TKT202609180010 - Application Crashing
        (1077 + 3, 'Open'),        # TKT202609180011 - Password Reset
        (1077 + 4, 'Pending'),     # TKT202609180012 - Software Installation
        (1077 + 5, 'In Progress'), # TKT202609180013 - Email Not Working
        (1077 + 6, 'Resolved'),    # TKT202609180014 - Login Problem
        (1077 + 7, 'Resolved'),    # TKT202609180015 - Printer Connection
        (1077 + 8, 'Resolved'),    # TKT202609180016 - Account Access
        (1077 + 9, 'Closed'),      # TKT202609180017 - System Performance
        (1077 + 10, 'Closed'),     # TKT202609180018 - File Upload
        (1077 + 11, 'Open'),       # TKT202609180019 - General Support
    ]
    
    # Wait, let me get the actual ticket IDs from the database
    with app.app_context():
        tickets = db.session.execute(text("""
            SELECT ticket_id, ticket_number FROM tickets
            WHERE requester_id = 229 AND title LIKE 'TEST - Customer Dashboard%'
            ORDER BY ticket_id ASC
        """)).fetchall()
        
        print("Test tickets and their IDs:")
        for t in tickets:
            print(f"  {t[0]}: {t[1]}")
        
        # Need to get the correct ticket IDs for the newly created tickets
        # (the 1077+offset was a guess, let me use actual IDs)
        new_tickets = [t[0] for t in tickets if 'TEST - Customer Dashboard' in t[1]]
        print(f"\nNew test ticket IDs: {new_tickets}")
        
        # Status distribution: 2 Open, 2 Pending, 2 In Progress, 3 Solved, 2 Closed
        # But I have 12 tickets, so I need to adjust. Let me use the first 10 with proper distribution
        # and keep the last 2 as Open
        statuses = [
            'Open', 'Pending', 'In Progress', 'Open', 'Pending', 'In Progress',
            'Resolved', 'Resolved', 'Resolved', 'Closed', 'Closed', 'Open'
        ]
        
        print(f"\nStatus distribution: {statuses.count('Open')} Open, {statuses.count('Pending')} Pending, {statuses.count('In Progress')} In Progress, {statuses.count('Resolved')} Solved, {statuses.count('Closed')} Closed")
        
        # Update each ticket status
        for i, ticket_id in enumerate(new_tickets):
            if i < len(statuses):
                new_status = statuses[i]
                # Get current status
                current = db.session.execute(text("""
                    SELECT status_name FROM tickets WHERE ticket_id = :tid
                """), {"tid": ticket_id}).fetchone()
                current_status = current[0] if current else 'Unknown'
                
                db.session.execute(text("""
                    UPDATE tickets SET status_name = :new_status WHERE ticket_id = :tid
                """), {"new_status": new_status, "tid": ticket_id})
                
                print(f"  {ticket_id}: {current_status} -> {new_status}")
        
        db.session.commit()
        
        # Verify
        print("\nVerification:")
        tickets = db.session.execute(text("""
            SELECT ticket_number, status_name FROM tickets
            WHERE requester_id = 229 AND title LIKE 'TEST - Customer Dashboard%'
            ORDER BY ticket_id ASC
        """)).fetchall()
        
        for t in tickets:
            print(f"  {t[0]}: {t[1]}")
        
        # Count by status
        status_counts = db.session.execute(text("""
            SELECT status_name, COUNT(*) FROM tickets
            WHERE requester_id = 229 AND title LIKE 'TEST - Customer Dashboard%'
            GROUP BY status_name
            ORDER BY status_name
        """)).fetchall()
        
        print("\nStatus counts:")
        for s in status_counts:
            print(f"  {s[0]}: {s[1]}")