# -*- coding: utf-8 -*-
"""Full code audit - find all issues"""
import os
import re
import sys

sys.stdout.reconfigure(encoding='utf-8', errors='replace')

issues = []

def check_file(filepath):
    """Check a Python file for common issues."""
    try:
        with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
            content = f.read()
            lines = content.split('\n')
    except (IOError, OSError):  # H12 FIX: File read errors
        return
    
    filename = os.path.basename(filepath)
    
    # Check for hardcoded secrets
    secret_patterns = [
        (r'api[_-]?key\s*=\s*["\'][^"\']{20,}["\']', 'Hardcoded API key'),
        (r'token\s*=\s*["\'][^"\']{20,}["\']', 'Hardcoded token'),
        (r'password\s*=\s*["\'][^"\']+["\']', 'Hardcoded password'),
        (r'0x[a-fA-F0-9]{64}', 'Possible private key'),
    ]
    
    for pattern, desc in secret_patterns:
        matches = re.findall(pattern, content, re.IGNORECASE)
        if matches:
            issues.append(f"[SECURITY] {filename}: {desc} found")
    
    # Check for TODO/FIXME/HACK comments
    for i, line in enumerate(lines, 1):
        if 'TODO' in line or 'FIXME' in line or 'HACK' in line:
            clean = line.strip()[:60]
            issues.append(f"[TODO] {filename}:{i}: {clean}")
    
    # Check for bare except
    if 'except:' in content:
        issues.append(f"[CODE] {filename}: Bare except clause (hides errors)")
    
    # Check for print statements in production code (not debug)
    print_count = len(re.findall(r'\bprint\s*\(', content))
    if print_count > 20:
        issues.append(f"[CODE] {filename}: {print_count} print statements (consider logging)")
    
    # Check for hardcoded IPs
    ips = re.findall(r'\b\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}\b', content)
    if len(ips) > 5:
        issues.append(f"[CONFIG] {filename}: {len(ips)} hardcoded IPs")
    
    # Check for hardcoded paths
    if 'C:\\Users\\' in content or '/Users/' in content:
        issues.append(f"[CONFIG] {filename}: Hardcoded user paths")
    
    # Check for time.sleep > 60 seconds
    sleeps = re.findall(r'time\.sleep\s*\(\s*(\d+)', content)
    long_sleeps = [s for s in sleeps if int(s) > 60]
    if long_sleeps:
        issues.append(f"[PERF] {filename}: Long sleep() calls: {long_sleeps}s")
    
    # Check for missing error handling on requests
    if 'requests.get' in content or 'requests.post' in content:
        if 'try:' not in content or 'except' not in content:
            issues.append(f"[CODE] {filename}: requests calls without error handling")
    
    # Check file size
    size_kb = len(content) / 1024
    if size_kb > 50:
        issues.append(f"[SIZE] {filename}: Large file ({size_kb:.1f}KB) - consider splitting")

# Scan all Python files
print("=" * 60)
print("FULL CODE AUDIT")
print("=" * 60)

py_files = []
for root, dirs, files in os.walk('.'):
    # Skip venv and __pycache__
    dirs[:] = [d for d in dirs if d not in ['venv', '__pycache__', '.git', 'node_modules']]
    for f in files:
        if f.endswith('.py'):
            py_files.append(os.path.join(root, f))

print(f"\nScanning {len(py_files)} Python files...\n")

for pf in py_files:
    check_file(pf)

# Categorize and print
print("=" * 60)
print(f"ISSUES FOUND: {len(issues)}")
print("=" * 60)

categories = {}
for issue in issues:
    cat = issue.split(']')[0] + ']'
    if cat not in categories:
        categories[cat] = []
    categories[cat].append(issue)

for cat in sorted(categories.keys()):
    print(f"\n{cat} ({len(categories[cat])} issues)")
    print("-" * 40)
    for i in categories[cat][:10]:  # Show first 10 per category
        print(f"  {i}")
    if len(categories[cat]) > 10:
        print(f"  ... and {len(categories[cat]) - 10} more")

print("\n" + "=" * 60)
print("AUDIT COMPLETE")
print("=" * 60)
