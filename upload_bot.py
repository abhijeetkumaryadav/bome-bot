import os
import json
import base64
import subprocess
import random
import time
from playwright.sync_api import sync_playwright

# CONFIGURATION
SOURCE_CHANNEL = "https://www.youtube.com/@ComedyClub-ty"  # Change this to your source channel
UPLOAD_LIMIT = 12  # Max videos per day

# Load cookies from base64 secret
COOKIES_B64 = os.environ.get("COOKIES_BASE64")
if not COOKIES_B64:
    raise Exception("COOKIES_BASE64 environment variable not set")

# Decode and save as cookies.txt
with open("cookies.txt", "wb") as f:
    f.write(base64.b64decode(COOKIES_B64))

print("[DEBUG] Cookies decoded and saved as cookies.txt")

# Parse cookies.txt for Playwright
def parse_netscape_cookies(filepath):
    cookies = []
    with open(filepath, "r") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            parts = line.split("\t")
            if len(parts) >= 7:
                domain = parts[0]
                flag = parts[1]
                path = parts[2]
                secure = parts[3] == "TRUE"
                expiry = float(parts[4]) if parts[4] != "0" else None
                name = parts[5]
                value = parts[6]
                cookies.append({
                    "name": name,
                    "value": value,
                    "domain": domain,
                    "path": path,
                    "secure": secure,
                    "httpOnly": False,
                    "expirationDate": expiry
                })
    return cookies

cookies = parse_netscape_cookies("cookies.txt")
print(f"[DEBUG] Loaded {len(cookies)} cookies for Playwright")

# Step 1: Download the latest Short using yt-dlp with cookies
def download_latest_short():
    print("[1/5] Fetching latest Short from source...")
    
    # Get the latest video ID
    cmd = [
        "yt-dlp",
        "--get-id",
        "--no-download",
        "--cookies", "cookies.txt",
        SOURCE_CHANNEL
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    
    if result.returncode != 0:
        print(f"yt-dlp error: {result.stderr}")
        raise Exception("Failed to fetch video ID")
    
    video_id = result.stdout.strip().split("\n")[0]
    if not video_id:
        raise Exception("No video found")

    print(f"Found video ID: {video_id}")
    
    # Download the video with cookies
    cmd_dl = [
        "yt-dlp",
        "-f", "mp4",
        "-o", "source.mp4",
        "--cookies", "cookies.txt",
        f"https://www.youtube.com/shorts/{video_id}"
    ]
    dl_result = subprocess.run(cmd_dl, capture_output=True, text=True)
    
    if dl_result.returncode != 0:
        print(f"Download error: {dl_result.stderr}")
        raise Exception("Failed to download video")
    
    return video_id

# Step 2: Mutate video (pitch shift + crop) to avoid duplicate detection
def mutate_video():
    print("[2/5] Mutating video (pitch shift + crop)...")
    cmd = [
        "ffmpeg",
        "-i", "source.mp4",
        "-af", "asetrate=44100*0.99,aresample=44100",
        "-vf", "crop=ih*9/16:ih",
        "-c:v", "libx264",
        "-preset", "fast",
        "-y",
        "mutated.mp4"
    ]
    subprocess.run(cmd, check=True)

# Step 3: Upload using Playwright
def upload_video(title):
    print("[3/5] Uploading via Playwright...")
    with sync_playwright() as p:
        # Launch headless Chrome with sandbox disabled for GitHub Actions
        browser = p.chromium.launch(
            headless=True,
            args=['--no-sandbox', '--disable-dev-shm-usage']
        )
        context = browser.new_context()
        # Add cookies
        context.add_cookies(cookies)
        page = context.new_page()
        
        # Go to YouTube Studio
        page.goto("https://studio.youtube.com")
        page.wait_for_timeout(2000)
        
        # Click Upload button
        page.click("ytcp-button#create-icon")
        page.click("tp-yt-paper-listbox ytcp-button:has-text('Upload videos')")
        page.wait_for_timeout(1000)
        
        # Select file
        with page.expect_file_chooser() as fc_info:
            page.click("ytcp-uploads-file-picker")
        file_chooser = fc_info.value
        file_chooser.set_files("mutated.mp4")
        
        # Wait for upload to process
        page.wait_for_selector("ytcp-uploads-progress", state="visible")
        page.wait_for_selector("ytcp-uploads-progress", state="hidden", timeout=60000)
        
        # Fill title
        title_input = page.locator("#title-textarea")
        title_input.fill(title)
        
        # Set to Public
        page.click("tp-yt-paper-radio-button[name='PUBLIC']")
        
        # Click through steps
        for _ in range(3):
            try:
                page.click("ytcp-button:has-text('Next')", timeout=5000)
            except:
                pass
            page.wait_for_timeout(500)
        
        # Click Publish
        try:
            page.click("ytcp-button:has-text('Publish')")
        except:
            page.click("ytcp-button:has-text('Done')")
        
        print("[4/5] Upload successful!")
        browser.close()

def main():
    video_id = download_latest_short()
    
    # Check if we already uploaded this video
    try:
        with open("history.txt", "r") as f:
            uploaded = f.read().splitlines()
    except FileNotFoundError:
        uploaded = []
    
    if video_id in uploaded:
        print(f"Video {video_id} already uploaded. Skipping.")
        return
    
    # Count today's uploads
    today = time.strftime("%Y-%m-%d")
    daily_count = sum(1 for line in uploaded if line.startswith(today))
    if daily_count >= UPLOAD_LIMIT:
        print(f"Daily limit of {UPLOAD_LIMIT} reached. Stopping.")
        return
    
    mutate_video()
    
    # Generate SEO title
    title = f"BOME Daily 🔥 #{video_id[:4]} #BOME #BookOfMeme #Solana #Shorts"
    
    upload_video(title)
    
    # Log upload
    with open("history.txt", "a") as f:
        f.write(f"{today} {video_id}\n")
    
    print("[5/5] Done!")

if __name__ == "__main__":
    main()
