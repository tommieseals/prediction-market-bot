"""
Elite Whale Tracker
===================
Track the TOP performing individual whales and alert on their moves.
No consensus - just follow the best.

Top 5 Whales (100% WR, 194 bets):
1. COMEONDUDE - 30W/0L
2. joosangyoo - 26W/0L  
3. UnfortunateSon - 52W/0L
4. 0x1bdd0465... - 50W/0L
5. 0x3333F4A3... - 36W/0L
"""
import sqlite3
from datetime import datetime, timedelta
import json
import os
import requests

DB_PATH = 'data/whale_hunter.db'
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "8392398778:AAH5lan45kR-VT74d3OiXAAIxlPyR4skGzU")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "939543801")

def get_elite_whales(conn, min_bets=20, min_wr=0.90):
    """Get elite whales with proven track records."""
    cur = conn.cursor()
    
    cur.execute('''
        SELECT w.address, w.display_name, w.elite_score, w.pnl,
               COUNT(*) as bets,
               SUM(CASE WHEN p.outcome='won' THEN 1 ELSE 0 END) as won,
               SUM(CASE WHEN p.outcome='lost' THEN 1 ELSE 0 END) as lost
        FROM tracked_whales w
        JOIN whale_positions p ON w.address = p.address
        WHERE p.outcome IN ('won', 'lost')
        GROUP BY w.address
        HAVING bets >= ? AND (won * 1.0 / (won + lost)) >= ?
        ORDER BY (won * 1.0 / (won + lost)) DESC, bets DESC
    ''', (min_bets, min_wr))
    
    elites = []
    for row in cur.fetchall():
        addr, name, elite, pnl, bets, won, lost = row
        elites.append({
            'address': addr,
            'name': name or addr[:12],
            'elite_score': elite or 0,
            'pnl': pnl or 0,
            'bets': bets,
            'won': won,
            'lost': lost,
            'win_rate': won / (won + lost) if (won + lost) > 0 else 0
        })
    
    return elites


def get_elite_positions(conn, addresses, hours=24):
    """Get recent positions from elite whales."""
    cur = conn.cursor()
    
    since = (datetime.utcnow() - timedelta(hours=hours)).isoformat()
    
    placeholders = ','.join(['?' for _ in addresses])
    cur.execute(f'''
        SELECT p.address, p.market_title, p.side, p.size_usd, 
               p.entry_price, p.detected_at, p.outcome,
               w.display_name
        FROM whale_positions p
        JOIN tracked_whales w ON p.address = w.address
        WHERE p.address IN ({placeholders})
        AND p.detected_at >= ?
        ORDER BY p.detected_at DESC
    ''', addresses + [since])
    
    return cur.fetchall()


def save_elite_list(conn, elites):
    """Save elite whale list to database."""
    cur = conn.cursor()
    
    cur.execute('''
        CREATE TABLE IF NOT EXISTS elite_whales (
            address TEXT PRIMARY KEY,
            name TEXT,
            win_rate REAL,
            bets INTEGER,
            won INTEGER,
            lost INTEGER,
            pnl REAL,
            tier TEXT,
            updated_at TEXT
        )
    ''')
    
    for e in elites:
        tier = 'LEGENDARY' if e['win_rate'] == 1.0 else 'ELITE' if e['win_rate'] >= 0.95 else 'TOP'
        cur.execute('''
            INSERT OR REPLACE INTO elite_whales 
            (address, name, win_rate, bets, won, lost, pnl, tier, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            e['address'], e['name'], e['win_rate'], e['bets'],
            e['won'], e['lost'], e['pnl'], tier, datetime.now().isoformat()
        ))
    
    conn.commit()


def send_alert(message):
    """Send alert to Telegram."""
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    try:
        requests.post(url, json={
            "chat_id": TELEGRAM_CHAT_ID,
            "text": message,
            "parse_mode": "Markdown"
        }, timeout=10)
        return True
    except:
        return False


def generate_elite_report(elites, positions):
    """Generate elite whale report."""
    report = f"""⭐ *ELITE WHALE TRACKER*
_{datetime.now().strftime('%Y-%m-%d %H:%M CDT')}_

These whales have 90%+ win rate on 20+ bets.
Follow them INDIVIDUALLY, not consensus.

"""
    
    # Legendary tier (100% WR)
    legendaries = [e for e in elites if e['win_rate'] == 1.0]
    if legendaries:
        report += "*🏆 LEGENDARY (100% WR):*\n"
        for e in legendaries[:5]:
            report += f"• {e['name']}: {e['won']}/{e['bets']} = {e['win_rate']*100:.0f}%\n"
        report += "\n"
    
    # Elite tier (95%+ WR)
    elite_tier = [e for e in elites if 0.95 <= e['win_rate'] < 1.0]
    if elite_tier:
        report += "*⭐ ELITE (95%+ WR):*\n"
        for e in elite_tier[:5]:
            report += f"• {e['name']}: {e['won']}/{e['bets']} = {e['win_rate']*100:.1f}%\n"
        report += "\n"
    
    # Recent positions
    if positions:
        report += "*📊 Recent Moves (24h):*\n"
        seen_markets = set()
        for pos in positions[:5]:
            addr, market, side, size, price, detected, outcome, name = pos
            if market not in seen_markets:
                market_short = market[:40] + '...' if len(market) > 40 else market
                report += f"• {name}: {side} on {market_short}\n"
                seen_markets.add(market)
    
    report += "\n_These whales are the real edge. Not consensus._"
    
    return report


def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('--report', action='store_true', help='Generate and send report')
    parser.add_argument('--scan', action='store_true', help='Scan for new elite moves')
    parser.add_argument('--list', action='store_true', help='List elite whales')
    args = parser.parse_args()
    
    conn = sqlite3.connect(DB_PATH)
    
    # Get elite whales
    elites = get_elite_whales(conn)
    
    # Save to database
    save_elite_list(conn, elites)
    
    if args.list or not any([args.report, args.scan]):
        print('=' * 70)
        print('ELITE WHALE TRACKER')
        print('=' * 70)
        print(f'\nFound {len(elites)} elite whales (90%+ WR, 20+ bets)')
        print()
        print(f'{"Name":<25} {"WR":<8} {"W/L":<12} {"PnL":<15} {"Tier"}')
        print('-' * 70)
        for e in elites[:25]:
            wr = f"{e['win_rate']*100:.1f}%"
            wl = f"{e['won']}/{e['lost']}"
            pnl = f"${e['pnl']:,.0f}" if e['pnl'] else '$0'
            tier = 'LEGENDARY' if e['win_rate'] == 1.0 else 'ELITE' if e['win_rate'] >= 0.95 else 'TOP'
            print(f"{e['name'][:23]:<25} {wr:<8} {wl:<12} {pnl:<15} {tier}")
    
    if args.report:
        addresses = [e['address'] for e in elites[:10]]
        positions = get_elite_positions(conn, addresses, hours=24)
        report = generate_elite_report(elites, positions)
        print(report)
        send_alert(report)
        print("\nReport sent to Telegram!")
    
    if args.scan:
        print("Scanning for new elite moves...")
        addresses = [e['address'] for e in elites[:10]]
        positions = get_elite_positions(conn, addresses, hours=1)
        
        if positions:
            print(f"Found {len(positions)} new positions from elite whales")
            for pos in positions:
                addr, market, side, size, price, detected, outcome, name = pos
                print(f"  {name}: {side} on {market[:50]}...")
        else:
            print("No new moves in the last hour")
    
    conn.close()


if __name__ == '__main__':
    main()
