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
            # STEP 1: GO DIRECTLY TO THE UPLOAD PAGE (the one you saw in your browser)
            # Use the exact URL pattern from your observation.
            # We'll use the channel ID from the redirect. It's constant.
            upload_url = "https://studio.youtube.com/channel/UC-PGIAfF6MGuaa-ZPv7lzLA/videos/upload?theme=dark&d=ud"
            print(f"[UPLOAD] Navigating directly to: {upload_url}")
            page.goto(upload_url, wait_until="networkidle", timeout=30000)
            page.wait_for_timeout(3000)

            # STEP 2: Select the file using the hidden input (NOW VISIBLE ON THIS PAGE)
            print("[UPLOAD] Selecting file...")
            # The file input is always present on the upload page.
            file_input = page.locator("input[type='file'][name='Filedata']")
            file_input.set_input_files(abs_path)
            print("[UPLOAD] File selected.")

            # STEP 3: Wait for upload to complete (progress bar)
            print("[UPLOAD] Waiting for upload to complete...")
            page.wait_for_selector("ytcp-uploads-progress", state="visible", timeout=30000)
            page.wait_for_selector("ytcp-uploads-progress", state="hidden", timeout=300000)
            print("[UPLOAD] Upload complete.")

            page.wait_for_timeout(2000)

            # STEP 4: Title
            print("[UPLOAD] Setting title...")
            title_input = page.locator("#title-textarea")
            title_input.fill(title)
            print(f"[UPLOAD] Title set: {title}")

            # STEP 5: Set Public
            print("[UPLOAD] Setting visibility to Public...")
            public_radio = page.locator("tp-yt-paper-radio-button[name='PUBLIC']")
            public_radio.click()
            print("[UPLOAD] Visibility set to Public.")

            # STEP 6: Click Next buttons (usually 3)
            for i in range(3):
                try:
                    next_btn = page.locator("ytcp-button:has-text('Next')")
                    if next_btn.count() > 0:
                        next_btn.first.click(timeout=5000)
                        print(f"[UPLOAD] Next {i+1} clicked.")
                        page.wait_for_timeout(1000)
                except:
                    break

            # STEP 7: Publish
            print("[UPLOAD] Publishing...")
            try:
                publish_btn = page.locator("ytcp-button:has-text('Publish')")
                if publish_btn.count() > 0:
                    publish_btn.first.click(timeout=15000)
                    print("[UPLOAD] Published!")
                else:
                    done_btn = page.locator("ytcp-button:has-text('Done')")
                    if done_btn.count() > 0:
                        done_btn.first.click(timeout=10000)
                        print("[UPLOAD] Clicked Done.")
            except Exception as e:
                print(f"[UPLOAD] Publish error: {e}")

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

    # Daily limit
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