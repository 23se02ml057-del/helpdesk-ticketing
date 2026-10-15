"""
ML Model Evaluation Module

Calculates regression metrics (MAE, RMSE, R²) and prediction
intervals for the resolution time prediction model.

If the dataset is too small for reliable train/test evaluation,
this module clearly indicates that.
"""

from typing import Dict, Any, Optional, Tuple
import numpy as np
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score


MIN_SAMPLES_FOR_EVALUATION = 5
MIN_SAMPLES_FOR_TRAIN_TEST_SPLIT = 10


def evaluate_model(y_true: np.ndarray, y_pred: np.ndarray) -> Dict[str, Any]:
    if y_true is None or y_pred is None:
        return _empty_evaluation()
    
    y_true = np.asarray(y_true, dtype=float).flatten()
    y_pred = np.asarray(y_pred, dtype=float).flatten()
    
    if len(y_true) < MIN_SAMPLES_FOR_EVALUATION:
        return {
            "trainable": len(y_true) > 0,
            "sufficient_data": False,
            "total_samples": int(len(y_true)),
            "warning": (
                f"Only {len(y_true)} samples available. "
                f"Minimum {MIN_SAMPLES_FOR_EVALUATION} required for evaluation. "
                "Metrics are indicative only, not statistically reliable."
            ),
            "mae": None,
            "rmse": None,
            "r2": None,
            "mae_minutes": None,
            "rmse_minutes": None,
        }
    
    mae = mean_absolute_error(y_true, y_pred)
    mse = mean_squared_error(y_true, y_pred)
    rmse = float(np.sqrt(mse))
    r2 = r2_score(y_true, y_pred)
    
    result = {
        "trainable": True,
        "sufficient_data": len(y_true) >= MIN_SAMPLES_FOR_TRAIN_TEST_SPLIT,
        "total_samples": int(len(y_true)),
        "mae": float(mae),
        "rmse": float(rmse),
        "r2": float(r2),
        "mae_minutes": float(mae),
        "rmse_minutes": float(rmse),
    }
    
    if len(y_true) < MIN_SAMPLES_FOR_TRAIN_TEST_SPLIT:
        result["warning"] = (
            f"Only {len(y_true)} samples available. "
            f"Minimum {MIN_SAMPLES_FOR_TRAIN_TEST_SPLIT} recommended for train/test split. "
            "Results are indicative only."
        )
    
    return result


def _empty_evaluation() -> Dict[str, Any]:
    return {
        "trainable": False,
        "sufficient_data": False,
        "total_samples": 0,
        "warning": "No training data available.",
        "mae": None,
        "rmse": None,
        "r2": None,
        "mae_minutes": None,
        "rmse_minutes": None,
    }


def predict_with_interval(
    model: Any,
    X: np.ndarray,
    training_predictions: Optional[np.ndarray] = None,
    training_actuals: Optional[np.ndarray] = None,
    confidence_level: float = 0.9
) -> Tuple[float, Optional[float], Optional[float], str]:
    """
    Predict resolution time with an uncertainty interval.
    
    Uses residual standard deviation from training data to estimate
    a prediction interval. If model does not support this, returns None.
    
    Returns:
        (prediction, lower_bound, upper_bound, confidence_status)
        confidence_status is "available" or "not_available"
    """
    try:
        prediction = float(model.predict(X)[0])
    except Exception:
        return (0.0, None, None, "not_available")
    
    if (training_predictions is not None and 
        training_actuals is not None and
        len(training_predictions) >= MIN_SAMPLES_FOR_EVALUATION):
        
        residuals = np.abs(np.array(training_actuals) - np.array(training_predictions))
        residual_std = float(np.std(residuals))
        
        z_score = 1.645 if confidence_level == 0.9 else 1.96
        
        lower = prediction - z_score * residual_std
        upper = prediction + z_score * residual_std
        
        lower = max(0, lower)
        
        return (prediction, float(lower), float(upper), "available")
    
    return (prediction, None, None, "not_available")
