import os
import json
import base64
import time
from datetime import datetime
from pathlib import Path
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

# ----- CONFIG -----
UPLOAD_LIMIT = 12
SCOPES = ["https://www.googleapis.com/auth/youtube.upload"]
CLIENT_SECRET_FILE = "client_secret.json"  # Not committed – keep local

# ----- LOAD TOKEN FROM SECRET OR LOCAL FILE -----
TOKEN_B64 = os.environ.get("TOKEN_BASE64")
if TOKEN_B64:
    with open("token.json", "w") as f:
        f.write(base64.b64decode(TOKEN_B64).decode())
    print("[DEBUG] Token decoded from secret.")
else:
    print("[DEBUG] No TOKEN_BASE64 secret found. Using local token.json if exists.")

# ----- AUTHENTICATION -----
def get_authenticated_service():
    creds = None
    if os.path.exists("token.json"):
        creds = Credentials.from_authorized_user_file("token.json", SCOPES)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            # If no token, fallback to local OAuth flow (requires client_secret.json)
            flow = InstalledAppFlow.from_client_secrets_file(CLIENT_SECRET_FILE, SCOPES)
            creds = flow.run_local_server(port=8080)
        with open("token.json", "w") as token:
            token.write(creds.to_json())
    return build("youtube", "v3", credentials=creds)

# ----- QUEUE MANAGEMENT -----
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

# ----- UPDATE PRIVACY (If you want to keep it) -----
def update_privacy(youtube, video_id, desired_status="public"):
    """Change video privacy. Works only if audit approved."""
    try:
        request = youtube.videos().update(
            part="status",
            body={
                "id": video_id,
                "status": {"privacyStatus": desired_status}
            }
        )
        request.execute()
        print(f"[UPDATE] ✅ Privacy changed to '{desired_status}'")
        return True
    except Exception as e:
        print(f"[UPDATE] ❌ Failed to set privacy to '{desired_status}': {e}")
        return False

# ----- UPLOAD FUNCTION -----
def upload_video(youtube, video_path, title, description=""):
    print(f"[UPLOAD] Uploading: {video_path}")
    if not Path(video_path).exists():
        raise Exception(f"File not found: {video_path}")

    body = {
        "snippet": {
            "title": title,
            "description": description,
            "tags": ["BOME", "BookOfMeme", "Solana", "Shorts"],
            "categoryId": "22"
        },
        "status": {
            "privacyStatus": "private"  # Start private
        }
    }

    media = MediaFileUpload(video_path, chunksize=-1, resumable=True)
    request = youtube.videos().insert(part="snippet,status", body=body, media_body=media)
    response = request.execute()
    video_id = response["id"]
    print(f"[UPLOAD] ✅ Success! Video ID: {video_id}")
    print(f"[UPLOAD] 🔗 URL: https://www.youtube.com/watch?v={video_id}")

    # Try to make it public (works after audit)
    update_privacy(youtube, video_id, "public")
    return response

# ----- MAIN -----
def main():
    print("[START] YouTube API Uploader started.")
    print(f"[START] Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    video_path = get_next_video()
    if not video_path:
        print("[INFO] No videos left in queue. Stopping.")
        return

    print(f"[INFO] Next video: {video_path}")

    try:
        with open("history.txt", "r") as f:
            uploaded_log = f.read().splitlines()
    except FileNotFoundError:
        uploaded_log = []

    today = time.strftime("%Y-%m-%d")
    daily_count = sum(1 for line in uploaded_log if line.startswith(today))
    if daily_count >= UPLOAD_LIMIT:
        print(f"[INFO] Daily limit ({UPLOAD_LIMIT}) reached. Stopping.")
        return

    print(f"[INFO] Videos uploaded today: {daily_count}/{UPLOAD_LIMIT}")

    vid_num = Path(video_path).stem.split("_")[-1]
    title = f"BOME Daily 🔥 #{vid_num} #BOME #BookOfMeme #Solana #Shorts"
    print(f"[INFO] Title: {title}")

    try:
        youtube = get_authenticated_service()
        upload_video(youtube, video_path, title, "Auto-generated BOME Short")

        with open("uploaded.txt", "a") as f:
            f.write(f"{video_path}\n")
        with open("history.txt", "a") as f:
            f.write(f"{today} {video_path}\n")

        print("[SUCCESS] ✅ Video uploaded successfully!")
    except Exception as e:
        print(f"[FATAL] Upload failed: {e}")
        raise

if __name__ == "__main__":
    main()