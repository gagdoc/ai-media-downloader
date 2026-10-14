import os
import sys
from huggingface_hub import HfApi

REPO_ID = "gagdox/image-finder-backup"
PROJECT_DIR = os.path.dirname(os.path.abspath(__file__))

def get_token():
    # 1. Environment variable
    token = os.environ.get("HF_TOKEN")
    if token:
        return token.strip()
    
    # 2. Local .env file
    env_file = os.path.join(PROJECT_DIR, ".env")
    if os.path.exists(env_file):
        with open(env_file, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line.startswith("HF_TOKEN="):
                    return line.split("=", 1)[1].strip().strip('"').strip("'")
    
    # 3. huggingface-cli saved token
    try:
        from huggingface_hub import get_token as hf_get_token
        saved = hf_get_token()
        if saved:
            return saved
    except Exception:
        pass
    
    raise ValueError("HF_TOKEN not found! Please check .env or environment variable.")

# Patterns to ignore during upload
IGNORE_PATTERNS = [
    ".venv/**",
    "venv/**",
    ".env*",
    "__pycache__/**",
    "downloads/**",
    "*.pyc",
    ".DS_Store",
    "test_*.py",
    "test_cookies.txt",
    "*.png",
    "*.mp4",
    "*.m4a",
    "*.webm"
]

def main():
    token = get_token()
    print(f"🚀 허깅페이스 백업 시작: {REPO_ID}")
    api = HfApi(token=token)
    
    # Ensure repo exists
    api.create_repo(repo_id=REPO_ID, repo_type="model", private=True, exist_ok=True)
    
    # Upload folder
    api.upload_folder(
        folder_path=PROJECT_DIR,
        repo_id=REPO_ID,
        repo_type="model",
        ignore_patterns=IGNORE_PATTERNS,
        commit_message="Backup from Mac local"
    )
    print(f"✅ 백업 성공 완료! 저장소: https://huggingface.co/{REPO_ID}")

if __name__ == "__main__":
    main()
