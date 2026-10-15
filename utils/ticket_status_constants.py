"""
Centralized ticket status constants for the Help Desk & Ticket Management System.

These statuses are developer-controlled and should not be managed via any admin UI.
To add/remove/change statuses, modify this file and run the appropriate migration.

Status ID mapping (stable):
    1 = New
    2 = Open
    3 = In Progress
    4 = On Hold
    5 = Resolved
    6 = Closed
"""

VALID_STATUSES = [
    "New",
    "Open",
    "In Progress",
    "On Hold",
    "Resolved",
    "Closed",
]

STATUS_ID_MAP = {
    "New": 1,
    "Open": 2,
    "In Progress": 3,
    "On Hold": 4,
    "Resolved": 5,
    "Closed": 6,
}

ID_STATUS_MAP = {
    1: "New",
    2: "Open",
    3: "In Progress",
    4: "On Hold",
    5: "Resolved",
    6: "Closed",
}

STATUS_DESCRIPTIONS = {
    "New": "Ticket has just been created and has not yet entered active processing.",
    "Open": "Ticket has been accepted and is ready for investigation/handling.",
    "In Progress": "An Agent/Support Team is actively working on the ticket.",
    "On Hold": "Work is temporarily paused because information, approval, customer response, or external dependency is required.",
    "Resolved": "The issue has been fixed by the support team and is waiting for confirmation/closure.",
    "Closed": "The ticket has been completely completed and closed.",
}

MIGRATION_MAP = {
    "New": "New",
    "Open": "Open",
    "In Progress": "In Progress",
    "On Hold": "On Hold",
    "Resolved": "Resolved",
    "Closed": "Closed",
    "Pending": "On Hold",
    "Assigned": "Open",
    "Escalated": "In Progress",
    "Reopened": "Open",
    "Waiting for Customer": "On Hold",
    "Cancelled": "Closed",
    "Duplicate": "Closed",
    "On-Hold": "On Hold",
}

def is_valid_status(status_name):
    return status_name in VALID_STATUSES


def get_status_id(status_name):
    return STATUS_ID_MAP.get(status_name)
