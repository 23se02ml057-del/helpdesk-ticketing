"""
ML Configuration Utility

Provides ML-specific configuration read from environment variables,
using the existing project configuration system.
"""

import os


def get_ml_config():
    """Return ML configuration dictionary from environment variables."""
    return {
        "ml_min_training_samples": int(os.environ.get("ML_MIN_TRAINING_SAMPLES", "5")),
        "ml_retrain_threshold": int(os.environ.get("ML_RETRAIN_THRESHOLD", "10")),
    }


def get_ml_config_value(key, default=None):
    """Get a specific ML config value."""
    config = get_ml_config()
    return config.get(key, default)
