import requests
import json

payload = {
    'title': 'Test NBA Game',
    'description': 'Simulate public discourse about Lakers vs Celtics NBA game prediction',
    'skip_zep': True
}

print("Testing /api/graph/ontology/generate...")
print(f"Payload: {json.dumps(payload, indent=2)}")
print()

try:
    r = requests.post(
        'http://localhost:5001/api/graph/ontology/generate', 
        json=payload,
        timeout=180
    )
    print(f"Status: {r.status_code}")
    
    if r.status_code == 200:
        data = r.json()
        print(f"Success!")
        print(f"Project ID: {data.get('project_id')}")
        print(f"Entity count: {data.get('entity_count')}")
        print(f"Relation count: {data.get('relation_count')}")
    else:
        print(f"Error Response:")
        try:
            err = r.json()
            print(json.dumps(err, indent=2))
        except:
            print(r.text[:2000])
            
except requests.exceptions.Timeout:
    print("TIMEOUT after 180 seconds!")
except Exception as e:
    print(f"Exception: {type(e).__name__}: {e}")
