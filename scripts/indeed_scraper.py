#!/usr/bin/env python3
"""
Indeed Easy Apply Job Scraper for Legion V3
Scrapes jobs and adds them to the PENDING queue.
"""

import argparse
import json
import hashlib
import time
from datetime import datetime
from pathlib import Path
from playwright.sync_api import sync_playwright

QUEUE_DIR = Path.home() / "legion-v3" / "PENDING"

def generate_job_id(url):
    """Generate unique job ID from URL"""
    return "indeed-" + hashlib.md5(url.encode()).hexdigest()[:16]

def scrape_indeed_jobs(query: str, location: str = "", max_jobs: int = 20):
    """Scrape Indeed for Easy Apply jobs"""
    
    with sync_playwright() as p:
        browser = p.chromium.connect_over_cdp("http://localhost:9223")
        contexts = browser.contexts
        if not contexts:
            print("❌ No browser contexts found")
            return []
        
        context = contexts[0]
        page = context.new_page()
        
        # Build search URL
        search_url = f"https://www.indeed.com/jobs?q={query.replace(' ', '+')}"
        if location:
            search_url += f"&l={location.replace(' ', '+')}"
        # Filter for Easy Apply jobs (indeedApply=1)
        search_url += "&indeedApply=1"
        
        print(f"🔍 Searching: {search_url}")
        page.goto(search_url, wait_until="domcontentloaded", timeout=60000)
        time.sleep(3)
        
        # Check for Cloudflare
        if "challenge" in page.url or "blocked" in page.content().lower():
            print("⚠️ Cloudflare challenge detected - may need manual solve")
            time.sleep(5)
        
        jobs = []
        
        # Find job cards
        job_cards = page.query_selector_all('[class*="job_seen_beacon"], .jobsearch-ResultsList > li')
        print(f"📋 Found {len(job_cards)} job cards")
        
        for i, card in enumerate(job_cards[:max_jobs]):
            try:
                # Get job title
                title_el = card.query_selector('h2 a, [class*="jobTitle"] a, a[data-jk]')
                if not title_el:
                    continue
                    
                title = title_el.inner_text().strip()
                href = title_el.get_attribute('href')
                
                if not href:
                    continue
                
                # Build full URL
                if href.startswith('/'):
                    job_url = f"https://www.indeed.com{href}"
                else:
                    job_url = href
                
                # Get company name
                company_el = card.query_selector('[data-testid="company-name"], .companyName, [class*="company"]')
                company = company_el.inner_text().strip() if company_el else "Unknown"
                
                # Get location
                loc_el = card.query_selector('[data-testid="text-location"], .companyLocation, [class*="location"]')
                job_location = loc_el.inner_text().strip() if loc_el else ""
                
                # Check for Easy Apply badge
                easy_apply = card.query_selector('[class*="iaLabel"], [aria-label*="Easily apply"]')
                
                job_id = generate_job_id(job_url)
                
                job_data = {
                    "id": job_id,
                    "platform": "indeed",
                    "title": title,
                    "company": company,
                    "location": job_location,
                    "url": job_url,
                    "easy_apply": bool(easy_apply),
                    "status": "PENDING",
                    "discovered_at": datetime.now().isoformat(),
                    "created_at": datetime.now().isoformat()
                }
                
                jobs.append(job_data)
                print(f"  ✓ {title[:50]} @ {company[:30]}")
                
            except Exception as e:
                print(f"  ⚠️ Error parsing card {i}: {e}")
                continue
        
        page.close()
        return jobs

def save_jobs_to_queue(jobs):
    """Save jobs to PENDING queue as JSON files"""
    QUEUE_DIR.mkdir(parents=True, exist_ok=True)
    
    saved = 0
    skipped = 0
    
    for job in jobs:
        job_file = QUEUE_DIR / f"{job['id']}.json"
        
        if job_file.exists():
            skipped += 1
            continue
        
        with open(job_file, 'w') as f:
            json.dump(job, f, indent=2)
        saved += 1
    
    return saved, skipped

def main():
    parser = argparse.ArgumentParser(description='Scrape Indeed Easy Apply jobs')
    parser.add_argument('--query', '-q', required=True, help='Search query')
    parser.add_argument('--location', '-l', default='', help='Location filter')
    parser.add_argument('--max', '-m', type=int, default=20, help='Max jobs to scrape')
    parser.add_argument('--dry-run', action='store_true', help='Print jobs without saving')
    args = parser.parse_args()
    
    print(f"\n🚀 Indeed Easy Apply Scraper")
    print(f"   Query: {args.query}")
    print(f"   Location: {args.location or 'Any'}")
    print(f"   Max jobs: {args.max}\n")
    
    jobs = scrape_indeed_jobs(args.query, args.location, args.max)
    
    if not jobs:
        print("\n❌ No jobs found")
        return
    
    print(f"\n📊 Found {len(jobs)} jobs")
    
    if args.dry_run:
        print("\n[DRY RUN - not saving]")
        for job in jobs:
            print(f"  - {job['title']} @ {job['company']}")
    else:
        saved, skipped = save_jobs_to_queue(jobs)
        print(f"\n✅ Saved {saved} jobs to queue")
        if skipped:
            print(f"   (Skipped {skipped} duplicates)")
        print(f"   Queue: {QUEUE_DIR}")

if __name__ == "__main__":
    main()
