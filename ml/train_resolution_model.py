"""
ML Model Training Script

Usage:
    python ml/train_resolution_model.py

This script:
1. Connects to PostgreSQL using existing project configuration.
2. Fetches eligible resolved tickets.
3. Validates data.
4. Calculates actual resolution minutes.
5. Prepares text features using TF-IDF.
6. Trains a Gradient Boosting Regressor model.
7. Evaluates it with MAE, RMSE, R2.
8. Saves the trained model, vectorizer, and metadata.
9. Implements safe model replacement - only saves if metrics are better.
10. Reports training statistics.

Training data eligibility:
- created_at exists
- resolved_at exists (status is Resolved or Closed)
- title or description exists
- category_name exists
- priority_name exists
- Actual resolution time is positive and not an outlier
"""

import os
import sys
import json
import pickle
import logging
from datetime import datetime
import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.ensemble import GradientBoostingRegressor
from sklearn.model_selection import train_test_split
from scipy.sparse import hstack

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from help_db import db
from sqlalchemy import text
from ml.preprocessing import preprocess_ticket_text
from ml.evaluation import evaluate_model
from ml.model_manager import (
    get_model_manager,
    MODEL_FILE,
    VECTORIZER_FILE,
    METADATA_FILE,
    MIN_TRAINING_SAMPLES,
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

MAX_RESOLUTION_HOURS = 168
MIN_RESOLUTION_MINUTES = 5


def fetch_training_data():
    """Fetch eligible resolved tickets for training."""
    query = text("""
        SELECT
            t.ticket_id,
            t.title,
            t.description,
            t.category_name,
            t.priority_name,
            t.department_id,
            t.issue_type_id,
            it.issue_name,
            d.department_name,
            t.created_at,
            t.resolved_at,
            t.status_name,
            (EXTRACT(EPOCH FROM (t.resolved_at - t.created_at)) / 60) AS actual_resolution_minutes
        FROM tickets t
        LEFT JOIN issue_types it ON t.issue_type_id = it.issue_type_id
        LEFT JOIN departments d ON t.department_id = d.department_id
        WHERE t.status_name IN (:resolved, :closed)
          AND t.resolved_at IS NOT NULL
          AND t.created_at IS NOT NULL
          AND t.category_name IS NOT NULL
          AND t.priority_name IS NOT NULL
          AND (t.title IS NOT NULL OR t.description IS NOT NULL)
          AND t.resolved_at > t.created_at
        ORDER BY t.ticket_id
    """)

    results = db.session.execute(query, {"resolved": "Resolved", "closed": "Closed"}).fetchall()

    training_data = []
    excluded = {
        "missing_title_desc": 0,
        "missing_category": 0,
        "missing_priority": 0,
        "missing_timestamps": 0,
        "negative_resolution": 0,
        "too_large": 0,
        "too_small": 0,
    }

    for row in results:
        title = row[1] or ""
        description = row[2] or ""
        category = row[3]
        priority = row[4]
        created_at = row[9]
        resolved_at = row[10]
        actual_minutes = row[12]
        issue_name = row[7]
        dept_name = row[8]

        if not title.strip() and not description.strip():
            excluded["missing_title_desc"] += 1
            continue
        if not category:
            excluded["missing_category"] += 1
            continue
        if not priority:
            excluded["missing_priority"] += 1
            continue
        if actual_minutes is None or actual_minutes < 0:
            excluded["negative_resolution"] += 1
            continue
        if actual_minutes > MAX_RESOLUTION_HOURS * 60:
            excluded["too_large"] += 1
            continue
        if actual_minutes < MIN_RESOLUTION_MINUTES:
            excluded["too_small"] += 1
            continue

        text_input = preprocess_ticket_text(title, description, issue_name)

        training_data.append({
            "ticket_id": row[0],
            "text": text_input,
            "title": title,
            "description": description,
            "category_name": category,
            "priority_name": priority,
            "department_name": dept_name,
            "issue_name": issue_name,
            "created_at": created_at,
            "resolved_at": resolved_at,
            "actual_resolution_minutes": float(actual_minutes),
        })

    return training_data, excluded


def train_model(training_data, excluded):
    if len(training_data) < MIN_TRAINING_SAMPLES:
        logger.warning(
            "Insufficient training data: only %d samples (minimum: %d). "
            "Model will not be trained.",
            len(training_data), MIN_TRAINING_SAMPLES
        )
        return None, None, None

    from ml.model_manager import get_model_manager

    texts = [d["text"] for d in training_data]
    y = np.array([d["actual_resolution_minutes"] for d in training_data])

    priority_map = {"Critical": 4, "High": 3, "Medium": 2, "Low": 1}
    structured_features = []
    for d in training_data:
        p_val = priority_map.get(d["priority_name"], 2)
        structured_features.append([p_val])
    X_struct = np.array(structured_features)

    tfidf = TfidfVectorizer(
        max_features=2000,
        ngram_range=(1, 2),
        stop_words="english",
        min_df=1,
        max_df=0.95,
        sublinear_tf=True,
    )

    X_tfidf = tfidf.fit_transform(texts)
    X = hstack([X_tfidf, X_struct])

    y_log = np.log1p(y)

    if len(training_data) >= 10:
        X_train, X_test, y_train, y_test = train_test_split(
            X, y_log, test_size=0.3, random_state=42
        )
    else:
        X_train, X_test = X, X
        y_train, y_test = y_log, y_log
        logger.warning("Dataset too small for train/test split. Using all data for both.")

    model = GradientBoostingRegressor(
        n_estimators=100,
        max_depth=4,
        learning_rate=0.1,
        subsample=0.8,
        random_state=42,
        min_samples_leaf=max(1, len(training_data) // 20),
    )

    model.fit(X_train, y_train)

    y_pred_log = model.predict(X_test)
    y_pred = np.expm1(y_pred_log)
    y_test_actual = np.expm1(y_test)

    eval_result = evaluate_model(y_test_actual, y_pred)

    y_train_pred_log = model.predict(X_train)
    model.fit(X, y_log)

    metadata = {
        "model_version": get_model_manager().increment_model_version(),
        "trained_at": datetime.utcnow().isoformat(),
        "training_records": len(training_data),
        "eligible_records": len(training_data),
        "excluded_records": sum(excluded.values()),
        "exclusion_reasons": excluded,
        "mae_minutes": eval_result.get("mae_minutes"),
        "rmse_minutes": eval_result.get("rmse_minutes"),
        "r2": eval_result.get("r2"),
        "warning": eval_result.get("warning"),
        "status": "active",
        "dataset_status": "limited" if len(training_data) < 50 else ("sufficient" if len(training_data) >= 100 else "moderate"),
        "training_config": {
            "model_type": "GradientBoostingRegressor",
            "n_estimators": 100,
            "max_depth": 4,
            "learning_rate": 0.1,
            "subsample": 0.8,
        },
        "tfidf_config": {
            "max_features": 2000,
            "ngram_range": [1, 2],
        },
        "feature_names": {
            "text_features": "TF-IDF of title + description + issue_type",
            "structured_features": ["priority_encoded"],
        },
    }

    training_preds_all = model.predict(X)
    metadata["training_predictions"] = [round(float(p), 1) for p in np.expm1(training_preds_all)][:50]
    metadata["training_actuals"] = [round(float(yv), 1) for yv in y][:50]

    return model, tfidf, metadata


def main():
    from app import app

    logger.info("=" * 60)
    logger.info("ML Model Training Script")
    logger.info("=" * 60)

    with app.app_context():
        mm = get_model_manager()
        existing_metrics = mm.get_metadata()

        logger.info("Existing model version: %s", existing_metrics.get("model_version", "none"))
        logger.info("Existing MAE: %s", existing_metrics.get("mae_minutes", "None"))

        logger.info("Fetching training data from database...")
        training_data, excluded = fetch_training_data()

        total_all = db.session.execute(text("SELECT COUNT(*) FROM tickets WHERE status_name IN (:r, :c)"),
                                       {"r": "Resolved", "c": "Closed"}).scalar()

        logger.info("Training Data Report:")
        logger.info("  Total resolved tickets in DB: %d", total_all)
        logger.info("  Eligible for training: %d", len(training_data))
        logger.info("  Excluded: %d", sum(excluded.values()))
        for reason, count in excluded.items():
            if count > 0:
                logger.info("    %s: %d", reason, count)

        if len(training_data) < MIN_TRAINING_SAMPLES:
            logger.warning(
                "Insufficient training data: %d samples (minimum: %d). "
                "Model training skipped. Existing model preserved.",
                len(training_data), MIN_TRAINING_SAMPLES
            )
            return False

        logger.info("Training model with %d samples...", len(training_data))
        model, tfidf, metadata = train_model(training_data, excluded)

        if model is None:
            logger.error("Model training failed.")
            return False

        logger.info("Training completed.")
        logger.info("  MAE: %s minutes", metadata.get("mae_minutes"))
        logger.info("  RMSE: %s minutes", metadata.get("rmse_minutes"))
        logger.info("  R2: %s", metadata.get("r2"))
        logger.info("  Dataset status: %s", metadata.get("dataset_status"))

        if metadata.get("warning"):
            logger.warning("  Warning: %s", metadata["warning"])

        should_deploy = mm.evaluate_replacement(metadata)

        if should_deploy:
            logger.info("Deploying new model (version %s)...", metadata["model_version"])
            if mm.save_model(model, tfidf, metadata):
                logger.info("Model deployed successfully!")
                logger.info("  Version: %s", metadata["model_version"])
                logger.info("  Training records: %d", metadata["training_records"])
                logger.info("  Last trained: %s", metadata["trained_at"])
                return True
            else:
                logger.error("Failed to save model.")
                return False
        else:
            logger.info("New model did not improve over existing model. Keeping existing model.")
            logger.info("  Existing MAE: %s", existing_metrics.get("mae_minutes"))
            logger.info("  New MAE: %s", metadata.get("mae_minutes"))
            return False


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
