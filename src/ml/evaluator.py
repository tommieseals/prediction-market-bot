"""
TerminatorBot - Model Evaluation Module

Comprehensive evaluation, backtesting, and performance analysis
for prediction market models.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional, Dict, List, Any, Callable, Tuple

import numpy as np

from platforms.base import UnifiedMarket

logger = logging.getLogger(__name__)


class ModelEvaluator:
    """
    Comprehensive model evaluation and backtesting framework.
    
    Supports:
    - Standard ML metrics (accuracy, ROC-AUC, Brier score)
    - Prediction market specific metrics (edge, calibration)
    - Strategy backtesting with P&L simulation
    - Rolling window evaluation
    - Feature importance analysis
    """

    def __init__(self, model=None):
        """
        Initialize evaluator.
        
        Args:
            model: Optional AlphaModel instance for evaluation
        """
        self.model = model
        self.results_history: List[Dict] = []

    def evaluate_predictions(
        self,
        y_true: np.ndarray,
        y_proba: np.ndarray,
        market_prices: np.ndarray | None = None,
    ) -> Dict[str, Any]:
        """
        Evaluate model predictions.
        
        Args:
            y_true: True outcomes (0 or 1)
            y_proba: Predicted probabilities
            market_prices: Optional market YES prices for edge analysis
        
        Returns:
            Dict with comprehensive metrics
        """
        try:
            from sklearn.metrics import (
                accuracy_score, brier_score_loss, log_loss,
                roc_auc_score, average_precision_score,
                precision_recall_curve, roc_curve,
            )
        except ImportError:
            logger.error("sklearn required for evaluation")
            return {'error': 'sklearn not installed'}
        
        y_pred = (y_proba > 0.5).astype(int)
        
        metrics = {
            'n_samples': len(y_true),
            'timestamp': datetime.now(timezone.utc).isoformat(),
            
            # Core metrics
            'accuracy': float(accuracy_score(y_true, y_pred)),
            'brier_score': float(brier_score_loss(y_true, y_proba)),
            'log_loss': float(log_loss(y_true, y_proba)),
            'roc_auc': float(roc_auc_score(y_true, y_proba)),
            'avg_precision': float(average_precision_score(y_true, y_proba)),
            
            # Calibration
            'calibration': self._compute_calibration(y_true, y_proba),
            
            # Prediction distribution
            'pred_stats': {
                'mean': float(y_proba.mean()),
                'std': float(y_proba.std()),
                'min': float(y_proba.min()),
                'max': float(y_proba.max()),
            },
        }
        
        # Edge analysis if market prices provided
        if market_prices is not None:
            metrics['edge_analysis'] = self._compute_edge_metrics(
                y_true, y_proba, market_prices
            )
        
        # Store in history
        self.results_history.append(metrics)
        
        return metrics

    def _compute_calibration(
        self,
        y_true: np.ndarray,
        y_proba: np.ndarray,
        n_bins: int = 10,
    ) -> Dict[str, Any]:
        """Compute calibration metrics and reliability diagram data."""
        bin_edges = np.linspace(0, 1, n_bins + 1)
        bin_indices = np.digitize(y_proba, bin_edges) - 1
        bin_indices = np.clip(bin_indices, 0, n_bins - 1)
        
        bin_counts = np.zeros(n_bins)
        bin_sums_pred = np.zeros(n_bins)
        bin_sums_true = np.zeros(n_bins)
        
        for i in range(len(y_proba)):
            bin_idx = bin_indices[i]
            bin_counts[bin_idx] += 1
            bin_sums_pred[bin_idx] += y_proba[i]
            bin_sums_true[bin_idx] += y_true[i]
        
        # Avoid division by zero
        bin_counts_safe = np.maximum(bin_counts, 1)
        bin_means_pred = bin_sums_pred / bin_counts_safe
        bin_means_true = bin_sums_true / bin_counts_safe
        
        # Expected Calibration Error (ECE)
        total = bin_counts.sum()
        ece = 0.0
        if total > 0:
            for i in range(n_bins):
                if bin_counts[i] > 0:
                    ece += (bin_counts[i] / total) * abs(bin_means_pred[i] - bin_means_true[i])
        
        # Maximum Calibration Error (MCE)
        mce = 0.0
        for i in range(n_bins):
            if bin_counts[i] > 0:
                mce = max(mce, abs(bin_means_pred[i] - bin_means_true[i]))
        
        return {
            'ece': float(ece),
            'mce': float(mce),
            'bin_counts': bin_counts.tolist(),
            'bin_predicted': bin_means_pred.tolist(),
            'bin_actual': bin_means_true.tolist(),
        }

    def _compute_edge_metrics(
        self,
        y_true: np.ndarray,
        y_proba: np.ndarray,
        market_prices: np.ndarray,
    ) -> Dict[str, Any]:
        """Compute edge-based metrics for prediction markets."""
        edges = y_proba - market_prices
        
        # Categorize by edge
        strong_positive = edges > 0.10
        weak_positive = (edges > 0.05) & (edges <= 0.10)
        neutral = (edges >= -0.05) & (edges <= 0.05)
        weak_negative = (edges < -0.05) & (edges >= -0.10)
        strong_negative = edges < -0.10
        
        def compute_accuracy(mask):
            if mask.sum() == 0:
                return None
            return float(y_true[mask].mean())
        
        return {
            'mean_edge': float(edges.mean()),
            'std_edge': float(edges.std()),
            'strong_positive': {
                'count': int(strong_positive.sum()),
                'accuracy': compute_accuracy(strong_positive),
            },
            'weak_positive': {
                'count': int(weak_positive.sum()),
                'accuracy': compute_accuracy(weak_positive),
            },
            'neutral': {
                'count': int(neutral.sum()),
                'accuracy': compute_accuracy(neutral),
            },
            'weak_negative': {
                'count': int(weak_negative.sum()),
                'accuracy': 1 - compute_accuracy(weak_negative) if compute_accuracy(weak_negative) else None,
            },
            'strong_negative': {
                'count': int(strong_negative.sum()),
                'accuracy': 1 - compute_accuracy(strong_negative) if compute_accuracy(strong_negative) else None,
            },
        }

    def backtest_strategy(
        self,
        predictions: List[Tuple[float, float, float, int]],  # (pred_prob, confidence, market_price, outcome)
        strategy: str = 'edge_threshold',
        **strategy_params,
    ) -> Dict[str, Any]:
        """
        Backtest a betting strategy.
        
        Args:
            predictions: List of (predicted_prob, confidence, market_price, outcome)
            strategy: Strategy name ('edge_threshold', 'kelly', 'fixed_size')
            **strategy_params: Strategy-specific parameters
        
        Returns:
            Backtest results with P&L, Sharpe ratio, etc.
        """
        strategy_fn = self._get_strategy(strategy, **strategy_params)
        
        bankroll = strategy_params.get('initial_bankroll', 1000.0)
        initial_bankroll = bankroll
        
        trades = []
        pnl_history = [0.0]
        bankroll_history = [bankroll]
        
        for pred_prob, confidence, market_price, outcome in predictions:
            bet = strategy_fn(pred_prob, confidence, market_price, bankroll)
            
            if bet is None or bet.get('size', 0) <= 0:
                continue
            
            side = bet['side']
            size = bet['size']
            
            # Clamp bet size to available bankroll
            size = min(size, bankroll * 0.95)
            
            # Calculate P&L
            if side == 'YES':
                if outcome == 1:
                    # Win: profit = size * (1/market_price - 1)
                    profit = size * ((1 / market_price) - 1)
                else:
                    profit = -size
            else:  # NO
                if outcome == 0:
                    # Win: profit = size * (1/(1-market_price) - 1)
                    profit = size * ((1 / (1 - market_price)) - 1)
                else:
                    profit = -size
            
            bankroll += profit
            pnl_history.append(pnl_history[-1] + profit)
            bankroll_history.append(bankroll)
            
            trades.append({
                'side': side,
                'size': size,
                'market_price': market_price,
                'predicted_prob': pred_prob,
                'outcome': outcome,
                'profit': profit,
                'bankroll_after': bankroll,
            })
        
        # Calculate performance metrics
        returns = np.diff(pnl_history)
        
        return {
            'strategy': strategy,
            'params': strategy_params,
            'n_trades': len(trades),
            'total_pnl': pnl_history[-1],
            'final_bankroll': bankroll,
            'return_pct': (bankroll - initial_bankroll) / initial_bankroll * 100,
            'win_rate': sum(1 for t in trades if t['profit'] > 0) / max(len(trades), 1),
            'avg_profit_per_trade': pnl_history[-1] / max(len(trades), 1),
            'max_drawdown': self._calculate_max_drawdown(bankroll_history),
            'sharpe_ratio': self._calculate_sharpe(returns),
            'sortino_ratio': self._calculate_sortino(returns),
            'pnl_history': pnl_history,
            'trades': trades[:100],  # Limit for storage
        }

    def _get_strategy(
        self,
        name: str,
        **params,
    ) -> Callable:
        """Get strategy function by name."""
        if name == 'edge_threshold':
            threshold = params.get('threshold', 0.05)
            bet_fraction = params.get('bet_fraction', 0.02)
            
            def strategy(pred_prob, confidence, market_price, bankroll):
                edge = pred_prob - market_price
                if abs(edge) > threshold:
                    side = 'YES' if edge > 0 else 'NO'
                    size = bankroll * bet_fraction * confidence
                    return {'side': side, 'size': size}
                return None
            
            return strategy
        
        elif name == 'kelly':
            fraction = params.get('kelly_fraction', 0.25)  # Fractional Kelly
            max_bet_pct = params.get('max_bet_pct', 0.10)
            
            def strategy(pred_prob, confidence, market_price, bankroll):
                # Kelly criterion: f* = (bp - q) / b
                # where b = odds, p = win probability, q = 1-p
                
                if pred_prob > market_price + 0.03:  # YES bet
                    b = (1 / market_price) - 1  # Decimal odds - 1
                    p = pred_prob
                    q = 1 - p
                    kelly = (b * p - q) / b if b > 0 else 0
                    kelly = kelly * fraction * confidence
                    if kelly > 0:
                        size = min(bankroll * kelly, bankroll * max_bet_pct)
                        return {'side': 'YES', 'size': size}
                
                elif pred_prob < market_price - 0.03:  # NO bet
                    no_price = 1 - market_price
                    b = (1 / no_price) - 1
                    p = 1 - pred_prob
                    q = 1 - p
                    kelly = (b * p - q) / b if b > 0 else 0
                    kelly = kelly * fraction * confidence
                    if kelly > 0:
                        size = min(bankroll * kelly, bankroll * max_bet_pct)
                        return {'side': 'NO', 'size': size}
                
                return None
            
            return strategy
        
        elif name == 'fixed_size':
            fixed_amount = params.get('amount', 10.0)
            threshold = params.get('threshold', 0.05)
            
            def strategy(pred_prob, confidence, market_price, bankroll):
                edge = pred_prob - market_price
                if abs(edge) > threshold:
                    side = 'YES' if edge > 0 else 'NO'
                    return {'side': side, 'size': fixed_amount}
                return None
            
            return strategy
        
        else:
            raise ValueError(f"Unknown strategy: {name}")

    def _calculate_max_drawdown(self, values: List[float]) -> float:
        """Calculate maximum drawdown from value history."""
        if len(values) < 2:
            return 0.0
        
        peak = values[0]
        max_dd = 0.0
        
        for val in values:
            if val > peak:
                peak = val
            dd = (peak - val) / peak if peak > 0 else 0
            max_dd = max(max_dd, dd)
        
        return max_dd

    def _calculate_sharpe(self, returns: np.ndarray) -> float:
        """Calculate Sharpe ratio (assuming 0 risk-free rate)."""
        if len(returns) < 2 or returns.std() == 0:
            return 0.0
        return float(returns.mean() / returns.std() * np.sqrt(252))

    def _calculate_sortino(self, returns: np.ndarray) -> float:
        """Calculate Sortino ratio (downside deviation)."""
        if len(returns) < 2:
            return 0.0
        
        downside_returns = returns[returns < 0]
        if len(downside_returns) == 0 or downside_returns.std() == 0:
            return 0.0 if returns.mean() <= 0 else float('inf')
        
        return float(returns.mean() / downside_returns.std() * np.sqrt(252))

    def rolling_evaluation(
        self,
        y_true: np.ndarray,
        y_proba: np.ndarray,
        window_size: int = 100,
        step_size: int = 50,
    ) -> List[Dict[str, Any]]:
        """
        Perform rolling window evaluation.
        
        Returns metrics for each window to track performance over time.
        """
        results = []
        n = len(y_true)
        
        for start in range(0, n - window_size + 1, step_size):
            end = start + window_size
            
            window_metrics = self.evaluate_predictions(
                y_true[start:end],
                y_proba[start:end],
            )
            window_metrics['window_start'] = start
            window_metrics['window_end'] = end
            
            results.append(window_metrics)
        
        return results

    def compare_models(
        self,
        models: Dict[str, Any],  # name -> model
        X: np.ndarray,
        y: np.ndarray,
    ) -> Dict[str, Any]:
        """
        Compare multiple models on the same dataset.
        
        Returns comparative metrics for model selection.
        """
        results = {}
        
        for name, model in models.items():
            try:
                y_proba = model.predict_proba(X)[:, 1]
                metrics = self.evaluate_predictions(y, y_proba)
                results[name] = metrics
            except Exception as e:
                logger.error(f"Error evaluating model {name}: {e}")
                results[name] = {'error': str(e)}
        
        # Rank models
        valid_results = {k: v for k, v in results.items() if 'error' not in v}
        
        if valid_results:
            rankings = {
                'by_brier_score': sorted(
                    valid_results.keys(),
                    key=lambda k: valid_results[k]['brier_score']
                ),
                'by_roc_auc': sorted(
                    valid_results.keys(),
                    key=lambda k: -valid_results[k]['roc_auc']
                ),
                'by_calibration': sorted(
                    valid_results.keys(),
                    key=lambda k: valid_results[k]['calibration']['ece']
                ),
            }
            results['_rankings'] = rankings
        
        return results

    def export_results(
        self,
        path: str | Path,
        include_history: bool = True,
    ) -> bool:
        """Export evaluation results to JSON."""
        try:
            export = {
                'timestamp': datetime.now(timezone.utc).isoformat(),
                'n_evaluations': len(self.results_history),
            }
            
            if include_history and self.results_history:
                export['history'] = self.results_history
                
                # Summary stats
                export['summary'] = {
                    'avg_accuracy': np.mean([r['accuracy'] for r in self.results_history]),
                    'avg_brier': np.mean([r['brier_score'] for r in self.results_history]),
                    'avg_roc_auc': np.mean([r['roc_auc'] for r in self.results_history]),
                }
            
            with open(path, 'w') as f:
                json.dump(export, f, indent=2)
            
            logger.info(f"Results exported to {path}")
            return True
        
        except Exception as e:
            logger.error(f"Failed to export results: {e}")
            return False

    def generate_report(self) -> str:
        """Generate a text report of evaluation results."""
        if not self.results_history:
            return "No evaluation results available."
        
        latest = self.results_history[-1]
        
        lines = [
            "=" * 60,
            "MODEL EVALUATION REPORT",
            "=" * 60,
            f"Timestamp: {latest.get('timestamp', 'N/A')}",
            f"Samples: {latest.get('n_samples', 'N/A')}",
            "",
            "Core Metrics:",
            f"  Accuracy:       {latest.get('accuracy', 0):.4f}",
            f"  Brier Score:    {latest.get('brier_score', 0):.4f} (lower is better)",
            f"  Log Loss:       {latest.get('log_loss', 0):.4f}",
            f"  ROC-AUC:        {latest.get('roc_auc', 0):.4f}",
            f"  Avg Precision:  {latest.get('avg_precision', 0):.4f}",
            "",
        ]
        
        if 'calibration' in latest:
            cal = latest['calibration']
            lines.extend([
                "Calibration:",
                f"  ECE (Expected):  {cal.get('ece', 0):.4f}",
                f"  MCE (Maximum):   {cal.get('mce', 0):.4f}",
                "",
            ])
        
        if 'edge_analysis' in latest:
            edge = latest['edge_analysis']
            lines.extend([
                "Edge Analysis:",
                f"  Mean Edge:      {edge.get('mean_edge', 0):.4f}",
                f"  Std Edge:       {edge.get('std_edge', 0):.4f}",
                "",
            ])
        
        lines.append("=" * 60)
        
        return "\n".join(lines)
