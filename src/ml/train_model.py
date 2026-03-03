"""
TerminatorBot - Model Training Script

Trains the XGBoost alpha model on historical market data.
Supports data loading from multiple sources, hyperparameter tuning,
and comprehensive evaluation.

Usage:
    python -m ml.train_model --data path/to/data.json
    python -m ml.train_model --fetch-historical --days 90
    python -m ml.train_model --tune-hyperparameters
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional, Dict, List, Any, Tuple

import numpy as np

# Add parent to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from ml.alpha_model import AlphaModel
from ml.feature_engine import FeatureEngine
from ml.sentiment_nlp import SentimentScorer
from platforms.base import UnifiedMarket

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
)
logger = logging.getLogger(__name__)

# Default paths
DATA_DIR = Path(__file__).parent.parent.parent / "data"
MODEL_DIR = Path(__file__).parent.parent.parent / "models"


class DataLoader:
    """Load and prepare training data from various sources."""
    
    def __init__(self, data_dir: Path | None = None):
        self.data_dir = data_dir or DATA_DIR
    
    def load_from_json(self, path: str) -> Tuple[List[UnifiedMarket], List[int]]:
        """
        Load markets and outcomes from JSON file.
        
        Expected format:
        [
            {
                "market_id": "...",
                "title": "...",
                "yes_price": 0.65,
                "no_price": 0.35,
                "volume": 10000,
                "outcome": 1  # 1 = YES won, 0 = NO won
            },
            ...
        ]
        """
        with open(path, 'r') as f:
            data = json.load(f)
        
        markets = []
        outcomes = []
        
        for item in data:
            if 'outcome' not in item:
                continue  # Skip unresolved markets
            
            market = UnifiedMarket(
                platform=item.get('platform', 'unknown'),
                market_id=item.get('market_id', str(len(markets))),
                title=item.get('title', ''),
                description=item.get('description', ''),
                yes_price=item.get('yes_price', 0.5),
                no_price=item.get('no_price', 0.5),
                volume=item.get('volume', 0),
                liquidity=item.get('liquidity', 0),
                open_interest=item.get('open_interest', 0),
                close_date=item.get('close_date'),
                category=item.get('category', ''),
            )
            markets.append(market)
            outcomes.append(item['outcome'])
        
        logger.info(f"Loaded {len(markets)} resolved markets from {path}")
        return markets, outcomes

    def load_from_csv(self, path: str) -> Tuple[List[UnifiedMarket], List[int]]:
        """Load markets from CSV file."""
        try:
            import pandas as pd
        except ImportError:
            logger.error("pandas required for CSV loading")
            return [], []
        
        df = pd.read_csv(path)
        
        required_cols = ['title', 'yes_price', 'outcome']
        for col in required_cols:
            if col not in df.columns:
                raise ValueError(f"Missing required column: {col}")
        
        markets = []
        outcomes = []
        
        for _, row in df.iterrows():
            market = UnifiedMarket(
                platform=row.get('platform', 'csv'),
                market_id=str(row.get('market_id', len(markets))),
                title=str(row['title']),
                description=str(row.get('description', '')),
                yes_price=float(row['yes_price']),
                no_price=float(row.get('no_price', 1 - row['yes_price'])),
                volume=float(row.get('volume', 0)),
                liquidity=float(row.get('liquidity', 0)),
                open_interest=float(row.get('open_interest', 0)),
                close_date=row.get('close_date'),
                category=str(row.get('category', '')),
            )
            markets.append(market)
            outcomes.append(int(row['outcome']))
        
        logger.info(f"Loaded {len(markets)} markets from CSV")
        return markets, outcomes

    def generate_synthetic_data(
        self,
        n_samples: int = 1000,
        seed: int = 42,
    ) -> Tuple[List[UnifiedMarket], List[int]]:
        """
        Generate synthetic training data for testing.
        
        Creates markets with known relationships between features
        and outcomes for model validation.
        """
        np.random.seed(seed)
        
        markets = []
        outcomes = []
        categories = ['politics', 'sports', 'crypto', 'finance', 'entertainment']
        
        for i in range(n_samples):
            # Generate base probability
            base_prob = np.random.beta(2, 2)  # Centered around 0.5
            
            # Add noise to create market price
            noise = np.random.normal(0, 0.1)
            yes_price = np.clip(base_prob + noise, 0.01, 0.99)
            
            # Generate outcome based on true probability
            outcome = int(np.random.random() < base_prob)
            
            # Generate other features
            volume = np.random.exponential(10000)
            liquidity = volume * np.random.uniform(0.5, 2.0)
            days_to_close = np.random.exponential(30)
            
            category = np.random.choice(categories)
            
            market = UnifiedMarket(
                platform='synthetic',
                market_id=f'syn_{i}',
                title=f'Synthetic market {i} about {category}?',
                description=f'This is a synthetic market for testing. Category: {category}',
                yes_price=yes_price,
                no_price=1 - yes_price,
                volume=volume,
                liquidity=liquidity,
                open_interest=volume * 0.3,
                close_date=(
                    datetime.now(timezone.utc) + timedelta(days=days_to_close)
                ).isoformat(),
                category=category,
            )
            markets.append(market)
            outcomes.append(outcome)
        
        logger.info(f"Generated {n_samples} synthetic markets")
        return markets, outcomes


def tune_hyperparameters(
    X: np.ndarray,
    y: np.ndarray,
    n_trials: int = 50,
) -> Dict[str, Any]:
    """
    Tune XGBoost hyperparameters using Optuna or GridSearch.
    
    Returns best parameters found.
    """
    try:
        import optuna
        from xgboost import XGBClassifier
        from sklearn.model_selection import cross_val_score
        
        def objective(trial):
            params = {
                'n_estimators': trial.suggest_int('n_estimators', 50, 500),
                'max_depth': trial.suggest_int('max_depth', 3, 10),
                'learning_rate': trial.suggest_float('learning_rate', 0.01, 0.3, log=True),
                'subsample': trial.suggest_float('subsample', 0.6, 1.0),
                'colsample_bytree': trial.suggest_float('colsample_bytree', 0.6, 1.0),
                'min_child_weight': trial.suggest_int('min_child_weight', 1, 10),
                'gamma': trial.suggest_float('gamma', 0, 0.5),
                'reg_alpha': trial.suggest_float('reg_alpha', 0, 1),
                'reg_lambda': trial.suggest_float('reg_lambda', 0, 1),
            }
            
            model = XGBClassifier(**params, random_state=42, eval_metric='logloss')
            scores = cross_val_score(model, X, y, cv=5, scoring='neg_brier_score')
            return -scores.mean()  # Minimize Brier score
        
        study = optuna.create_study(direction='minimize')
        study.optimize(objective, n_trials=n_trials, show_progress_bar=True)
        
        logger.info(f"Best trial: {study.best_trial.value:.4f}")
        logger.info(f"Best params: {study.best_params}")
        
        return study.best_params
    
    except ImportError:
        logger.warning("Optuna not installed, using default parameters")
        return {}


def train_model(
    markets: List[UnifiedMarket],
    outcomes: List[int],
    output_path: str | None = None,
    tune: bool = False,
    **kwargs,
) -> Dict[str, Any]:
    """
    Train the alpha model on prepared data.
    
    Args:
        markets: List of resolved markets
        outcomes: List of outcomes (1=YES, 0=NO)
        output_path: Where to save the model
        tune: Whether to tune hyperparameters
        **kwargs: Additional arguments for training
    
    Returns:
        Training metrics and results
    """
    # Initialize components
    sentiment = SentimentScorer()
    features = FeatureEngine(sentiment_scorer=sentiment)
    
    # Extract features
    logger.info("Extracting features...")
    X, indices = features.extract_batch(markets)
    y = np.array([outcomes[i] for i in indices])
    
    logger.info(f"Feature matrix shape: {X.shape}")
    logger.info(f"Label distribution: YES={y.sum()}, NO={len(y) - y.sum()}")
    
    if X.shape[0] < 50:
        logger.warning("Very small dataset, results may be unreliable")
    
    # Hyperparameter tuning
    xgb_params = {}
    if tune:
        logger.info("Tuning hyperparameters...")
        xgb_params = tune_hyperparameters(X, y)
    
    # Train model
    logger.info("Training model...")
    model = AlphaModel(
        feature_engine=features,
        model_path=output_path or str(MODEL_DIR / "alpha_xgb.pkl"),
    )
    
    metrics = model.train(X, y, save=True, calibrate=True, **xgb_params)
    
    # Print results
    print("\n" + "=" * 60)
    print("TRAINING RESULTS")
    print("=" * 60)
    print(f"Samples: {metrics.get('metadata', {}).get('n_samples', len(y))}")
    print(f"Features: {X.shape[1]}")
    print()
    print("Core Metrics:")
    print(f"  Accuracy:    {metrics.get('accuracy', 0):.4f}")
    print(f"  Brier Score: {metrics.get('brier_score', 0):.4f} (lower is better)")
    print(f"  Log Loss:    {metrics.get('log_loss', 0):.4f}")
    print(f"  ROC-AUC:     {metrics.get('roc_auc', 0):.4f}")
    print(f"  F1 Score:    {metrics.get('f1', 0):.4f}")
    print()
    print("Cross-Validation:")
    print(f"  CV Accuracy: {metrics.get('cv_accuracy_mean', 0):.4f} ± {metrics.get('cv_accuracy_std', 0):.4f}")
    print()
    
    if 'calibration' in metrics:
        print(f"Calibration (ECE): {metrics['calibration'].get('ece', 0):.4f}")
    
    if 'top_features' in metrics:
        print("\nTop 10 Features:")
        for name, importance in metrics['top_features']:
            print(f"  {name}: {importance:.4f}")
    
    print("=" * 60 + "\n")
    
    return metrics


def evaluate_model(
    model_path: str,
    test_markets: List[UnifiedMarket],
    test_outcomes: List[int],
) -> Dict[str, Any]:
    """
    Evaluate a trained model on test data.
    """
    sentiment = SentimentScorer()
    features = FeatureEngine(sentiment_scorer=sentiment)
    
    model = AlphaModel(feature_engine=features, model_path=model_path)
    if not model.load():
        logger.error("Failed to load model")
        return {'error': 'model load failed'}
    
    # Run backtest
    results = model.backtest(test_markets, test_outcomes)
    
    print("\n" + "=" * 60)
    print("EVALUATION RESULTS")
    print("=" * 60)
    print(f"Test Samples: {results.get('n_markets', 0)}")
    print(f"Brier Score:  {results.get('brier_score', 0):.4f}")
    print(f"ROC-AUC:      {results.get('roc_auc', 0):.4f}")
    
    if 'strategy' in results:
        strat = results['strategy']
        print(f"\nStrategy Performance:")
        print(f"  Total Bets:   {strat.get('total_bets', 0)}")
        print(f"  Win Rate:     {strat.get('win_rate', 0):.2%}")
        print(f"  Total P&L:    {strat.get('total_pnl', 0):.2f}")
        print(f"  Max Drawdown: {strat.get('max_drawdown', 0):.2f}")
        print(f"  Sharpe Ratio: {strat.get('sharpe_ratio', 0):.2f}")
    
    print("=" * 60 + "\n")
    
    return results


def main():
    parser = argparse.ArgumentParser(description='Train TerminatorBot Alpha Model')
    
    # Data source options
    parser.add_argument(
        '--data', '-d',
        type=str,
        help='Path to training data (JSON or CSV)',
    )
    parser.add_argument(
        '--synthetic',
        type=int,
        default=0,
        help='Generate N synthetic samples for testing',
    )
    
    # Model options
    parser.add_argument(
        '--output', '-o',
        type=str,
        help='Output path for trained model',
    )
    parser.add_argument(
        '--tune',
        action='store_true',
        help='Tune hyperparameters with Optuna',
    )
    
    # Evaluation options
    parser.add_argument(
        '--evaluate',
        type=str,
        help='Evaluate existing model on test data',
    )
    parser.add_argument(
        '--test-data',
        type=str,
        help='Path to test data for evaluation',
    )
    
    args = parser.parse_args()
    
    # Ensure directories exist
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    MODEL_DIR.mkdir(parents=True, exist_ok=True)
    
    loader = DataLoader()
    
    # Load or generate data
    if args.data:
        ext = Path(args.data).suffix.lower()
        if ext == '.json':
            markets, outcomes = loader.load_from_json(args.data)
        elif ext == '.csv':
            markets, outcomes = loader.load_from_csv(args.data)
        else:
            logger.error(f"Unsupported file format: {ext}")
            return 1
    elif args.synthetic > 0:
        markets, outcomes = loader.generate_synthetic_data(args.synthetic)
    else:
        # Default: generate synthetic data for demo
        logger.info("No data specified, generating 500 synthetic samples for demo")
        markets, outcomes = loader.generate_synthetic_data(500)
    
    # Evaluate existing model
    if args.evaluate:
        if args.test_data:
            ext = Path(args.test_data).suffix.lower()
            if ext == '.json':
                test_markets, test_outcomes = loader.load_from_json(args.test_data)
            else:
                test_markets, test_outcomes = loader.load_from_csv(args.test_data)
        else:
            # Use loaded data as test data
            test_markets, test_outcomes = markets, outcomes
        
        return 0 if evaluate_model(args.evaluate, test_markets, test_outcomes) else 1
    
    # Train model
    metrics = train_model(
        markets,
        outcomes,
        output_path=args.output,
        tune=args.tune,
    )
    
    # Save metrics
    metrics_path = MODEL_DIR / "training_metrics.json"
    with open(metrics_path, 'w') as f:
        # Convert numpy types to Python types for JSON serialization
        def convert(obj, depth=0):
            if depth > 50:
                return str(obj)  # Prevent infinite recursion
            if isinstance(obj, np.ndarray):
                return obj.tolist()
            elif isinstance(obj, np.bool_):
                return bool(obj)
            elif isinstance(obj, (np.integer, np.int64, np.int32)):
                return int(obj)
            elif isinstance(obj, (np.floating, np.float64, np.float32)):
                return float(obj)
            elif isinstance(obj, dict):
                return {str(k): convert(v, depth + 1) for k, v in obj.items()}
            elif isinstance(obj, (list, tuple)):
                return [convert(v, depth + 1) for v in obj]
            elif hasattr(obj, '__dict__'):
                return str(type(obj).__name__)  # Skip complex objects
            return obj
        
        json.dump(convert(metrics), f, indent=2)
    logger.info(f"Metrics saved to {metrics_path}")
    
    return 0


if __name__ == '__main__':
    sys.exit(main())
