async (page) => {
    await page.goto('https://app.getzep.com');
    await page.waitForTimeout(2000);
    await page.click('button:has-text("Sign Up")');
    await page.waitForTimeout(3000);
    await page.screenshot({ path: 'C:/Users/USER/clawd/zep-signup.png', fullPage: true });
    return page.url();
}