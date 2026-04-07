"""Test Groq LLM speed directly"""
import os
import sys
import time

# Add mirofish to path
sys.path.insert(0, r'C:\Users\USER\Desktop\mirofish-secure\backend')

from dotenv import load_dotenv
load_dotenv(r'C:\Users\USER\Desktop\mirofish-secure\.env', override=True)

from openai import OpenAI

api_key = os.getenv('LLM_API_KEY')
base_url = os.getenv('LLM_BASE_URL')
model = os.getenv('LLM_MODEL_NAME')

print(f'Config:')
print(f'  Base URL: {base_url}')
print(f'  Model: {model}')
print(f'  Key: {api_key[:20] if api_key else "MISSING"}...')

if not api_key:
    print("ERROR: No API key!")
    sys.exit(1)

client = OpenAI(api_key=api_key, base_url=base_url)

print('\nTesting LLM speed with complex prompt...')
start = time.time()

# Simulate a report-style prompt
prompt = """You are writing a prediction report. Based on the following simulated data, 
write a detailed analysis paragraph about public sentiment:

Simulated Data:
- 45% of users expressed concern about market volatility
- 30% showed optimism about long-term growth
- 25% were neutral or undecided
- Key topics: inflation, interest rates, tech stocks

Write a professional analysis paragraph (150-200 words)."""

response = client.chat.completions.create(
    model=model,
    messages=[{'role': 'user', 'content': prompt}],
    max_tokens=400
)
elapsed = time.time() - start

tokens = response.usage.total_tokens if response.usage else 0
tok_per_sec = tokens / elapsed if elapsed > 0 else 0

print(f'\n[OK] Response in {elapsed:.2f}s')
print(f'Tokens: {tokens} ({tok_per_sec:.0f} tok/s)')
print(f'\nOutput:\n{response.choices[0].message.content[:500]}')

if elapsed < 3:
    print('\n[EXCELLENT] Groq is FAST!')
elif elapsed < 10:
    print('\n[GOOD] Acceptable speed')
else:
    print('\n[SLOW] Something may be wrong')
