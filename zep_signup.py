"""
Zep Sign Up Automation
Navigate to Zep, click Sign Up, and capture the signup form
"""
import subprocess
import time
import json

def run_mcporter(code):
    """Run mcporter browser command"""
    # Navigate first
    result = subprocess.run(
        ['mcporter', 'call', 'browser.browser_run_code', f'code={code}'],
        capture_output=True, text=True, timeout=60
    )
    return result.stdout + result.stderr

# Step 1: Navigate and click Sign Up
code = """async (page) => {
    await page.goto('https://app.getzep.com');
    await page.waitForTimeout(2000);
    
    // Click Sign Up button
    await page.click('button:has-text("Sign Up")');
    await page.waitForTimeout(3000);
    
    // Screenshot the signup form
    await page.screenshot({ path: 'C:/Users/USER/clawd/zep-signup.png', fullPage: true });
    
    // Return page title and URL
    return JSON.stringify({
        title: await page.title(),
        url: page.url()
    });
}"""

print("Navigating to Zep and clicking Sign Up...")
result = run_mcporter(code)
print(result)
