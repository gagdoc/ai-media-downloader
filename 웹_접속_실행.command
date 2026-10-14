#!/bin/bash
DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
cd "$DIR"

echo "=========================================================="
echo " 🌐 AI 미디어 일괄 다운로더 - 웹 접속 모드 실행 중..."
echo "=========================================================="
echo ""

# 기존 Streamlit 프로세스 정리 (포트 8501 충돌 방지)
pkill -f "streamlit run app.py" 2>/dev/null
pkill -f "cloudflared tunnel" 2>/dev/null
sleep 1

# 가상환경 활성화
if [ -d ".venv" ]; then
    source .venv/bin/activate
fi

# Streamlit 백그라운드 실행
echo "🚀 [1/2] 로컬 서버 구동 중..."
streamlit run app.py --server.headless=true --server.port=8501 > /dev/null 2>&1 &
STREAMLIT_PID=$!

# 서버 시작 대기
sleep 2

# Cloudflare 터널 경로 탐색
CLOUDFLARE_BIN="/opt/homebrew/bin/cloudflared"
if [ ! -f "$CLOUDFLARE_BIN" ]; then
    CLOUDFLARE_BIN=$(which cloudflared)
fi

if [ -z "$CLOUDFLARE_BIN" ]; then
    echo "❌ cloudflared 명령어를 찾을 수 없습니다."
    kill $STREAMLIT_PID 2>/dev/null
    exit 1
fi

echo "🌍 [2/2] 외부 접속용 보안 웹 링크 생성 중..."
echo ""

# 임시 로그 파일 생성
TUNNEL_LOG="/tmp/cf_media_tunnel.log"
rm -f "$TUNNEL_LOG"

# 터널 실행
$CLOUDFLARE_BIN tunnel --url http://127.0.0.1:8501 > "$TUNNEL_LOG" 2>&1 &
TUNNEL_PID=$!

# URL 감지 루프 (최대 20초)
TUNNEL_URL=""
for i in {1..20}; do
    TUNNEL_URL=$(grep -o 'https://[-a-zA-Z0-9]*\.trycloudflare\.com' "$TUNNEL_LOG" | head -n 1)
    if [ -n "$TUNNEL_URL" ]; then
        break
    fi
    sleep 1
done

if [ -n "$TUNNEL_URL" ]; then
    echo "=========================================================="
    echo " 🎉 웹 접속 주소가 준비되었습니다!"
    echo " 📱 스마트폰이나 다른 기기에서 아래 링크로 접속하세요:"
    echo ""
    echo " 👉 $TUNNEL_URL"
    echo ""
    echo " (맥북 브라우저에서도 위 주소 또는 http://localhost:8501 로 접속 가능합니다)"
    echo "=========================================================="
    echo ""
    echo "⚠️ 이 터미널 창을 닫으면 웹 접속이 종료됩니다."
    
    # 기본 브라우저로 열기
    open "$TUNNEL_URL"
else
    echo "⚠️ 웹 링크 생성에 시간이 걸리고 있습니다."
    echo "로그 내용 확인: cat $TUNNEL_LOG"
fi

# 종료 처리 핸들러 (Ctrl+C 등으로 닫을 때 자식 프로세스 자동 종료)
cleanup() {
    echo ""
    echo "🛑 웹 서버 및 터널을 안전하게 종료합니다..."
    kill $STREAMLIT_PID 2>/dev/null
    kill $TUNNEL_PID 2>/dev/null
    exit 0
}
trap cleanup SIGINT SIGTERM EXIT

# 프로세스 대기
wait $STREAMLIT_PID
