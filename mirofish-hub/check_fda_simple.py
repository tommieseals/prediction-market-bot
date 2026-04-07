"""
Simple FDA PDUFA Calendar Checker
No MiroFish dependency - just read the database directly
"""
import sqlite3
from datetime import datetime, timedelta

def check_fda_calendar():
    """Check for upcoming PDUFA dates in the next 14 days."""
    try:
        conn = sqlite3.connect('C:/Users/USER/clawd/mirofish-hub/outcomes.db')
        cur = conn.cursor()
        
        # Get upcoming catalysts
        cur.execute('''
            SELECT ticker, drug, pdufa_date, base_probability 
            FROM fda_catalysts 
            WHERE pdufa_date BETWEEN date('now') AND date('now', '+14 days')
            ORDER BY pdufa_date
        ''')
        
        catalysts = cur.fetchall()
        conn.close()
        
        if not catalysts:
            print("No FDA PDUFAs in next 14 days")
            return
        
        print(f"\n{'='*60}")
        print(f"FDA PDUFA CALENDAR - Next 14 Days")
        print(f"{'='*60}\n")
        
        for ticker, drug, pdufa_date, base_prob in catalysts:
            # Calculate days until PDUFA
            pdufa_dt = datetime.strptime(pdufa_date, '%Y-%m-%d')
            days_out = (pdufa_dt - datetime.now()).days
            
            # Determine urgency
            if days_out <= 1:
                urgency = "[!!] TOMORROW"
            elif days_out <= 3:
                urgency = "[**] IMMINENT"
            elif days_out <= 7:
                urgency = "[**] HEADS UP"
            else:
                urgency = "[OK] ON RADAR"
            
            print(f"{urgency} - T-{days_out}")
            print(f"${ticker} {drug}")
            print(f"PDUFA: {pdufa_date}")
            print(f"Base: {base_prob}%")
            print()
        
        print(f"{'='*60}\n")
        
    except Exception as e:
        print(f"Error checking FDA calendar: {e}")

if __name__ == "__main__":
    check_fda_calendar()
