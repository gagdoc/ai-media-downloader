#!/usr/bin/env python3
"""
4개 이미지를 원본 크기 유지하면서 2x2 그리드로 합치는 스크립트
각 이미지의 원본 크기를 유지하며, 가장 큰 이미지 크기를 기준으로 캔버스를 생성합니다.
"""

from PIL import Image
import os
import sys
import glob

def find_images(folder="."):
    """폴더에서 이미지 파일 자동 탐색"""
    extensions = ["*.jpg", "*.jpeg", "*.png", "*.webp", "*.bmp", "*.tiff"]
    images = []
    for ext in extensions:
        images.extend(glob.glob(os.path.join(folder, ext)))
        images.extend(glob.glob(os.path.join(folder, ext.upper())))
    return sorted(images)

def make_2x2_grid(image_paths, output_path="output_2x2.jpg", gap=10, bg_color=(255, 255, 255)):
    """
    4개 이미지를 원본 크기 유지하며 2x2 그리드로 합치기
    
    Args:
        image_paths: 이미지 경로 리스트 (4개)
        output_path: 출력 파일 경로
        gap: 이미지 간 간격 (픽셀)
        bg_color: 배경 색상 (R, G, B)
    """
    if len(image_paths) != 4:
        print(f"❌ 이미지 4개가 필요합니다. 현재 {len(image_paths)}개 찾음")
        sys.exit(1)

    print("📂 이미지 로딩 중...")
    imgs = []
    for i, path in enumerate(image_paths):
        img = Image.open(path).convert("RGBA")
        imgs.append(img)
        print(f"  [{i+1}] {os.path.basename(path)} → {img.size[0]}x{img.size[1]} px")

    # 각 행/열의 최대 크기 계산
    # 배치: [0][1]
    #       [2][3]
    w0, h0 = imgs[0].size  # 좌상단
    w1, h1 = imgs[1].size  # 우상단
    w2, h2 = imgs[2].size  # 좌하단
    w3, h3 = imgs[3].size  # 우하단

    # 각 열의 최대 너비, 각 행의 최대 높이
    col0_w = max(w0, w2)  # 왼쪽 열
    col1_w = max(w1, w3)  # 오른쪽 열
    row0_h = max(h0, h1)  # 위 행
    row1_h = max(h2, h3)  # 아래 행

    # 전체 캔버스 크기
    total_w = col0_w + col1_w + gap * 3  # 양쪽 여백 + 중간 간격
    total_h = row0_h + row1_h + gap * 3

    print(f"\n📐 캔버스 크기: {total_w}x{total_h} px")
    print(f"   간격: {gap}px")

    # 캔버스 생성
    canvas = Image.new("RGBA", (total_w, total_h), (*bg_color, 255))

    # 이미지 배치 좌표 계산 (각 이미지를 각 셀 내 좌상단 기준 배치)
    positions = [
        (gap,                col0_w + gap * 2),   # x 좌표: 좌상, 우상
        (gap,                col0_w + gap * 2),   # x 좌표 (재사용)
    ]

    x_left  = gap
    x_right = col0_w + gap * 2
    y_top   = gap
    y_bot   = row0_h + gap * 2

    placements = [
        (x_left,  y_top,  imgs[0]),  # 좌상단
        (x_right, y_top,  imgs[1]),  # 우상단
        (x_left,  y_bot,  imgs[2]),  # 좌하단
        (x_right, y_bot,  imgs[3]),  # 우하단
    ]

    for x, y, img in placements:
        canvas.paste(img, (x, y), img)

    # 저장
    final = canvas.convert("RGB")
    final.save(output_path, quality=97)
    print(f"\n✅ 저장 완료: {output_path}")
    print(f"   최종 크기: {final.size[0]}x{final.size[1]} px")


# ─────────────────────────────────────────────
# 메인 실행
# ─────────────────────────────────────────────
if __name__ == "__main__":
    # 방법 1: 명령줄 인수로 이미지 경로 직접 지정
    #   python3 make_2x2_grid.py img1.jpg img2.jpg img3.jpg img4.jpg
    #
    # 방법 2: 현재 폴더에서 자동 탐색 (이미지가 정확히 4개여야 함)
    #   python3 make_2x2_grid.py

    if len(sys.argv) == 5:
        # 명령줄에서 4개 경로 직접 입력
        paths = sys.argv[1:5]
    elif len(sys.argv) == 1:
        # 현재 폴더 자동 탐색
        paths = find_images(".")
        if len(paths) != 4:
            print(f"❌ 현재 폴더에서 이미지 {len(paths)}개 발견 (정확히 4개 필요)")
            print("   사용법: python3 make_2x2_grid.py img1.jpg img2.jpg img3.jpg img4.jpg")
            sys.exit(1)
    else:
        print("사용법:")
        print("  python3 make_2x2_grid.py img1.jpg img2.jpg img3.jpg img4.jpg")
        print("  python3 make_2x2_grid.py  (현재 폴더에 이미지 4개만 있을 경우 자동 인식)")
        sys.exit(1)

    # 출력 파일명
    output = "output_2x2.jpg"

    make_2x2_grid(
        image_paths=paths,
        output_path=output,
        gap=10,            # 간격 픽셀 (0이면 간격 없음)
        bg_color=(255, 255, 255),  # 배경: 흰색
    )
