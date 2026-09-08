import os
import subprocess
import sys
import time

# ---------- CONFIG ----------
print("\n📥 YouTube Shorts Downloader + Auto-Push")
print("----------------------------------------")

channel_input = input("Enter channel URL or handle (e.g., @ComedyClub-ty): ").strip()
while not channel_input:
    print("❌ You must enter a channel URL or handle.")
    channel_input = input("Enter channel URL or handle: ").strip()

if channel_input.startswith("@"):
    CHANNEL_URL = f"https://www.youtube.com/{channel_input}"
else:
    CHANNEL_URL = channel_input

if CHANNEL_URL.endswith("/"):
    CHANNEL_URL = CHANNEL_URL[:-1]

print(f"Using channel: {CHANNEL_URL}")

count_input = input("How many videos to download? (default 10): ").strip()
COUNT = int(count_input) if count_input.isdigit() else 10
print(f"Will download {COUNT} videos.\n")
# ----------------------------

print(f"[START] Preparing {COUNT} videos from {CHANNEL_URL}")

os.makedirs("raw", exist_ok=True)
os.makedirs("videos", exist_ok=True)

print("[1/4] Downloading videos...")
cmd_dl = [
    "yt-dlp",
    "-f", "mp4",
    "-o", "raw/%(title)s.%(ext)s",
    "--playlist-end", str(COUNT),
    CHANNEL_URL
]
try:
    subprocess.run(cmd_dl, check=True)
except subprocess.CalledProcessError as e:
    print(f"❌ Download failed: {e}")
    sys.exit(1)

raw_files = [f for f in os.listdir("raw") if f.endswith(".mp4")]
print(f"Downloaded {len(raw_files)} files.")

if not raw_files:
    print("❌ No videos downloaded.")
    sys.exit(1)

# Process videos
new_entries = []
for i, filename in enumerate(raw_files, 1):
    input_path = os.path.join("raw", filename)
    output_name = f"vid_{i:03d}.mp4"
    output_path = os.path.join("videos", output_name)

    print(f"[2/4] Processing {i}/{len(raw_files)}: {output_name}")
    cmd_ff = [
        "ffmpeg",
        "-i", input_path,
        "-af", "asetrate=44100*0.99,aresample=44100",
        "-vf", "crop=ih*9/16:ih",
        "-c:v", "libx264",
        "-preset", "fast",
        "-y",
        output_path
    ]
    subprocess.run(cmd_ff, check=True, capture_output=True)
    new_entries.append(f"videos/{output_name}")
    os.remove(input_path)

# Update queue.txt
print("[3/4] Updating queue...")
with open("queue.txt", "a") as f:
    for entry in new_entries:
        f.write(f"{entry}\n")

# Git operations
print("[4/4] Pushing to GitHub...")

# First, pull latest changes to avoid rejection
pull_result = subprocess.run(["git", "pull", "--rebase"], capture_output=True, text=True)
if pull_result.returncode != 0:
    print("⚠️  Git pull failed. Trying a normal pull...")
    subprocess.run(["git", "pull"], check=False)

# Add, commit, push
subprocess.run(["git", "add", "videos/", "queue.txt"], check=True)
subprocess.run(["git", "commit", "-m", f"Added {len(new_entries)} new prepared videos"], check=True)
push_result = subprocess.run(["git", "push"], capture_output=True, text=True)

if push_result.returncode != 0:
    print("❌ Git push failed. Please run manually:")
    print("   git pull")
    print("   git push")
    sys.exit(1)

print(f"\n✅ SUCCESS! Added {len(new_entries)} videos to the queue.")
print("They will be uploaded automatically by the bot every 2 hours.")
try:
    os.rmdir("raw")
except OSError:
    pass