"""
ML Resolution Predictor Module

Loads the trained model (cached) and provides prediction services
for ticket resolution time estimation.
"""

import os
import logging
import numpy as np
from scipy.sparse import hstack
from typing import Dict, Any, Optional, Tuple

logger = logging.getLogger(__name__)

PRIORITY_MAP = {"Critical": 4, "High": 3, "Medium": 2, "Low": 1}


class ResolutionPredictor:
    def __init__(self):
        self._model = None
        self._vectorizer = None
        self._metadata = None
        self._initialized = False
        self._model_loaded = False

    def initialize(self):
        if self._initialized:
            return
        self._initialized = True

        try:
            from ml.model_manager import get_model_manager
            mm = get_model_manager()
            self._model = mm.get_model()
            self._vectorizer = mm.get_vectorizer()
            self._metadata = mm.get_metadata()
            self._model_loaded = self._model is not None and self._vectorizer is not None

            if self._model_loaded:
                logger.info("ML predictor initialized (version %s)",
                           self._metadata.get("model_version", "unknown"))
            else:
                logger.info("ML predictor initialized but no model available (not trained yet)")
        except Exception as e:
            logger.error("Failed to initialize ML predictor: %s", str(e))
            self._model_loaded = False

    def predict(
        self,
        title: str,
        description: str,
        category: str = None,
        priority: str = None,
        department: str = None,
        issue_type: str = None
    ) -> Dict[str, Any]:
        """Predict resolution time for a ticket."""
        from ml.model_manager import get_model_manager

        if not self._initialized:
            self.initialize()

        mm = get_model_manager()
        self._model = mm.get_model()
        self._vectorizer = mm.get_vectorizer()
        self._metadata = mm.get_metadata()

        self._model_loaded = self._model is not None and self._vectorizer is not None

        if not self._model_loaded:
            return {
                "success": False,
                "predicted_minutes": None,
                "predicted_hours": None,
                "predicted_display": "Unavailable",
                "lower_bound_minutes": None,
                "upper_bound_minutes": None,
                "confidence_status": "not_available",
                "model_version": self._metadata.get("model_version", "none"),
                "training_records": self._metadata.get("training_records", 0),
                "dataset_status": self._metadata.get("dataset_status", "no_data"),
                "error": "ML model not trained yet. Run training to enable predictions."
            }

        try:
            from ml.preprocessing import preprocess_ticket_text

            text_input = preprocess_ticket_text(title, description, issue_type)

            if not text_input:
                return {
                    "success": False,
                    "predicted_minutes": None,
                    "predicted_hours": None,
                    "predicted_display": "Unavailable",
                    "lower_bound_minutes": None,
                    "upper_bound_minutes": None,
                    "confidence_status": "not_available",
                    "model_version": self._metadata.get("model_version", "unknown"),
                    "training_records": self._metadata.get("training_records", 0),
                    "dataset_status": self._metadata.get("dataset_status", "limited"),
                    "error": "Insufficient ticket text for prediction"
                }

            # Build features: TF-IDF + priority (matching training format)
            X_tfidf = self._vectorizer.transform([text_input])

            # Priority feature (same encoding as training)
            priority_val = PRIORITY_MAP.get(priority, 2) if priority else 2
            X_struct = np.array([[priority_val]])

            X = hstack([X_tfidf, X_struct])

            # Model predicts in log scale (trained with np.log1p)
            prediction_log = float(self._model.predict(X)[0])
            prediction = float(np.expm1(prediction_log))
            prediction = max(0, prediction)

            # Get prediction interval from metadata if available
            training_pred = self._metadata.get("training_predictions")
            training_actuals = self._metadata.get("training_actuals")
            lower = None
            upper = None
            confidence_status = "not_available"

            predicted_hours = round(prediction / 60, 1) if prediction else 0
            predicted_display = _format_duration(prediction)

            return {
                "success": True,
                "predicted_minutes": round(prediction, 1),
                "predicted_hours": predicted_hours,
                "predicted_display": predicted_display,
                "lower_bound_minutes": None,
                "upper_bound_minutes": None,
                "lower_bound_display": None,
                "upper_bound_display": None,
                "confidence_status": confidence_status,
                "model_version": self._metadata.get("model_version", "unknown"),
                "training_records": self._metadata.get("training_records", 0),
                "dataset_status": self._metadata.get("dataset_status", "limited"),
                "training_predictions": training_pred,
                "training_actuals": training_actuals,
            }

        except Exception as e:
            logger.error("ML prediction failed: %s", str(e))
            return {
                "success": False,
                "predicted_minutes": None,
                "predicted_hours": None,
                "predicted_display": "Unavailable",
                "lower_bound_minutes": None,
                "upper_bound_minutes": None,
                "confidence_status": "not_available",
                "model_version": self._metadata.get("model_version", "unknown"),
                "training_records": self._metadata.get("training_records", 0),
                "dataset_status": self._metadata.get("dataset_status", "no_data"),
                "error": str(e)
            }

    def get_model_info(self) -> Dict[str, Any]:
        from ml.model_manager import get_model_manager
        mm = get_model_manager()

        metadata = mm.get_metadata()
        stats = mm.get_training_stats()

        training_records = metadata.get("training_records", 0)
        eligible = stats.get("eligible_for_training", 0)

        is_small_dataset = training_records < 50

        return {
            "model_version": metadata.get("model_version", "not_trained"),
            "trained_at": metadata.get("trained_at", None),
            "training_records": training_records,
            "mae_minutes": metadata.get("mae_minutes"),
            "rmse_minutes": metadata.get("rmse_minutes"),
            "r2": metadata.get("r2"),
            "model_status": metadata.get("status", "not_trained"),
            "dataset_status": "limited" if is_small_dataset else "sufficient",
            "eligible_training_records": eligible,
            "sufficient_data": training_records >= 5,
            "needs_retraining": (eligible - training_records) >= 10,
            "warning": (
                f"The current dataset has only {training_records} training records. "
                "The model will improve as more verified resolved tickets are collected."
                if is_small_dataset and training_records > 0
                else (
                    "No training data available. The model has not been trained yet."
                    if training_records == 0
                    else None
                )
            )
        }

    def refresh(self):
        self._initialized = False
        self.initialize()


def _format_duration(minutes: float) -> str:
    if minutes is None:
        return "N/A"

    minutes = float(minutes)
    if minutes < 1:
        return f"{int(round(minutes))} min"

    hours = int(minutes // 60)
    mins = int(round(minutes % 60))

    if hours == 0:
        return f"{mins} min"

    if mins == 0:
        return f"{hours}h"

    return f"{hours}h {mins}m"


_resolution_predictor = None


def get_resolution_predictor() -> ResolutionPredictor:
    global _resolution_predictor
    if _resolution_predictor is None:
        _resolution_predictor = ResolutionPredictor()
        _resolution_predictor.initialize()
    return _resolution_predictor
