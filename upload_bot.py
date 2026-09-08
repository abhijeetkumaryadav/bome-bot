import os
import json
import base64
import time
from datetime import datetime
from pathlib import Path
from playwright.sync_api import sync_playwright

UPLOAD_LIMIT = 12

# Load cookies
COOKIES_B64 = os.environ.get("COOKIES_BASE64")
if not COOKIES_B64:
    raise Exception("COOKIES_BASE64 not set")

with open("cookies.txt", "wb") as f:
    f.write(base64.b64decode(COOKIES_B64))

print("[DEBUG] Cookies decoded.")

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
print(f"[DEBUG] Loaded {len(cookies)} cookies.")

def get_next_video():
    try:
        with open("queue.txt", "r") as f:
            all_videos = [line.strip() for line in f if line.strip()]
    except FileNotFoundError:
        raise Exception("queue.txt not found!")
    try:
        with open("uploaded.txt", "r") as f:
            uploaded = set(line.strip() for line in f if line.strip())
    except FileNotFoundError:
        uploaded = set()
    for video in all_videos:
        if video not in uploaded:
            return video
    return None

def upload_video(video_path, title):
    print(f"[UPLOAD] Starting: {video_path}")
    if not Path(video_path).exists():
        raise Exception(f"File not found: {video_path}")
    abs_path = str(Path(video_path).resolve())

    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=True,
            args=['--no-sandbox', '--disable-dev-shm-usage']
        )
        context = browser.new_context(
            viewport={'width': 1280, 'height': 800},
            user_agent='Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        )
        context.add_cookies(cookies)
        page = context.new_page()

        try:
            # Go to YouTube Studio
            print("[UPLOAD] Navigating to Studio...")
            page.goto("https://studio.youtube.com", wait_until="networkidle", timeout=30000)
            page.wait_for_timeout(3000)

            # Click CREATE button
            create_btn = page.locator("ytcp-button#create-icon, ytcp-button[aria-label='Create'], ytcp-button:has-text('Create')")
            create_btn.first.click(timeout=10000)
            print("[UPLOAD] Clicked Create.")
            page.wait_for_timeout(2000)

            # Click "Upload videos"
            upload_btn = page.locator("tp-yt-paper-listbox ytcp-button:has-text('Upload videos'), ytcp-button:has-text('Upload videos')")
            upload_btn.first.click(timeout=10000)
            print("[UPLOAD] Clicked Upload videos.")
            page.wait_for_timeout(2000)

            # Select file using the hidden input
            print("[UPLOAD] Selecting file via hidden input...")
            file_input = page.locator("input[name='Filedata']")
            file_input.set_input_files(abs_path)
            print("[UPLOAD] File selected.")

            # Wait for upload to complete (progress appears and disappears)
            print("[UPLOAD] Waiting for upload...")
            page.wait_for_selector("ytcp-uploads-progress", state="visible", timeout=30000)
            page.wait_for_selector("ytcp-uploads-progress", state="hidden", timeout=300000)
            print("[UPLOAD] Upload complete.")

            page.wait_for_timeout(2000)

            # Title
            print("[UPLOAD] Setting title...")
            try:
                page.fill("#title-textarea", title, timeout=10000)
            except:
                page.fill("ytcp-social-metadata-editor #title", title, timeout=10000)
            print(f"[UPLOAD] Title set: {title}")

            # Public
            print("[UPLOAD] Setting Public...")
            public_radio = page.locator("tp-yt-paper-radio-button[name='PUBLIC']")
            public_radio.click(timeout=10000)
            print("[UPLOAD] Public set.")

            # Click Next buttons (usually 2-3)
            for i in range(3):
                try:
                    next_btn = page.locator("ytcp-button:has-text('Next')")
                    if next_btn.count() > 0:
                        next_btn.first.click(timeout=5000)
                        print(f"[UPLOAD] Next {i+1} clicked.")
                        page.wait_for_timeout(1000)
                except:
                    break

            # Publish
            print("[UPLOAD] Publishing...")
            try:
                publish_btn = page.locator("ytcp-button:has-text('Publish')")
                publish_btn.first.click(timeout=15000)
                print("[UPLOAD] Published!")
            except:
                # If already published, try Done
                done_btn = page.locator("ytcp-button:has-text('Done')")
                if done_btn.count() > 0:
                    done_btn.first.click(timeout=10000)
                    print("[UPLOAD] Clicked Done.")

            print("[UPLOAD] Workflow complete.")

        except Exception as e:
            print(f"[ERROR] {e}")
            raise
        finally:
            browser.close()

def main():
    print("[START] YouTube Shorts Uploader started.")
    video_path = get_next_video()
    if not video_path:
        print("No videos left.")
        return

    # Daily limit check
    try:
        with open("history.txt", "r") as f:
            uploaded_log = f.read().splitlines()
    except:
        uploaded_log = []
    today = time.strftime("%Y-%m-%d")
    if sum(1 for line in uploaded_log if line.startswith(today)) >= UPLOAD_LIMIT:
        print(f"Daily limit reached.")
        return

    vid_num = Path(video_path).stem.split("_")[-1]
    title = f"BOME Daily 🔥 #{vid_num} #BOME #BookOfMeme #Solana #Shorts"
    upload_video(video_path, title)

    with open("uploaded.txt", "a") as f:
        f.write(f"{video_path}\n")
    with open("history.txt", "a") as f:
        f.write(f"{today} {video_path}\n")
    print("[SUCCESS] Video uploaded!")

if __name__ == "__main__":
    main()