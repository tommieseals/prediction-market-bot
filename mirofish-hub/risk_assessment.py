"""
Risk Assessment Tool
====================
Assess risk for a given market based on our data.
"""
import sqlite3
from datetime import datetime

DB_PATH = 'data/whale_hunter.db'


def assess_market_risk(conn, market_title_or_condition):
    """Assess risk for a market."""
    cur = conn.cursor()
    
    # Find market
    cur.execute('''
        SELECT DISTINCT market_title, condition_id, side
        FROM whale_positions
        WHERE market_title LIKE ? OR condition_id LIKE ?
        LIMIT 5
    ''', (f'%{market_title_or_condition}%', f'%{market_title_or_condition}%'))
    
    markets = cur.fetchall()
    if not markets:
        return None
    
    market = markets[0][0]
    condition_id = markets[0][1]
    
    assessment = {
        'market': market,
        'condition_id': condition_id,
        'risk_score': 50,  # Base risk (50/100)
        'factors': []
    }
    
    # Factor 1: Whale count
    cur.execute('''
        SELECT COUNT(DISTINCT address), side
        FROM whale_positions
        WHERE market_title = ?
        GROUP BY side
    ''', (market,))
    
    whale_sides = {}
    for count, side in cur.fetchall():
        whale_sides[side] = count
    
    total_whales = sum(whale_sides.values())
    
    if total_whales >= 7:
        assessment['risk_score'] += 20
        assessment['factors'].append(f"HIGH RISK: {total_whales} whales (>7 = bad)")
    elif total_whales >= 5:
        assessment['risk_score'] += 10
        assessment['factors'].append(f"ELEVATED: {total_whales} whales")
    else:
        assessment['factors'].append(f"OK: {total_whales} whales")
    
    # Factor 2: Elite whale presence
    cur.execute('''
        SELECT COUNT(*) FROM whale_positions p
        JOIN elite_whales e ON p.address = e.address
        WHERE p.market_title = ?
    ''', (market,))
    elite_count = cur.fetchone()[0]
    
    if elite_count >= 3:
        assessment['risk_score'] -= 15
        assessment['factors'].append(f"GOOD: {elite_count} elite whales")
    elif elite_count >= 1:
        assessment['risk_score'] -= 5
        assessment['factors'].append(f"OK: {elite_count} elite whale(s)")
    else:
        assessment['risk_score'] += 10
        assessment['factors'].append("RISK: No elite whales")
    
    # Factor 3: Category
    t = market.lower()
    if 'politics' in t or 'election' in t:
        assessment['risk_score'] += 15
        assessment['factors'].append("HIGH RISK: Politics category")
    elif 'tennis' in t or 'spread' in t:
        assessment['risk_score'] -= 10
        assessment['factors'].append("GOOD: Favorable category")
    
    # Factor 4: Agreement (one-sided = risky)
    if whale_sides:
        max_side = max(whale_sides.values())
        min_side = min(whale_sides.values()) if len(whale_sides) > 1 else 0
        if max_side > 0 and min_side == 0:
            assessment['risk_score'] -= 5  # All on one side is actually slightly better
            assessment['factors'].append("One-sided whale agreement")
    
    # Factor 5: Day of week
    dow = datetime.now().weekday()
    if dow in [3, 4]:  # Thu, Fri
        assessment['risk_score'] += 10
        assessment['factors'].append("ELEVATED: Trading on Thu/Fri")
    elif dow in [0, 1, 2]:  # Mon, Tue, Wed
        assessment['risk_score'] -= 5
        assessment['factors'].append("GOOD: Mon-Wed trading")
    
    # Clamp risk score
    assessment['risk_score'] = max(0, min(100, assessment['risk_score']))
    
    # Overall rating
    if assessment['risk_score'] >= 70:
        assessment['rating'] = 'HIGH RISK'
    elif assessment['risk_score'] >= 50:
        assessment['rating'] = 'MODERATE'
    else:
        assessment['rating'] = 'LOW RISK'
    
    return assessment


def print_assessment(assessment):
    """Print risk assessment."""
    if not assessment:
        print("Market not found")
        return
    
    print('=' * 60)
    print('RISK ASSESSMENT')
    print('=' * 60)
    print(f'\nMarket: {assessment["market"][:50]}...')
    print(f'\nRisk Score: {assessment["risk_score"]}/100')
    print(f'Rating: {assessment["rating"]}')
    print(f'\nFactors:')
    for f in assessment['factors']:
        print(f'  • {f}')
    
    print()
    if assessment['rating'] == 'HIGH RISK':
        print('⚠️ RECOMMENDATION: Avoid or reduce position size')
    elif assessment['rating'] == 'MODERATE':
        print('⚡ RECOMMENDATION: Trade with caution')
    else:
        print('✅ RECOMMENDATION: Favorable conditions')


def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('market', nargs='?', help='Market title or condition ID')
    args = parser.parse_args()
    
    if not args.market:
        print("Usage: python risk_assessment.py <market_title>")
        print("Example: python risk_assessment.py 'Miami Open'")
        return
    
    conn = sqlite3.connect(DB_PATH)
    assessment = assess_market_risk(conn, args.market)
    print_assessment(assessment)
    conn.close()


if __name__ == '__main__':
    main()
