#!/bin/bash
DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
cd "$DIR"

echo "======================================"
echo " 🚀 Hugging Face 안전 백업 시작"
echo "======================================"

if [ -f ".venv/bin/python" ]; then
    .venv/bin/python hf_backup.py
else
    python3 hf_backup.py
fi

echo ""
read -p "엔터 키를 누르면 창이 닫힙니다..."
