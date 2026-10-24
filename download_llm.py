import os
import sys
import time
import zipfile
import io
import urllib.request

MODELS = {
    "1": {
        "name": "Qwen 2.5 0.5B Instruct (Ultra-Fast, ~468 MB, Best for GT 730 2GB GPU)",
        "filename": "qwen2.5-0.5b-instruct-q4_k_m.gguf",
        "url": "https://huggingface.co/Qwen/Qwen2.5-0.5B-Instruct-GGUF/resolve/main/qwen2.5-0.5b-instruct-q4_k_m.gguf"
    },
    "2": {
        "name": "Qwen 2.5 1.5B Instruct (Deeper Reasoning, ~986 MB, High Accuracy)",
        "filename": "qwen2.5-1.5b-instruct-q4_k_m.gguf",
        "url": "https://huggingface.co/Qwen/Qwen2.5-1.5B-Instruct-GGUF/resolve/main/qwen2.5-1.5b-instruct-q4_k_m.gguf"
    }
}

LLAMA_VULKAN_URL = "https://github.com/ggml-org/llama.cpp/releases/download/b11751/llama-b11751-bin-win-vulkan-x64.zip"

def download_file_with_progress(url: str, dest_path: str, label: str):
    print(f"\n[+] Downloading {label}...")
    print(f"    From: {url}")
    print(f"    To:   {dest_path}")
    
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    start_t = time.time()
    with urllib.request.urlopen(req) as resp, open(dest_path, "wb") as f:
        total = int(resp.headers.get("content-length", 0))
        downloaded = 0
        while True:
            chunk = resp.read(1024 * 1024 * 2) # 2MB
            if not chunk:
                break
            f.write(chunk)
            downloaded += len(chunk)
            pct = (downloaded / total * 100) if total else 0
            elapsed = time.time() - start_t + 0.001
            speed = (downloaded / (1024 * 1024)) / elapsed
            print(f"\r    Progress: {downloaded/(1024*1024):.1f}/{total/(1024*1024):.1f} MB ({pct:.1f}%) @ {speed:.2f} MB/s", end="", flush=True)
    print("\n[+] Download complete!")

def ensure_llama_server():
    bin_dir = os.path.join("models", "llama_bin")
    server_exe = os.path.join(bin_dir, "llama-server.exe")
    if os.path.exists(server_exe):
        print(f"[✓] llama-server found at {server_exe}")
        return True

    print("\n[*] Downloading llama.cpp Vulkan/GPU Windows binaries (35 MB)...")
    req = urllib.request.Request(LLAMA_VULKAN_URL, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req) as resp:
        content = resp.read()
        with zipfile.ZipFile(io.BytesIO(content)) as z:
            os.makedirs(bin_dir, exist_ok=True)
            z.extractall(bin_dir)
            print(f"[✓] Successfully extracted llama-server to {bin_dir}")
    return True

def main():
    print("=" * 60)
    print("  CoinDCX AI Trading Terminal - Local LLM Setup")
    print("  Priority: GPU VRAM First (Kepler/CUDA/Vulkan Acceleration)")
    print("=" * 60)
    
    os.makedirs("models", exist_ok=True)
    ensure_llama_server()

    # Check existing models
    existing = [f for f in os.listdir("models") if f.endswith(".gguf")]
    if existing:
        print(f"\n[✓] Existing models detected in ./models/: {', '.join(existing)}")
    
    choice = "1"
    if len(sys.argv) > 1:
        choice = sys.argv[1]
    else:
        print("\nSelect model to download:")
        for k, v in MODELS.items():
            status = "[INSTALLED]" if os.path.exists(os.path.join("models", v["filename"])) else "[DOWNLOAD]"
            print(f"  [{k}] {v['name']} {status}")
        user_in = input("\nEnter choice (default 1): ").strip()
        if user_in in MODELS:
            choice = user_in

    m = MODELS[choice]
    target_file = os.path.join("models", m["filename"])
    if os.path.exists(target_file):
        print(f"[✓] Model {m['filename']} is already installed and ready to trade!")
    else:
        download_file_with_progress(m["url"], target_file, m["name"])

    print("\n[✓] All AI model requirements ready for offline trading execution.")

if __name__ == "__main__":
    main()
