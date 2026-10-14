import os
import re
import json
import time
import subprocess
import shutil
import urllib.parse
import requests
from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright
import yt_dlp
from PIL import Image

def launch_browser(playwright_instance):
    """
    Launches Chromium with auto-installation fallback and cloud container flags.
    """
    args = [
        "--no-sandbox",
        "--disable-setuid-sandbox",
        "--disable-dev-shm-usage",
        "--disable-gpu",
        "--single-process"
    ]
    try:
        return playwright_instance.chromium.launch(headless=True, args=args)
    except Exception as e:
        # If browser is missing (common on Streamlit Cloud), auto-install it
        print("⚠️ Chromium binary not found, attempting auto-installation via playwright install chromium...")
        try:
            subprocess.run([shutil.which("playwright") or "playwright", "install", "chromium"], check=True)
            return playwright_instance.chromium.launch(headless=True, args=args)
        except Exception as install_err:
            print(f"❌ Failed to auto-install playwright chromium: {install_err}")
            raise e


def scrape_bing(keyword, limit=50, progress_callback=None):
    """
    Scrapes high-resolution image URLs using Bing Images search with Playwright.
    """
    urls = []
    with sync_playwright() as p:
        browser = launch_browser(p)
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
        )
        page = context.new_page()
        search_url = f"https://www.bing.com/images/search?q={urllib.parse.quote(keyword)}"
        page.goto(search_url)
        page.wait_for_timeout(2000)
        
        scroll_attempts = 0
        last_height = page.evaluate("document.body.scrollHeight")
        
        while len(urls) < limit and scroll_attempts < 15:
            page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
            page.wait_for_timeout(1500)
            
            html = page.content()
            soup = BeautifulSoup(html, 'html.parser')
            links = soup.find_all('a', class_='iusc')
            
            for a in links:
                m_attr = a.get('m')
                if m_attr:
                    try:
                        m_json = json.loads(m_attr)
                        murl = m_json.get('murl')
                        if murl and murl not in urls and murl.startswith('http'):
                            urls.append(murl)
                            if len(urls) >= limit:
                                break
                    except Exception:
                        pass
                        
            if progress_callback:
                progress_callback(min(len(urls), limit), limit)
                
            new_height = page.evaluate("document.body.scrollHeight")
            if new_height == last_height:
                scroll_attempts += 1
            else:
                scroll_attempts = 0
            last_height = new_height
            
        browser.close()
    return urls[:limit]

def scrape_google(keyword, limit=50, progress_callback=None):
    """
    Scrapes image URLs using Google Images search with Playwright.
    """
    urls = []
    with sync_playwright() as p:
        browser = launch_browser(p)
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
        )
        page = context.new_page()
        search_url = f"https://www.google.com/search?q={urllib.parse.quote(keyword)}&tbm=isch"
        page.goto(search_url)
        
        # Google Consent
        try:
            consent_btn = page.query_selector('button:has-text("동의"), button:has-text("Accept all"), button:has-text("I agree")')
            if consent_btn:
                consent_btn.click()
                page.wait_for_timeout(1000)
        except Exception:
            pass

        last_height = page.evaluate("document.body.scrollHeight")
        scroll_attempts = 0
        
        while len(urls) < limit and scroll_attempts < 15:
            page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
            page.wait_for_timeout(1500)
            
            html = page.content()
            soup = BeautifulSoup(html, 'html.parser')
            
            links = soup.find_all('a', href=True)
            for link in links:
                href = link['href']
                if '/imgres?imgurl=' in href:
                    parsed = urllib.parse.urlparse(href)
                    query = urllib.parse.parse_qs(parsed.query)
                    if 'imgurl' in query:
                        img_url = query['imgurl'][0]
                        if img_url not in urls and img_url.startswith('http'):
                            urls.append(img_url)
                            if len(urls) >= limit:
                                break
                                
            # Fallback
            if len(urls) < limit:
                for img in soup.find_all('img'):
                    src = img.get('src') or img.get('data-src') or img.get('data-iurl')
                    if src and src.startswith('http') and 'gstatic.com' not in src and 'google' not in src:
                        if src not in urls:
                            urls.append(src)
                            if len(urls) >= limit:
                                break
                                
            if progress_callback:
                progress_callback(min(len(urls), limit), limit)
                
            new_height = page.evaluate("document.body.scrollHeight")
            if new_height == last_height:
                more_btn = page.query_selector('input[type="button"][value="결과 더보기"], input[type="button"][value="More results"], input[type="button"][value="Show more results"]')
                if more_btn and more_btn.is_visible():
                    more_btn.click()
                    page.wait_for_timeout(2000)
                else:
                    scroll_attempts += 1
            else:
                scroll_attempts = 0
            last_height = new_height
            
        browser.close()
    return urls[:limit]

def scrape_image_urls(keyword, limit=50, engine="Bing", progress_callback=None):
    """
    Unified entrypoint to scrape image URLs from Bing, Google, or Instagram.
    """
    if engine.lower() == "google":
        return scrape_google(keyword, limit, progress_callback)
    elif engine.lower() == "instagram":
        instagram_query = f"site:instagram.com {keyword}"
        return scrape_bing(instagram_query, limit, progress_callback)
    else:
        return scrape_bing(keyword, limit, progress_callback)

def scrape_instagram(url, progress_callback=None):
    """
    Scrapes image URLs from an Instagram post using Playwright.
    Filters out related posts by checking the image's Y coordinate.
    """
    urls = []
    with sync_playwright() as p:
        browser = launch_browser(p)
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
            viewport={"width": 1280, "height": 800}
        )
        page = context.new_page()
        
        try:
            page.goto(url, timeout=30000)
            page.wait_for_timeout(4000)
            
            # Dismiss login popup if exists
            try:
                close_btn = page.locator('svg[aria-label="Close"], svg[aria-label="닫기"]').first
                if close_btn.is_visible(timeout=1000):
                    close_btn.click(timeout=1000)
                    page.wait_for_timeout(1000)
            except Exception:
                pass
            
            def extract_current_images():
                images = page.locator('img').all()
                for img in images:
                    try:
                        src = img.get_attribute('src')
                        # Include standard instagram cdn links, exclude small profile pictures
                        if src and ('scontent' in src or 'instagram' in src) and 'http' in src:
                            if '150x150' not in src and '100x100' not in src:
                                # Filter out related posts at the bottom by checking the vertical position
                                bbox = img.bounding_box()
                                if bbox and bbox['y'] < 600:
                                    if src not in urls:
                                        urls.append(src)
                    except Exception:
                        pass

            # Extract initial images before clicking
            extract_current_images()
            
            # Click next buttons on carousel if any to load all images
            for _ in range(10): # max 10 clicks for carousel
                try:
                    next_btn = page.locator('button[aria-label="Next"], button[aria-label="다음"]').first
                    if next_btn.is_visible(timeout=1000):
                        next_btn.click(timeout=2000)
                        page.wait_for_timeout(1000)
                        extract_current_images() # Extract images as they appear
                    else:
                        break
                except Exception as e:
                    print("Carousel click error:", e)
                    break
        except Exception as e:
            print(f"Failed to scrape Instagram: {e}")
        finally:
            browser.close()
            
    if progress_callback:
        progress_callback(len(urls), len(urls))
    return urls

def download_images(keyword, urls, base_dir="downloads", progress_callback=None):
    """
    Downloads images from a list of URLs and saves them into {base_dir}/{keyword}/.
    """
    download_dir = os.path.join(base_dir, keyword)
    os.makedirs(download_dir, exist_ok=True)
    
    headers = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
    }
    
    downloaded_files = []
    
    for idx, url in enumerate(urls):
        try:
            ext = "jpg"
            parsed_url = urllib.parse.urlparse(url)
            path_ext = os.path.splitext(parsed_url.path)[1].lower()
            if path_ext in [".jpg", ".jpeg", ".png", ".webp", ".gif", ".bmp"]:
                ext = path_ext.lstrip(".")
            
            ext = re.sub(r'[^a-z0-9]', '', ext)[:4]
            if not ext:
                ext = "jpg"
                
            import hashlib
            url_hash = hashlib.md5(url.encode('utf-8')).hexdigest()[:12]
            file_name = f"{keyword}_{url_hash}.{ext}"
            file_path = os.path.join(download_dir, file_name)
            
            response = requests.get(url, headers=headers, timeout=10)
            if response.status_code == 200:
                with open(file_path, "wb") as f:
                    f.write(response.content)
                downloaded_files.append(file_path)
        except Exception as e:
            print(f"Failed to download image {idx+1} from {url}: {e}")
            
        if progress_callback:
            progress_callback(idx + 1, len(urls))
            
    return downloaded_files

def get_youtube_info(url):
    """
    Fetches video metadata info from YouTube or Instagram links using yt-dlp.
    """
    ydl_opts = {
        'skip_download': True,
        'quiet': True,
    }
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        try:
            info = ydl.extract_info(url, download=False)
            formats = info.get('formats', [])
            
            # Extract distinct heights (resolutions) like 2160, 1440, 1080, 720, 480, 360, etc.
            resolutions = set()
            for f in formats:
                height = f.get('height')
                # Only include formats that contain video stream
                if height and f.get('vcodec') != 'none':
                    resolutions.add(height)
            
            sorted_res = sorted(list(resolutions), reverse=True)
            res_options = []
            for r in sorted_res:
                if r >= 2160:
                    res_options.append(f"{r}p (4K UHD)")
                elif r >= 1440:
                    res_options.append(f"{r}p (2K QHD)")
                elif r >= 1080:
                    res_options.append(f"{r}p (1080p Full HD)")
                elif r >= 720:
                    res_options.append(f"{r}p (720p HD)")
                else:
                    res_options.append(f"{r}p")
                    
            if not res_options:
                res_options = ["기본 고화질 (Best Quality)"]

            uploader = info.get('uploader') or info.get('channel') or info.get('uploader_id') or "알 수 없음"
            title = info.get('title') or "온라인 비디오"

            return {
                'title': title,
                'thumbnail': info.get('thumbnail'),
                'duration': info.get('duration'),  # in seconds
                'uploader': uploader,
                'view_count': info.get('view_count'),
                'resolutions': res_options
            }
        except Exception as e:
            print(f"Failed to fetch video info: {e}")
            return None

def reencode_video_for_mac(input_path, output_path=None, crf="22", preset="fast", progress_callback=None):
    """
    Re-encodes video & audio with H.264/AAC + yuv420p + faststart to ensure 100% macOS QuickTime & Finder preview compatibility.
    Handles videos without audio stream by generating a silent stereo track if needed.
    """
    import subprocess
    import imageio_ffmpeg

    if not input_path or not os.path.exists(input_path):
        print(f"File not found: {input_path}")
        return None

    ffmpeg_exe = imageio_ffmpeg.get_ffmpeg_exe()

    if output_path is None:
        base_name = os.path.splitext(input_path)[0]
        output_path = base_name + ".mp4"

    dir_name = os.path.dirname(output_path)
    if dir_name:
        os.makedirs(dir_name, exist_ok=True)

    temp_mac_path = output_path + ".mac_temp.mp4"

    cmd = [
        ffmpeg_exe, "-y",
        "-i", input_path,
        "-c:v", "libx264",
        "-preset", preset,
        "-crf", str(crf),
        "-pix_fmt", "yuv420p",
        "-c:a", "aac",
        "-ar", "44100",
        "-ac", "2",
        "-b:a", "192k",
        "-movflags", "+faststart",
        temp_mac_path
    ]

    res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)

    if res.returncode != 0:
        # Fallback if audio stream missing or failed: generate silent audio track
        fallback_cmd = [
            ffmpeg_exe, "-y",
            "-i", input_path,
            "-f", "lavfi", "-i", "anullsrc=channel_layout=stereo:sample_rate=44100",
            "-c:v", "libx264",
            "-preset", preset,
            "-crf", str(crf),
            "-pix_fmt", "yuv420p",
            "-c:a", "aac",
            "-b:a", "192k",
            "-shortest",
            "-movflags", "+faststart",
            temp_mac_path
        ]
        res2 = subprocess.run(fallback_cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        if res2.returncode != 0:
            print(f"Mac re-encoding error: {res2.stderr.decode('utf-8', errors='ignore')}")
            if os.path.exists(temp_mac_path):
                os.remove(temp_mac_path)
            return input_path if os.path.exists(input_path) else None

    if os.path.exists(temp_mac_path):
        if os.path.exists(output_path) and os.path.abspath(output_path) != os.path.abspath(input_path):
            os.remove(output_path)
        if os.path.abspath(input_path) == os.path.abspath(output_path) and os.path.exists(input_path):
            os.remove(input_path)
        os.rename(temp_mac_path, output_path)
        return output_path

    return input_path if os.path.exists(input_path) else None

def download_youtube_video(url, base_dir="downloads", quality="1080p", progress_callback=None, reencode_mac=True):
    """
    Downloads high-quality YouTube or Instagram video into base_dir using yt-dlp.
    Re-encodes video & audio with H.264/AAC + faststart to ensure 100% macOS QuickTime & Finder preview compatibility if reencode_mac is True.
    """
    import imageio_ffmpeg
    os.makedirs(base_dir, exist_ok=True)
    
    def hook(d):
        if d['status'] == 'downloading':
            total_bytes = d.get('total_bytes') or d.get('total_bytes_estimate')
            downloaded = d.get('downloaded_bytes', 0)
            if total_bytes and progress_callback:
                percent = downloaded / total_bytes
                speed = d.get('speed', 0)  # bytes per second
                eta = d.get('eta', 0)  # seconds
                progress_callback(percent, speed, eta)
                
    # Extract numerical height from quality string (e.g. "1080p (1080p Full HD)" -> 1080)
    height_match = re.search(r'\d+', quality)
    if height_match:
        height = height_match.group()
        fmt = f'bestvideo[height<={height}]+bestaudio/best[height<={height}]/best'
    else:
        fmt = 'bestvideo+bestaudio/best'
    
    # Get the static ffmpeg executable path installed by imageio-ffmpeg
    ffmpeg_path = imageio_ffmpeg.get_ffmpeg_exe()
    
    ydl_opts = {
        'format': fmt,
        'outtmpl': os.path.join(base_dir, '%(title)s.%(ext)s'),
        'ffmpeg_location': ffmpeg_path,
        'progress_hooks': [hook],
        'quiet': True,
    }
    
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        try:
            info = ydl.extract_info(url, download=True)
            filename = ydl.prepare_filename(info)
            
            # Extensions can resolve dynamically after merge (e.g. mkv -> mp4)
            basename = os.path.splitext(filename)[0]
            dir_name = os.path.dirname(filename)
            actual_path = filename
            if os.path.exists(dir_name):
                for f in os.listdir(dir_name):
                    if f.startswith(os.path.basename(basename)) and not f.endswith('.part') and not f.endswith('.mac_temp.mp4'):
                        actual_path = os.path.join(dir_name, f)
                        break

            # macOS QuickTime & QuickLook Compatibility Fix
            if reencode_mac and actual_path and os.path.exists(actual_path):
                final_target = os.path.splitext(actual_path)[0] + ".mp4"
                mac_encoded = reencode_video_for_mac(actual_path, final_target, crf="22")
                if mac_encoded:
                    return mac_encoded

            return actual_path
        except Exception as e:
            print(f"Video download failed: {e}")
            return None

def create_video_from_images(image_paths, output_path, duration_per_image=2, progress_callback=None):
    """
    Compiles list of image file paths into a slideshow video.
    """
    import cv2
    if not image_paths:
        return None
        
    first_img = cv2.imread(image_paths[0])
    if first_img is None:
        return None
    height, width, _ = first_img.shape
    
    fps = 24
    frames_per_image = int(fps * duration_per_image)
    
    fourcc = cv2.VideoWriter_fourcc(*'mp4v')
    video = cv2.VideoWriter(output_path, fourcc, fps, (width, height))
    
    total_images = len(image_paths)
    for idx, img_path in enumerate(image_paths):
        img = cv2.imread(img_path)
        if img is not None:
            if img.shape[0] != height or img.shape[1] != width:
                img = cv2.resize(img, (width, height))
            
            for _ in range(frames_per_image):
                video.write(img)
                
        if progress_callback:
            progress_callback(idx + 1, total_images)
            
    video.release()
    return output_path

def extract_m3u8_from_webpage(page_url):
    """
    Launches Chromium browser to bypass bot protection, 
    monitors network requests, and extracts HLS playlist (.m3u8), MP4, or MPD stream URLs,
    along with the webpage title.
    """
    import urllib.parse

    video_urls = []
    video_referers = {}
    extracted_title = ""

    img_exts = ('.png', '.jpg', '.jpeg', '.gif', '.webp', '.svg', '.ico', '.css', '.js')

    with sync_playwright() as p:
        browser = launch_browser(p)
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
            viewport={"width": 1280, "height": 800}
        )

        def handle_request(request):
            req_url = request.url
            req_type = request.resource_type
            
            is_video_stream = (
                ".m3u8" in req_url or 
                ".mpd" in req_url or 
                (".mp4" in req_url and not any(req_url.lower().endswith(ext) for ext in img_exts)) or
                (req_type == "media" and not any(req_url.lower().endswith(ext) for ext in img_exts))
            )
            
            if is_video_stream and req_url not in video_urls:
                video_urls.append(req_url)
                video_referers[req_url] = request.headers.get("referer", page_url)

        def attach_page_listeners(pg):
            pg.on("request", handle_request)

        context.on("page", attach_page_listeners)
        page = context.new_page()
        attach_page_listeners(page)

        try:
            page.goto(page_url, timeout=60000)
            page.wait_for_timeout(3000)
            extracted_title = page.title()

            # Click Server 2 / Server 3 buttons to load full video embed server
            try:
                server_btns = page.get_by_text("Server").all()
                for btn in server_btns:
                    try:
                        txt = btn.text_content().strip()
                        if '2' in txt or '3' in txt:
                            btn.click(timeout=1000)
                            page.wait_for_timeout(2000)
                            break
                    except Exception:
                        pass
            except Exception:
                pass

            # Inspect all iframes & DOM elements for embed servers (e.g. jav-master, upload18, etc.)
            try:
                iframe_srcs = [f.url for f in page.frames]
                for elem in page.query_selector_all('iframe[src], a[data-src], button[data-src], div[data-src]'):
                    src = elem.get_attribute('src') or elem.get_attribute('data-src') or elem.get_attribute('data-url')
                    if src and src.startswith('http') and src not in iframe_srcs:
                        iframe_srcs.append(src)

                for f_url in iframe_srcs:
                    if 'jav-master' in f_url or '/e/' in f_url:
                        parsed = urllib.parse.urlparse(f_url)
                        match = re.search(r'/e/([a-zA-Z0-9_]+)', parsed.path)
                        if match:
                            hash_id = match.group(1)
                            api_url = f"{parsed.scheme}://{parsed.netloc}/stream?id={hash_id}"
                            try:
                                res = requests.get(api_url, headers={'Referer': f_url, 'User-Agent': 'Mozilla/5.0'}, timeout=5)
                                if res.status_code == 200:
                                    data = res.json()
                                    stream_hls = data.get('media', {}).get('stream')
                                    if stream_hls and stream_hls not in video_urls:
                                        video_urls.insert(0, stream_hls)
                                        video_referers[stream_hls] = f_url
                            except Exception as err:
                                print(f"API fetch error: {err}")
            except Exception:
                pass

            try:
                play_selectors = [
                    'video', '.jw-display-icon-container', 'button.play', '.vjs-big-play-button',
                    'div[aria-label="Play"]', 'button[aria-label="Play"]', '.play-btn', '#player'
                ]
                for sel in play_selectors:
                    elem = page.locator(sel).first
                    if elem.is_visible(timeout=1000):
                        elem.click(timeout=1000)
                        break
            except Exception:
                pass

            for _ in range(5):
                page.wait_for_timeout(1000)
                if any(".m3u8" in u for u in video_urls):
                    break

        except Exception as e:
            print(f"Error loading webpage: {e}")
        finally:
            browser.close()

    best_url = None
    m3u8_playlists = [u for u in video_urls if "playlist.m3u8" in u or "video.m3u8" in u or ".m3u8" in u]
    mp4_streams = [u for u in video_urls if ".mp4" in u]

    if m3u8_playlists:
        best_url = m3u8_playlists[0]
    elif mp4_streams:
        best_url = mp4_streams[0]
    elif video_urls:
        best_url = video_urls[0]

    if best_url:
        return {
            "url": best_url,
            "referer": video_referers.get(best_url, page_url),
            "title": extracted_title or "web_video"
        }
    return None

def download_web_video(m3u8_url, base_dir="downloads", output_name="web_video.mp4", progress_callback=None, referer=None, reencode_mac=True):
    """
    Downloads HLS stream with customized headers (e.g., Referer) and configurations.
    """
    os.makedirs(base_dir, exist_ok=True)
    
    def hook(d):
        if d['status'] == 'downloading':
            total_bytes = d.get('total_bytes') or d.get('total_bytes_estimate')
            downloaded = d.get('downloaded_bytes', 0)
            
            percent = 0.0
            frag_index = d.get('fragment_index')
            frag_count = d.get('fragment_count')
            if frag_index and frag_count:
                percent = frag_index / frag_count
            elif total_bytes:
                percent = downloaded / total_bytes
                
            if progress_callback:
                speed = d.get('speed', 0)
                eta = d.get('eta', 0)
                progress_callback(percent, speed, eta)

    if not referer:
        referer = "https://iframe.mediadelivery.net/"
    output_path = os.path.join(base_dir, output_name)
    
    ydl_opts = {
        'http_headers': {
            'Referer': referer,
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36',
        },
        'outtmpl': output_path,
        'external_downloader_args': {
            'ffmpeg': ['-allowed_extensions', 'ALL']
        },
        'progress_hooks': [hook],
        'quiet': True,
    }
    
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        try:
            info = ydl.extract_info(m3u8_url, download=True)
            filename = ydl.prepare_filename(info)
            
            # Post-processing: Remux using ffmpeg to resolve macOS QuickTime and Premiere Pro compatibility issues
            if reencode_mac and filename and os.path.exists(filename):
                mac_encoded = reencode_video_for_mac(filename, output_path, crf="22")
                if mac_encoded:
                    return mac_encoded
            
            return filename
        except Exception as e:
            print(f"Web video download failed: {e}")
            return None


def merge_videos(video_paths, output_path, resolution="1080p", progress_callback=None):
    """
    Concatenates multiple video files into a single standardized MP4 video file.
    Re-encodes each video chunk to H.264/AAC with matching resolution and frame rate,
    then merges them seamlessly using ffmpeg.
    """
    import subprocess
    import tempfile
    import imageio_ffmpeg
    import shutil
    
    if not video_paths:
        return None
        
    ffmpeg_exe = imageio_ffmpeg.get_ffmpeg_exe()
    output_dir = os.path.dirname(output_path)
    if output_dir:
        os.makedirs(output_dir, exist_ok=True)
        
    res_map = {
        "4K (2160p)": (3840, 2160),
        "2K (1440p)": (2560, 1440),
        "1080p": (1920, 1080),
        "720p": (1280, 720),
        "480p": (854, 480),
    }
    
    w, h = 1920, 1080  # Default 1080p
    for k, v in res_map.items():
        if k in resolution:
            w, h = v
            break
            
    temp_dir = tempfile.mkdtemp(prefix="vid_merge_")
    norm_paths = []
    total_steps = len(video_paths) + 1  # Normalize steps + concat step
    
    try:
        # Step 1: Normalize each video clip
        for idx, src_path in enumerate(video_paths):
            if not os.path.exists(src_path):
                continue
                
            norm_path = os.path.join(temp_dir, f"norm_{idx:04d}.mp4")
            
            vf_filter = (
                f"scale={w}:{h}:force_original_aspect_ratio=decrease,"
                f"pad={w}:{h}:(ow-iw)/2:(oh-ih)/2:black,setsar=1,fps=30"
            )
            
            cmd = [
                ffmpeg_exe, "-y",
                "-i", src_path,
                "-vf", vf_filter,
                "-c:v", "libx264",
                "-preset", "fast",
                "-crf", "22",
                "-pix_fmt", "yuv420p",
                "-c:a", "aac",
                "-ar", "44100",
                "-ac", "2",
                "-b:a", "192k",
                "-shortest",
                norm_path
            ]
            
            res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            if res.returncode != 0:
                # Fallback if video has no audio track: generate silent audio
                fallback_cmd = [
                    ffmpeg_exe, "-y",
                    "-i", src_path,
                    "-f", "lavfi", "-i", "anullsrc=channel_layout=stereo:sample_rate=44100",
                    "-vf", vf_filter,
                    "-c:v", "libx264",
                    "-preset", "fast",
                    "-crf", "22",
                    "-pix_fmt", "yuv420p",
                    "-c:a", "aac",
                    "-b:a", "192k",
                    "-shortest",
                    norm_path
                ]
                res2 = subprocess.run(fallback_cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                if res2.returncode != 0:
                    print(f"Error normalizing video {src_path}: {res2.stderr.decode('utf-8', errors='ignore')}")
                    continue
                    
            if os.path.exists(norm_path):
                norm_paths.append(norm_path)
                
            if progress_callback:
                progress_callback(idx + 1, total_steps, f"클립 변환 중 ({idx+1}/{len(video_paths)}): {os.path.basename(src_path)}")

        if not norm_paths:
            return None
            
        # Step 2: Concat normalized clips using concat demuxer
        concat_txt = os.path.join(temp_dir, "concat_list.txt")
        with open(concat_txt, "w", encoding="utf-8") as f:
            for p in norm_paths:
                f.write(f"file '{p}'\n")
                
        if progress_callback:
            progress_callback(len(video_paths) + 0.5, total_steps, "최종 영상 이어붙이기 병합 중...")
            
        concat_cmd = [
            ffmpeg_exe, "-y",
            "-f", "concat",
            "-safe", "0",
            "-i", concat_txt,
            "-c", "copy",
            "-movflags", "+faststart",
            output_path
        ]
        
        c_res = subprocess.run(concat_cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        if c_res.returncode == 0 and os.path.exists(output_path):
            if progress_callback:
                progress_callback(total_steps, total_steps, "병합 완료!")
            return output_path
        else:
            print(f"Concat failed: {c_res.stderr.decode('utf-8', errors='ignore')}")
            return None
    finally:
        try:
            shutil.rmtree(temp_dir, ignore_errors=True)
        except Exception:
            pass


def merge_images(image_paths, output_path, direction="vertical", resize_mode="min_width", background_color=(0, 0, 0, 0)):
    """
    여러 이미지를 가로(horizontal) 또는 세로(vertical)로 이어붙입니다.
    
    :param image_paths: 병합할 이미지 파일의 절대 경로 리스트
    :param output_path: 저장할 결과 이미지 파일 경로
    :param direction: "horizontal" (가로로 붙이기) 또는 "vertical" (세로로 붙이기)
    :param resize_mode: 
        - "min_width": 가장 작은 이미지의 가로 폭에 맞춰 다른 이미지들을 리사이즈 (비율 유지)
        - "min_height": 가장 작은 이미지의 세로 높이에 맞춰 다른 이미지들을 리사이즈 (비율 유지)
        - "none": 리사이즈 안 함
    :param background_color: 빈 공간을 채울 배경색 (RGBA 튜플, 기본값 투명 (0, 0, 0, 0))
    :return: 저장된 결과 이미지 경로 (성공 시) 또는 None (실패 시)
    """
    if not image_paths:
        return None
        
    try:
        # 1. 이미지 로드
        images = []
        for p in image_paths:
            if os.path.exists(p):
                try:
                    images.append(Image.open(p).convert("RGBA"))
                except Exception as e:
                    print(f"Error opening image {p}: {e}")
        
        if not images:
            return None
            
        # 2. 리사이즈 처리
        resized_images = []
        if resize_mode == "min_width":
            # 모든 이미지 중 최소 가로 폭 찾기
            min_w = min(img.width for img in images)
            for img in images:
                if img.width == min_w:
                    resized_images.append(img)
                else:
                    # 비율을 유지하며 가로를 min_w로 리사이즈
                    ratio = min_w / img.width
                    new_h = int(img.height * ratio)
                    
                    try:
                        resample_filter = Image.Resampling.LANCZOS
                    except AttributeError:
                        try:
                            resample_filter = Image.LANCZOS
                        except AttributeError:
                            resample_filter = Image.ANTIALIAS
                    resized_images.append(img.resize((min_w, new_h), resample_filter))
                    
        elif resize_mode == "min_height":
            # 모든 이미지 중 최소 세로 높이 찾기
            min_h = min(img.height for img in images)
            for img in images:
                if img.height == min_h:
                    resized_images.append(img)
                else:
                    # 비율을 유지하며 세로를 min_h로 리사이즈
                    ratio = min_h / img.height
                    new_w = int(img.width * ratio)
                    
                    try:
                        resample_filter = Image.Resampling.LANCZOS
                    except AttributeError:
                        try:
                            resample_filter = Image.LANCZOS
                        except AttributeError:
                            resample_filter = Image.ANTIALIAS
                    resized_images.append(img.resize((new_w, min_h), resample_filter))
        else:
            resized_images = images
            
        # 3. 병합 크기 계산
        if direction == "horizontal":
            # 가로로 붙이기
            total_width = sum(img.width for img in resized_images)
            max_height = max(img.height for img in resized_images)
            
            # 결과 이미지 생성
            new_img = Image.new("RGBA", (total_width, max_height), background_color)
            
            # 이미지 붙이기 (세로 중앙 정렬)
            current_x = 0
            for img in resized_images:
                y_offset = (max_height - img.height) // 2
                new_img.paste(img, (current_x, y_offset), mask=img.split()[3])
                current_x += img.width
        else:
            # 세로로 붙이기
            max_width = max(img.width for img in resized_images)
            total_height = sum(img.height for img in resized_images)
            
            # 결과 이미지 생성
            new_img = Image.new("RGBA", (max_width, total_height), background_color)
            
            # 이미지 붙이기 (가로 중앙 정렬)
            current_y = 0
            for img in resized_images:
                x_offset = (max_width - img.width) // 2
                new_img.paste(img, (x_offset, current_y), mask=img.split()[3])
                current_y += img.height
                
        # 4. 결과 저장
        ext = os.path.splitext(output_path)[1].lower()
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        
        if ext in ['.jpg', '.jpeg']:
            # RGBA를 RGB로 변환 (흰색 배경)
            bg = Image.new("RGB", new_img.size, (255, 255, 255))
            bg.paste(new_img, mask=new_img.split()[3])
            bg.save(output_path, "JPEG", quality=95)
        else:
            new_img.save(output_path)
            
        return output_path
    except Exception as e:
        print(f"Error in merge_images: {e}")
        return None


