-- ML Predictions Table
-- Stores ML prediction results for each ticket for historical comparison
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
