#!/usr/bin/env python3
from playwright.sync_api import sync_playwright
import time

with sync_playwright() as p:
    browser = p.chromium.connect_over_cdp("http://localhost:9223")
    contexts = browser.contexts
    if contexts:
        context = contexts[0]
        
        # Open Indeed in new tab
        page = context.new_page()
        print("Opening Indeed...")
        page.goto("https://www.indeed.com/", wait_until="domcontentloaded", timeout=30000)
        time.sleep(3)
        
        print(f"Current URL: {page.url}")
        
        # Check login status
        content = page.content()
        if "Sign Out" in content or "signout" in content.lower() or "profile" in content.lower():
            print("✅ Indeed: LOGGED IN")
            
            # Try to find account name
            try:
                account_el = page.query_selector('[data-gnav-element-name="Account"]')
                if account_el:
                    print(f"Account element found")
            except:
                pass
        elif "Sign in" in content or "signin" in content.lower():
            print("⚠️ Indeed: NOT LOGGED IN - needs manual login")
        else:
            print("? Indeed: Login status unclear")
        
        print(f"\nTab URL: {page.url}")
