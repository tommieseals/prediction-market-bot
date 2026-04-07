import requests

# Test CLOB API directly
print("Testing Polymarket CLOB API...")
try:
    r = requests.get('https://clob.polymarket.com/markets?limit=1', timeout=10)
    print(f'CLOB Status: {r.status_code}')
    if r.status_code == 403:
        print('BLOCKED - Need different IP/region')
    else:
        print('API ACCESSIBLE!')
except Exception as e:
    print(f'Error: {e}')

# Show current IP
print("\nChecking IP...")
r2 = requests.get('https://ipinfo.io/json', timeout=10)
ip_info = r2.json()
print(f"IP: {ip_info.get('ip')}")
print(f"Location: {ip_info.get('city')}, {ip_info.get('country')}")
print(f"ASN: {ip_info.get('org')}")
