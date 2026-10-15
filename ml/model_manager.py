"""
ML Model Manager Module

Handles model loading, caching, version management, and safe
deployment of new models. Ensures that a new model only replaces
the existing one if it performs better.
"""

import os
import json
import pickle
import logging
from datetime import datetime
from typing import Dict, Any, Optional

from help_db import db
from sqlalchemy import text

logger = logging.getLogger(__name__)

ML_DIR = os.path.dirname(os.path.abspath(__file__))
MODELS_DIR = os.path.join(ML_DIR, "models")
METADATA_DIR = os.path.join(ML_DIR, "metadata")

MODEL_FILE = os.path.join(MODELS_DIR, "resolution_model.pkl")
VECTORIZER_FILE = os.path.join(MODELS_DIR, "tfidf_vectorizer.pkl")
METADATA_FILE = os.path.join(METADATA_DIR, "model_metadata.json")

MIN_TRAINING_SAMPLES = 5
RETRAIN_THRESHOLD = 10


class ModelManager:
    def __init__(self):
        self._model = None
        self._vectorizer = None
        self._metadata = None
        self._loaded = False

    def _load_model(self):
        if self._loaded:
            return self._model is not None

        self._loaded = True

        try:
            if not os.path.exists(MODEL_FILE):
                logger.info("ML model file not found at %s", MODEL_FILE)
                return False

            with open(MODEL_FILE, "rb") as f:
                self._model = pickle.load(f)

            with open(VECTORIZER_FILE, "rb") as f:
                self._vectorizer = pickle.load(f)

            self._metadata = self._load_metadata()

            logger.info("ML model loaded successfully (version %s)",
                       self._metadata.get("model_version", "unknown"))
            return True

        except Exception as e:
            logger.error("Failed to load ML model: %s", str(e))
            self._model = None
            self._vectorizer = None
            self._metadata = None
            return False

    def _load_metadata(self):
        if os.path.exists(METADATA_FILE):
            try:
                with open(METADATA_FILE, "r") as f:
                    return json.load(f)
            except Exception:
                return {}
        return {}

    def _save_metadata(self, metadata):
        try:
            os.makedirs(METADATA_DIR, exist_ok=True)
            with open(METADATA_FILE, "w") as f:
                json.dump(metadata, f, indent=2)
            return True
        except Exception as e:
            logger.error("Failed to save metadata: %s", str(e))
            return False

    def get_model(self):
        if not self._load_model():
            return None
        return self._model

    def get_vectorizer(self):
        if not self._load_model():
            return None
        return self._vectorizer

    def get_metadata(self):
        if not self._load_model():
            return {
                "model_version": "none",
                "trained_at": None,
                "training_records": 0,
                "mae_minutes": None,
                "rmse_minutes": None,
                "r2": None,
                "status": "not_trained",
                "dataset_status": "no_data"
            }
        return self._metadata or {}

    def is_model_available(self):
        return self._load_model()

    def save_model(self, model, vectorizer, metadata):
        try:
            os.makedirs(MODELS_DIR, exist_ok=True)
            os.makedirs(METADATA_DIR, exist_ok=True)

            with open(MODEL_FILE, "wb") as f:
                pickle.dump(model, f)

            with open(VECTORIZER_FILE, "wb") as f:
                pickle.dump(vectorizer, f)

            self._save_metadata(metadata)

            self._model = model
            self._vectorizer = vectorizer
            self._metadata = metadata
            self._loaded = True

            return True
        except Exception as e:
            logger.error("Failed to save model: %s", str(e))
            return False

    def evaluate_replacement(self, new_metrics):
        existing = self.get_metadata()

        if existing.get("status") == "not_trained":
            return True

        new_mae = new_metrics.get("mae")
        existing_mae = existing.get("mae_minutes")

        if new_mae is None:
            return False

        if existing_mae is None:
            return True

        return new_mae < existing_mae

    def increment_model_version(self, current_version=None):
        if not current_version or current_version == "none":
            return "v1.0"

        try:
            parts = current_version.lstrip("v").split(".")
            major = int(parts[0])
            minor = int(parts[1]) if len(parts) > 1 else 0
            minor += 1
            return f"v{major}.{minor}"
        except (ValueError, IndexError):
            return "v1.0"

    def get_training_stats(self):
        """Get statistics about available training data."""
        try:
            from flask import current_app, has_app_context

            def _query_stats():
                total_row = db.session.execute(text(
                    "SELECT COUNT(*) FROM tickets"
                )).scalar()

                resolved_row = db.session.execute(text(
                    "SELECT COUNT(*) FROM tickets WHERE status_name IN ('Resolved', 'Closed')"
                )).scalar()

                eligible_row = db.session.execute(text("""
                    SELECT COUNT(*) FROM tickets
                    WHERE status_name IN ('Resolved', 'Closed')
                      AND resolved_at IS NOT NULL
                      AND created_at IS NOT NULL
                      AND category_name IS NOT NULL
                      AND priority_name IS NOT NULL
                """)).scalar()

                return {
                    "total_tickets": total_row or 0,
                    "resolved_tickets": resolved_row or 0,
                    "eligible_for_training": eligible_row or 0,
                }

            if has_app_context():
                return _query_stats()
            else:
                from app import app
                with app.app_context():
                    return _query_stats()

        except Exception as e:
            logger.error("Failed to get training stats: %s", str(e))
            return {
                "total_tickets": 0,
                "resolved_tickets": 0,
                "eligible_for_training": 0,
            }


_model_manager = None


def get_model_manager():
    global _model_manager
    if _model_manager is None:
        _model_manager = ModelManager()
    return _model_manager
