"""
Zep Sign Up Browser Automation
"""
import asyncio
from playwright.async_api import async_playwright

async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False)
        page = await browser.new_page()
        
        print("Navigating to Zep...")
        await page.goto('https://app.getzep.com')
        await page.wait_for_timeout(2000)
        
        print("Clicking Sign Up...")
        await page.click('button:has-text("Sign Up")')
        await page.wait_for_timeout(3000)
        
        print(f"Current URL: {page.url}")
        await page.screenshot(path='C:/Users/USER/clawd/zep-signup.png', full_page=True)
        print("Screenshot saved to zep-signup.png")
        
        # Get snapshot of the page
        html = await page.content()
        # Look for the signup form structure
        inputs = await page.query_selector_all('input')
        print(f"Found {len(inputs)} input fields")
        
        for i, inp in enumerate(inputs):
            input_type = await inp.get_attribute('type')
            input_name = await inp.get_attribute('name')
            input_placeholder = await inp.get_attribute('placeholder')
            print(f"  Input {i}: type={input_type}, name={input_name}, placeholder={input_placeholder}")
        
        # Look for OAuth buttons
        buttons = await page.query_selector_all('button')
        for btn in buttons:
            text = await btn.inner_text()
            if text.strip():
                print(f"  Button: {text.strip()}")
        
        # Keep browser open 
        print("\nBrowser will stay open for 60 seconds so Rusty can see...")
        await page.wait_for_timeout(60000)
        
        await browser.close()

if __name__ == "__main__":
    asyncio.run(main())
