import os
import json
import time
from playwright.sync_api import sync_playwright

def get_fresh_cookies():
    email = os.environ.get("GMAIL_EMAIL")
    password = os.environ.get("GMAIL_PASSWORD")
    
    if not email or not password:
        raise Exception("GMAIL_EMAIL or GMAIL_PASSWORD not set in environment")
    
    with sync_playwright() as p:
        # Launch with specific args to avoid detection
        browser = p.chromium.launch(
            headless=True,
            args=[
                '--no-sandbox',
                '--disable-dev-shm-usage',
                '--disable-blink-features=AutomationControlled',
                '--disable-gpu'
            ]
        )
        context = browser.new_context(
            user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        )
        page = context.new_page()
        
        print("[INFO] Logging into Google...")
        
        # Go to Google login
        page.goto("https://accounts.google.com/signin")
        page.wait_for_timeout(3000)
        
        # Use the specific ID Google uses for email
        try:
            page.fill("#identifierId", email)
        except:
            # Fallback: try the generic input
            page.fill("input[type='email']", email)
        
        page.click("button:has-text('Next')")
        page.wait_for_timeout(3000)
        
        # Wait for password field to appear
        try:
            page.wait_for_selector("input[type='password']", timeout=10000)
        except:
            # Fallback: try the password input by name
            page.wait_for_selector("input[name='Passwd']", timeout=10000)
        
        # Fill password
        try:
            page.fill("input[type='password']", password)
        except:
            page.fill("input[name='Passwd']", password)
        
        page.click("button:has-text('Next')")
        page.wait_for_timeout(5000)
        
        # Navigate to YouTube to complete the session
        print("[INFO] Navigating to YouTube...")
        page.goto("https://www.youtube.com")
        page.wait_for_timeout(3000)
        
        # Navigate to YouTube Studio to ensure upload session
        page.goto("https://studio.youtube.com")
        page.wait_for_timeout(3000)
        
        # Extract cookies
        cookies = context.cookies()
        
        # Save cookies in Netscape format for yt-dlp
        print("[INFO] Saving cookies...")
        with open("cookies.txt", "w") as f:
            f.write("# Netscape HTTP Cookie File\n")
            for cookie in cookies:
                domain = cookie.get('domain', '')
                flag = 'TRUE' if domain.startswith('.') else 'FALSE'
                path = cookie.get('path', '/')
                secure = 'TRUE' if cookie.get('secure', False) else 'FALSE'
                expiry = int(cookie.get('expires', time.time() + 31536000))
                name = cookie.get('name', '')
                value = cookie.get('value', '')
                f.write(f"{domain}\t{flag}\t{path}\t{secure}\t{expiry}\t{name}\t{value}\n")
        
        # Also save as JSON for Playwright upload
        with open("cookies.json", "w") as f:
            json.dump(cookies, f)
        
        print("[INFO] Cookies saved successfully!")
        print(f"[INFO] Total cookies saved: {len(cookies)}")
        browser.close()
        return cookies

if __name__ == "__main__":
    get_fresh_cookies()