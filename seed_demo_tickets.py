"""
Seed script for generating approximately 300 realistic demo tickets.

This is a developer-controlled seed utility. It:
1. Reads existing customers, categories, departments, priorities, agents, skills, and statuses from the DB.
2. Generates 300 diverse, realistic help desk tickets.
3. Assigns tickets to appropriate agents based on department and skills.
4. Generates realistic dates, priorities, and statuses.
5. Ensures no duplicate ticket numbers.
6. Is idempotent - checks for a marker before inserting.

Usage:
    venv\\Scripts\\python.exe seed_demo_tickets.py
"""

import sys
import os
import random
from datetime import datetime, timedelta

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from help_db import db
from app import app
from sqlalchemy import text
from utils.ticket_status_constants import VALID_STATUSES, STATUS_ID_MAP, MIGRATION_MAP

SEED_MARKER = "DEMO_SEED_COMPLETE"

STATUS_DISTRIBUTION = {
    "New": 50,
    "Open": 60,
    "In Progress": 70,
    "On Hold": 35,
    "Resolved": 45,
    "Closed": 40,
}

TOTAL_TICKETS = 300


def load_reference_data():
    ref = {}
    with app.app_context():
        status_rows = db.session.execute(
            text("SELECT status_id, status_name FROM ticket_status ORDER BY status_id")
        ).fetchall()
        ref['statuses'] = {r[1]: r[0] for r in status_rows}
        print(f"Statuses found: {list(ref['statuses'].keys())}")

        cust_rows = db.session.execute(
            text("SELECT user_id, first_name, last_name, email, department_id FROM users WHERE role_id = 6 ORDER BY user_id")
        ).fetchall()
        ref['customers'] = [
            {'user_id': r[0], 'first_name': r[1], 'last_name': r[2], 'email': r[3], 'department_id': r[4]}
            for r in cust_rows
        ]
        print(f"Customers found: {len(ref['customers'])}")

        cat_rows = db.session.execute(
            text("SELECT category_name, department_id FROM categories ORDER BY category_name")
        ).fetchall()
        ref['categories'] = [{'category_name': r[0], 'department_id': r[1]} for r in cat_rows]
        print(f"Categories found: {len(ref['categories'])}")

        dept_rows = db.session.execute(
            text("SELECT department_id, department_name FROM departments ORDER BY department_id")
        ).fetchall()
        ref['departments'] = [{'department_id': r[0], 'department_name': r[1]} for r in dept_rows]
        print(f"Departments found: {len(ref['departments'])}")

        prio_rows = db.session.execute(
            text("SELECT priority_id, priority_name FROM priorities WHERE priority_name IN ('Low','Medium','High','Critical') ORDER BY priority_id")
        ).fetchall()
        ref['priorities'] = [{'priority_id': r[0], 'priority_name': r[1]} for r in prio_rows]
        print(f"Priorities found: {len(ref['priorities'])}")

        agent_rows = db.session.execute(
            text("SELECT user_id, first_name, last_name, department_id FROM users WHERE role_id = 3 ORDER BY user_id")
        ).fetchall()
        ref['agents'] = [
            {'user_id': r[0], 'first_name': r[1], 'last_name': r[2], 'department_id': r[3]}
            for r in agent_rows
        ]
        print(f"Agents found: {len(ref['agents'])}")

        skill_rows = db.session.execute(
            text("SELECT s.skill_id, s.skill_name, s.category, s.department_id FROM skills s ORDER BY s.skill_id")
        ).fetchall()
        ref['skills'] = [
            {'skill_id': r[0], 'skill_name': r[1], 'category': r[2], 'department_id': r[3]}
            for r in skill_rows
        ]

        agent_skill_rows = db.session.execute(
            text("SELECT user_id, skill_id FROM agent_skills ORDER BY user_id")
        ).fetchall()
        agent_skills = {}
        for uid, sid in agent_skill_rows:
            if uid not in agent_skills:
                agent_skills[uid] = []
            for s in ref['skills']:
                if s['skill_id'] == sid:
                    agent_skills[uid].append(s['category'])
                    break
        ref['agent_skills'] = agent_skills

        sla_rows = db.session.execute(
            text("SELECT priority_id, resolution_time FROM sla_rules WHERE status = 'Active'")
        ).fetchall()
        ref['sla_rules'] = {r[0]: r[1] for r in sla_rows}
        print(f"SLA Rules found: {len(ref['sla_rules'])}")

    return ref


# Define diverse ticket issues mapping to categories, priorities, and agent matching
# Each issue: (title, description_template, category, priority, agent_category_hint)
# agent_category_hint is a skill category that helps match the right agent
ISSUE_TEMPLATES = [
    # === IT Support: Hardware Issue ===
    ("Computer not starting", "The customer's desktop computer does not power on at all. No fans spin, no LED indicators, and the monitor remains black. Tried a different power outlet with no change. Suspecting a hardware failure, possibly the power supply or motherboard.",
     "Hardware Issue", "Medium", "Hardware Issue"),
    ("Laptop overheating", "Customer reports the laptop is overheating significantly, especially during video calls. The fan runs loudly and the bottom is too hot to touch. Concerned about potential hardware damage from sustained high temperatures.",
     "Hardware Issue", "Medium", "Hardware Issue"),
    ("System running very slowly", "The customer's desktop takes an unusually long time to boot and applications respond slowly. Multiple apps freeze intermittently. Performance has degraded over the past week despite disk cleanup attempts.",
     "Hardware Issue", "Medium", "System Access"),
    ("Blue screen error", "Customer encounters a Blue Screen of Death (BSOD) with error code 'IRQL_NOT_LESS_OR_EQUAL' every few hours. The system restarts automatically. This is causing significant work disruption.",
     "Hardware Issue", "High", "Hardware Issue"),
    ("Keyboard not responding", "Several keys on the customer's keyboard are not registering input. Affected keys include Enter, Spacebar, and the letter R. The keyboard is mechanical and worked fine yesterday.",
     "Hardware Issue", "Low", "Hardware Issue"),
    ("Wireless mouse not working", "Customer's wireless mouse stops working intermittently. The cursor freezes or moves erratically. Replacing the batteries did not help. The mouse worked fine until this morning.",
     "Hardware Issue", "Low", "Hardware Issue"),
    ("Monitor no signal", "The external monitor shows 'No Signal' when connected to the laptop via HDMI. The laptop screen works fine. Tried a different HDMI cable and monitor with the same result.",
     "Hardware Issue", "Medium", "Hardware Issue"),
    ("USB ports not functioning", "None of the USB ports on the customer's desktop recognize any devices. USB keyboard, mouse, and flash drive all fail to connect. Audio and ethernet ports work fine.",
     "Hardware Issue", "Low", "Hardware Issue"),
    ("Webcam showing black image", "During video conferences, the customer's built-in webcam shows a black blank image. The webcam light turns on but no video feed is available. Issue persists across Teams, Zoom, and Camera app.",
     "Hardware Issue", "Low", "Hardware Issue"),
    ("Microphone not picking up sound", "Customer's laptop microphone is not recording audio during Teams calls. Other participants cannot hear them. Audio works fine through headphones, suggesting the built-in mic may be faulty.",
     "Hardware Issue", "Low", "Hardware Issue"),
    ("Speakers no sound", "Laptop speakers produce no sound despite volume being at maximum and no mute indicators. Audio works through headphones. Issue started after a recent Windows update.",
     "Hardware Issue", "Medium", "Hardware Issue"),
    ("Hard drive clicking noise", "Customer hears a repetitive clicking sound from their desktop and accessing files is very slow. This is a potential sign of imminent hard drive failure. Need urgent attention.",
     "Hardware Issue", "Critical", "Hardware Issue"),
    ("Laptop charger not charging", "The customer's laptop is not charging when the charger is plugged in. The charging indicator light does not illuminate. The laptop runs on battery power but the battery is now critically low.",
     "Hardware Issue", "High", "Hardware Issue"),
    ("RAM error detected", "Customer receives memory error notifications during application crashes. Windows Memory Diagnostic reports hardware errors. The system has 16GB RAM. Frequent crashes and BSOD occurrences reported.",
     "Hardware Issue", "High", "Hardware Issue"),
    ("Docking station display issue", "When connecting to the docking station, the laptop does not detect the dual external monitors. USB devices through the dock work fine, but display outputs are not recognized.",
     "Hardware Issue", "Medium", "Hardware Issue"),

    # === IT Support: Software Issue ===
    ("Windows Update stuck", "Windows Update has been stuck at 85 percent for over 3 hours. The system shows 'Working on updates' but progress is not advancing. No other updates can be installed while this is pending.",
     "Software Issue", "Medium", "Software Issue"),
    ("Application crashing on startup", "The customer's primary business application (ERP) crashes immediately upon launch with error 'Application has stopped working'. It worked fine yesterday. Reinstallation did not resolve the issue.",
     "Software Issue", "High", "Software Issue"),
    ("Application not opening", "The customer cannot open the CRM application. Clicking the icon does nothing and no error message is displayed. The application process does not appear in Task Manager.",
     "Software Issue", "Medium", "Software Issue"),
    ("Software installation problem", "Customer needs to install a new software package but the installer fails with error code 1603. The software requires administrator privileges which the customer has, but installation still fails.",
     "Software Issue", "Low", "Software Issue"),
    ("Excel file corruption", "The customer's Excel workbook shows a file corruption warning and some formulas are returning incorrect results. The file was shared by a colleague. Excel's built-in repair tool did not fix the issue.",
     "Software Issue", "Low", "Software Issue"),
    ("Word document formatting issue", "A Word document shared by a colleague displays incorrectly with garbled text and missing images. The customer's Word is up to date. Other documents open fine.",
     "Software Issue", "Low", "Software Issue"),
    ("Browser performance issue", "Chrome browser is running very slowly, taking several seconds to load pages that normally load instantly. The customer has many tabs open and extensions installed. Clearing cache provided temporary relief.",
     "Software Issue", "Medium", "Software Issue"),
    ("PDF application error", "The customer cannot open PDF files. The PDF reader crashes immediately upon opening any file. Error message: 'Critical failure in PDF rendering engine'.",
     "Software Issue", "Low", "Software Issue"),
    ("Database connection error", "The customer cannot connect to the project database from their development environment. Error: 'Connection refused'. The database server is confirmed running by other users.",
     "Software Issue", "High", "Software Issue"),
    ("Email client not syncing", "The customer's Outlook email client is not syncing new emails. The send/receive progress shows 0 items processed. The customer can access email via web browser.",
     "Email Issue", "Medium", "Email Issue"),
    ("Outlook not opening", "The customer cannot open Microsoft Outlook. The application shows a loading spinner and then closes without any error message. Other Office applications work fine.",
     "Email Issue", "Medium", "Email Issue"),
    ("Email not sending", "Customer sends emails that appear to go out but recipients do not receive them. No error notification is returned. The sent items folder shows the messages as sent successfully.",
     "Email Issue", "Medium", "Email Issue"),
    ("Email not receiving", "The customer has not received several expected emails over the past two days. Other team members using the same email system have received similar messages. The emails are not in the spam/junk folder.",
     "Email Issue", "Medium", "Email Issue"),
    ("Spam email issue", "The customer is receiving a large volume of spam emails (50+ per day) that are not being filtered by the spam protection. This is interfering with their ability to track legitimate emails.",
     "Email Issue", "Low", "Email Issue"),
    ("Email attachment failure", "Customer cannot download or open email attachments. The download fails midway with 'Download interrupted' error. The attachments are under 10MB and the mailbox is not full.",
     "Email Issue", "Low", "Email Issue"),
    ("Mailbox full", "Customer's email mailbox is full (50GB used/50GB limit). They cannot receive new emails and senders are getting bounce-back messages. Need to archive old emails.",
     "Email Issue", "Medium", "Email Issue"),
    ("Email synchronization problem", "The customer's mobile email app is not syncing with the server. Read/unread status and folders are showing inconsistently between desktop and mobile. Last synced 3 hours ago.",
     "Email Issue", "Medium", "Email Issue"),
    ("Email forwarding not working", "Customer set up email forwarding to their personal account but emails are not being forwarded. The forwarding rule is active in settings but no emails arrive at the target account.",
     "Email Issue", "Low", "Email Issue"),
    ("Exchange server error", "Customer receives 'Server unavailable' error when trying to access shared calendars and contacts. This is affecting their ability to schedule meetings with colleagues.",
     "Email Issue", "High", "Email Issue"),

    # === IT Support: Network Issue ===
    ("Wi-Fi not connecting", "Customer cannot connect to the office Wi-Fi network. The network appears in available networks but authentication fails after entering the password. Other devices connect normally to the same network.",
     "Network Issue", "High", "Wi-Fi Issue"),
    ("Internet not working", "The customer's workstation has no internet access. Browsers show 'This site can't be reached'. The network icon shows 'No internet, connected'. Restarting did not help.",
     "Network Issue", "High", "Network Issue"),
    ("Slow internet speed", "Internet connection is significantly slower than expected. Speed tests show 2 Mbps download instead of the contracted 100 Mbps. This affects video calls and large file downloads.",
     "Network Issue", "Medium", "Network Issue"),
    ("Router not responding", "The office router admin interface is inaccessible. Router lights show power and internet but no devices can connect. Multiple restarts attempted without success.",
     "Network Issue", "Critical", "Network Issue"),
    ("Network connection dropping", "Network connection drops every 10-15 minutes, requiring manual reconnection. This happens throughout the workday affecting both wired and wireless connections.",
     "Network Issue", "High", "Network Issue"),
    ("LAN cable problem", "Customer's wired connection shows 'Network cable unplugged' despite the cable being securely connected. Different switch ports tried with same result. Cable tested fine on another device.",
     "Network Issue", "Low", "Network Issue"),
    ("VPN connection problem", "Customer cannot connect to the corporate VPN. Error: 'Authentication failed'. Credentials work for other services. Preventing remote work and accessing internal resources.",
     "Network Issue", "High", "Network Issue"),
    ("DNS issue", "Customer's computer cannot resolve domain names. Pinging IP addresses works but web URLs do not load. nslookup returns 'DNS request timed out'.",
     "Network Issue", "Medium", "Network Issue"),
    ("IP conflict", "Customer receives 'IP address conflict' error when connecting. Two devices on the network have the same IP. Network connectivity is intermittent.",
     "Network Issue", "Medium", "Network Issue"),
    ("Wi-Fi signal weak", "Wi-Fi signal in the main conference room is extremely weak, causing frequent disconnections during presentations. Adjacent rooms have strong signal. Needs immediate attention.",
     "Wi-Fi Issue", "High", "Wi-Fi Issue"),
    ("Network printer unavailable", "Customers cannot print to the shared network printer. The printer shows as 'Offline' in the printer list. It is physically powered on and connected to the network.",
     "Network Issue", "Medium", "Network Issue"),

    # === IT Support: Login Issue ===
    ("Password reset", "Customer needs to reset their password. They forgot the current password and cannot access their account. Account is not locked but they need assistance with the reset process.",
     "Password Reset", "Low", "Login Issue"),
    ("Account locked", "Customer's account is locked after multiple failed login attempts. They were entering an old password. Need to unlock the account and reset credentials.",
     "Login Issue", "High", "Login Issue"),
    ("Login failure", "Customer cannot log in to the system. The login page accepts credentials but redirects back to the login page without any error message. This started after a password change.",
     "Login Issue", "Medium", "Login Issue"),
    ("Two-factor authentication issue", "Customer cannot complete two-factor authentication. The SMS code is not received on their phone and the authenticator app shows 'Invalid code'.",
     "Login Issue", "High", "Login Issue"),
    ("Email password problem", "Customer's email password was changed but their mobile device still shows authentication errors. Manual configuration update did not resolve the issue.",
     "Login Issue", "Low", "Login Issue"),
    ("Shared folder access", "Customer cannot access a shared network folder that they previously had access to. The folder is visible in the network but opening it produces 'Access denied'.",
     "Login Issue", "Medium", "Login Issue"),
    ("Application access request", "Customer needs access to a new software application for their role. They have submitted the access request form but have not received access after 3 business days.",
     "Login Issue", "Low", "Login Issue"),
    ("VPN credentials problem", "Customer has VPN credentials but cannot authenticate. The VPN connection establishes but authentication fails. This was working last week.",
     "Login Issue", "High", "Login Issue"),
    ("Multi-device sync issue", "Customer's account settings are not syncing across their laptop, desktop, and mobile devices. Changes made on one device do not appear on others.",
     "Login Issue", "Low", "Login Issue"),
    ("Session timeout issue", "Customer is being logged out of the application unexpectedly after 5-10 minutes of inactivity. The session settings were supposedly configured for 30 minutes.",
     "Login Issue", "Low", "Login Issue"),
]

# Add more issues for other departments (Finance, HR, Administration, Customer Support)
ISSUE_TEMPLATES += [
    # === Finance: Billing ===
    ("Invoice issue", "Customer reports an issue with invoice INV-2026-045. The amount charged differs from the agreed contract terms. Customer has the original quote and the invoice for comparison.",
     "Billing", "High", "Billing"),
    ("Invoice download problem", "Customer cannot download invoice PDF from the customer portal. Clicking the download button produces no response or a blank page. The invoice is visible in the list.",
     "Invoice", "Medium", "Invoice"),
    ("Payment status not updated", "Customer paid an invoice 5 days ago but the system still shows it as unpaid. The payment was made via bank transfer and the payment reference is attached.",
     "Payment Issue", "High", "Billing"),
    ("Duplicate payment", "Customer was charged twice for the same invoice. Both charges appear on their bank statement but only one invoice was issued. Need to process a refund.",
     "Payment Issue", "Critical", "Payment Issue"),
    ("Transaction failed", "Customer's payment transaction failed at checkout. The payment gateway returned 'Transaction declined' but the card was not declined for other purchases.",
     "Payment Issue", "High", "Payment Issue"),
    ("Payment confirmation missing", "After completing a payment, the customer did not receive a payment confirmation email or receipt. The payment was apparently processed but there is no confirmation.",
     "Payment Issue", "Medium", "Payment Issue"),
    ("Billing mismatch", "Customer's monthly bill shows charges for services they did not use. Specifically, they see charges for 3 additional user licenses that were not requested.",
     "Billing", "High", "Billing"),
    ("Refund request", "Customer is requesting a refund for services they were charged for but did not receive. The support ticket was closed but the refund has not been processed after 2 weeks.",
     "Payment Issue", "High", "Payment Issue"),

    # === HR: Employee Documents ===
    ("Employee portal issue", "Customer cannot log in to the employee portal. The login credentials that worked last week are now rejected. The error message says 'Invalid credentials'.",
     "Employee Documents", "Medium", "Employee Documents"),
    ("Attendance portal problem", "Customer's attendance is not being recorded correctly in the attendance system. They clocked in at 9:00 AM but the system shows 11:00 AM. Multiple days affected.",
     "Attendance", "Medium", "Attendance"),
    ("Leave application issue", "Customer submitted a leave application 3 days ago but has not received any acknowledgment or approval. The application status still shows 'Pending'.",
     "Leave Request", "Low", "Leave Request"),
    ("Employee profile update", "Customer needs to update their employee profile to reflect a change of address and phone number. The self-service update form is not working.",
     "Employee Documents", "Low", "Employee Documents"),
    ("HR document upload problem", "Customer cannot upload their completed tax forms to the HR document portal. The upload fails with 'File type not supported' despite using a PDF.",
     "Employee Documents", "Low", "Employee Documents"),
    ("Employee onboarding access", "A new employee starting next week does not have access to their email account or shared drives. Onboarding access was requested 2 days ago.",
     "Employee Documents", "High", "Employee Documents"),
    ("Employee offboarding access removal", "An employee who left the company last week still has access to email and shared drives. Their accounts need to be deactivated immediately.",
     "Employee Documents", "Critical", "Employee Documents"),

    # === Administration: Asset Request ===
    ("Asset request tracking", "Customer submitted an asset request for a new laptop 1 week ago but has not received any update. The request was approved but the status has not changed.",
     "Asset Request", "Medium", "Asset Request"),
    ("ID card replacement", "Customer's ID card was stolen and they need a replacement. They have reported the incident to security but need the physical card for building access.",
     "ID Card", "High", "ID Card"),
    ("Office maintenance request", "Customer reported a broken AC unit in conference room A 2 days ago. The room is still unusable due to extreme heat. This is affecting scheduled meetings.",
     "Office Maintenance", "High", "Office Maintenance"),
    ("Facilities room booking", "Customer cannot book a meeting room through the facilities management system. The system shows 'No rooms available' for all time slots despite rooms being empty.",
     "Facilities", "Medium", "Facilities"),
    ("Document upload problem", "Customer cannot upload a document to the shared employee directory. The upload fails with an unspecified error. The file is a 5MB PDF.",
     "General Administration", "Low", "General Administration"),
    ("Asset handover delay", "Customer's laptop handover for their new manager has been delayed. The laptop has been prepared but not delivered. The manager starts next Monday.",
     "Asset Request", "High", "Asset Request"),
    ("Office supplies request", "Customer needs to request office supplies (pens, notebooks, sticky notes) for their team. The online request form is not loading properly.",
     "General Administration", "Low", "General Administration"),

    # === Customer Support: Account Issue ===
    ("Customer cannot login", "A customer reports they cannot log in to the customer portal. They are entering the correct credentials but the login page refreshes without logging them in.",
     "Account Issue", "High", "Account Issue"),
    ("Profile update problem", "Customer cannot update their profile information in the customer portal. Specifically, they need to change their phone number but the save button does not work.",
     "Account Issue", "Low", "Account Issue"),
    ("Password reset email not received", "Customer requested a password reset but did not receive the reset email. They checked the spam folder and it is not there either. This has happened twice.",
     "Account Issue", "Medium", "Account Issue"),

    # === Customer Support: General Query ===
    ("Ticket submission failure", "Customer reports that when they try to submit a ticket through the portal, the form does not submit and shows no error message. This has happened with different browsers.",
     "General Query", "Medium", "General Query"),
    ("Ticket attachment problem", "Customer cannot attach files to their ticket. When they select a file and click 'Attach', nothing happens. The file is a 3MB PDF.",
     "General Query", "Low", "General Query"),
    ("Ticket not visible", "Customer submitted a ticket 3 days ago but cannot see it in their 'My Tickets' list. They do not have the ticket number to search for it.",
     "General Query", "High", "General Query"),
    ("Notification not received", "Customer is not receiving email notifications about their ticket updates. They have checked spam/junk folders and the notifications are not there.",
     "General Query", "Low", "General Query"),

    # === Customer Support: Product Issue ===
    ("Product not working", "Customer reports that the widget they purchased is not functioning as described in the manual. Specifically, the auto-start feature does not engage when the device is powered on.",
     "Product Issue", "Medium", "Product Issue"),
    ("Product feature question", "Customer has a question about how to use the advanced reporting feature of the product. They have read the documentation but need clarification on specific steps.",
     "Product Issue", "Low", "Product Issue"),
    ("Product warranty claim", "Customer's product stopped working after 8 months, which is within the 2-year warranty period. They need to file a warranty claim and request a replacement.",
     "Product Issue", "High", "Product Issue"),

    # === Customer Support: Service Issue ===
    ("Service outage", "Customer reports that the online service has been completely unavailable since yesterday morning. The status page shows 'Operational' but the customer cannot access their account.",
     "Service Issue", "Critical", "Service Issue"),
    ("Service performance degraded", "Customer reports that the service has been running significantly slower than usual over the past week. Response times that were under 2 seconds are now taking 10+ seconds.",
     "Service Issue", "High", "Service Issue"),
    ("Service quality concern", "Customer is dissatisfied with the quality of service they received during their last support interaction. They feel their issue was not resolved properly.",
     "Service Issue", "Medium", "Service Issue"),

    # === Customer Support: Customer Complaint ===
    ("Urgent complaint", "Customer has filed an urgent complaint regarding billing practices. They feel they were misled about pricing during the sales process. Need to escalate to management.",
     "Customer Complaint", "Critical", "Customer Complaint"),
    ("Recurring issue complaint", "Customer has had the same issue for the third time in 2 months. Despite multiple tickets being created and closed as resolved, the problem keeps recurring. The customer is frustrated.",
     "Customer Complaint", "High", "Customer Complaint"),
]

# Priority weight adjustment based on issue severity
def determine_priority(issue_priority, category, title):
    """Fine-tune priority based on the specific issue."""
    title_lower = title.lower()
    if ("not working" in title_lower and "company" in title_lower) or "outage" in title_lower:
        return "Critical"
    if "stolen" in title_lower:
        return "Critical"
    if "security" in title_lower or "phishing" in title_lower or "malware" in title_lower:
        return "Critical"
    if "failure" in title_lower and "payment" in title_lower:
        return "High"
    if "unavailable" in title_lower:
        return "Critical"
    if "down" in title_lower or "outage" in title_lower:
        return "Critical"
    return issue_priority


def find_suitable_agent(ref, category_name, department_id):
    """Find an agent whose department matches or whose skills include the category."""
    agents_in_dept = [a for a in ref['agents'] if a['department_id'] == department_id]
    if agents_in_dept:
        return random.choice(agents_in_dept)['user_id']
    agents_with_skill = [
        a for a in ref['agents']
        if category_name in ref['agent_skills'].get(a['user_id'], [])
    ]
    if agents_with_skill:
        return random.choice(agents_with_skill)['user_id']
    if ref['agents']:
        return random.choice(ref['agents'])['user_id']
    return None


def generate_ticket_number(ref):
    """Generate a unique ticket number following the existing format: TKTYYYYMMDDXXXX."""
    today = datetime.now()
    date_str = today.strftime('%Y%m%d')

    with app.app_context():
        last_tickets = db.session.execute(
            text("SELECT ticket_number FROM tickets WHERE ticket_number LIKE 'TKT%' ORDER BY ticket_id DESC LIMIT 1000")
        ).fetchall()

    existing_numbers = set()
    for row in last_tickets:
        existing_numbers.add(row[0])

    # Determine the starting sequence number
    existing_today = sorted([
        n for n in existing_numbers if n.startswith(f"TKT{date_str}")
    ], key=lambda x: int(x[-4:]) if len(x) >= 4 and x[-4:].isdigit() else 0)

    start_seq = 1
    if existing_today:
        try:
            start_seq = int(existing_today[-1][-4:]) + 1
        except (ValueError, IndexError):
            start_seq = 1

    # Generate unique numbers
    seq = start_seq
    numbers = []
    while len(numbers) < TOTAL_TICKETS:
        num = f"TKT{date_str}{seq:04d}"
        if num not in existing_numbers and num not in numbers:
            numbers.append(num)
        seq += 1
        if seq > 9999:
            seq = 1
    return numbers


def run_seed():
    with app.app_context():
        ref = load_reference_data()
        if not ref['customers']:
            print("ERROR: No customers found in the database. Cannot seed tickets.")
            return
        if not ref['categories']:
            print("ERROR: No categories found. Cannot seed tickets.")
            return
        if not ref['priorities']:
            print("ERROR: No priorities found. Cannot seed tickets.")
            return

        for s in VALID_STATUSES:
            if s not in ref['statuses']:
                print(f"ERROR: Status '{s}' not found in database. Run migration first.")
                return

        # Check if already seeded (idempotency)
        existing = db.session.execute(
            text("SELECT COUNT(*) FROM tickets WHERE description LIKE '%Seed marker: SEED_DEMO_TICKETS%'")
        ).scalar()
        if existing > 0:
            print(f"\nA previous seed of {existing} demo tickets was found.")
            try:
                response = input("Run again? This will add more tickets. (y/N): ")
                if response.lower() != 'y':
                    print("Seed aborted.")
                    return
            except EOFError:
                print("Non-interactive mode - skipping re-seed.")
                return

        print("\nGenerating ticket numbers...")
        ticket_numbers = generate_ticket_number(ref)

        print(f"Creating {TOTAL_TICKETS} tickets...")

        now = datetime.now()
        tickets_to_insert = []
        status_counts = {s: 0 for s in VALID_STATUSES}
        priority_counts = {"Low": 0, "Medium": 0, "High": 0, "Critical": 0}
        inserted = 0

        # Build status list matching the distribution
        status_list = []
        for s, count in STATUS_DISTRIBUTION.items():
            status_list.extend([s] * count)
        random.shuffle(status_list)

        # Ensure exact total
        while len(status_list) < TOTAL_TICKETS:
            status_list.append(random.choice(VALID_STATUSES))
        status_list = status_list[:TOTAL_TICKETS]

        try:
            for i in range(TOTAL_TICKETS):
                issue = ISSUE_TEMPLATES[i % len(ISSUE_TEMPLATES)]
                title, desc, category_name, priority_name, agent_skill_cat = issue
                priority_name = determine_priority(priority_name, category_name, title)

                # Fetch department_id from category
                cat_dept = None
                for c in ref['categories']:
                    if c['category_name'] == category_name:
                        cat_dept = c['department_id']
                        break

                # Find an agent
                assigned_agent = find_suitable_agent(ref, category_name, cat_dept)
                assigned_at = None
                resolved_at = None
                due_date = None

                # Determine status and dates
                status = status_list[i]
                status_counts[status] += 1
                priority_counts[priority_name] += 1

                # Created date - spread over last 60 days
                days_ago = random.randint(0, 60)
                created_at = now - timedelta(days=days_ago, hours=random.randint(0, 23), minutes=random.randint(0, 59))

                # For New status: no assignment, no resolution
                if status == "New":
                    assigned_agent = None
                    assigned_at = None
                else:
                    # Assign to an agent
                    if assigned_agent:
                        assigned_at = created_at + timedelta(hours=random.randint(1, 24))
                    else:
                        assigned_agent = find_suitable_agent(ref, category_name, cat_dept)
                        if assigned_agent:
                            assigned_at = created_at + timedelta(hours=random.randint(1, 24))

                # Set resolved_at for Resolved and Closed
                if status in ("Resolved", "Closed"):
                    resolved_at = assigned_at + timedelta(hours=random.randint(1, 72)) if assigned_at else created_at + timedelta(hours=random.randint(1, 72))

                # Due date based on SLA
                prio_row = next((p for p in ref['priorities'] if p['priority_name'] == priority_name), None)
                if prio_row and prio_row['priority_id'] in ref['sla_rules']:
                    sla_hours = ref['sla_rules'][prio_row['priority_id']]
                    due_date = created_at + timedelta(hours=sla_hours)

                customer = random.choice(ref['customers'])

                # Vary the description slightly to avoid duplicates
                variations = [
                    desc,
                    desc + " Customer provided additional details upon request.",
                    desc + " Multiple attempts to resolve have been made.",
                    desc + " Customer reports this is an urgent issue affecting their work.",
                    desc + " Issue started occurring after a recent system update.",
                ]
                full_desc = random.choice(variations)
                # Add seed marker to description for idempotency
                full_desc = full_desc + " [Seed marker: SEED_DEMO_TICKETS]"

                # Vary the title slightly
                title_variations = [
                    title,
                    title + " - Urgent",
                    title + " - Needs attention",
                ]
                full_title = random.choice(title_variations)[:200]

                tickets_to_insert.append({
                    "ticket_number": ticket_numbers[i],
                    "title": full_title,
                    "description": full_desc,
                    "category_name": category_name,
                    "priority_name": priority_name,
                    "status_name": status,
                    "requester_id": customer['user_id'],
                    "assigned_to": assigned_agent,
                    "department_id": cat_dept,
                    "created_at": created_at,
                    "updated_at": created_at + timedelta(hours=random.randint(0, 48)),
                    "assigned_at": assigned_at,
                    "due_date": due_date,
                "resolved_at": resolved_at,
            })

            # Insert tickets
            for t in tickets_to_insert:
                result = db.session.execute(
                    text("""
                        INSERT INTO tickets
                        (ticket_number, title, description, category_name, priority_name,
                         status_name, requester_id, assigned_to, department_id,
                         source, created_at, updated_at, assigned_at, due_date, resolved_at)
                        VALUES (:ticket_number, :title, :description, :category_name,
                                :priority_name, :status_name, :requester_id, :assigned_to,
                                :department_id, 'Web', :created_at, :updated_at,
                                :assigned_at, :due_date, :resolved_at)
                        RETURNING ticket_id
                    """),
                    t
                )
                ticket_id = result.fetchone()[0]
                inserted += 1

                # Insert a status history record for tickets that aren't "New" and have an agent
                if t['status_name'] != 'New' and t['assigned_to']:
                    db.session.execute(
                        text("""
                            INSERT INTO ticket_status_history (ticket_id, old_status, new_status, changed_by, changed_at)
                            VALUES (:ticket_id, :old_status, :new_status, :changed_by, :changed_at)
                        """),
                        {
                            "ticket_id": ticket_id,
                            "old_status": "New",
                            "new_status": t['status_name'],
                            "changed_by": t['assigned_to'],
                            "changed_at": t['created_at'] + timedelta(hours=1),
                        }
                    )

                if inserted % 50 == 0:
                    db.session.commit()
                    print(f"  ... {inserted} tickets created")

            db.session.commit()

            print(f"\nCreated: {inserted}")

            print("\nStatus Distribution:")
            for s, c in status_counts.items():
                print(f"  {s}: {c}")

            print("\nPriority Distribution:")
            for p, c in priority_counts.items():
                print(f"  {p}: {c}")

            print("\n" + "=" * 50)
            print("Seed completed successfully.")
            print("=" * 50)

        except Exception as e:
            db.session.rollback()
            print(f"\nERROR: {e}")
            print("Transaction rolled back.")
            raise


if __name__ == "__main__":
    run_seed()
