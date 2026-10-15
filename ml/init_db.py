"""
Initialize the ticket_ml_predictions table in the PostgreSQL database.
Run this once to set up the ML predictions table.
"""

import os
import sys
import logging

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from help_db import db
from sqlalchemy import text

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def create_ml_predictions_table():
    schema_sql = """
    CREATE TABLE IF NOT EXISTS ticket_ml_predictions (
        prediction_id SERIAL PRIMARY KEY,
        ticket_id INTEGER NOT NULL REFERENCES tickets(ticket_id) ON DELETE CASCADE,
        model_version VARCHAR(50),
        predicted_resolution_minutes NUMERIC(10,2),
        prediction_lower_minutes NUMERIC(10,2),
        prediction_upper_minutes NUMERIC(10,2),
        prediction_status VARCHAR(50) DEFAULT 'unavailable',
        prediction_created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
        actual_resolution_minutes NUMERIC(10,2),
        prediction_error_minutes NUMERIC(10,2)
    );
    CREATE INDEX IF NOT EXISTS idx_ml_predictions_ticket_id ON ticket_ml_predictions(ticket_id);
    CREATE INDEX IF NOT EXISTS idx_ml_predictions_model_version ON ticket_ml_predictions(model_version);
    CREATE INDEX IF NOT EXISTS idx_ml_predictions_created_at ON ticket_ml_predictions(prediction_created_at);
    """
    
    db.session.execute(text(schema_sql))
    db.session.commit()
    logger.info("Created ticket_ml_predictions table (if not exists)")


if __name__ == "__main__":
    from app import app
    with app.app_context():
        create_ml_predictions_table()
        logger.info("ML predictions table created successfully!")
