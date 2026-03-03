"""
TerminatorBot - XGBoost Alpha Prediction Model

Predicts the true probability of market outcomes using historical
features. Trained on resolved markets, deployed on live ones.
Includes comprehensive evaluation metrics and backtesting support.
"""

from __future__ import annotations

import logging
import os
import pickle
import json
from datetime import datetime
from typing import Optional, Dict, List, Any, Tuple, Callable

import numpy as np

from platforms.base import UnifiedMarket
from ml.feature_engine import FeatureEngine

logger = logging.getLogger(__name__)

MODEL_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "models")


class AlphaModel:
    """
    XGBoost prediction model for market outcomes.

    Predicts P(YES wins) for a given market, returning
    (probability, confidence) tuples.
    
    Includes:
    - Training with cross-validation
    - Comprehensive evaluation metrics
    - Backtesting hooks for strategy simulation
    - Model versioning and persistence
    """

    def __init__(
        self,
        feature_engine: FeatureEngine,
        model_path: str | None = None,
    ):
        self._features = feature_engine
        self._model = None
        self._model_path = model_path or os.path.join(MODEL_DIR, "alpha_xgb.pkl")
        self._loaded = False
        self._metadata: Dict[str, Any] = {}
        self._calibrator = None  # For probability calibration
        
        # Backtesting state
        self._prediction_log: List[Dict] = []

    def load(self) -> bool:
        """Load a trained model from disk."""
        if not os.path.exists(self._model_path):
            logger.info("No trained model at %s", self._model_path)
            return False

        try:
            with open(self._model_path, "rb") as f:
                saved = pickle.load(f)
            
            # Handle both old (just model) and new (dict with model + metadata) formats
            if isinstance(saved, dict):
                self._model = saved['model']
                self._metadata = saved.get('metadata', {})
                self._calibrator = saved.get('calibrator', None)
            else:
                self._model = saved
                self._metadata = {}
            
            self._loaded = True
            logger.info("Alpha model loaded from %s", self._model_path)
            return True
        except Exception as e:
            logger.error("Failed to load model: %s", e)
            return False

    def save(self, path: str | None = None) -> bool:
        """Save model with metadata."""
        path = path or self._model_path
        try:
            os.makedirs(os.path.dirname(path), exist_ok=True)
            saved = {
                'model': self._model,
                'metadata': self._metadata,
                'calibrator': self._calibrator,
            }
            with open(path, "wb") as f:
                pickle.dump(saved, f)
            logger.info("Model saved to %s", path)
            return True
        except Exception as e:
            logger.error("Failed to save model: %s", e)
            return False

    def predict(self, market: UnifiedMarket) -> tuple[float, float] | None:
        """
        Predict P(YES) for a market.

        Returns (probability, confidence) or None if prediction fails.
        """
        if not self._loaded or self._model is None:
            return None

        features = self._features.extract(market)
        if features is None:
            return None

        try:
            X = features.reshape(1, -1)
            prob = float(self._model.predict_proba(X)[0, 1])
            
            # Apply calibration if available
            if self._calibrator is not None:
                prob = float(self._calibrator.predict_proba(np.array([[prob]]))[0, 1])
            
            # Confidence based on multiple factors
            confidence = self._compute_confidence(prob, features)
            
            # Log for backtesting
            self._log_prediction(market, prob, confidence, features)
            
            return (prob, confidence)
        except Exception as e:
            logger.warning("Prediction failed for %s: %s", market.market_id, e)
            return None

    def _compute_confidence(self, prob: float, features: np.ndarray) -> float:
        """
        Compute prediction confidence based on multiple signals.
        
        Factors:
        - Distance from 50% (more extreme = more confident)
        - Liquidity (more liquidity = more market efficiency)
        - Days to close (more time = more uncertainty)
        """
        # Base: distance from uncertainty
        base_confidence = 0.5 + abs(prob - 0.5)
        
        # Liquidity boost (feature index 2 = log_liquidity)
        if len(features) > 2:
            liquidity_factor = min(features[2] / 10.0, 0.2)  # Max 20% boost
        else:
            liquidity_factor = 0
        
        # Time penalty (feature index 10 = days_to_close)
        if len(features) > 10:
            days = features[10]
            time_factor = -min(days / 100.0, 0.15)  # Max 15% penalty
        else:
            time_factor = 0
        
        confidence = base_confidence + liquidity_factor + time_factor
        return min(1.0, max(0.0, confidence))

    def _log_prediction(
        self,
        market: UnifiedMarket,
        prob: float,
        confidence: float,
        features: np.ndarray,
    ) -> None:
        """Log prediction for backtesting analysis."""
        self._prediction_log.append({
            'timestamp': datetime.utcnow().isoformat(),
            'market_id': market.market_id,
            'market_title': market.title[:100],
            'predicted_prob': prob,
            'confidence': confidence,
            'market_yes_price': market.yes_price,
            'features': features.tolist() if features is not None else None,
        })
        
        # Limit log size
        if len(self._prediction_log) > 10000:
            self._prediction_log = self._prediction_log[-5000:]

    def predict_batch(
        self,
        markets: list[UnifiedMarket],
    ) -> list[tuple[UnifiedMarket, float, float]]:
        """
        Predict for a batch of markets.

        Returns list of (market, probability, confidence) tuples.
        """
        if not self._loaded or self._model is None:
            return []

        X, indices = self._features.extract_batch(markets)
        if X.shape[0] == 0:
            return []

        try:
            raw_probs = self._model.predict_proba(X)[:, 1]
            
            # Apply calibration if available
            if self._calibrator is not None:
                probs = self._calibrator.predict_proba(raw_probs.reshape(-1, 1))[:, 1]
            else:
                probs = raw_probs
            
            results = []
            for i, idx in enumerate(indices):
                prob = float(probs[i])
                confidence = self._compute_confidence(prob, X[i])
                results.append((markets[idx], prob, confidence))
            return results
        except Exception as e:
            logger.error("Batch prediction failed: %s", e)
            return []

    def train(
        self,
        X: np.ndarray,
        y: np.ndarray,
        save: bool = True,
        calibrate: bool = True,
        **xgb_params,
    ) -> Dict[str, Any]:
        """
        Train the model on historical data.

        X: feature matrix (n_samples, n_features)
        y: binary labels (0 = NO won, 1 = YES won)
        calibrate: Whether to apply probability calibration

        Returns comprehensive training metrics.
        """
        try:
            from xgboost import XGBClassifier
            from sklearn.model_selection import cross_val_score, train_test_split
            from sklearn.calibration import CalibratedClassifierCV
        except ImportError:
            logger.error("xgboost or sklearn not installed")
            return {"error": "missing dependencies"}

        # Default XGBoost parameters
        default_params = {
            'n_estimators': 200,
            'max_depth': 5,
            'learning_rate': 0.05,
            'subsample': 0.8,
            'colsample_bytree': 0.8,
            'eval_metric': 'logloss',
            'random_state': 42,
        }
        default_params.update(xgb_params)

        # Split for calibration
        if calibrate:
            X_train, X_calib, y_train, y_calib = train_test_split(
                X, y, test_size=0.2, random_state=42, stratify=y
            )
        else:
            X_train, y_train = X, y
            X_calib, y_calib = None, None

        # Train model
        self._model = XGBClassifier(**default_params)
        self._model.fit(X_train, y_train)
        self._loaded = True

        # Calibrate probabilities (Platt scaling)
        if calibrate and X_calib is not None:
            try:
                from sklearn.linear_model import LogisticRegression
                
                # Get raw predictions on calibration set
                calib_probs = self._model.predict_proba(X_calib)[:, 1]
                
                # Train a simple logistic regression for calibration
                self._calibrator = LogisticRegression()
                self._calibrator.fit(calib_probs.reshape(-1, 1), y_calib)
                logger.info("Probability calibration applied (Platt scaling)")
            except Exception as e:
                logger.warning("Calibration failed: %s", e)
                self._calibrator = None

        # Compute comprehensive metrics
        metrics = self._evaluate_model(X, y)
        
        # Add training metadata
        self._metadata = {
            'trained_at': datetime.utcnow().isoformat(),
            'n_samples': len(y),
            'n_features': X.shape[1],
            'feature_names': FeatureEngine.FEATURE_NAMES,
            'params': default_params,
            'metrics': metrics,
            'calibrated': self._calibrator is not None,
        }
        
        metrics['metadata'] = self._metadata

        if save:
            self.save()

        logger.info(
            "Model trained: accuracy=%.3f, brier=%.4f, log_loss=%.4f",
            metrics['accuracy'],
            metrics['brier_score'],
            metrics['log_loss'],
        )
        return metrics

    def _evaluate_model(self, X: np.ndarray, y: np.ndarray) -> Dict[str, Any]:
        """
        Compute comprehensive evaluation metrics.
        
        Returns metrics dict with accuracy, Brier score, log loss,
        ROC-AUC, precision, recall, F1, and calibration info.
        """
        try:
            from sklearn.metrics import (
                accuracy_score, brier_score_loss, log_loss,
                roc_auc_score, precision_score, recall_score, f1_score,
                confusion_matrix, classification_report,
            )
            from sklearn.model_selection import cross_val_score
        except ImportError:
            return {"error": "sklearn not installed"}

        # Predictions
        y_pred = self._model.predict(X)
        y_proba = self._model.predict_proba(X)[:, 1]
        
        # Apply calibration if available
        if self._calibrator is not None:
            y_proba = self._calibrator.predict_proba(y_proba.reshape(-1, 1))[:, 1]

        # Core metrics
        metrics = {
            'accuracy': float(accuracy_score(y, y_pred)),
            'brier_score': float(brier_score_loss(y, y_proba)),
            'log_loss': float(log_loss(y, y_proba)),
            'roc_auc': float(roc_auc_score(y, y_proba)),
            'precision': float(precision_score(y, y_pred, zero_division=0)),
            'recall': float(recall_score(y, y_pred, zero_division=0)),
            'f1': float(f1_score(y, y_pred, zero_division=0)),
        }

        # Cross-validation
        cv_scores = cross_val_score(self._model, X, y, cv=5, scoring='accuracy')
        metrics['cv_accuracy_mean'] = float(cv_scores.mean())
        metrics['cv_accuracy_std'] = float(cv_scores.std())

        # Confusion matrix
        cm = confusion_matrix(y, y_pred)
        metrics['confusion_matrix'] = cm.tolist()
        metrics['true_negatives'] = int(cm[0, 0])
        metrics['false_positives'] = int(cm[0, 1])
        metrics['false_negatives'] = int(cm[1, 0])
        metrics['true_positives'] = int(cm[1, 1])

        # Calibration analysis
        metrics['calibration'] = self._analyze_calibration(y, y_proba)

        # Feature importance
        if hasattr(self._model, 'feature_importances_'):
            feature_names = FeatureEngine.FEATURE_NAMES
            if len(feature_names) == len(self._model.feature_importances_):
                metrics['feature_importance'] = dict(zip(
                    feature_names,
                    self._model.feature_importances_.tolist(),
                ))
                # Top features
                sorted_features = sorted(
                    metrics['feature_importance'].items(),
                    key=lambda x: x[1],
                    reverse=True,
                )
                metrics['top_features'] = sorted_features[:10]

        # Prediction distribution
        metrics['prediction_stats'] = {
            'mean': float(y_proba.mean()),
            'std': float(y_proba.std()),
            'min': float(y_proba.min()),
            'max': float(y_proba.max()),
            'median': float(np.median(y_proba)),
        }

        return metrics

    def _analyze_calibration(
        self,
        y_true: np.ndarray,
        y_proba: np.ndarray,
        n_bins: int = 10,
    ) -> Dict[str, Any]:
        """
        Analyze probability calibration.
        
        Returns calibration curve data and ECE (Expected Calibration Error).
        """
        bin_edges = np.linspace(0, 1, n_bins + 1)
        bin_counts = []
        bin_means_pred = []
        bin_means_true = []
        
        for i in range(n_bins):
            mask = (y_proba >= bin_edges[i]) & (y_proba < bin_edges[i + 1])
            if mask.sum() > 0:
                bin_counts.append(int(mask.sum()))
                bin_means_pred.append(float(y_proba[mask].mean()))
                bin_means_true.append(float(y_true[mask].mean()))
            else:
                bin_counts.append(0)
                bin_means_pred.append(float(bin_edges[i] + bin_edges[i + 1]) / 2)
                bin_means_true.append(float(bin_edges[i] + bin_edges[i + 1]) / 2)

        # Expected Calibration Error
        total = sum(bin_counts)
        if total > 0:
            ece = sum(
                (count / total) * abs(pred - true)
                for count, pred, true in zip(bin_counts, bin_means_pred, bin_means_true)
            )
        else:
            ece = 0.0

        return {
            'ece': float(ece),
            'bin_counts': bin_counts,
            'bin_predicted': bin_means_pred,
            'bin_actual': bin_means_true,
        }

    # ==================== BACKTESTING HOOKS ====================

    def backtest(
        self,
        markets: List[UnifiedMarket],
        outcomes: List[int],
        strategy_fn: Callable[[float, float, UnifiedMarket], Dict[str, Any]] | None = None,
    ) -> Dict[str, Any]:
        """
        Backtest the model on historical markets with known outcomes.
        
        Args:
            markets: List of historical markets
            outcomes: List of outcomes (1 = YES won, 0 = NO won)
            strategy_fn: Optional function(prob, confidence, market) -> bet_decision
        
        Returns:
            Comprehensive backtest results
        """
        if len(markets) != len(outcomes):
            raise ValueError("markets and outcomes must have same length")
        
        predictions = []
        confidences = []
        actuals = []
        bets = []
        
        for market, outcome in zip(markets, outcomes):
            result = self.predict(market)
            if result is None:
                continue
            
            prob, conf = result
            predictions.append(prob)
            confidences.append(conf)
            actuals.append(outcome)
            
            # Apply strategy if provided
            if strategy_fn:
                bet = strategy_fn(prob, conf, market)
                bets.append(bet)
            else:
                # Default strategy: bet YES if prob > market price + threshold
                edge = prob - market.yes_price
                bet = {
                    'side': 'YES' if prob > 0.5 else 'NO',
                    'edge': edge,
                    'bet': abs(edge) > 0.05,  # Only bet if >5% edge
                    'size': min(abs(edge) * 100, 10),  # Size by edge
                }
                bets.append(bet)
        
        if not predictions:
            return {'error': 'no valid predictions'}
        
        # Convert to arrays
        predictions = np.array(predictions)
        actuals = np.array(actuals)
        confidences = np.array(confidences)
        
        # Prediction metrics
        from sklearn.metrics import brier_score_loss, roc_auc_score
        
        results = {
            'n_markets': len(predictions),
            'brier_score': float(brier_score_loss(actuals, predictions)),
            'roc_auc': float(roc_auc_score(actuals, predictions)),
            'mean_confidence': float(confidences.mean()),
        }
        
        # Strategy P&L simulation
        if bets:
            pnl_results = self._simulate_pnl(bets, actuals, predictions)
            results['strategy'] = pnl_results
        
        # Calibration
        results['calibration'] = self._analyze_calibration(actuals, predictions)
        
        # Edge analysis
        results['edge_analysis'] = self._analyze_edge(
            predictions,
            actuals,
            [m.yes_price for m in markets[:len(predictions)]],
        )
        
        return results

    def _simulate_pnl(
        self,
        bets: List[Dict],
        actuals: np.ndarray,
        predictions: np.ndarray,
    ) -> Dict[str, Any]:
        """Simulate P&L from betting strategy."""
        total_bets = 0
        wins = 0
        losses = 0
        total_pnl = 0.0
        pnl_history = []
        
        for i, (bet, actual) in enumerate(zip(bets, actuals)):
            if not bet.get('bet', False):
                continue
            
            total_bets += 1
            side = bet.get('side', 'YES')
            size = bet.get('size', 1.0)
            
            # Simple P&L: win = size, lose = -size
            if (side == 'YES' and actual == 1) or (side == 'NO' and actual == 0):
                pnl = size
                wins += 1
            else:
                pnl = -size
                losses += 1
            
            total_pnl += pnl
            pnl_history.append(total_pnl)
        
        return {
            'total_bets': total_bets,
            'wins': wins,
            'losses': losses,
            'win_rate': wins / max(total_bets, 1),
            'total_pnl': total_pnl,
            'avg_pnl_per_bet': total_pnl / max(total_bets, 1),
            'max_drawdown': self._calculate_drawdown(pnl_history),
            'sharpe_ratio': self._calculate_sharpe(pnl_history),
        }

    def _calculate_drawdown(self, pnl_history: List[float]) -> float:
        """Calculate maximum drawdown from P&L history."""
        if not pnl_history:
            return 0.0
        
        peak = pnl_history[0]
        max_dd = 0.0
        
        for pnl in pnl_history:
            if pnl > peak:
                peak = pnl
            dd = peak - pnl
            if dd > max_dd:
                max_dd = dd
        
        return max_dd

    def _calculate_sharpe(self, pnl_history: List[float]) -> float:
        """Calculate Sharpe ratio from P&L history."""
        if len(pnl_history) < 2:
            return 0.0
        
        returns = np.diff(pnl_history)
        if returns.std() == 0:
            return 0.0
        
        return float(returns.mean() / returns.std() * np.sqrt(252))  # Annualized

    def _analyze_edge(
        self,
        predictions: np.ndarray,
        actuals: np.ndarray,
        market_prices: List[float],
    ) -> Dict[str, Any]:
        """Analyze prediction edge vs market prices."""
        market_prices = np.array(market_prices[:len(predictions)])
        
        # Edge = our prediction - market price
        edges = predictions - market_prices
        
        # Split by edge direction
        positive_edge_mask = edges > 0.05
        negative_edge_mask = edges < -0.05
        
        results = {
            'mean_edge': float(edges.mean()),
            'std_edge': float(edges.std()),
            'positive_edge_count': int(positive_edge_mask.sum()),
            'negative_edge_count': int(negative_edge_mask.sum()),
        }
        
        # Accuracy when we have positive edge
        if positive_edge_mask.sum() > 0:
            results['accuracy_positive_edge'] = float(actuals[positive_edge_mask].mean())
        
        # Accuracy when we have negative edge
        if negative_edge_mask.sum() > 0:
            results['accuracy_negative_edge'] = float(1 - actuals[negative_edge_mask].mean())
        
        return results

    def get_prediction_log(self) -> List[Dict]:
        """Get the prediction log for analysis."""
        return self._prediction_log.copy()

    def clear_prediction_log(self) -> None:
        """Clear the prediction log."""
        self._prediction_log = []

    def export_predictions(self, path: str) -> bool:
        """Export prediction log to JSON file."""
        try:
            with open(path, 'w') as f:
                json.dump(self._prediction_log, f, indent=2)
            return True
        except Exception as e:
            logger.error("Failed to export predictions: %s", e)
            return False

    @property
    def is_loaded(self) -> bool:
        return self._loaded

    @property
    def metadata(self) -> Dict[str, Any]:
        return self._metadata.copy()
