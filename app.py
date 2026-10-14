import streamlit as st
import os
import re
import subprocess
import tempfile
from downloader import scrape_image_urls, download_images, get_youtube_info, download_youtube_video, create_video_from_images, extract_m3u8_from_webpage, download_web_video, scrape_instagram, merge_videos, reencode_video_for_mac, merge_images
from PIL import Image
# Page configuration
st.set_page_config(
    page_title="AI Media Batch Downloader",
    page_icon="🎬",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# Custom premium CSS styling
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Outfit:wght@300;400;600;800&display=swap');
    
    html, body, [class*="css"] {
        font-family: 'Outfit', sans-serif;
    }
    
    .main-title {
        font-size: 3.2rem;
        font-weight: 800;
        background: linear-gradient(135deg, #FF4B4B, #FF8F00, #E040FB);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        margin-bottom: 0.2rem;
        text-align: center;
        letter-spacing: -1px;
    }
    
    .sub-title {
        font-size: 1.15rem;
        color: #888888;
        text-align: center;
        margin-bottom: 2.5rem;
    }
    
    .stButton>button {
        background: linear-gradient(90deg, #FF4B4B, #FF8F00) !important;
        color: white !important;
        border: none !important;
        padding: 0.6rem 2rem !important;
        font-weight: 600 !important;
        font-size: 1.1rem !important;
        border-radius: 12px !important;
        box-shadow: 0 4px 15px rgba(255, 75, 75, 0.3) !important;
        transition: all 0.3s ease !important;
    }
    
    .stButton>button:hover {
        transform: translateY(-2px) !important;
        box-shadow: 0 6px 20px rgba(255, 75, 75, 0.4) !important;
    }
    
    .stButton>button:active {
        transform: translateY(0px) !important;
    }
    
    .yt-card {
        background-color: #1e1e1e;
        border-radius: 16px;
        padding: 1.5rem;
        border: 1px solid #333333;
        margin-bottom: 1.5rem;
    }
</style>
""", unsafe_allow_html=True)

# Main UI title
st.markdown('<h1 class="main-title">🎬 AI 미디어 일괄 다운로더</h1>', unsafe_allow_html=True)
st.markdown('<p class="sub-title">고화질 이미지 크롤링, 유튜브 비디오 추출, 맥북 전용 영상 재인코딩, 사진으로 동영상 만들기까지 올인원 미디어 스튜디오.</p>', unsafe_allow_html=True)

# Thread-safe macOS native folder picker using AppleScript (Forces Finder to foreground)
def select_folder_via_applescript(prompt="저장할 폴더를 선택하세요:"):
    try:
        script = f'''
        tell application "Finder"
            activate
            set selectedFolder to choose folder with prompt "{prompt}"
            return POSIX path of selectedFolder
        end tell
        '''
        proc = subprocess.run(
            ['osascript', '-e', script],
            capture_output=True,
            text=True
        )
        if proc.returncode == 0:
            return proc.stdout.strip()
    except Exception as e:
        pass
    return None

# Format YouTube duration into human-readable format
def format_duration(seconds):
    if not seconds:
        return "알 수 없음"
    mins, secs = divmod(seconds, 60)
    hours, mins = divmod(mins, 60)
    if hours > 0:
        return f"{hours:02d}:{mins:02d}:{secs:02d}"
    return f"{mins:02d}:{secs:02d}"

# Initialize Session States
if "scraped_urls" not in st.session_state:
    st.session_state.scraped_urls = []
if "search_keyword" not in st.session_state:
    st.session_state.search_keyword = ""
if "save_dir" not in st.session_state:
    st.session_state.save_dir = "/Users/gagdox/Pictures/AuraLens_Sorted/소스/"
if "yt_save_dir" not in st.session_state:
    st.session_state.yt_save_dir = "/Users/gagdox/Pictures/AuraLens_Sorted/소스/"
if "yt_info" not in st.session_state:
    st.session_state.yt_info = None
if "mac_reencode_dir" not in st.session_state:
    st.session_state.mac_reencode_dir = "/Users/gagdox/Pictures/AuraLens_Sorted/소스/"
if "mac_reencode_out_dir" not in st.session_state:
    st.session_state.mac_reencode_out_dir = "/Users/gagdox/Pictures/AuraLens_Sorted/소스/"
if "mac_reencode_results" not in st.session_state:
    st.session_state.mac_reencode_results = []
if "slideshow_dir" not in st.session_state:
    st.session_state.slideshow_dir = "/Users/gagdox/Pictures/AuraLens_Sorted/소스/"
if "slideshow_out_dir" not in st.session_state:
    st.session_state.slideshow_out_dir = "/Users/gagdox/Pictures/AuraLens_Sorted/소스/"
if "generated_video_path" not in st.session_state:
    st.session_state.generated_video_path = None
if "web_save_dir" not in st.session_state:
    st.session_state.web_save_dir = "/Users/gagdox/Pictures/AuraLens_Sorted/소스/"
if "web_m3u8_url" not in st.session_state:
    st.session_state.web_m3u8_url = None
if "webm_convert_dir" not in st.session_state:
    st.session_state.webm_convert_dir = "/Users/gagdox/Pictures/AuraLens_Sorted/소스/"
if "webm_output_dir" not in st.session_state:
    st.session_state.webm_output_dir = "/Users/gagdox/Pictures/AuraLens_Sorted/소스/"
if "webm_convert_results" not in st.session_state:
    st.session_state.webm_convert_results = []
if "merge_video_items" not in st.session_state:
    st.session_state.merge_video_items = []
if "merge_uploader_signature" not in st.session_state:
    st.session_state.merge_uploader_signature = None
if "merge_save_dir" not in st.session_state:
    st.session_state.merge_save_dir = "/Users/gagdox/Pictures/AuraLens_Sorted/소스/"

# Image Merge Session States
if "img_merge_items" not in st.session_state:
    st.session_state.img_merge_items = []
if "img_merge_uploader_signature" not in st.session_state:
    st.session_state.img_merge_uploader_signature = None
if "img_merge_save_dir" not in st.session_state:
    st.session_state.img_merge_save_dir = "/Users/gagdox/Pictures/AuraLens_Sorted/소스/"


# Tab Layout
tab1, tab2, tab_mac, tab3, tab4, tab5, tab6, tab_img_merge = st.tabs([
    "📷 이미지 일괄 다운로더",
    "🎥 유튜브 / 인스타 영상 다운로더",
    "🍏 맥북(QuickTime) 호환 재인코딩",
    "🎬 이미지로 영상 만들기",
    "🌐 일반 웹 영상 다운로더",
    "🔄 WEBM → MP4 변환",
    "🎬 영상 순서 병합 (이어붙이기)",
    "🖼️ 이미지 나란히 붙이기"
])


# ==================== TAB 1: 이미지 다운로더 ====================
with tab1:
    col1, col2 = st.columns([1, 2], gap="large")
    
    with col1:
        st.subheader("⚙️ 이미지 설정")
        st.write("---")
        
        mode = st.radio("⬇️ 수집 방식 선택", ["키워드로 이미지 검색", "인스타그램 링크로 가져오기"], horizontal=True)
        
        if mode == "키워드로 이미지 검색":
            keyword = st.text_input("🔍 검색 키워드 입력", placeholder="예: 우주성운, 스포츠카, 귀여운 고양이", key="img_keyword")
            limit = st.slider("📦 최대 검색 개수 지정", min_value=5, max_value=200, value=30, step=5, key="img_limit")
            
            # Engine Selection
            engine = st.selectbox(
                "🌐 검색 엔진 선택",
                options=["Bing", "Google", "Instagram"],
                format_func=lambda x: "Bing (권장 - 캡차 없음/고속)" if x == "Bing" else ("Google (검색 결과 상이/캡차 위험 있음)" if x == "Google" else "Instagram (Bing 색인 검색 - 로그인 불필요)"),
                index=0,
                key="img_engine"
            )
            default_subfolder = keyword if keyword else "images"
        else:
            insta_url = st.text_input("🔗 인스타그램 게시물 링크(URL)", placeholder="https://www.instagram.com/p/...", key="insta_url")
            keyword = "instagram_post" # For internal search keyword state
            limit = 0 # Not used
            engine = "Instagram"
            default_subfolder = "instagram_post"
            
        subfolder_name = st.text_input("📁 세부 저장 폴더명 (상위 폴더 하위에 생성됩니다)", value=default_subfolder, key="img_subfolder")
            
        # Folder Path Row Layout (Text input + Finder button)
        path_col, button_col = st.columns([3, 1])
        with path_col:
            st.text_input("📁 저장 디렉토리 경로", key="save_dir")
        with button_col:
            def on_img_folder_pick():
                path = select_folder_via_applescript("이미지를 저장할 폴더를 선택하세요:")
                if path:
                    st.session_state.save_dir = path
                    
            st.button("📁 폴더 선택", key="img_finder_btn", on_click=on_img_folder_pick, use_container_width=True)
                    
        st.write("")
        search_btn = st.button("🔍 이미지 수집 및 분석 시작", key="img_search_btn", use_container_width=True)
        
    with col2:
        st.subheader("📊 이미지 추출 및 다운로드 진행")
        st.write("---")
        
        if search_btn:
            if mode == "키워드로 이미지 검색" and not keyword.strip():
                st.warning("⚠️ 검색할 키워드를 먼저 입력해 주세요!")
            elif mode == "인스타그램 링크로 가져오기" and not insta_url.strip():
                st.warning("⚠️ 인스타그램 링크를 먼저 입력해 주세요!")
            else:
                # Clear previous selection state to initialize checkboxes
                for k in list(st.session_state.keys()):
                    if k.startswith("img_cb_"):
                        del st.session_state[k]
                        
                st.session_state.search_keyword = keyword.strip()
                status_container = st.empty()
                if mode == "키워드로 이미지 검색":
                    status_container.info(f"🔗 '{keyword}' 키워드로 {engine}에서 고화질 원본 이미지 주소를 분석 중입니다...")
                else:
                    status_container.info(f"🔗 인스타그램 링크에서 이미지를 추출 중입니다...")
                
                scraping_progress = st.progress(0)
                scraping_text = st.empty()
                
                def scrape_cb(current, total):
                    if total > 0:
                        scraping_progress.progress(current / total)
                    scraping_text.markdown(f"**URL 추출 진행 상황:** `{current} / {total}` 개 탐색 완료")
                
                if mode == "키워드로 이미지 검색":
                    urls = scrape_image_urls(keyword, limit=limit, engine=engine, progress_callback=scrape_cb)
                else:
                    urls = scrape_instagram(insta_url.strip(), progress_callback=scrape_cb)
                
                if urls:
                    st.session_state.scraped_urls = urls
                    scraping_progress.progress(1.0)
                    scraping_text.markdown(f"✨ **추출 성공:** 총 `{len(urls)}`개의 고화질 이미지 경로를 찾았습니다! 아래 갤러리에서 다운로드할 이미지를 선택해 주세요.")
                    status_container.success("🎉 이미지 추출이 완료되었습니다. 이제 다운로드할 이미지를 선택하여 다운로드해 주세요.")
                else:
                    st.session_state.scraped_urls = []
                    if engine == "Google":
                        status_container.error(
                            "⚠️ **구글 이미지 검색에서 자동화 수집 차단(reCAPTCHA)이 발생했습니다.**\n\n"
                            "구글의 매우 엄격한 보안 정책으로 인해 현재 네트워크 환경에서의 자동 크롤링이 일시적으로 차단되었습니다.\n\n"
                            "💡 **해결 방법:** 왼쪽 메뉴의 **🌐 검색 엔진 선택**에서 **Bing (권장 - 캡차 없음/고속)**으로 변경한 뒤 다시 검색해 주세요! Bing은 캡차 블록 없이 고화질 원본 이미지를 즉시 안정적으로 다운로드할 수 있습니다."
                        )
                    elif engine == "Instagram":
                        if mode == "인스타그램 링크로 가져오기":
                            status_container.error("❌ 인스타그램에서 이미지를 수집하지 못했습니다. 링크가 올바르지 않거나, 로그인이 필요한 비공개 게시물일 수 있습니다.")
                        else:
                            status_container.error("❌ 인스타그램 키워드 검색 결과 이미지를 수집하지 못했습니다. 검색 키워드를 변경해 보시거나 네트워크 설정을 확인해 주세요.")
                    else:
                        status_container.error("❌ 이미지를 수집하지 못했습니다. 키워드에 특수문자가 들어있거나 네트워크 방화벽이 차단 중인지 확인해 주세요.")
                        
        # Display Interactive Image Selection Grid
        if st.session_state.scraped_urls:
            st.write("")
            st.subheader("🖼&nbsp; 다운로드할 이미지 선택 (수동 체크 필요)")
            st.write("기본적으로 모두 선택 해제 상태로 시작됩니다. 다운로드하고자 하는 이미지의 **선택** 박스를 클릭해 체크해 주세요.")
            
            btn_col1, btn_col2, _ = st.columns([1, 1, 3])
            with btn_col1:
                if st.button("✅ 전체 선택", use_container_width=True):
                    for idx in range(len(st.session_state.scraped_urls)):
                        st.session_state[f"img_cb_{idx}"] = True
            with btn_col2:
                if st.button("❌ 전체 해제", use_container_width=True):
                    for idx in range(len(st.session_state.scraped_urls)):
                        st.session_state[f"img_cb_{idx}"] = False
            
            st.write("---")
            
            cols = st.columns(4)
            selected_urls = []
            
            for idx, url in enumerate(st.session_state.scraped_urls):
                if f"img_cb_{idx}" not in st.session_state:
                    st.session_state[f"img_cb_{idx}"] = False
                    
                with cols[idx % 4]:
                    try:
                        st.image(url, use_container_width=True)
                        is_selected = st.checkbox("선택", key=f"img_cb_{idx}")
                        if is_selected:
                            selected_urls.append(url)
                    except Exception:
                        is_selected = st.checkbox(f"이미지 {idx+1} (미리보기 실패)", key=f"img_cb_{idx}")
                        if is_selected:
                            selected_urls.append(url)
            
            st.write("---")
            st.markdown(f"**현재 선택된 이미지 수:** `{len(selected_urls)}` / `{len(st.session_state.scraped_urls)}` 개")
            
            download_selected_btn = st.button("📥 선택한 이미지 일괄 다운로드 시작", key="img_download_btn", use_container_width=True)
            
            if download_selected_btn:
                if not selected_urls:
                    st.warning("⚠️ 최소 1개 이상의 이미지를 선택해야 다운로드할 수 있습니다!")
                else:
                    download_status = st.empty()
                    download_status.info("📥 선택된 이미지를 지정된 폴더에 저장하는 중...")
                    
                    downloading_progress = st.progress(0)
                    downloading_text = st.empty()
                    log_container = st.empty()
                    log_list = []
                    
                    def download_cb(current, total):
                        downloading_progress.progress(current / total)
                        downloading_text.markdown(f"**로컬 저장 중:** `{current} / {total}` 개 파일 다운로드 중...")
                        
                        log_list.append(f"[{current:03d}/{total:03d}] {st.session_state.save_dir}/{st.session_state.img_subfolder}/{st.session_state.img_subfolder}_{current:03d} 저장 완료.")
                        log_container.code("\n".join(log_list[-6:]))
                    
                    downloaded_files = download_images(
                        keyword=st.session_state.img_subfolder,
                        urls=selected_urls,
                        base_dir=st.session_state.save_dir,
                        progress_callback=download_cb
                    )
                    
                    download_status.success(f"🎉 **일괄 다운로드 완료!** 총 `{len(downloaded_files)}`개의 이미지가 `{os.path.abspath(os.path.join(st.session_state.save_dir, st.session_state.img_subfolder))}/` 경로에 모두 저장되었습니다!")
        else:
            if not search_btn:
                st.info("💡 왼쪽에 키워드와 다운로드 수량을 입력한 뒤, **이미지 검색 및 분석 시작** 버튼을 눌러주세요.")

# ==================== TAB 2: 유튜브 / 인스타 영상 다운로더 ====================
with tab2:
    yt_col1, yt_col2 = st.columns([1, 2], gap="large")
    
    with yt_col1:
        st.subheader("⚙️ 영상 다운로드 설정")
        st.write("---")
        
        yt_url = st.text_input("🔗 유튜브 / 인스타 영상 링크(URL) 입력", placeholder="https://youtu.be/... 또는 https://www.instagram.com/reel/...")
        
        # Folder Path Row Layout (Text input + Finder button)
        yt_path_col, yt_button_col = st.columns([3, 1])
        with yt_path_col:
            st.text_input("📁 다운로드 폴더 지정", key="yt_save_dir")
        with yt_button_col:
            def on_yt_folder_pick():
                path = select_folder_via_applescript("영상을 저장할 폴더를 선택하세요:")
                if path:
                    st.session_state.yt_save_dir = path
                    
            st.button("📁 폴더 선택", key="yt_finder_btn", on_click=on_yt_folder_pick, use_container_width=True)
        
        st.write("")
        analyze_btn = st.button("🔍 영상 정보 분석", key="yt_analyze_btn", use_container_width=True)
        
        if yt_url.strip() and (analyze_btn or st.session_state.yt_info is not None):
            if analyze_btn or (st.session_state.yt_info and st.session_state.yt_info.get('_url') != yt_url.strip()):
                with st.spinner("영상 데이터를 분석하는 중..."):
                    info = get_youtube_info(yt_url.strip())
                    if info:
                        info['_url'] = yt_url.strip()
                        st.session_state.yt_info = info
                    else:
                        st.session_state.yt_info = None
                        st.error("❌ 영상 정보를 가져오지 못했습니다. 링크 주소가 올바른지 확인해 주세요.")
            
            if st.session_state.yt_info:
                st.write("")
                st.subheader("🎥 분석된 영상 정보")
                thumb_html = f'<img src="{st.session_state.yt_info["thumbnail"]}" style="width: 100%; border-radius: 8px; margin-bottom: 1rem;"/>' if st.session_state.yt_info.get('thumbnail') else ''
                st.markdown(
                    f"""
                    <div class="yt-card">
                        {thumb_html}
                        <h4 style="margin: 0.5rem 0; font-size: 1.1rem; line-height: 1.4;">{st.session_state.yt_info['title']}</h4>
                        <p style="color: #888888; font-size: 0.9rem; margin: 0.2rem 0;"><b>채널/작성자:</b> {st.session_state.yt_info['uploader']}</p>
                        <p style="color: #888888; font-size: 0.9rem; margin: 0.2rem 0;"><b>길이:</b> {format_duration(st.session_state.yt_info['duration'])}</p>
                    </div>
                    """, 
                    unsafe_allow_html=True
                )
                
                # Resolution list fetched dynamically
                resolutions = st.session_state.yt_info.get('resolutions', ["기본 고화질 (Best Quality)"])
                selected_quality = st.selectbox(
                    "🎬 다운로드 화질 선택",
                    options=resolutions,
                    index=0,
                    help="동영상의 가용 화질 목록입니다. 고해상도 선택 시 오디오와 비디오 결합 렌더링이 자동으로 수행됩니다."
                )
                
                mac_reencode_opt = st.checkbox(
                    "🍏 맥북(QuickTime/Finder) 100% 호환 자동 재인코딩 적용",
                    value=True,
                    help="체크 시 H.264 / AAC / yuv420p / +faststart 포맷으로 자동으로 변환하여 맥북 기본 플레이어 및 미리보기 오류를 완벽 방지합니다."
                )
                
                yt_download_btn = st.button("📥 MP4 영상 다운로드 시작", key="yt_download_btn", use_container_width=True)
                
    with yt_col2:
        st.subheader("📊 영상 다운로드 진행 현황")
        st.write("---")
        
        if 'yt_download_btn' in locals() and yt_download_btn and st.session_state.yt_info:
            yt_status = st.empty()
            yt_status.info("📥 동영상을 고화질로 다운로드하고 있습니다... 잠시만 기다려 주세요.")
            
            yt_progress = st.progress(0)
            yt_progress_text = st.empty()
            yt_log_box = st.empty()
            
            def yt_progress_cb(percent, speed, eta):
                yt_progress.progress(percent)
                speed_mb = speed / (1024 * 1024) if speed else 0
                eta_str = f"{int(eta)}초" if eta else "계산 중"
                yt_progress_text.markdown(f"**다운로드 진행률:** `{percent * 100:.1f}%` 완료")
                yt_log_box.code(
                    f"진행 속도: {speed_mb:.2f} MB/s\n"
                    f"남은 시간: {eta_str}\n"
                    f"저장 위치: {st.session_state.yt_save_dir}/"
                )
                
            downloaded_video = download_youtube_video(
                url=st.session_state.yt_info['_url'],
                base_dir=st.session_state.yt_save_dir,
                quality=selected_quality,
                progress_callback=yt_progress_cb,
                reencode_mac=mac_reencode_opt
            )
            
            if downloaded_video:
                yt_progress.progress(1.0)
                yt_progress_text.markdown("**다운로드 진행률:** `100.0%` 완료")
                yt_status.success(f"🎉 **다운로드 최종 성공!**\n\n영상 파일이 성공적으로 저장되었습니다:\n\n`{downloaded_video}`")
                yt_log_box.code(f"성공적으로 비디오 추출 완료.\n완료 경로: {downloaded_video}")
            else:
                yt_status.error("❌ 영상 다운로드 중 오류가 발생했습니다. 네트워크 환경 또는 영상 접근성(비공개/로그인 필요 등)을 확인해 주세요.")
        else:
            st.info("💡 왼쪽에 유튜브 또는 인스타그램 URL을 입력하고 **영상 정보 분석**을 마친 뒤, **다운로드 시작** 버튼을 눌러주세요.")


# ==================== TAB MAC: 맥북 전용 영상 재인코딩 ====================
with tab_mac:
    mac_col1, mac_col2 = st.columns([1, 2], gap="large")

    with mac_col1:
        st.subheader("⚙️ 맥북 호환 재인코딩 설정")
        st.write("---")
        st.markdown("유튜브/인스타 등에서 다운로드한 비디오가 맥북 QuickTime이나 Finder 공간(QuickLook)에서 **재생 불가, 검은 화면, 음성 미출력**인 경우 H.264 / AAC / yuv420p 규격으로 즉시 재인코딩합니다.")

        mac_input_mode = st.selectbox(
            "📤 비디오 불러오기 방식",
            options=["직접 동영상 파일 업로드 (최대 10GB)", "로컬 폴더에서 일괄 재인코딩", "파일 경로 직접 입력 (용량 무제한)"],
            index=0,
            key="mac_input_mode"
        )

        mac_files_to_convert = []  # list of (display_name, file_data_or_path, original_name)

        if mac_input_mode == "직접 동영상 파일 업로드 (최대 10GB)":
            st.info("ℹ️ 업로드 한도: **10 GB**. 그 이상은 **파일 경로 직접 입력** 방식을 추천합니다.")
            uploaded_mac_vids = st.file_uploader(
                "🎬 동영상 파일을 선택해 주세요 (다중 선택 가능)",
                type=["mp4", "mkv", "mov", "webm", "avi", "flv", "wmv", "m4v"],
                accept_multiple_files=True,
                key="mac_vids_uploader"
            )
            if uploaded_mac_vids:
                st.success(f"✅ 총 `{len(uploaded_mac_vids)}`개의 비디오 파일이 업로드되었습니다.")
                for uf in uploaded_mac_vids:
                    mac_files_to_convert.append((uf.name, uf.read(), uf.name))

        elif mac_input_mode == "파일 경로 직접 입력 (용량 무제한)":
            st.info("ℹ️ 파일 경로를 직접 입력하면 브라우저 업로드 과정 없이 **용량 무제한**으로 빠르게 처리됩니다.")
            mac_direct_paths_input = st.text_area(
                "📄 동영상 파일 경로 입력 (줄바꿈으로 여러 개 입력 가능)",
                placeholder="/Users/yourname/Downloads/youtube_clip.mp4\n/Users/yourname/Downloads/insta_reel.mkv",
                height=140,
                key="mac_direct_paths"
            )
            if mac_direct_paths_input.strip():
                raw_lines = [p.strip() for p in mac_direct_paths_input.strip().splitlines() if p.strip()]
                ok_count = 0
                for p in raw_lines:
                    if os.path.isfile(p):
                        mac_files_to_convert.append((os.path.basename(p), p, os.path.basename(p)))
                        ok_count += 1
                    else:
                        st.error(f"❌ 파일을 찾을 수 없습니다: `{p}`")
                if ok_count:
                    st.success(f"✅ 유효한 비디오 파일 `{ok_count}`개가 확인되었습니다.")
        else:
            mac_src_path_col, mac_src_btn_col = st.columns([3, 1])
            with mac_src_path_col:
                st.text_input("📁 비디오 파일이 있는 폴더 경로", key="mac_reencode_dir")
            with mac_src_btn_col:
                def on_mac_src_folder_pick():
                    path = select_folder_via_applescript("비디오 파일들이 있는 폴더를 선택하세요:")
                    if path:
                        st.session_state.mac_reencode_dir = path
                st.button("📁 폴더 선택", key="mac_src_finder_btn", on_click=on_mac_src_folder_pick, use_container_width=True)

            src_mac_dir = st.session_state.mac_reencode_dir
            if os.path.exists(src_mac_dir):
                valid_exts = ('.mp4', '.mkv', '.mov', '.webm', '.avi', '.flv', '.wmv', '.m4v')
                found_vids = [
                    f for f in sorted(os.listdir(src_mac_dir))
                    if f.lower().endswith(valid_exts) and not f.endswith('.mac_temp.mp4')
                ]
                if found_vids:
                    st.success(f"✅ 폴더에서 총 `{len(found_vids)}`개의 비디오 파일을 찾았습니다.")
                    for fname in found_vids:
                        mac_files_to_convert.append((fname, os.path.join(src_mac_dir, fname), fname))
                else:
                    st.warning("⚠️ 선택한 폴더에 동영상 파일이 존재하지 않습니다.")

        st.write("")
        st.markdown("**🎛️ 인코딩 화질 옵션**")
        mac_quality = st.selectbox(
            "화질 (CRF, 낮을수록 고화질)",
            options=["최고화질 (CRF 18)", "고화질 (CRF 22 - 권장)", "표준화질 (CRF 28)"],
            index=1,
            key="mac_quality"
        )
        mac_crf_map = {
            "최고화질 (CRF 18)": "18",
            "고화질 (CRF 22 - 권장)": "22",
            "표준화질 (CRF 28)": "28"
        }
        mac_crf_val = mac_crf_map[mac_quality]

        # Output folder selector
        mac_out_path_col, mac_out_btn_col = st.columns([3, 1])
        with mac_out_path_col:
            st.text_input("📁 재인코딩된 MP4 저장 폴더", key="mac_reencode_out_dir")
        with mac_out_btn_col:
            def on_mac_out_folder_pick():
                path = select_folder_via_applescript("변환된 비디오를 저장할 폴더를 선택하세요:")
                if path:
                    st.session_state.mac_reencode_out_dir = path
            st.button("📁 폴더 선택", key="mac_out_finder_btn", on_click=on_mac_out_folder_pick, use_container_width=True)

        st.write("")
        mac_convert_btn = st.button("🍏 맥북 호환 재인코딩 시작", key="mac_reencode_start_btn", use_container_width=True)

    with mac_col2:
        st.subheader("📊 맥북 최적화 재인코딩 진행 현황")
        st.write("---")

        if mac_convert_btn:
            if not mac_files_to_convert:
                st.error("❌ 변환할 비디오 파일이 선택되지 않았습니다.")
            else:
                out_dir = st.session_state.mac_reencode_out_dir
                os.makedirs(out_dir, exist_ok=True)

                mac_status = st.empty()
                mac_status.info(f"⏳ 총 `{len(mac_files_to_convert)}`개의 동영상을 macOS QuickTime 표준 규격(H.264/AAC/yuv420p)으로 인코딩 중...")

                mac_prog = st.progress(0)
                mac_prog_text = st.empty()
                mac_log_box = st.empty()
                mac_logs = []
                mac_results = []

                for idx, (display_name, file_data, original_name) in enumerate(mac_files_to_convert):
                    base_name = os.path.splitext(original_name)[0]
                    out_filename = f"{base_name}_mac.mp4"
                    out_path = os.path.join(out_dir, out_filename)

                    mac_prog_text.markdown(f"**재인코딩 중:** `{display_name}` ({idx+1}/{len(mac_files_to_convert)})")

                    try:
                        if isinstance(file_data, bytes):
                            ext = os.path.splitext(original_name)[1] or ".mp4"
                            with tempfile.NamedTemporaryFile(suffix=ext, delete=False) as tmp:
                                tmp.write(file_data)
                                in_path = tmp.name
                            is_tmp = True
                        else:
                            in_path = file_data
                            is_tmp = False

                        encoded_path = reencode_video_for_mac(
                            input_path=in_path,
                            output_path=out_path,
                            crf=mac_crf_val
                        )

                        if is_tmp:
                            try:
                                os.unlink(in_path)
                            except Exception:
                                pass

                        if encoded_path and os.path.exists(encoded_path):
                            sz_mb = os.path.getsize(encoded_path) / (1024 * 1024)
                            mac_logs.append(f"✅ [{idx+1:02d}/{len(mac_files_to_convert):02d}] {display_name} → {out_filename} ({sz_mb:.1f} MB)")
                            mac_results.append({"name": display_name, "out": encoded_path, "success": True})
                        else:
                            mac_logs.append(f"❌ [{idx+1:02d}/{len(mac_files_to_convert):02d}] {display_name} → 인코딩 실패")
                            mac_results.append({"name": display_name, "out": None, "success": False})

                    except Exception as e:
                        mac_logs.append(f"❌ [{idx+1:02d}/{len(mac_files_to_convert):02d}] {display_name} → 오류: {str(e)[:80]}")
                        mac_results.append({"name": display_name, "out": None, "success": False})

                    mac_prog.progress((idx + 1) / len(mac_files_to_convert))
                    mac_log_box.code("\n".join(mac_logs[-8:]))

                st.session_state.mac_reencode_results = mac_results
                succ_cnt = sum(1 for r in mac_results if r["success"])
                fail_cnt = len(mac_results) - succ_cnt

                if fail_cnt == 0:
                    mac_status.success(f"🎉 **모든 영상 맥북 호환 인코딩 완료!** 총 `{succ_cnt}`개 비디오 저장이 완료되었습니다.\n\n저장 경로: `{out_dir}`")
                else:
                    mac_status.warning(f"⚠️ 재인코딩 완료: 성공 `{succ_cnt}`개 / 실패 `{fail_cnt}`개\n\n저장 경로: `{out_dir}`")

        if st.session_state.mac_reencode_results:
            st.write("")
            st.subheader("📋 변환 완료 목록 및 미리보기")
            for r in st.session_state.mac_reencode_results:
                if r["success"]:
                    st.markdown(f"✅ **{r['name']}** → `{r['out']}`")
                    st.video(r["out"])
                else:
                    st.markdown(f"❌ **{r['name']}** → 인코딩 실패")
        else:
            if not mac_convert_btn:
                st.info("💡 왼쪽에서 재생 불가능하거나 맥북에 맞게 변경할 동영상을 선택한 후 **🍏 맥북 호환 재인코딩 시작** 버튼을 클릭해 주세요.")

# ==================== TAB 3: 이미지로 영상 만들기 ====================
with tab3:
    vid_col1, vid_col2 = st.columns([1, 2], gap="large")
    
    with vid_col1:
        st.subheader("⚙️ 비디오 제작 설정")
        st.write("---")
        
        input_mode = st.selectbox(
            "📤 이미지 불러오기 방식",
            options=["직접 이미지 파일 업로드", "로컬 폴더 내 이미지 불러오기"],
            index=0
        )
        
        image_files = []
        if input_mode == "직접 이미지 파일 업로드":
            uploaded_files = st.file_uploader(
                "🖼️ 이미지 파일들을 선택해 주세요 (다중 선택 가능)",
                type=["png", "jpg", "jpeg"],
                accept_multiple_files=True
            )
            
            if uploaded_files:
                # Save uploaded files into a temporary directory so we have file paths
                temp_dir = tempfile.mkdtemp()
                for uf in uploaded_files:
                    path = os.path.join(temp_dir, uf.name)
                    with open(path, "wb") as f:
                        f.write(uf.getbuffer())
                    image_files.append(path)
                st.success(f"✅ 총 `{len(image_files)}`개의 이미지가 정상 업로드되었습니다.")
                
        else:
            # Local Folder mode
            slideshow_path_col, slideshow_button_col = st.columns([3, 1])
            with slideshow_path_col:
                st.text_input("📁 이미지 소스 폴더 경로", key="slideshow_dir")
            with slideshow_button_col:
                def on_slideshow_folder_pick():
                    path = select_folder_via_applescript("합성할 이미지들이 담긴 소스 폴더를 선택하세요:")
                    if path:
                        st.session_state.slideshow_dir = path
                        
                st.button("📁 폴더 선택", key="slideshow_finder_btn", on_click=on_slideshow_folder_pick, use_container_width=True)
            
            # Read files from local directory
            if os.path.exists(st.session_state.slideshow_dir):
                all_files = os.listdir(st.session_state.slideshow_dir)
                image_files = [
                    os.path.join(st.session_state.slideshow_dir, f)
                    for f in all_files
                    if f.lower().endswith(('.png', '.jpg', '.jpeg', '.webp'))
                ]
                # Sort to ensure sequential layout
                image_files.sort()
                
                if image_files:
                    st.success(f"✅ 폴더 내에서 총 `{len(image_files)}`개의 이미지 파일을 찾았습니다.")
                else:
                    st.warning("⚠️ 선택하신 폴더 내에 이미지 파일(png, jpg, jpeg, webp)이 존재하지 않습니다.")
            else:
                st.error("❌ 지정하신 폴더 경로가 올바르지 않습니다.")
                
        # Slideshow settings
        duration = st.slider("⏱️ 이미지 1장당 노출 시간 (초)", min_value=1, max_value=10, value=2, step=1)
        video_name = st.text_input("📹 출력 영상 파일명", value="slideshow.mp4")
        
        # Output Folder Picker
        out_path_col, out_button_col = st.columns([3, 1])
        with out_path_col:
            st.text_input("📁 저장 디렉토리 경로 지정", key="slideshow_out_dir")
        with out_button_col:
            def on_slideshow_out_folder_pick():
                path = select_folder_via_applescript("동영상을 저장할 대상 폴더를 선택하세요:")
                if path:
                    st.session_state.slideshow_out_dir = path
                    
            st.button("📁 폴더 선택", key="slideshow_out_finder_btn", on_click=on_slideshow_out_folder_pick, use_container_width=True)
                    
        st.write("")
        compile_btn = st.button("🎬 슬라이드쇼 비디오 제작 시작", use_container_width=True)

    with vid_col2:
        st.subheader("📊 비디오 컴파일 및 미리보기")
        st.write("---")
        
        if compile_btn:
            if not image_files:
                st.error("❌ 비디오로 변환할 이미지가 존재하지 않습니다. 먼저 이미지를 업로드하거나 소스 폴더를 올바르게 선택해 주세요.")
            elif len(image_files) < 2:
                st.error("❌ 비디오 슬라이드쇼를 만들려면 최소 2장 이상의 이미지가 필요합니다.")
            else:
                compiling_status = st.empty()
                compiling_status.info("🎬 이미지를 읽어와서 동영상 타임라인으로 병합하는 중... 잠시만 기다려 주세요.")
                
                compiling_progress = st.progress(0)
                compiling_text = st.empty()
                
                def compile_cb(current, total):
                    compiling_progress.progress(current / total)
                    compiling_text.markdown(f"**이미지 처리 중:** `{current} / {total}` 장 프레임 병합 완료")
                
                output_video_path = os.path.join(st.session_state.slideshow_out_dir, video_name)
                
                compiled_video = create_video_from_images(
                    image_paths=image_files,
                    output_path=output_video_path,
                    duration_per_image=duration,
                    progress_callback=compile_cb
                )
                
                if compiled_video and os.path.exists(compiled_video):
                    st.session_state.generated_video_path = compiled_video
                    compiling_status.success(f"🎉 **슬라이드쇼 비디오 제작 최종 성공!**\n\n저장 완료 경로: `{compiled_video}`")
                    compiling_text.markdown("**작업 완료:** 슬라이드쇼 컴파일이 성공적으로 종료되었습니다.")
                else:
                    st.session_state.generated_video_path = None
                    compiling_status.error("❌ 비디오 제작 도중 예상치 못한 오류가 발생했습니다. 이미지 포맷을 점검해 주세요.")
                    
        # Embedded Video Player for Preview
        if st.session_state.generated_video_path and os.path.exists(st.session_state.generated_video_path):
            st.write("")
            st.subheader("👁️ 제작된 슬라이드쇼 동영상 재생")
            st.write("아래 플레이어에서 생성된 동영상을 바로 확인해 보세요!")
            st.video(st.session_state.generated_video_path)
        else:
            st.info("💡 왼쪽에 설정을 지정하고 **비디오 제작 시작** 버튼을 눌러주시면, 여기에 완성된 플레이어가 제공됩니다.")

# ==================== TAB 4: 일반 웹 영상 다운로더 ====================
with tab4:
    web_col1, web_col2 = st.columns([1, 2], gap="large")
    
    with web_col1:
        st.subheader("⚙️ 일반 웹 영상 설정")
        st.write("---")
        st.caption("💡 **javclick.com**, **sogirl**, **HLS(.m3u8)**, **임베드 MP4 플레이어** 등 일반 웹사이트 비디오 링크 지원")
        
        web_page_url = st.text_input("🔗 웹페이지 링크(URL) 입력", placeholder="https://javclick.com/en/movie-info/6ab942ac131836087e0e7fd0", key="web_page_url_input")
        web_output_name = st.text_input("📹 저장할 파일명 (.mp4)", value=st.session_state.get('web_suggested_filename', 'downloaded_video.mp4'), key="web_output_name_input")
        
        # Folder Path Row Layout (Text input + Finder button)
        web_path_col, web_button_col = st.columns([3, 1])
        with web_path_col:
            st.text_input("📁 다운로드 폴더 지정", key="web_save_dir")
        with web_button_col:
            def on_web_folder_pick():
                path = select_folder_via_applescript("영상을 저장할 폴더를 선택하세요:")
                if path:
                    st.session_state.web_save_dir = path
                    
            st.button("📁 폴더 선택", key="web_finder_btn", on_click=on_web_folder_pick, use_container_width=True)
        
        st.write("")
        web_analyze_btn = st.button("🔍 웹페이지 스트리밍 주소 분석", key="web_analyze_btn", use_container_width=True)
        
        if web_page_url.strip() and web_analyze_btn:
            with st.spinner("웹페이지에서 동영상 스트리밍 주소 및 미디어 정보를 분석 중..."):
                m3u8_info = extract_m3u8_from_webpage(web_page_url.strip())
                if m3u8_info and m3u8_info.get("url"):
                    st.session_state.web_m3u8_url = m3u8_info["url"]
                    st.session_state.web_m3u8_referer = m3u8_info.get("referer")
                    raw_title = m3u8_info.get("title", "")
                    if raw_title:
                        clean_title = re.sub(r'[\\/*?:"<>|]', "", raw_title).strip()
                        if clean_title:
                            st.session_state.web_suggested_filename = clean_title + ".mp4"
                    st.success("✅ 스트리밍 비디오 주소 추출 성공!")
                else:
                    st.session_state.web_m3u8_url = None
                    st.session_state.web_m3u8_referer = None
                    st.error("❌ 스트리밍 링크를 찾지 못했습니다. 올바른 페이지 주소이거나 동영상 플레이어가 있는지 확인해 주세요.")
                    
        if st.session_state.web_m3u8_url:
            st.write("")
            st.subheader("🎥 분석 완료된 비디오 정보")
            st.code(st.session_state.web_m3u8_url, wrap_lines=True)

            web_mac_reencode_opt = st.checkbox(
                "🍏 맥북(QuickTime/Finder) 100% 호환 자동 재인코딩 적용",
                value=True,
                key="web_mac_reencode_opt",
                help="체크 시 H.264 / AAC / yuv420p / +faststart 포맷으로 자동으로 변환하여 맥북 기본 플레이어 및 미리보기 오류를 완벽 방지합니다."
            )
            
            web_download_btn = st.button("📥 MP4 웹 영상 다운로드 시작", key="web_download_btn", use_container_width=True)
            
    with web_col2:
        st.subheader("📊 일반 웹 영상 다운로드 진행 현황")
        st.write("---")
        
        if 'web_download_btn' in locals() and web_download_btn and st.session_state.web_m3u8_url:
            web_status = st.empty()
            web_status.info("📥 고화질 동영상 스트림을 다운로드하고 맥북 호환 포맷(H.264/AAC)으로 변환 중입니다... 잠시만 기다려 주세요.")
            
            web_progress = st.progress(0)
            web_progress_text = st.empty()
            web_log_box = st.empty()
            
            def web_progress_cb(percent, speed, eta):
                web_progress.progress(percent)
                speed_mb = speed / (1024 * 1024) if speed else 0
                eta_str = f"{int(eta)}초" if eta else "계산 중"
                web_progress_text.markdown(f"**다운로드 진행률:** `{percent * 100:.1f}%` 완료")
                web_log_box.code(
                    f"진행 속도: {speed_mb:.2f} MB/s\n"
                    f"남은 시간: {eta_str}\n"
                    f"저장 위치: {os.path.join(st.session_state.web_save_dir, web_output_name)}"
                )
                
            downloaded_file = download_web_video(
                m3u8_url=st.session_state.web_m3u8_url,
                base_dir=st.session_state.web_save_dir,
                output_name=web_output_name,
                progress_callback=web_progress_cb,
                referer=st.session_state.get('web_m3u8_referer'),
                reencode_mac=web_mac_reencode_opt
            )
            
            if downloaded_file:
                web_progress.progress(1.0)
                web_progress_text.markdown("**다운로드 진행률:** `100.0%` 완료")
                web_status.success(f"🎉 **다운로드 최종 성공!**\n\n영상 파일이 성공적으로 저장되었습니다:\n\n`{downloaded_file}`")
                web_log_box.code(f"성공적으로 웹 비디오 추출 완료.\n완료 경로: {downloaded_file}")
            else:
                web_status.error("❌ 영상 다운로드 중 오류가 발생했습니다. pycryptodomex 패키지 및 네트워크 환경을 확인해 주세요.")
        else:
            st.info("💡 왼쪽에 웹페이지 URL을 입력하고 **스트리밍 주소 분석**을 마친 뒤, **다운로드 시작** 버튼을 눌러주세요.")


# ==================== TAB 5: WEBM → MP4 변환기 ====================
with tab5:
    conv_col1, conv_col2 = st.columns([1, 2], gap="large")

    with conv_col1:
        st.subheader("⚙️ 변환 설정")
        st.write("---")

        conv_input_mode = st.selectbox(
            "📤 WEBM 파일 불러오기 방식",
            options=["직접 파일 업로드 (최대 10GB)", "로컬 폴더에서 일괄 변환", "파일 경로 직접 입력 (용량 무제한)"],
            index=0,
            key="conv_input_mode"
        )

        webm_files_to_convert = []  # list of (display_name, file_path_or_bytes, original_name)

        if conv_input_mode == "직접 파일 업로드 (최대 10GB)":
            st.info("ℹ️ 업로드 한도: **10 GB** (.streamlit/config.toml 설정). 그 이상은 아래 **파일 경로 직접 입력** 방식을 사용하세요.")
            uploaded_webm = st.file_uploader(
                "🎬 WEBM 파일을 선택해 주세요 (다중 선택 가능)",
                type=["webm"],
                accept_multiple_files=True,
                key="webm_uploader"
            )
            if uploaded_webm:
                st.success(f"✅ 총 `{len(uploaded_webm)}`개의 WEBM 파일이 업로드되었습니다.")
                for uf in uploaded_webm:
                    webm_files_to_convert.append((uf.name, uf.read(), uf.name))

        elif conv_input_mode == "파일 경로 직접 입력 (용량 무제한)":
            st.info("ℹ️ 파일 경로를 직접 입력하면 브라우저 업로드 없이 변환됩니다. **파일 크기 제한 없음.**")
            direct_paths_input = st.text_area(
                "📄 WEBM 파일 경로 입력 (줄바꿈으로 여러 개 입력 가능)",
                placeholder="/Users/yourname/Videos/clip1.webm\n/Users/yourname/Videos/clip2.webm",
                height=140,
                key="webm_direct_paths"
            )
            if direct_paths_input.strip():
                raw_lines = [p.strip() for p in direct_paths_input.strip().splitlines() if p.strip()]
                ok_count = 0
                for p in raw_lines:
                    if os.path.isfile(p) and p.lower().endswith(".webm"):
                        webm_files_to_convert.append((os.path.basename(p), p, os.path.basename(p)))
                        ok_count += 1
                    elif os.path.isfile(p):
                        st.warning(f"⚠️ WEBM 파일이 아닙니다: `{p}`")
                    else:
                        st.error(f"❌ 파일을 찾을 수 없습니다: `{p}`")
                if ok_count:
                    st.success(f"✅ 유효한 WEBM 파일 `{ok_count}`개가 확인되었습니다.")
        else:
            conv_path_col, conv_btn_col = st.columns([3, 1])
            with conv_path_col:
                st.text_input("📁 WEBM 파일이 있는 폴더", key="webm_convert_dir")
            with conv_btn_col:
                def on_webm_src_folder_pick():
                    path = select_folder_via_applescript("WEBM 파일이 있는 폴더를 선택하세요:")
                    if path:
                        st.session_state.webm_convert_dir = path
                st.button("📁 폴더 선택", key="webm_src_finder_btn", on_click=on_webm_src_folder_pick, use_container_width=True)

            src_dir = st.session_state.webm_convert_dir
            if os.path.exists(src_dir):
                found_webm = [
                    f for f in os.listdir(src_dir)
                    if f.lower().endswith(".webm")
                ]
                found_webm.sort()
                if found_webm:
                    st.success(f"✅ 폴더에서 총 `{len(found_webm)}`개의 WEBM 파일을 찾았습니다.")
                    for fname in found_webm:
                        webm_files_to_convert.append((fname, os.path.join(src_dir, fname), fname))
                else:
                    st.warning("⚠️ 선택한 폴더에 WEBM 파일이 없습니다.")

        st.write("")
        st.markdown("**🎛️ 변환 품질 옵션**")
        conv_quality = st.selectbox(
            "화질 (CRF, 낮을수록 고화질)",
            options=["최고화질 (CRF 18)", "고화질 (CRF 23)", "표준 (CRF 28)", "저용량 (CRF 34)"],
            index=1,
            key="conv_quality"
        )
        crf_map = {
            "최고화질 (CRF 18)": "18",
            "고화질 (CRF 23)": "23",
            "표준 (CRF 28)": "28",
            "저용량 (CRF 34)": "34",
        }
        crf_value = crf_map[conv_quality]

        # Output folder
        conv_out_path_col, conv_out_btn_col = st.columns([3, 1])
        with conv_out_path_col:
            st.text_input("📁 변환된 MP4 저장 폴더", key="webm_output_dir")
        with conv_out_btn_col:
            def on_webm_out_folder_pick():
                path = select_folder_via_applescript("변환된 MP4를 저장할 폴더를 선택하세요:")
                if path:
                    st.session_state.webm_output_dir = path
            st.button("📁 폴더 선택", key="webm_out_finder_btn", on_click=on_webm_out_folder_pick, use_container_width=True)

        st.write("")
        convert_btn = st.button("🔄 MP4로 일괄 변환 시작", key="webm_convert_btn", use_container_width=True)

    with conv_col2:
        st.subheader("📊 변환 진행 현황")
        st.write("---")

        if convert_btn:
            if not webm_files_to_convert:
                st.error("❌ 변환할 WEBM 파일이 없습니다. 파일을 업로드하거나 폴더를 선택해 주세요.")
            else:
                output_dir = st.session_state.webm_output_dir
                os.makedirs(output_dir, exist_ok=True)

                conv_status = st.empty()
                conv_status.info(f"🔄 총 `{len(webm_files_to_convert)}`개의 WEBM 파일을 MP4로 변환하는 중입니다...")

                conv_progress = st.progress(0)
                conv_progress_text = st.empty()
                conv_log_box = st.empty()
                log_lines = []
                results = []

                for i, (display_name, file_data, original_name) in enumerate(webm_files_to_convert):
                    base_name = os.path.splitext(original_name)[0]
                    out_filename = base_name + ".mp4"
                    out_path = os.path.join(output_dir, out_filename)

                    conv_progress_text.markdown(f"**변환 중:** `{display_name}` ({i+1}/{len(webm_files_to_convert)})")

                    try:
                        # Write to temp file if bytes (uploaded), otherwise use path directly
                        if isinstance(file_data, bytes):
                            with tempfile.NamedTemporaryFile(suffix=".webm", delete=False) as tmp:
                                tmp.write(file_data)
                                input_path = tmp.name
                            is_temp = True
                        else:
                            input_path = file_data
                            is_temp = False

                        ffmpeg_cmd = [
                            "ffmpeg", "-y",
                            "-i", input_path,
                            "-c:v", "libx264",
                            "-crf", crf_value,
                            "-preset", "fast",
                            "-c:a", "aac",
                            "-b:a", "192k",
                            "-movflags", "+faststart",
                            out_path
                        ]

                        result = subprocess.run(
                            ffmpeg_cmd,
                            capture_output=True,
                            text=True
                        )

                        if is_temp:
                            try:
                                os.unlink(input_path)
                            except Exception:
                                pass

                        if result.returncode == 0 and os.path.exists(out_path):
                            size_mb = os.path.getsize(out_path) / (1024 * 1024)
                            log_lines.append(f"✅ [{i+1:02d}/{len(webm_files_to_convert):02d}] {display_name}  →  {out_filename}  ({size_mb:.1f} MB)")
                            results.append({"name": display_name, "out": out_path, "success": True})
                        else:
                            log_lines.append(f"❌ [{i+1:02d}/{len(webm_files_to_convert):02d}] {display_name}  →  변환 실패")
                            results.append({"name": display_name, "out": None, "success": False})

                    except Exception as e:
                        log_lines.append(f"❌ [{i+1:02d}/{len(webm_files_to_convert):02d}] {display_name}  →  오류: {str(e)[:80]}")
                        results.append({"name": display_name, "out": None, "success": False})

                    conv_progress.progress((i + 1) / len(webm_files_to_convert))
                    conv_log_box.code("\n".join(log_lines[-8:]))

                st.session_state.webm_convert_results = results

                success_count = sum(1 for r in results if r["success"])
                fail_count = len(results) - success_count

                if fail_count == 0:
                    conv_status.success(f"🎉 **모든 변환 완료!** 총 `{success_count}`개의 파일이 MP4로 성공적으로 변환되었습니다.\n\n저장 위치: `{output_dir}`")
                else:
                    conv_status.warning(f"⚠️ 변환 완료: 성공 `{success_count}`개 / 실패 `{fail_count}`개\n\n저장 위치: `{output_dir}`")

                conv_progress_text.markdown("**변환 완료!**")

        # Show previous results if they exist
        if st.session_state.webm_convert_results:
            st.write("")
            st.subheader("📋 변환 결과 목록")
            for r in st.session_state.webm_convert_results:
                if r["success"]:
                    st.markdown(f"✅ **{r['name']}** → `{r['out']}`")
                else:
                    st.markdown(f"❌ **{r['name']}** → 변환 실패")
        else:
            if not convert_btn:
                st.info("💡 왼쪽에서 WEBM 파일을 선택하고 **MP4로 일괄 변환 시작** 버튼을 눌러주세요.")


# ==================== TAB 6: 영상 순서 병합 (이어붙이기) ====================
with tab6:
    m_col1, m_col2 = st.columns([1, 2], gap="large")
    
    with m_col1:
        st.subheader("⚙️ 병합 영상 설정")
        st.write("---")
        
        m_input_mode = st.selectbox(
            "📤 영상 불러오기 방식",
            options=["직접 동영상 파일 업로드", "로컬 폴더 내 동영상 전체 불러오기"],
            index=0,
            key="merge_input_mode"
        )
        
        if m_input_mode == "직접 동영상 파일 업로드":
            m_uploaded_files = st.file_uploader(
                "🎥 동영상 파일들을 선택해 주세요 (다중 선택 가능)",
                type=["mp4", "mov", "avi", "mkv", "webm", "flv"],
                accept_multiple_files=True,
                key="merge_file_uploader"
            )
            if m_uploaded_files:
                current_sig = tuple((uf.name, uf.size) for uf in m_uploaded_files)
                if st.session_state.merge_uploader_signature != current_sig:
                    st.session_state.merge_uploader_signature = current_sig
                    temp_merge_dir = tempfile.mkdtemp(prefix="m_upload_")
                    new_items = []
                    for uf in m_uploaded_files:
                        fp = os.path.join(temp_merge_dir, uf.name)
                        with open(fp, "wb") as f:
                            f.write(uf.getbuffer())
                        new_items.append({"name": uf.name, "path": fp, "size": uf.size})
                    st.session_state.merge_video_items = new_items
            else:
                if st.session_state.merge_uploader_signature is not None and st.session_state.merge_uploader_signature != "cleared":
                    st.session_state.merge_uploader_signature = None
                    st.session_state.merge_video_items = []
        else:
            m_folder_col, m_btn_col = st.columns([3, 1])
            with m_folder_col:
                st.text_input("📁 로컬 폴더 경로", key="merge_src_dir")
            with m_btn_col:
                def on_merge_src_pick():
                    path = select_folder_via_applescript("영상들이 들어있는 폴더를 선택하세요:")
                    if path:
                        st.session_state.merge_src_dir = path
                st.button("📁 폴더 선택", key="merge_src_finder_btn", on_click=on_merge_src_pick, use_container_width=True)
                
            if st.button("🔄 폴더 내 영상 검색", key="merge_scan_btn", use_container_width=True):
                if st.session_state.get("merge_src_dir") and os.path.exists(st.session_state.merge_src_dir):
                    valid_exts = ('.mp4', '.mov', '.avi', '.mkv', '.webm', '.flv')
                    found_files = []
                    for f in sorted(os.listdir(st.session_state.merge_src_dir)):
                        if f.lower().endswith(valid_exts):
                            full_p = os.path.join(st.session_state.merge_src_dir, f)
                            found_files.append({"name": f, "path": full_p, "size": os.path.getsize(full_p)})
                    st.session_state.merge_video_items = found_files
                    st.success(f"총 `{len(found_files)}`개의 영상 파일을 찾았습니다!")
                else:
                    st.error("❌ 올바른 로컬 폴더 경로를 지정해 주세요.")
                    
        st.write("")
        st.subheader("⚙️ 저장 및 인코딩 옵션")
        
        m_res = st.selectbox(
            "🎬 병합 출력 화질 (해상도)",
            options=["1080p (Full HD)", "4K (2160p)", "2K (1440p)", "720p (HD)", "480p"],
            index=0,
            help="모든 동영상을 해당 해상도 및 30fps H.264/AAC MP4 표준 포맷으로 자동 일치시켜 병합합니다."
        )
        
        out_name = st.text_input("📝 출력 파일명", value="merged_video.mp4", key="merge_out_name")
        
        # Save Dir Selector
        m_path_col, m_save_btn_col = st.columns([3, 1])
        with m_path_col:
            st.text_input("📁 저장 폴더 지정", key="merge_save_dir")
        with m_save_btn_col:
            def on_merge_save_pick():
                path = select_folder_via_applescript("병합된 영상을 저장할 폴더를 선택하세요:")
                if path:
                    st.session_state.merge_save_dir = path
            st.button("📁 폴더 선택", key="merge_save_finder_btn", on_click=on_merge_save_pick, use_container_width=True)
            
        m_start_btn = st.button("🎬 영상 이어붙이기 병합 시작", key="merge_start_btn", use_container_width=True)
        
    with m_col2:
        st.subheader("📋 순서 목록 및 병합 진행 현황")
        st.write("---")
        
        items = st.session_state.merge_video_items
        if items:
            st.write(f"**총 선택된 영상:** `{len(items)}`개")
            
            # List header with Clear All button
            clear_col1, clear_col2 = st.columns([3, 1])
            with clear_col2:
                if st.button("🗑️ 전체 비우기", key="merge_clear_btn", use_container_width=True):
                    st.session_state.merge_video_items = []
                    st.session_state.merge_uploader_signature = "cleared"
                    st.rerun()
                    
            # Item order list with Move Up / Move Down / Delete controls
            for i, item in enumerate(st.session_state.merge_video_items):
                i_col_num, i_col_name, i_col_up, i_col_down, i_col_del = st.columns([1, 6, 1, 1, 1])
                with i_col_num:
                    st.markdown(f"**#{i+1}**")
                with i_col_name:
                    sz_mb = item['size'] / (1024 * 1024) if 'size' in item else 0
                    st.text(f"{item['name']} ({sz_mb:.1f} MB)")
                with i_col_up:
                    if st.button("▲", key=f"m_up_{i}", disabled=(i == 0)):
                        st.session_state.merge_video_items[i], st.session_state.merge_video_items[i-1] = (
                            st.session_state.merge_video_items[i-1], st.session_state.merge_video_items[i]
                        )
                        st.rerun()
                with i_col_down:
                    if st.button("▼", key=f"m_down_{i}", disabled=(i == len(st.session_state.merge_video_items) - 1)):
                        st.session_state.merge_video_items[i], st.session_state.merge_video_items[i+1] = (
                            st.session_state.merge_video_items[i+1], st.session_state.merge_video_items[i]
                        )
                        st.rerun()
                with i_col_del:
                    if st.button("❌", key=f"m_del_{i}"):
                        st.session_state.merge_video_items.pop(i)
                        st.rerun()
                        
            st.write("---")
        else:
            st.info("💡 왼쪽에 동영상 파일들을 추가하거나 폴더에서 불러온 후 순서를 지정해 주세요.")
            
        if m_start_btn:
            if not items:
                st.error("❌ 병합할 동영상 파일이 선택되지 않았습니다.")
            else:
                m_status = st.empty()
                m_status.info("⏳ 동영상 포맷 표준화 및 하나로 이어붙이는 작업을 시작합니다...")
                
                m_progress = st.progress(0)
                m_progress_text = st.empty()
                m_log_box = st.empty()
                
                output_full_path = os.path.join(st.session_state.merge_save_dir, out_name)
                
                def merge_progress_cb(current, total, msg):
                    ratio = min(current / total, 1.0)
                    m_progress.progress(ratio)
                    m_progress_text.markdown(f"**병합 작업 진행률:** `{ratio * 100:.1f}%` 완료")
                    m_log_box.code(f"진행 정보: {msg}\n저장 파일: {output_full_path}")
                    
                video_paths = [it['path'] for it in items]
                res_path = merge_videos(
                    video_paths=video_paths,
                    output_path=output_full_path,
                    resolution=m_res,
                    progress_callback=merge_progress_cb
                )
                
                if res_path and os.path.exists(res_path):
                    m_progress.progress(1.0)
                    m_progress_text.markdown("**병합 작업 진행률:** `100.0%` 완료")
                    m_status.success(f"🎉 **영상 이어붙이기 병합 성공!**\n\n완료된 영상 파일:\n\n`{res_path}`")
                    m_log_box.code(f"성공적으로 병합 완료.\n결과 경로: {res_path}")
                else:
                    m_status.error("❌ 영상 병합 처리 중 오류가 발생했습니다.")


# ==================== TAB: 이미지 나란히 붙이기 ====================
with tab_img_merge:
    col1, col2 = st.columns([1, 1], gap="large")
    
    with col1:
        st.subheader("⚙️ 이미지 병합 설정")
        st.write("---")
        
        img_source_mode = st.radio("⬇️ 이미지 불러오기 방식", ["파일 직접 업로드", "로컬 폴더에서 불러오기"], horizontal=True, key="img_merge_source_mode")
        
        if img_source_mode == "파일 직접 업로드":
            # 파일 업로더
            uploaded_imgs = st.file_uploader(
                "📷 병합할 이미지 파일 선택 (다중 선택 가능)",
                type=["png", "jpg", "jpeg", "webp"],
                accept_multiple_files=True,
                key="img_merge_uploader"
            )
            
            # 업로드 시그니처 감지하여 새 업로드 처리
            current_signature = ",".join([f"{f.name}_{f.size}" for f in uploaded_imgs]) if uploaded_imgs else ""
            if current_signature and st.session_state.img_merge_uploader_signature != current_signature:
                st.session_state.img_merge_uploader_signature = current_signature
                new_items = []
                temp_dir = tempfile.gettempdir()
                for uf in uploaded_imgs:
                    fp = os.path.join(temp_dir, uf.name)
                    with open(fp, "wb") as f:
                        f.write(uf.getbuffer())
                    new_items.append({"name": uf.name, "path": fp, "size": uf.size})
                st.session_state.img_merge_items = new_items
            elif not current_signature:
                if st.session_state.img_merge_uploader_signature is not None and st.session_state.img_merge_uploader_signature != "cleared":
                    st.session_state.img_merge_uploader_signature = None
                    st.session_state.img_merge_items = []
        else:
            # 로컬 폴더
            im_folder_col, im_btn_col = st.columns([3, 1])
            with im_folder_col:
                st.text_input("📁 로컬 폴더 경로", key="img_merge_src_dir")
            with im_btn_col:
                def on_img_merge_src_pick():
                    path = select_folder_via_applescript("이미지들이 들어있는 폴더를 선택하세요:")
                    if path:
                        st.session_state.img_merge_src_dir = path
                st.button("📁 폴더 선택", key="img_merge_src_finder_btn", on_click=on_img_merge_src_pick, use_container_width=True)
                
            if st.button("🔍 폴더 내 이미지 검색", key="img_merge_scan_btn", use_container_width=True):
                if st.session_state.get("img_merge_src_dir") and os.path.exists(st.session_state.img_merge_src_dir):
                    valid_exts = ('.png', '.jpg', '.jpeg', '.webp')
                    found_files = []
                    for f in sorted(os.listdir(st.session_state.img_merge_src_dir)):
                        if f.lower().endswith(valid_exts):
                            full_p = os.path.join(st.session_state.img_merge_src_dir, f)
                            found_files.append({"name": f, "path": full_p, "size": os.path.getsize(full_p)})
                    st.session_state.img_merge_items = found_files
                    st.success(f"총 `{len(found_files)}`개의 이미지 파일을 찾았습니다!")
                else:
                    st.error("❌ 올바른 로컬 폴더 경로를 지정해 주세요.")
                    
        st.write("")
        st.subheader("⚙️ 레이아웃 및 리사이즈 옵션")
        
        img_direction = st.radio(
            "🎬 병합 방향 선택",
            options=["horizontal", "vertical"],
            format_func=lambda x: "가로로 합치기 (옆으로)" if x == "horizontal" else "세로로 합치기 (위아래로)",
            index=0,
            horizontal=True,
            key="img_merge_direction"
        )
        
        # 가로 합치기일 때는 세로 높이를 통일하는 min_height를 기본값으로, 세로 합치기일 때는 가로 폭을 통일하는 min_width를 기본값으로 설정
        default_resize_index = 1 if img_direction == "horizontal" else 0
        
        img_resize_mode = st.selectbox(
            "📐 이미지 리사이즈 기준",
            options=["min_width", "min_height", "none"],
            format_func=lambda x: "가장 작은 이미지의 가로 폭(Width)에 맞춤 (비율 유지) [추천: 세로 병합]" if x == "min_width" else 
                                  ("가장 작은 이미지의 세로 높이(Height)에 맞춤 (비율 유지) [추천: 가로 병합]" if x == "min_height" else "원본 크기 유지 (리사이즈 없음)"),
            index=default_resize_index,
            key="img_merge_resize_mode",
            help="이미지 크기가 서로 다를 때, 이미지 비율을 찌그러뜨리지 않고 유지하면서 작은 이미지의 크기에 맞춰서 리사이즈합니다."
        )
        
        img_bg_color_name = st.selectbox(
            "🎨 배경색",
            options=["transparent", "white", "black"],
            format_func=lambda x: "투명 (PNG 권장)" if x == "transparent" else ("흰색 (White)" if x == "white" else "검은색 (Black)"),
            index=0,
            key="img_merge_bg_color"
        )
        
        # RGBA 튜플 매핑
        bg_color_map = {
            "transparent": (0, 0, 0, 0),
            "white": (255, 255, 255, 255),
            "black": (0, 0, 0, 255)
        }
        bg_color_rgba = bg_color_map[img_bg_color_name]
        
        img_out_name = st.text_input("📝 출력 파일명", value="merged_image.png", key="img_merge_out_name")
        
        # Save Dir Selector
        im_path_col, im_save_btn_col = st.columns([3, 1])
        with im_path_col:
            st.text_input("📁 저장 폴더 지정", key="img_merge_save_dir")
        with im_save_btn_col:
            def on_img_merge_save_pick():
                path = select_folder_via_applescript("병합된 이미지를 저장할 폴더를 선택하세요:")
                if path:
                    st.session_state.img_merge_save_dir = path
            st.button("📁 폴더 선택", key="img_merge_save_finder_btn", on_click=on_img_merge_save_pick, use_container_width=True)
            
        img_start_btn = st.button("🖼️ 이미지 병합 시작", key="img_merge_start_btn", use_container_width=True)
        
    with col2:
        st.subheader("📋 순서 목록 및 병합 결과 미리보기")
        st.write("---")
        
        items = st.session_state.img_merge_items
        if items:
            st.write(f"**총 선택된 이미지:** `{len(items)}`개")
            
            # List header with Clear All button
            clear_col1, clear_col2 = st.columns([3, 1])
            with clear_col2:
                if st.button("🗑️ 전체 비우기", key="img_merge_clear_btn", use_container_width=True):
                    st.session_state.img_merge_items = []
                    st.session_state.img_merge_uploader_signature = "cleared"
                    st.rerun()
                    
            # Item order list with Move Up / Move Down / Delete controls
            for i, item in enumerate(st.session_state.img_merge_items):
                i_col_num, i_col_name, i_col_up, i_col_down, i_col_del = st.columns([1, 6, 1, 1, 1])
                with i_col_num:
                    st.markdown(f"**#{i+1}**")
                with i_col_name:
                    sz_kb = item['size'] / 1024 if 'size' in item else 0
                    st.text(f"{item['name']} ({sz_kb:.1f} KB)")
                with i_col_up:
                    if st.button("▲", key=f"im_up_{i}", disabled=(i == 0)):
                        st.session_state.img_merge_items[i], st.session_state.img_merge_items[i-1] = (
                            st.session_state.img_merge_items[i-1], st.session_state.img_merge_items[i]
                        )
                        st.rerun()
                with i_col_down:
                    if st.button("▼", key=f"im_down_{i}", disabled=(i == len(st.session_state.img_merge_items) - 1)):
                        st.session_state.img_merge_items[i], st.session_state.img_merge_items[i+1] = (
                            st.session_state.img_merge_items[i+1], st.session_state.img_merge_items[i]
                        )
                        st.rerun()
                with i_col_del:
                    if st.button("❌", key=f"im_del_{i}"):
                        st.session_state.img_merge_items.pop(i)
                        st.rerun()
                        
            st.write("---")
        else:
            st.info("💡 왼쪽에 이미지 파일들을 추가하거나 폴더에서 불러온 후 순서를 지정해 주세요.")
            
        if img_start_btn:
            if not items:
                st.error("❌ 병합할 이미지 파일이 선택되지 않았습니다.")
            else:
                m_status = st.empty()
                m_status.info("⏳ 이미지 병합 및 리사이즈 작업을 진행 중입니다...")
                
                output_full_path = os.path.join(st.session_state.img_merge_save_dir, img_out_name)
                image_paths = [it['path'] for it in items]
                
                res_path = merge_images(
                    image_paths=image_paths,
                    output_path=output_full_path,
                    direction=img_direction,
                    resize_mode=img_resize_mode,
                    background_color=bg_color_rgba
                )
                
                if res_path and os.path.exists(res_path):
                    m_status.success(f"🎉 **이미지 병합 성공!**\n\n결과 파일: `{res_path}`")
                    st.image(res_path, caption="병합 결과 미리보기", use_container_width=True)
                else:
                    m_status.error("❌ 이미지 병합 처리 중 오류가 발생했습니다.")

