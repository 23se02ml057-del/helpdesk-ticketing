"""
ML Module for Help Desk Ticket Resolution Time Prediction

This module provides:
- Training: Train the resolution time prediction model
- Prediction: Predict estimated resolution time for new tickets
- Evaluation: Metrics (MAE, RMSE, R2) and confidence intervals
- Model management: Version control, safe deployment, caching

Usage:
    from ml.resolution_predictor import get_resolution_predictor
    predictor = get_resolution_predictor()
    result = predictor.predict(title="WiFi down", description="Cannot connect")
"""

__version__ = "1.0.0"
