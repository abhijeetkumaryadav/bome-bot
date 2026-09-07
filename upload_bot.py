import os
import json
import subprocess
import random
import time
from playwright.sync_api import sync_playwright

# CONFIGURATION
<<<<<<< HEAD
SOURCE_CHANNEL = "https://www.youtube.com/@DeepsInsights"  # Change this to your source channel
UPLOAD_LIMIT = 12  # Max videos per day

# Load cookies from environment variable (set in GitHub Secrets)
=======
SOURCE_CHANNEL = "https://www.youtube.com/@DeepsInsights"  # Change this to your target source
UPLOAD_LIMIT = 12

# Load cookies from environment variable
>>>>>>> 0d8a8def29f74e2f0be5e7a0a9574ba8d03af2af
COOKIES_JSON = os.environ.get("YOUTUBE_COOKIES")
if not COOKIES_JSON:
    raise Exception("YOUTUBE_COOKIES environment variable not set")

cookies = json.loads(COOKIES_JSON)

<<<<<<< HEAD
=======
# --- NEW FUNCTION: Convert JSON cookies to Netscape format ---
def convert_cookies_to_netscape(cookies_list, output_file):
    """Converts a JSON cookie array to a Netscape format .txt file for yt-dlp."""
    with open(output_file, 'w') as f:
        f.write("# Netscape HTTP Cookie File\n")
        for cookie in cookies_list:
            domain = cookie.get('domain', '')
            # flag: 'TRUE' if domain starts with '.' to allow subdomains
            flag = 'TRUE' if domain.startswith('.') else 'FALSE'
            path = cookie.get('path', '/')
            secure = 'TRUE' if cookie.get('secure', False) else 'FALSE'
            # Convert expiration to integer (if missing, set to 1 year from now)
            expiry = cookie.get('expirationDate')
            if expiry is None:
                expiry = int(time.time()) + 31536000  # 1 year
            else:
                expiry = int(expiry)
            name = cookie.get('name', '')
            value = cookie.get('value', '')
            # Write: domain flag path secure expiry name value
            f.write(f"{domain}\t{flag}\t{path}\t{secure}\t{expiry}\t{name}\t{value}\n")
    print(f"[DEBUG] Cookies converted to Netscape format: {output_file}")

>>>>>>> 0d8a8def29f74e2f0be5e7a0a9574ba8d03af2af
# Step 1: Download the latest Short using yt-dlp with cookies
def download_latest_short():
    print("[1/5] Fetching latest Short from source...")
    
<<<<<<< HEAD
    # Write cookies to a temporary file (yt-dlp needs it in Netscape format)
    # But yt-dlp also accepts JSON cookies via --cookies, so we can just pass the JSON file
    cookies_file = "cookies.json"
    with open(cookies_file, "w") as f:
        json.dump(cookies, f)
=======
    # Convert cookies to Netscape format for yt-dlp
    cookies_file = "cookies.txt"
    convert_cookies_to_netscape(cookies, cookies_file)
>>>>>>> 0d8a8def29f74e2f0be5e7a0a9574ba8d03af2af
    
    # Get the latest video ID
    cmd = [
        "yt-dlp",
        "--get-id",
        "--no-download",
        "--cookies", cookies_file,
        SOURCE_CHANNEL
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    
    if result.returncode != 0:
        print(f"yt-dlp error: {result.stderr}")
<<<<<<< HEAD
=======
        os.remove(cookies_file)
>>>>>>> 0d8a8def29f74e2f0be5e7a0a9574ba8d03af2af
        raise Exception("Failed to fetch video ID")
    
    video_id = result.stdout.strip().split("\n")[0]
    if not video_id:
        os.remove(cookies_file)
        raise Exception("No video found")

    print(f"Found video ID: {video_id}")
    
    # Download the video with cookies
    cmd_dl = [
        "yt-dlp",
        "-f", "mp4",
        "-o", "source.mp4",
        "--cookies", cookies_file,
        f"https://www.youtube.com/shorts/{video_id}"
    ]
    dl_result = subprocess.run(cmd_dl, capture_output=True, text=True)
    
<<<<<<< HEAD
=======
    # Clean up cookies file
    os.remove(cookies_file)
    
>>>>>>> 0d8a8def29f74e2f0be5e7a0a9574ba8d03af2af
    if dl_result.returncode != 0:
        print(f"Download error: {dl_result.stderr}")
        raise Exception("Failed to download video")
    
<<<<<<< HEAD
    # Clean up cookies file
    os.remove(cookies_file)
    
=======
>>>>>>> 0d8a8def29f74e2f0be5e7a0a9574ba8d03af2af
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
        # Add cookies (Playwright accepts the JSON format directly)
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
        
        # Click through steps (Next, Next, Next, Publish)
        for _ in range(3):
            page.click("ytcp-button:has-text('Next')")
            page.wait_for_timeout(500)
        
        # Click Publish
        page.click("ytcp-button:has-text('Publish')")
        print("[4/5] Upload successful!")
        browser.close()

def main():
    video_id = download_latest_short()
    
    # Check history to avoid duplicates
    try:
        with open("history.txt", "r") as f:
            uploaded = f.read().splitlines()
    except FileNotFoundError:
        uploaded = []
    
    if video_id in uploaded:
        print(f"Video {video_id} already uploaded. Skipping.")
        return
    
    # Check daily limit
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
