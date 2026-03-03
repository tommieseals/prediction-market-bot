"""Test the sentiment scorer with various inputs."""

from ml.sentiment_nlp import SentimentScorer

def main():
    scorer = SentimentScorer()
    print(f'Backend: {scorer.backend}')
    print(f'Enabled: {scorer.enabled}')
    print()

    # Test market titles
    titles = [
        'Will Bitcoin reach $100,000 by December 2025?',
        'Trump wins 2024 presidential election',
        'Apple stock crashes amid iPhone sales decline',
        'Fed likely to cut interest rates in Q2',
        'Ukraine peace deal imminent as ceasefire holds',
    ]

    print('=== Market Title Sentiment ===')
    for title in titles:
        score = scorer.score_market(title)
        signal = 'BULLISH' if score > 0.55 else 'BEARISH' if score < 0.45 else 'NEUTRAL'
        print(f'{score:.3f} [{signal:8s}] {title}')

    print()

    # Test news aggregation
    print('=== News Aggregation ===')
    headlines = [
        'Bitcoin ETF sees record inflows',
        'Institutional investors bullish on crypto',
        'Regulatory concerns remain a headwind',
    ]
    market_key = 'bitcoin-100k'
    sentiment = scorer.ingest_news(market_key, headlines, source='news_major')
    print(f'Aggregated sentiment for {market_key}: {sentiment:.3f}')

    print()

    # Test social media
    print('=== Social Media Sentiment ===')
    tweets = [
        'BTC to the moon!',
        'This is definitely going to dump',
        'Neutral observation about market',
    ]
    for tweet in tweets:
        score = scorer.score_market(tweet)
        print(f'{score:.3f} - {tweet}')

    print()

    # Test comprehensive analysis
    print('=== Comprehensive Market Analysis ===')
    result = scorer.analyze_market_context(
        market_title='Will Tesla stock exceed $400 by March 2025?',
        description='Resolves YES if Tesla (TSLA) closes above $400 on NASDAQ.',
        news_headlines=['Tesla reports record deliveries', 'EV market faces headwinds'],
    )
    print(f"Aggregate Sentiment: {result['aggregate_sentiment']:.3f}")
    print(f"Confidence: {result['confidence']:.3f}")
    print(f"Signals: {result['signals']}")
    
    print()
    print('=== Entity Extraction ===')
    print(f"Entities: {result['entities']}")


if __name__ == '__main__':
    main()
