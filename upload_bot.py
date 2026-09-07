import os
import json
import subprocess
import random
import time
from playwright.sync_api import sync_playwright

# CONFIGURATION
SOURCE_CHANNEL = "https://www.youtube.com/@DeepsInsights"  # REPLACE THIS WITH YOUR SOURCE CHANNEL URL
UPLOAD_LIMIT = 12  # Max videos per day

# Load cookies from environment variable (we will store it on GitHub)
COOKIES_JSON = os.environ.get("YOUTUBE_COOKIES")
if not COOKIES_JSON:
    raise Exception("YOUTUBE_COOKIES environment variable not set")

cookies = json.loads(COOKIES_JSON)

# Step 1: Download the latest Short using yt-dlp
def download_latest_short():
    print("[1/5] Fetching latest Short from source...")
    cmd = [
        "yt-dlp",
        "--get-id",  # Only get video ID
        "--no-download",
        SOURCE_CHANNEL
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    video_id = result.stdout.strip().split("\n")[0]
    if not video_id:
        raise Exception("No video found")

    print(f"Found video ID: {video_id}")
    
    # Download the video
    cmd_dl = [
        "yt-dlp",
        "-f", "mp4",
        "-o", "source.mp4",
        f"https://www.youtube.com/shorts/{video_id}"
    ]
    subprocess.run(cmd_dl, check=True)
    return video_id

# Step 2: Mutate video (pitch shift + 1px crop) to avoid duplicate detection
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
        # Launch headless Chrome (works in GitHub Actions)
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
            page.click("ytcp-button:has-text('Next')")
            page.wait_for_timeout(500)
        
        # Click Publish
        page.click("ytcp-button:has-text('Publish')")
        print("[4/5] Upload successful!")
        browser.close()

def main():
    video_id = download_latest_short()
    
    # Check if we already uploaded this video (store history in file)
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
    
    # Generate title (SEO optimized)
    title = f"BOME Daily 🔥 #{video_id[:4]} #BOME #BookOfMeme #Solana #Shorts"
    
    upload_video(title)
    
    # Log upload
    with open("history.txt", "a") as f:
        f.write(f"{today} {video_id}\n")
    
    print("[5/5] Done!")

if __name__ == "__main__":
    main()