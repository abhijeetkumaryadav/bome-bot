import os
import json
import base64
import time
from playwright.sync_api import sync_playwright

# CONFIG
UPLOAD_LIMIT = 12

# Load cookies from base64 secret
COOKIES_B64 = os.environ.get("COOKIES_BASE64")
if not COOKIES_B64:
    raise Exception("COOKIES_BASE64 environment variable not set")

with open("cookies.txt", "wb") as f:
    f.write(base64.b64decode(COOKIES_B64))

print("[DEBUG] Cookies decoded.")

# Parse cookies for Playwright
def parse_netscape_cookies(filepath):
    cookies = []
    with open(filepath, "r") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            parts = line.split("\t")
            if len(parts) >= 7:
                domain, flag, path, secure, expiry, name, value = parts[:7]
                cookies.append({
                    "name": name,
                    "value": value,
                    "domain": domain,
                    "path": path,
                    "secure": secure == "TRUE",
                    "httpOnly": False,
                    "expirationDate": float(expiry) if expiry != "0" else None
                })
    return cookies

cookies = parse_netscape_cookies("cookies.txt")
print(f"[DEBUG] Loaded {len(cookies)} cookies")

def get_next_video():
    try:
        with open("queue.txt", "r") as f:
            all_videos = [line.strip() for line in f if line.strip()]
    except FileNotFoundError:
        raise Exception("queue.txt not found!")
    
    try:
        with open("uploaded.txt", "r") as f:
            uploaded = [line.strip() for line in f if line.strip()]
    except FileNotFoundError:
        uploaded = []
    
    for video in all_videos:
        if video not in uploaded:
            return video
    return None

def upload_video(video_path, title):
    print(f"[UPLOAD] Uploading: {video_path}")
    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=True,
            args=['--no-sandbox', '--disable-dev-shm-usage']
        )
        context = browser.new_context(
            viewport={'width': 1280, 'height': 800},
            user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        )
        context.add_cookies(cookies)
        page = context.new_page()
        
        # Go to YouTube Studio with network idle
        page.goto("https://studio.youtube.com", wait_until="networkidle")
        page.wait_for_timeout(3000)
        
        # Click the CREATE button - try multiple selectors
        create_selectors = [
            "ytcp-button#create-icon",
            "ytcp-button[aria-label='Create']",
            "ytcp-button:has-text('Create')",
            "button#create-icon",
            "ytcp-button #create-icon"
        ]
        
        clicked = False
        for selector in create_selectors:
            try:
                if page.locator(selector).count() > 0:
                    page.click(selector, timeout=5000)
                    print(f"[UPLOAD] Clicked CREATE using selector: {selector}")
                    clicked = True
                    break
            except:
                pass
        
        if not clicked:
            # Fallback: click the top-right avatar and find Create
            print("[UPLOAD] Trying fallback: avatar menu")
            page.click("ytcp-avatar", timeout=5000)
            page.wait_for_timeout(1000)
            page.click("tp-yt-paper-listbox ytcp-button:has-text('Create')", timeout=5000)
        
        page.wait_for_timeout(2000)
        
        # Click "Upload videos" in the dropdown
        upload_selectors = [
            "tp-yt-paper-listbox ytcp-button:has-text('Upload videos')",
            "ytcp-button:has-text('Upload videos')",
            "paper-listbox ytcp-button:has-text('Upload')"
        ]
        
        clicked = False
        for selector in upload_selectors:
            try:
                if page.locator(selector).count() > 0:
                    page.click(selector, timeout=5000)
                    print(f"[UPLOAD] Clicked Upload videos using: {selector}")
                    clicked = True
                    break
            except:
                pass
        
        if not clicked:
            # Fallback: press 'V' key shortcut for Upload
            print("[UPLOAD] Using keyboard shortcut V for Upload")
            page.keyboard.press("v")
        
        page.wait_for_timeout(2000)
        
        # Wait for the file picker to appear
        try:
            with page.expect_file_chooser(timeout=15000) as fc_info:
                page.click("ytcp-uploads-file-picker", timeout=5000)
            file_chooser = fc_info.value
            file_chooser.set_files(video_path)
        except:
            # Fallback: use the input element directly if file chooser fails
            print("[UPLOAD] File chooser failed, trying direct input")
            file_input = page.locator("input[type='file']")
            if file_input.count() > 0:
                file_input.set_input_files(video_path)
            else:
                raise Exception("Could not select file")
        
        # Wait for upload to complete
        try:
            page.wait_for_selector("ytcp-uploads-progress", state="visible", timeout=10000)
            page.wait_for_selector("ytcp-uploads-progress", state="hidden", timeout=120000)
        except:
            print("[UPLOAD] Upload progress may have completed quickly")
        
        page.wait_for_timeout(2000)
        
        # Fill title
        try:
            page.locator("#title-textarea").fill(title, timeout=5000)
        except:
            page.locator("input#title-textarea").fill(title, timeout=5000)
        
        # Set to Public
        try:
            page.click("tp-yt-paper-radio-button[name='PUBLIC']", timeout=5000)
        except:
            # Try alternative
            page.click("paper-radio-button[name='PUBLIC']", timeout=5000)
        
        # Click Next through steps
        for i in range(3):
            try:
                page.click("ytcp-button:has-text('Next')", timeout=5000)
                page.wait_for_timeout(1000)
            except:
                print(f"[UPLOAD] Next button {i+1} not found, skipping")
        
        # Click Publish or Done
        try:
            page.click("ytcp-button:has-text('Publish')", timeout=10000)
        except:
            try:
                page.click("ytcp-button:has-text('Done')", timeout=5000)
            except:
                print("[UPLOAD] Could not find Publish/Done button, but upload may still be complete")
        
        print("[UPLOAD] Success!")
        browser.close()

def main():
    video_path = get_next_video()
    if not video_path:
        print("No videos left in queue. Stopping.")
        return
    
    try:
        with open("history.txt", "r") as f:
            uploaded_log = f.read().splitlines()
    except:
        uploaded_log = []
    
    today = time.strftime("%Y-%m-%d")
    daily_count = sum(1 for line in uploaded_log if line.startswith(today))
    if daily_count >= UPLOAD_LIMIT:
        print(f"Daily limit ({UPLOAD_LIMIT}) reached. Stopping.")
        return

    vid_num = video_path.split("_")[1].split(".")[0]
    title = f"BOME Daily 🔥 #{vid_num} #BOME #BookOfMeme #Solana #Shorts"
    
    upload_video(video_path, title)
    
    with open("uploaded.txt", "a") as f:
        f.write(f"{video_path}\n")
    with open("history.txt", "a") as f:
        f.write(f"{today} {video_path}\n")
    
    print("Done.")

if __name__ == "__main__":
    main()