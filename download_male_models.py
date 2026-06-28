"""Download all male voice models from HF mirror (China-friendly)"""
import os
import urllib.request
import urllib.parse

# Mirror for China access
HF_BASE = "https://hf-mirror.com/chaye741/RVC-Voice-Models/resolve/main"

# Male models to download: (folder, chinese_name, pinyin_name)
MODELS = [
    # Numbered male voices
    ("weights", "男声-01号", "nansheng_01"),
    ("weights", "男声-02号", "nansheng_02"),
    ("weights", "男声-03号", "nansheng_03"),
    ("weights", "男声-04号", "nansheng_04"),
    ("weights", "男声-06号", "nansheng_06"),
    ("weights", "男声-07号", "nansheng_07"),
    ("weights", "男声-08号", "nansheng_08"),
    ("weights", "男声-09号", "nansheng_09"),
    ("weights", "男声-10号", "nansheng_10"),
    # Special male voices
    ("weights", "男声-烟嗓", "nansheng_yansang"),     # smoky voice
    ("weights", "男声-男神", "nansheng_nanshen"),     # male god / magnetic
    ("weights", "男声-青年", "nansheng_qingnian"),    # young male
    ("weights", "男声-青年瘦弱", "nansheng_shouruo"), # thin young male
    # Famous male voices
    ("weights", "丁真", "dingzhen"),
    ("weights", "卢本伟", "lubenwei"),
]

# Corresponding index files
INDICES = [
    ("indices", "男声-01号", "nansheng_01"),
    ("indices", "男声-02号", "nansheng_02"),
    ("indices", "男声-03号", "nansheng_03"),
    ("indices", "男声-04号", "nansheng_04"),
    ("indices", "男声-06号", "nansheng_06"),
    ("indices", "男声-07号", "nansheng_07"),
    ("indices", "男声-08号", "nansheng_08"),
    ("indices", "男声-09号", "nansheng_09"),
    ("indices", "男声-10号", "nansheng_10"),
    ("indices", "男声-烟嗓", "nansheng_yansang"),
    ("indices", "男声-男神", "nansheng_nanshen"),
    ("indices", "男声-青年", "nansheng_qingnian"),
    ("indices", "男声-青年瘦弱", "nansheng_shouruo"),
    ("indices", "丁真", "dingzhen"),
    ("indices", "卢本伟", "lubenwei"),
]

DEST_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "assets", "weights")
os.makedirs(DEST_DIR, exist_ok=True)

def download(folder, cn_name, py_name, ext):
    """Download a single model file"""
    url_path = f"{folder}/{urllib.parse.quote(cn_name)}.{ext}"
    url = f"{HF_BASE}/{url_path}"
    dest = os.path.join(DEST_DIR, f"{py_name}.{ext}")

    if os.path.exists(dest):
        size = os.path.getsize(dest)
        if size > 1000000:  # > 1MB, probably complete
            print(f"  [SKIP] {py_name}.{ext} (already exists, {size//1024//1024}MB)")
            return True
        print(f"  [RETRY] {py_name}.{ext} (file too small, redownloading...)")

    print(f"  [DOWNLOAD] {cn_name} -> {py_name}.{ext} ...", end=" ", flush=True)
    try:
        urllib.request.urlretrieve(url, dest)
        size_mb = os.path.getsize(dest) / 1024 / 1024
        print(f"{size_mb:.1f}MB OK")
        return True
    except Exception as e:
        print(f"FAILED: {e}")
        return False

# Download all .pth files
print("=" * 50)
print("Downloading male voice models (.pth)")
print("=" * 50)
for folder, cn_name, py_name in MODELS:
    download(folder, cn_name, py_name, "pth")

# Download all .index files
print("")
print("=" * 50)
print("Downloading male voice indices (.index)")
print("=" * 50)
for folder, cn_name, py_name in INDICES:
    download(folder, cn_name, py_name, "index")

print("")
print("Done!")
