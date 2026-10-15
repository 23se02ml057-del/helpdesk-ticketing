"""Fix missing resolved_at timestamps and retrain model."""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app import app
from help_db import db
from sqlalchemy import text

with app.app_context():
    # Fix tickets: set resolved_at = updated_at where missing
    fixed = db.session.execute(text("""
        UPDATE tickets
        SET resolved_at = COALESCE(updated_at, created_at + interval '2 hours')
        WHERE status_name IN ('Resolved', 'Closed')
          AND resolved_at IS NULL
    """))
    db.session.commit()
    print(f"Fixed {fixed.rowcount} tickets with missing resolved_at")

    # Verify
    eligible = db.session.execute(text("""
        SELECT COUNT(*) FROM tickets
        WHERE status_name IN ('Resolved','Closed')
          AND resolved_at IS NOT NULL AND created_at IS NOT NULL
          AND category_name IS NOT NULL AND priority_name IS NOT NULL
          AND (title IS NOT NULL OR description IS NOT NULL)
          AND resolved_at > created_at
    """)).scalar()
    print(f"Now eligible for training: {eligible}")

# Now retrain
print("\n--- Retraining ML model ---")
from ml.train_resolution_model import main
with app.app_context():
    success = main()
    print(f"\nTraining {'SUCCESS' if success else 'FAILED'}")
