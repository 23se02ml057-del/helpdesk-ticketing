"""Quick check of ticket data for ML training."""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app import app
from help_db import db
from sqlalchemy import text

with app.app_context():
    total = db.session.execute(text("SELECT COUNT(*) FROM tickets")).scalar()
    print(f"Total tickets: {total}")

    rows = db.session.execute(text(
        "SELECT status_name, COUNT(*) as c FROM tickets GROUP BY status_name ORDER BY c DESC"
    )).fetchall()
    for r in rows:
        print(f"  {r[0]}: {r[1]}")

    resolved = db.session.execute(text(
        "SELECT COUNT(*) FROM tickets WHERE status_name IN ('Resolved','Closed')"
    )).scalar()
    print(f"\nResolved/Closed: {resolved}")

    eligible = db.session.execute(text("""
        SELECT COUNT(*) FROM tickets
        WHERE status_name IN ('Resolved','Closed')
          AND resolved_at IS NOT NULL AND created_at IS NOT NULL
          AND category_name IS NOT NULL AND priority_name IS NOT NULL
          AND (title IS NOT NULL OR description IS NOT NULL)
          AND resolved_at > created_at
    """)).scalar()
    print(f"Eligible for training: {eligible}")

    # Check tickets without resolved_at that could be updated
    no_resolved = db.session.execute(text("""
        SELECT COUNT(*) FROM tickets
        WHERE status_name IN ('Resolved','Closed') AND resolved_at IS NULL
    """)).scalar()
    print(f"Resolved/Closed but missing resolved_at: {no_resolved}")

    # Check all tickets with updated_at that could serve as proxy
    all_with_updated = db.session.execute(text("""
        SELECT COUNT(*) FROM tickets
        WHERE status_name IN ('Resolved','Closed') AND resolved_at IS NULL AND updated_at IS NOT NULL
    """)).scalar()
    print(f"  Of those, have updated_at: {all_with_updated}")
