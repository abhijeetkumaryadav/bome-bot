import os
import json
import base64
import time
from datetime import datetime
from pathlib import Path
from playwright.sync_api import sync_playwright, expect

# CONFIG
UPLOAD_LIMIT = 12
UPLOAD_TIMEOUT = 300000  # 5 minutes for upload completion

# Load cookies from base64 secret
COOKIES_B64 = os.environ.get("COOKIES_BASE64")
if not COOKIES_B64:
    raise Exception("COOKIES_BASE64 environment variable not set")

with open("cookies.txt", "wb") as f:
    f.write(base64.b64decode(COOKIES_B64))

print("[DEBUG] Cookies decoded successfully.")

# Parse cookies for Playwright
def parse_netscape_cookies(filepath):
    """Parse Netscape-format cookies file and return as list of dicts for Playwright."""
    cookies = []
    with open(filepath, "r") as f:
        for line in f:
            line = line.strip()
            # Skip comments and empty lines
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
    """Read queue.txt and return the first video that hasn't been uploaded yet."""
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
    """
    Upload a single video to YouTube using Playwright.
    
    Args:
        video_path: Path to the video file (e.g., 'videos/vid_001.mp4')
        title: Title for the YouTube video
    """
    print(f"[UPLOAD] Starting upload for: {video_path}")
    
    # Verify file exists
    if not Path(video_path).exists():
        raise Exception(f"Video file not found: {video_path}")
    
    abs_video_path = str(Path(video_path).resolve())
    print(f"[UPLOAD] Absolute path: {abs_video_path}")
    
    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=True,
            args=[
                '--no-sandbox',
                '--disable-dev-shm-usage',
                '--disable-gpu'
            ]
        )
        
        context = browser.new_context(
            viewport={'width': 1280, 'height': 720},
            user_agent='Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            ignore_https_errors=True
        )
        
        # Add cookies to context
        context.add_cookies(cookies)
        page = context.new_page()
        
        try:
            # Navigate to YouTube upload page
            print("[UPLOAD] Navigating to upload page...")
            page.goto("https://www.youtube.com/upload", wait_until="networkidle", timeout=30000)
            page.wait_for_load_state("domcontentloaded", timeout=15000)
            print("[UPLOAD] Upload page loaded.")
            
            # Wait for page to stabilize
            page.wait_for_timeout(2000)
            
            # ===== FILE SELECTION (KEY FIX) =====
            # Use the actual name attribute of the hidden file input
            print("[UPLOAD] Selecting video file (hidden input)...")
            file_input_selector = "input[name='Filedata']"
            
            # Do NOT wait for visibility - just locate and set files directly
            file_input = page.locator(file_input_selector)
            
            try:
                # This works on hidden elements - Playwright bypasses visibility checks
                file_input.set_input_files(abs_video_path)
                print(f"[UPLOAD] File selected successfully: {abs_video_path}")
            except Exception as e:
                print(f"[UPLOAD] Error selecting file: {e}")
                # Try alternative selector
                print("[UPLOAD] Trying alternative file input selector...")
                file_input_alt = page.locator("input[type='file']")
                file_input_alt.set_input_files(abs_video_path)
                print(f"[UPLOAD] File selected with alternative selector.")
            
            # Wait for upload progress to appear and complete
            print("[UPLOAD] Waiting for upload to complete...")
            try:
                # Wait for upload progress container to appear
                page.wait_for_selector("ytcp-uploads-progress", state="visible", timeout=30000)
                print("[UPLOAD] Upload progress detected.")
                
                # Wait for upload to finish (progress container hidden)
                page.wait_for_selector("ytcp-uploads-progress", state="hidden", timeout=UPLOAD_TIMEOUT)
                print("[UPLOAD] Upload completed.")
            except Exception as e:
                print(f"[UPLOAD] Upload progress monitoring error (continuing): {e}")
            
            # Wait for page to stabilize after upload
            page.wait_for_timeout(3000)
            
            # ===== TITLE INPUT =====
            print("[UPLOAD] Setting video title...")
            try:
                # Try to find and fill the title textarea
                title_input = page.locator("#title-textarea, ytcp-social-metadata-editor #title")
                title_input.first.fill(title, timeout=10000)
                print(f"[UPLOAD] Title set: {title}")
            except Exception as e:
                print(f"[UPLOAD] Could not set title with primary selector: {e}")
                try:
                    # Fallback: try plain text field
                    page.fill("textarea", title, timeout=10000)
                    print(f"[UPLOAD] Title set with fallback selector.")
                except Exception as e2:
                    print(f"[UPLOAD] Warning: Could not set title: {e2}")
            
            page.wait_for_timeout(1000)
            
            # ===== SET TO PUBLIC =====
            print("[UPLOAD] Setting video to Public...")
            try:
                # Try to find and click the PUBLIC radio button
                public_button = page.locator("tp-yt-paper-radio-button[name='PUBLIC'], paper-radio-button[name='PUBLIC']")
                public_button.first.click(timeout=10000)
                print("[UPLOAD] Video set to Public.")
            except Exception as e:
                print(f"[UPLOAD] Warning: Could not set to Public: {e}")
            
            page.wait_for_timeout(1000)
            
            # ===== CLICK THROUGH "NEXT" BUTTONS =====
            print("[UPLOAD] Clicking through Next buttons...")
            next_attempts = 0
            max_next_attempts = 5
            
            while next_attempts < max_next_attempts:
                try:
                    next_button = page.locator("ytcp-button:has-text('Next'), button:has-text('Next')")
                    
                    if next_button.count() > 0:
                        next_button.first.click(timeout=5000)
                        next_attempts += 1
                        print(f"[UPLOAD] Clicked Next button ({next_attempts}).")
                        page.wait_for_timeout(1000)
                    else:
                        print(f"[UPLOAD] No more Next buttons found.")
                        break
                except Exception as e:
                    print(f"[UPLOAD] Next button {next_attempts + 1} not found or clickable: {e}")
                    break
            
            page.wait_for_timeout(2000)
            
            # ===== PUBLISH =====
            print("[UPLOAD] Publishing video...")
            publish_success = False
            
            try:
                # Try to click Publish button
                publish_button = page.locator("ytcp-button:has-text('Publish'), button:has-text('Publish')")
                if publish_button.count() > 0:
                    publish_button.first.click(timeout=15000)
                    print("[UPLOAD] Publish button clicked.")
                    publish_success = True
                    page.wait_for_timeout(3000)
            except Exception as e:
                print(f"[UPLOAD] Publish button error: {e}")
            
            # If Publish didn't work, try Done button
            if not publish_success:
                try:
                    done_button = page.locator("ytcp-button:has-text('Done'), button:has-text('Done')")
                    if done_button.count() > 0:
                        done_button.first.click(timeout=10000)
                        print("[UPLOAD] Done button clicked.")
                        publish_success = True
                        page.wait_for_timeout(3000)
                except Exception as e:
                    print(f"[UPLOAD] Done button error: {e}")
            
            if not publish_success:
                print("[UPLOAD] Warning: Could not confirm publish action, but upload may still be in progress.")
            
            print("[UPLOAD] Upload workflow completed!")
            
        except Exception as e:
            print(f"[ERROR] Upload failed: {e}")
            raise
        
        finally:
            browser.close()
            print("[UPLOAD] Browser closed.")

def main():
    """Main function to process queue and upload videos."""
    print("[START] YouTube Shorts Uploader started.")
    print(f"[START] Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    # Get next video to upload
    video_path = get_next_video()
    if not video_path:
        print("[INFO] No videos left in queue. Stopping.")
        return
    
    print(f"[INFO] Next video to upload: {video_path}")
    
    # Check daily limit
    try:
        with open("history.txt", "r") as f:
            uploaded_log = f.read().splitlines()
    except FileNotFoundError:
        uploaded_log = []
    
    today = time.strftime("%Y-%m-%d")
    daily_count = sum(1 for line in uploaded_log if line.startswith(today))
    
    if daily_count >= UPLOAD_LIMIT:
        print(f"[INFO] Daily limit ({UPLOAD_LIMIT} videos) reached. Stopping.")
        return
    
    print(f"[INFO] Videos uploaded today: {daily_count}/{UPLOAD_LIMIT}")
    
    # Extract video number from filename
    try:
        # Expected format: videos/vid_001.mp4 or vid_001.mp4
        filename = Path(video_path).stem  # Get filename without extension
        vid_num = filename.split("_")[-1]  # Get the number part
    except Exception as e:
        print(f"[WARN] Could not extract video number: {e}")
        vid_num = "0"
    
    # Format title
    title = f"BOME Daily 🔥 #{vid_num} #BOME #BookOfMeme #Solana #Shorts"
    print(f"[INFO] Video title: {title}")
    
    # Upload video
    try:
        upload_video(video_path, title)
        
        # Mark as uploaded
        with open("uploaded.txt", "a") as f:
            f.write(f"{video_path}\n")
        
        # Log to history
        with open("history.txt", "a") as f:
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            f.write(f"{today} {video_path} {timestamp}\n")
        
        print("[SUCCESS] Video uploaded and logged successfully!")
        
    except Exception as e:
        print(f"[FATAL] Upload failed: {e}")
        raise

if __name__ == "__main__":
    main()