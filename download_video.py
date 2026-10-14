import os
import sys
import re
from playwright.sync_api import sync_playwright
import yt_dlp

def extract_m3u8(page_url):
    print(f"[*] Opening browser to load page: {page_url}")
    print("[*] Please solve Turnstile (Cloudflare) check in the browser window if it pops up...")
    
    video_urls = []
    
    with sync_playwright() as p:
        # Launching headful browser to easily bypass bot protection
        browser = p.chromium.launch(headless=False)
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
        )
        page = context.new_page()
        
        def handle_request(request):
            req_url = request.url
            if ".m3u8" in req_url and "b-cdn.net" in req_url and req_url not in video_urls:
                video_urls.append(req_url)
                
        page.on("request", handle_request)
        
        try:
            page.goto(page_url, timeout=60000)
            # Wait to capture requests
            for i in range(15):
                page.wait_for_timeout(1000)
                if any("playlist.m3u8" in u for u in video_urls):
                    break
        except Exception as e:
            print(f"[!] Error loading page: {e}")
        finally:
            browser.close()
            
    # Prefer playlist.m3u8 if multiple found
    playlists = [u for u in video_urls if "playlist.m3u8" in u]
    if playlists:
        return playlists[0]
    elif video_urls:
        return video_urls[0]
    return None

def download_stream(m3u8_url, output_name="video.mp4"):
    print(f"[*] Found stream URL: {m3u8_url}")
    print(f"[*] Starting download to '{output_name}'...")
    
    referer = "https://iframe.mediadelivery.net/"
    ydl_opts = {
        'http_headers': {
            'Referer': referer,
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36',
        },
        'outtmpl': output_name,
        # Allow all extensions since BunnyCDN uses .dts extensions
        'external_downloader_args': {
            'ffmpeg': ['-allowed_extensions', 'ALL']
        }
    }
    
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([m3u8_url])
        print(f"[+] Download finished successfully! File saved as '{output_name}'")
    except Exception as e:
        print(f"[!] Download failed: {e}")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        url = input("Enter the webpage URL: ").strip()
    else:
        url = sys.argv[1]
        
    if not url:
        print("Usage: python download_video.py <URL>")
        sys.exit(1)
        
    m3u8 = extract_m3u8(url)
    if m3u8:
        # Generate safe filename from url or page title
        output_filename = "downloaded_video.mp4"
        download_stream(m3u8, output_filename)
    else:
        print("[!] Could not extract streaming URL. Make sure the page has loaded completely and contains a video player.")
