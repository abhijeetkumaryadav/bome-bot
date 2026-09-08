import os
import json
import base64
import subprocess
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
        context = browser.new_context()
        context.add_cookies(cookies)
        page = context.new_page()
        
        page.goto("https://studio.youtube.com")
        page.wait_for_timeout(2000)
        
        page.click("ytcp-button#create-icon")
        page.click("tp-yt-paper-listbox ytcp-button:has-text('Upload videos')")
        page.wait_for_timeout(1000)
        
        with page.expect_file_chooser() as fc_info:
            page.click("ytcp-uploads-file-picker")
        file_chooser = fc_info.value
        file_chooser.set_files(video_path)
        
        page.wait_for_selector("ytcp-uploads-progress", state="visible")
        page.wait_for_selector("ytcp-uploads-progress", state="hidden", timeout=60000)
        
        page.locator("#title-textarea").fill(title)
        page.click("tp-yt-paper-radio-button[name='PUBLIC']")
        
        for _ in range(3):
            try:
                page.click("ytcp-button:has-text('Next')", timeout=5000)
            except:
                pass
            page.wait_for_timeout(500)
        
        try:
            page.click("ytcp-button:has-text('Publish')")
        except:
            page.click("ytcp-button:has-text('Done')")
        
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