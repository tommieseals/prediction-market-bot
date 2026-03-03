"""
TerminatorBot ML Module

Machine learning components for prediction market analysis:
- AlphaModel: XGBoost prediction model with backtesting
- FeatureEngine: Feature extraction from market data
- SentimentScorer: NLP sentiment analysis
- ModelEvaluator: Comprehensive model evaluation
"""

from ml.alpha_model import AlphaModel
from ml.feature_engine import FeatureEngine
from ml.sentiment_nlp import SentimentScorer
from ml.evaluator import ModelEvaluator

__all__ = [
    'AlphaModel',
    'FeatureEngine',
    'SentimentScorer',
    'ModelEvaluator',
]
