import os
import sys
import argparse
from huggingface_hub import snapshot_download

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
        
    return None

def main():
    parser = argparse.ArgumentParser(description="허깅페이스에서 이미지 찾기 앱 원본 복원")
    parser.add_argument("--dest", default=PROJECT_DIR, help="복원할 대상 디렉토리 경로 (기본값: 현재 폴더)")
    parser.add_argument("--token", default=None, help="Hugging Face User Access Token")
    args = parser.parse_args()

    token = args.token or get_token()
    if not token:
        token = input("🔑 허깅페이스 Access Token을 입력하세요 (hf_...): ").strip()

    target_dir = os.path.abspath(args.dest)
    os.makedirs(target_dir, exist_ok=True)

    print(f"📥 허깅페이스 저장소({REPO_ID})에서 복원을 시작합니다...")
    print(f"📂 대상 경로: {target_dir}")

    try:
        snapshot_download(
            repo_id=REPO_ID,
            repo_type="model",
            local_dir=target_dir,
            token=token,
            ignore_patterns=[".gitattributes"]
        )
        print("\n🎉 모든 코드와 모델 파일이 성공적으로 복원되었습니다!")
        print(f"👉 실행 방법: cd '{target_dir}' && ./실행.command")
    except Exception as e:
        print(f"\n❌ 복원 중 오류 발생: {e}")

if __name__ == "__main__":
    main()
