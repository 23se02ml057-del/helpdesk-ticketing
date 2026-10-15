import sys
sys.path.insert(0, 'C:\\Users\\kikan\\OneDrive\\Desktop\\HELP_DESK&TICKET')
from app import app
with app.test_client() as client:
    # Login as customer ID 78 (Khushi Gajera - 45 tickets)
    with client.session_transaction() as sess:
        sess['user_id'] = 78
    
    resp = client.get('/customer-dashboard')
    print(f'Status: {resp.status_code}')
    content = resp.data.decode('utf-8')
    
    # Check for dashboard content
    if 'My Dashboard' in content or 'my_dashboard' in content:
        print('Dashboard loaded')
    
    # Extract stats
    import re
    # Look for ticket counts in the HTML
    stats = re.findall(r'<h2 class="fw-bold text-\w+ mb-0">(\d+)</h2>', content)
    print(f'Stat cards found: {stats}')
    
    # Check recent tickets table
    if 'recent_tickets' in content.lower() or 'ticket' in content.lower():
        print('Recent tickets section present')
    
    # Check for charts
    if 'statusChart' in content and 'activityChart' in content:
        print('Chart canvases present')
    
    # Check for JavaScript data
    if 'statusLabels' in content or 'status_labels' in content:
        print('Chart data present in JS')
    
    # Print a portion of the response to inspect
    print('\n--- Page excerpt ---')
    # Find the stats section
    idx = content.find('My Dashboard')
    if idx == -1:
        idx = content.find('my_dashboard')
    if idx == -1:
        idx = content.find('My Tickets')
    if idx >= 0:
        print(content[idx:idx+2000])
    else:
        print(content[:2000])