#!/usr/bin/env python3
import os
import json
import base64
import subprocess
import time
import shutil
from datetime import datetime
from pathlib import Path
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

# ---------- CONFIG ----------
UPLOAD_LIMIT = 12
MAX_PER_CHANNEL = 50
CHANNELS_FILE = "channels.txt"
DOWNLOADED_FILE = "downloaded_ids.txt"
PENDING_FILE = "pending.txt"
UPLOADED_FILE = "uploaded_ids.txt"
HISTORY_FILE = "history.txt"
TOKEN_FILE = "token.json"
CLIENT_SECRET_FILE = "client_secret.json"
SCOPES = ["https://www.googleapis.com/auth/youtube.upload"]

# ---------- COOKIES DECODING ----------
def load_cookies():
    cookies_b64 = os.environ.get("COOKIES_BASE64")
    if cookies_b64:
        with open("cookies.txt", "wb") as f:
            f.write(base64.b64decode(cookies_b64))
        print("[DEBUG] Cookies decoded and saved.")
        return True
    else:
        print("[WARNING] COOKIES_BASE64 not set; yt-dlp may be blocked.")
        return False

# ---------- LOAD CHANNELS ----------
def load_channels():
    if not os.path.exists(CHANNELS_FILE):
        raise Exception(f"{CHANNELS_FILE} not found!")
    with open(CHANNELS_FILE, "r") as f:
        return [line.strip() for line in f if line.strip()]

def load_ids(filepath):
    if not os.path.exists(filepath):
        return set()
    with open(filepath, "r") as f:
        return {line.strip() for line in f if line.strip()}

def save_ids(filepath, ids):
    with open(filepath, "w") as f:
        for vid in sorted(ids):
            f.write(vid + "\n")

def load_pending():
    if not os.path.exists(PENDING_FILE):
        return []
    with open(PENDING_FILE, "r") as f:
        return [line.strip() for line in f if line.strip()]

def save_pending(pending):
    with open(PENDING_FILE, "w") as f:
        for vid in pending:
            f.write(vid + "\n")

def log_upload(video_id, channel=None):
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with open(HISTORY_FILE, "a") as f:
        f.write(f"{timestamp} {video_id} {channel or 'unknown'}\n")

# ---------- FETCH VIDEO IDs (web client + cookies + remote solver) ----------
def get_channel_video_ids(channel_url, limit=MAX_PER_CHANNEL):
    cmd = [
        "yt-dlp",
        "--flat-playlist",
        "--get-id",
        "--playlist-end", str(limit),
        "--js-runtimes", "node",
        "--remote-components", "ejs:github",
        "--extractor-args", "youtube:player_client=web",
        "--extractor-args", "youtube:skip=hls,dash",
        "--cookies", "cookies.txt",
        channel_url + "/shorts"
    ]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        ids = [line.strip() for line in result.stdout.splitlines() if line.strip()]
        return ids
    except subprocess.CalledProcessError as e:
        print(f"[ERROR] Failed to fetch IDs from {channel_url}: {e.stderr}")
        return []

# ---------- DOWNLOAD & MUTATE (web client + cookies + scale+pad) ----------
def download_and_mutate(video_id, output_filename="source.mp4"):
    url = f"https://www.youtube.com/shorts/{video_id}"
    cmd_dl = [
        "yt-dlp",
        "-f", "mp4",
        "-o", output_filename,
        "--js-runtimes", "node",
        "--remote-components", "ejs:github",
        "--extractor-args", "youtube:player_client=web",
        "--extractor-args", "youtube:skip=hls,dash",
        "--cookies", "cookies.txt",
        url
    ]
    try:
        subprocess.run(cmd_dl, check=True, capture_output=True)
    except subprocess.CalledProcessError as e:
        print(f"[ERROR] Download failed for {video_id}: {e.stderr}")
        return None

    mutated_file = f"mutated_{video_id}.mp4"
    # Scale to fit 1080x1920 (9:16) and pad with black bars to center
    cmd_ff = [
        "ffmpeg",
        "-i", output_filename,
        "-af", "asetrate=44100*0.99,aresample=44100",
        "-vf", "scale=1080:1920:force_original_aspect_ratio=decrease,pad=1080:1920:(ow-iw)/2:(oh-ih)/2",
        "-c:v", "libx264",
        "-preset", "fast",
        "-y",
        mutated_file
    ]
    try:
        subprocess.run(cmd_ff, check=True, capture_output=True)
    except subprocess.CalledProcessError as e:
        print(f"[ERROR] Mutation failed for {video_id}: {e.stderr}")
        return None

    os.remove(output_filename)
    return mutated_file

# ---------- YOUTUBE API UPLOAD ----------
def get_authenticated_service():
    token_b64 = os.environ.get("TOKEN_BASE64")
    if token_b64:
        with open(TOKEN_FILE, "w") as f:
            f.write(base64.b64decode(token_b64).decode())
        print("[DEBUG] Token decoded from secret.")
    creds = None
    if os.path.exists(TOKEN_FILE):
        creds = Credentials.from_authorized_user_file(TOKEN_FILE, SCOPES)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(CLIENT_SECRET_FILE, SCOPES)
            creds = flow.run_local_server(port=8080)
        with open(TOKEN_FILE, "w") as token:
            token.write(creds.to_json())
    return build("youtube", "v3", credentials=creds)

def upload_video(youtube, file_path, title, description=""):
    body = {
        "snippet": {
            "title": title,
            "description": description,
            "tags": ["BOME", "Shorts", "Automated"],
            "categoryId": "22"
        },
        "status": {"privacyStatus": "private"}
    }
    media = MediaFileUpload(file_path, chunksize=-1, resumable=True)
    request = youtube.videos().insert(part="snippet,status", body=body, media_body=media)
    response = request.execute()
    video_id = response["id"]
    try:
        youtube.videos().update(
            part="status",
            body={"id": video_id, "status": {"privacyStatus": "public"}}
        ).execute()
        print(f"[UPDATE] Video {video_id} set to public.")
    except Exception as e:
        print(f"[UPDATE] Could not set public: {e}. Video remains private.")
    return video_id

# ---------- MAIN ----------
def main():
    load_cookies()

    print("[START] BOME Auto Bot started.")
    print(f"[START] Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    channels = load_channels()
    if not channels:
        print("[ERROR] No channels found.")
        return

    downloaded = load_ids(DOWNLOADED_FILE)
    uploaded = load_ids(UPLOADED_FILE)
    pending = load_pending()

    if pending:
        print(f"[UPLOAD] {len(pending)} videos still pending.")
    else:
        print("[REFRESH] No pending videos. Scanning channels for new content...")
        channel_data = []
        for channel in channels:
            ids = get_channel_video_ids(channel)
            new_ids = [vid for vid in ids if vid not in downloaded and vid not in uploaded]
            channel_data.append({
                "url": channel,
                "total": len(ids),
                "new": len(new_ids),
                "new_ids": new_ids
            })
        channel_data.sort(key=lambda x: x["total"])

        for data in channel_data:
            if data["new_ids"]:
                print(f"  Adding {data['new']} videos from {data['url']} (total: {data['total']})")
                downloaded.update(data["new_ids"])
                pending.extend(data["new_ids"])
                save_ids(DOWNLOADED_FILE, downloaded)
                save_pending(pending)
                break

    today = datetime.now().strftime("%Y-%m-%d")
    if os.path.exists(HISTORY_FILE):
        with open(HISTORY_FILE, "r") as f:
            lines = f.readlines()
        today_uploads = sum(1 for line in lines if line.startswith(today))
    else:
        today_uploads = 0

    if today_uploads >= UPLOAD_LIMIT:
        print(f"[UPLOAD] Daily limit ({UPLOAD_LIMIT}) reached. Stopping.")
        return

    if not pending:
        print("[UPLOAD] No videos pending.")
        return

    next_video_id = pending[0]
    print(f"[UPLOAD] Next video: {next_video_id}")

    try:
        mutated_file = download_and_mutate(next_video_id)
        if not mutated_file:
            raise Exception("Download/mutation failed.")
        youtube = get_authenticated_service()
        title = f"BOME Daily 🔥 #{next_video_id[:4]} #BOME #BookOfMeme #Solana #Shorts"
        video_id = upload_video(youtube, mutated_file, title, "Auto-generated BOME Short")
        print(f"[UPLOAD] ✅ Uploaded successfully! Video ID: {video_id}")

        os.remove(mutated_file)

        uploaded.add(next_video_id)
        save_ids(UPLOADED_FILE, uploaded)

        pending.pop(0)
        save_pending(pending)

        log_upload(next_video_id, channel="multi")
        print("[SUCCESS] Full cycle complete!")

    except Exception as e:
        print(f"[ERROR] Upload failed: {e}")
        pending.pop(0)
        save_pending(pending)
        print("[INFO] Removed failed video from pending queue.")

if __name__ == "__main__":
    main()