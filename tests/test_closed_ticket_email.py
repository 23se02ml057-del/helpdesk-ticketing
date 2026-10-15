"""
Tests for closed-ticket email trigger.

Verifies that send_closed_ticket_email():
  1. Does NOT send email on ticket creation (status = 'New')
  2. Does NOT send on Open -> On Hold transition
  3. Does NOT send on On Hold -> In Progress transition
  4. Sends exactly one email on In Progress -> Closed transition
  5. Does NOT send again when editing an already-closed ticket
  6. Sends to the correct customer email (not another customer's)
  7. Handles missing/invalid requester email safely
  8. Handles mail API failure without breaking the ticket update
"""
import sys
import os
from unittest.mock import patch, MagicMock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

try:
    from dotenv import load_dotenv
    load_dotenv()
except Exception:
    pass


def _make_ticket_row(ticket_number='TKT001', title='Test Issue',
                     first_name='John', last_name='Doe', email='john@example.com'):
    """Create a mock Row-like object returned by db.session.execute().fetchone()."""
    row = MagicMock()
    row.__getitem__ = MagicMock(side_effect=[
        ticket_number, title, first_name, last_name, email, None, 1
    ])
    return row


class FakeExecuteResult:
    """Mimics the Result object returned by SQLAlchemy session.execute()."""
    def __init__(self, row):
        self._row = row
    def fetchone(self):
        return self._row


def test_01_no_email_on_creation_new_status():
    """New ticket creation (New status) -> no email."""
    from utils.email_service import send_closed_ticket_email
    with patch('utils.email_service.send_email') as mock_send, \
         patch('help_db.db') as mock_db:
        mock_db.session.execute.return_value = FakeExecuteResult(
            _make_ticket_row()
        )
        result = send_closed_ticket_email(1, 'New', 'New')
        assert result.get("success") is False
        mock_send.assert_not_called()
    print("[PASS] No email on ticket creation (New status)")


def test_02_no_email_open_to_pending():
    """Open -> On Hold transition -> no email."""
    from utils.email_service import send_closed_ticket_email
    with patch('utils.email_service.send_email') as mock_send, \
         patch('help_db.db') as mock_db:
        mock_db.session.execute.return_value = FakeExecuteResult(
            _make_ticket_row()
        )
        result = send_closed_ticket_email(1, 'Open', 'On Hold')
        assert result.get("success") is False
        mock_send.assert_not_called()
    print("[PASS] No email on Open -> On Hold transition")


def test_03_no_email_pending_to_in_progress():
    """On Hold -> In Progress transition -> no email."""
    from utils.email_service import send_closed_ticket_email
    with patch('utils.email_service.send_email') as mock_send, \
         patch('help_db.db') as mock_db:
        mock_db.session.execute.return_value = FakeExecuteResult(
            _make_ticket_row()
        )
        result = send_closed_ticket_email(1, 'On Hold', 'In Progress')
        assert result.get("success") is False
        mock_send.assert_not_called()
    print("[PASS] No email on On Hold -> In Progress transition")


def test_04_email_on_in_progress_to_closed():
    """In Progress -> Closed transition -> exactly one email sent."""
    from utils.email_service import send_closed_ticket_email
    with patch('utils.email_service.send_email') as mock_send, \
         patch('help_db.db') as mock_db:
        mock_db.session.execute.return_value = FakeExecuteResult(
            _make_ticket_row()
        )
        mock_send.return_value = {"success": True, "message_id": "test123", "error": None}
        result = send_closed_ticket_email(1, 'In Progress', 'Closed')
        assert result.get("success") is True
        mock_send.assert_called_once()
        kwargs = mock_send.call_args.kwargs
        assert kwargs.get("recipient") == 'john@example.com'
        assert kwargs.get("template_id") == 2
        params = kwargs.get("params", {})
        assert params.get("ticket_number") == 'TKT001'
        assert params.get("ticket_title") == 'Test Issue'
        assert params.get("user_name") == 'John Doe'
    print("[PASS] Email sent on In Progress -> Closed transition")


def test_05_no_duplicate_email_on_already_closed():
    """Closed -> Closed transition -> no email (no duplicate)."""
    from utils.email_service import send_closed_ticket_email
    with patch('utils.email_service.send_email') as mock_send, \
         patch('help_db.db') as mock_db:
        mock_db.session.execute.return_value = FakeExecuteResult(
            _make_ticket_row()
        )
        result = send_closed_ticket_email(1, 'Closed', 'Closed')
        assert result.get("success") is False
        mock_send.assert_not_called()
    print("[PASS] No duplicate email on already-Closed ticket edit")


def test_06_correct_customer_email():
    """Email goes to the requester's email, not someone else's."""
    from utils.email_service import send_closed_ticket_email
    with patch('utils.email_service.send_email') as mock_send, \
         patch('help_db.db') as mock_db:
        mock_db.session.execute.return_value = FakeExecuteResult(
            _make_ticket_row(
                ticket_number='TKT-CUST-A',
                title='Custom Issue',
                first_name='Alice',
                last_name='Smith',
                email='alice@customer.com'
            )
        )
        mock_send.return_value = {"success": True, "message_id": "test123", "error": None}
        result = send_closed_ticket_email(42, 'Resolved', 'Closed')
        assert result.get("success") is True
        mock_send.assert_called_once()
        kwargs = mock_send.call_args.kwargs
        assert kwargs.get("recipient") == 'alice@customer.com'
        params = kwargs.get("params", {})
        assert params.get("user_name") == 'Alice Smith'
        assert params.get("ticket_number") == 'TKT-CUST-A'
    print("[PASS] Email sent to correct customer email")


def test_07_missing_requester_email():
    """Ticket with no requester email -> ticket still closes, no email, no crash."""
    from utils.email_service import send_closed_ticket_email
    with patch('utils.email_service.send_email') as mock_send, \
         patch('help_db.db') as mock_db:
        mock_db.session.execute.return_value = FakeExecuteResult(
            _make_ticket_row(email=None)
        )
        result = send_closed_ticket_email(1, 'In Progress', 'Closed')
        assert result.get("success") is False
        mock_send.assert_not_called()
    print("[PASS] Missing requester email handled safely")


def test_08_empty_requester_email():
    """Ticket with empty requester email -> no email, no crash."""
    from utils.email_service import send_closed_ticket_email
    with patch('utils.email_service.send_email') as mock_send, \
         patch('help_db.db') as mock_db:
        mock_db.session.execute.return_value = FakeExecuteResult(
            _make_ticket_row(email='')
        )
        result = send_closed_ticket_email(1, 'In Progress', 'Closed')
        assert result.get("success") is False
        mock_send.assert_not_called()
    print("[PASS] Empty requester email handled safely")


def test_09_mail_api_failure():
    """Mail API failure -> function returns failure dict, no exception raised."""
    from utils.email_service import send_closed_ticket_email
    with patch('utils.email_service.send_email') as mock_send, \
         patch('help_db.db') as mock_db:
        mock_db.session.execute.return_value = FakeExecuteResult(
            _make_ticket_row()
        )
        mock_send.return_value = {"success": False, "message_id": None, "error": "API error"}
        result = send_closed_ticket_email(1, 'In Progress', 'Closed')
        assert result.get("success") is False
        mock_send.assert_called_once()
    print("[PASS] Mail API failure handled safely")


def test_10_send_email_raises_exception():
    """send_email raising an exception -> no crash, function returns failure dict."""
    from utils.email_service import send_closed_ticket_email
    with patch('utils.email_service.send_email') as mock_send, \
         patch('help_db.db') as mock_db:
        mock_db.session.execute.return_value = FakeExecuteResult(
            _make_ticket_row()
        )
        mock_send.side_effect = Exception("SMTP server unreachable")
        result = send_closed_ticket_email(1, 'In Progress', 'Closed')
        assert result.get("success") is False
    print("[PASS] send_email exception handled safely")


def test_11_db_query_fails():
    """Database query failure -> no crash, function returns failure dict."""
    from utils.email_service import send_closed_ticket_email
    with patch('utils.email_service.send_email') as mock_send, \
         patch('help_db.db') as mock_db:
        mock_db.session.execute.side_effect = Exception("DB connection error")
        result = send_closed_ticket_email(1, 'In Progress', 'Closed')
        assert result.get("success") is False
        mock_send.assert_not_called()
    print("[PASS] DB query failure handled safely")


def test_12_ticket_not_found():
    """Ticket not found in DB -> function returns failure dict, no email."""
    from utils.email_service import send_closed_ticket_email
    with patch('utils.email_service.send_email') as mock_send, \
         patch('help_db.db') as mock_db:
        mock_db.session.execute.return_value = FakeExecuteResult(None)
        result = send_closed_ticket_email(999, 'In Progress', 'Closed')
        assert result.get("success") is False
        mock_send.assert_not_called()
    print("[PASS] Ticket not found handled safely")


def test_13_name_fallback_for_no_name():
    """Customer with no name -> email still sent with fallback name."""
    from utils.email_service import send_closed_ticket_email
    with patch('utils.email_service.send_email') as mock_send, \
         patch('help_db.db') as mock_db:
        mock_db.session.execute.return_value = FakeExecuteResult(
            _make_ticket_row(first_name=None, last_name=None, email='cust@example.com')
        )
        mock_send.return_value = {"success": True, "message_id": "test123", "error": None}
        result = send_closed_ticket_email(1, 'In Progress', 'Closed')
        assert result.get("success") is True
        mock_send.assert_called_once()
        kwargs = mock_send.call_args.kwargs
        assert kwargs.get("recipient") == 'cust@example.com'
        params = kwargs.get("params", {})
        assert params.get("user_name") == 'Valued Customer'
    print("[PASS] Name fallback works correctly")


def test_14_only_closed_triggers_email():
    """Various non-Closed transitions never trigger email."""
    from utils.email_service import send_closed_ticket_email
    non_closed_transitions = [
        ('Open', 'In Progress'),
        ('In Progress', 'On Hold'),
        ('On Hold', 'Open'),
        ('New', 'Open'),
        ('Open', 'Resolved'),
        ('Resolved', 'In Progress'),
        ('Resolved', 'On Hold'),
        ('New', 'Resolved'),
    ]
    for old_st, new_st in non_closed_transitions:
        with patch('utils.email_service.send_email') as mock_send, \
             patch('help_db.db') as mock_db:
            mock_db.session.execute.return_value = FakeExecuteResult(
                _make_ticket_row()
            )
            result = send_closed_ticket_email(1, old_st, new_st)
            assert result.get("success") is False, f"Expected no email for {old_st} -> {new_st}"
            mock_send.assert_not_called(), f"Expected no email call for {old_st} -> {new_st}"
    print(f"[PASS] No email for any non-Closed transition ({len(non_closed_transitions)} cases checked)")


def test_15_email_subject_contains_ticket_number():
    """Verify email subject format when using Brevo template."""
    from utils.email_service import send_closed_ticket_email
    with patch('utils.email_service.send_email') as mock_send, \
         patch('help_db.db') as mock_db:
        mock_db.session.execute.return_value = FakeExecuteResult(
            _make_ticket_row(ticket_number='TKT-2024-001', title='Login issue')
        )
        mock_send.return_value = {"success": True, "message_id": "test123", "error": None}
        send_closed_ticket_email(1, 'In Progress', 'Closed')
        kwargs = mock_send.call_args.kwargs
        assert kwargs.get("subject") == 'Your Help Desk Ticket Has Been Closed'
        params = kwargs.get("params", {})
        assert params.get("ticket_number") == 'TKT-2024-001'
    print("[PASS] Email subject and params correct")


def test_16_email_body_content():
    """Verify email params contain all required elements."""
    from utils.email_service import send_closed_ticket_email
    with patch('utils.email_service.send_email') as mock_send, \
         patch('help_db.db') as mock_db:
        mock_db.session.execute.return_value = FakeExecuteResult(
            _make_ticket_row(
                ticket_number='TKT-500',
                title='Server unreachable',
                first_name='Jane',
                last_name='Smith',
                email='jane@test.com'
            )
        )
        mock_send.return_value = {"success": True, "message_id": "test123", "error": None}
        send_closed_ticket_email(1, 'Resolved', 'Closed')
        kwargs = mock_send.call_args.kwargs
        params = kwargs.get("params", {})
        assert params.get("user_name") == 'Jane Smith'
        assert params.get("ticket_number") == 'TKT-500'
        assert params.get("ticket_title") == 'Server unreachable'
        assert params.get("closed_at")
        assert kwargs.get("recipient") == 'jane@test.com'
    print("[PASS] Email params contain all required content")


if __name__ == '__main__':
    test_01_no_email_on_creation_new_status()
    test_02_no_email_open_to_pending()
    test_03_no_email_pending_to_in_progress()
    test_04_email_on_in_progress_to_closed()
    test_05_no_duplicate_email_on_already_closed()
    test_06_correct_customer_email()
    test_07_missing_requester_email()
    test_08_empty_requester_email()
    test_09_mail_api_failure()
    test_10_send_email_raises_exception()
    test_11_db_query_fails()
    test_12_ticket_not_found()
    test_13_name_fallback_for_no_name()
    test_14_only_closed_triggers_email()
    test_15_email_subject_contains_ticket_number()
    test_16_email_body_content()
    print('\nAll closed-ticket email tests passed!')
