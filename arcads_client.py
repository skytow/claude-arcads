import requests, time, os, subprocess, shutil

try:
    from dotenv import load_dotenv
    load_dotenv()
except ModuleNotFoundError:
    env_path = os.path.join(os.path.dirname(__file__), ".env")
    if os.path.exists(env_path):
        with open(env_path) as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                key, value = line.split("=", 1)
                os.environ.setdefault(key, value)

AUTH = os.getenv("ARCADS_KEY")
PRODUCT_ID = os.getenv("ARCADS_PRODUCT_ID")
BASE = "https://external-api.arcads.ai"
HEADERS = {"Authorization": AUTH, "Content-Type": "application/json"}


def get_ffmpeg():
    exe = subprocess.run(
        ["python3", "-c", "import imageio_ffmpeg; print(imageio_ffmpeg.get_ffmpeg_exe())"],
        capture_output=True, text=True
    ).stdout.strip()
    if exe:
        return exe
    system_ffmpeg = shutil.which("ffmpeg")
    if system_ffmpeg:
        return system_ffmpeg
    raise RuntimeError("ffmpeg not found: install imageio_ffmpeg or put ffmpeg on PATH")


def upload_file(filepath, filetype):
    r = requests.post(f"{BASE}/v1/file-upload/get-presigned-url", headers=HEADERS, json={"fileType": filetype})
    data = r.json()
    with open(filepath, "rb") as f:
        requests.put(data["presignedUrl"], data=f, headers={"Content-Type": filetype})
    return data["filePath"]


def generate_video(prompt, duration, ref_images=None, ref_videos=None, aspect_ratio="9:16", resolution="720p"):
    payload = {
        "model": "seedance-2.0",
        "productId": PRODUCT_ID,
        "aspectRatio": aspect_ratio,
        "duration": duration,
        "resolution": resolution,
        "prompt": prompt,
    }
    if ref_images:
        payload["referenceImages"] = ref_images
    if ref_videos:
        payload["referenceVideos"] = ref_videos
    r = requests.post(f"{BASE}/v2/videos/generate", headers=HEADERS, json=payload)
    d = r.json()
    print(f"  Job ID: {d.get('id')} | Credits: {d.get('data', {}).get('creditsCharged', '?')}", flush=True)
    if not d.get("id"):
        print(f"  Arcads response: {d}", flush=True)
    return d.get("id"), d.get("data", {}).get("creditsCharged", "?")


def poll(asset_id, label="Generating"):
    if not asset_id:
        raise RuntimeError(f"No Arcads asset id returned for {label}; refusing to poll /v1/assets/None")
    while True:
        time.sleep(30)
        r = requests.get(f"{BASE}/v1/assets/{asset_id}", headers=HEADERS)
        status = r.json().get("status", "?")
        print(f"  {time.strftime('%H:%M:%S')} {label}: {status}", flush=True)
        if status in ("generated", "failed"):
            return r.json()


def download(asset_data, dest):
    url = asset_data.get("url", "")
    if not url:
        print("  No URL in response.")
        return False
    r = requests.get(url, stream=True)
    with open(dest, "wb") as f:
        for chunk in r.iter_content(chunk_size=8192):
            f.write(chunk)
    print(f"  Saved: {dest} ({os.path.getsize(dest) // 1024}KB)", flush=True)
    return True


def next_version(folder, prefix):
    existing = [f for f in os.listdir(folder) if f.startswith(prefix) and f.endswith(".mp4")]
    return len(existing) + 1
