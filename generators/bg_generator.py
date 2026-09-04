# 기사 원문의 대표 이미지(og:image)를 스크랩하여 세트별 배경 이미지로 배치하는 모듈입니다.
# 기사에 사진이 없는 경우 직전 슬라이드의 사진(이전 사진)을 자동으로 이어받아 적용하며,
# 템플릿 CSS의 블러(blur) 및 다크 톤 처리를 통해 선명한 가독성과 감성적인 무드를 제공합니다.

import os
import shutil
import base64
import urllib.request
import urllib.parse
from pathlib import Path
from typing import List
from bs4 import BeautifulSoup
from config import BASE_DIR

# 기본 비상용 프리셋 에셋 경로 (첫 장부터 사진이 전혀 없을 때의 최후 Fallback)
FALLBACK_BG_DIR = BASE_DIR / "assets" / "backgrounds"
DEFAULT_FALLBACK_IMAGE = FALLBACK_BG_DIR / "bg_clinic.jpg"

def fetch_article_og_image(article_url: str) -> str:
    """
    기사 링크(구글 뉴스 RSS 링크 또는 일반 언론사 링크)에서
    원문 기사의 대표 이미지(og:image 또는 twitter:image) URL을 스크랩합니다.
    """
    if not article_url:
        return ""

    real_url = article_url
    # 구글 뉴스 RSS 중계 링크인 경우 원문 URL로 디코딩
    if "news.google.com" in article_url:
        try:
            from googlenewsdecoder import gnewsdecoder
            res = gnewsdecoder(article_url)
            if isinstance(res, dict) and res.get("status"):
                real_url = res.get("decoded_url", article_url)
            elif isinstance(res, str):
                real_url = res
        except Exception:
            pass

    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    }

    try:
        req = urllib.request.Request(real_url, headers=headers)
        with urllib.request.urlopen(req, timeout=8) as resp:
            html = resp.read().decode("utf-8", errors="ignore")

        soup = BeautifulSoup(html, "html.parser")

        # 1. OpenGraph 이미지 메타태그 우선 탐색
        og_img = soup.find("meta", property="og:image")
        if not og_img or not og_img.get("content"):
            og_img = soup.find("meta", attrs={"name": "twitter:image"})

        img_url = og_img.get("content", "").strip() if og_img else ""

        # 구글 로고, 빈 이미지 등 무효 이미지 필터링
        if img_url and not any(bad in img_url for bad in ["googleusercontent.com", "favicon", "blank.gif", "default_image_share"]):
            # 상대 경로(URL) 처리
            if img_url.startswith("//"):
                img_url = "https:" + img_url
            elif img_url.startswith("/") and not img_url.startswith("//"):
                parsed = urllib.parse.urlparse(real_url)
                img_url = f"{parsed.scheme}://{parsed.netloc}{img_url}"
            return img_url
    except Exception:
        pass

    return ""

def download_image_to_file(image_url: str, target_path: Path, timeout: int = 10) -> bool:
    """이미지 URL을 다운로드하여 target_path에 저장합니다 (최소 5KB 이상 유효성 검증)."""
    if not image_url:
        return False

    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    }

    try:
        req = urllib.request.Request(image_url, headers=headers)
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            data = resp.read()

        if len(data) > 5000:  # 최소 5KB 이상인 유효 이미지 검증
            target_path.parent.mkdir(parents=True, exist_ok=True)
            with open(target_path, "wb") as f:
                f.write(data)
            return True
    except Exception:
        pass

    return False

def file_to_base64_uri(file_path: Path) -> str:
    """파일 경로를 받아 Base64 Data URI로 인코딩합니다."""
    if file_path.exists():
        with open(file_path, "rb") as f:
            b64 = base64.b64encode(f.read()).decode("utf-8")
            ext = file_path.suffix.lower().replace(".", "")
            if ext == "jpg":
                ext = "jpeg"
            return f"data:image/{ext};base64,{b64}"
    return ""

def prepare_set_backgrounds(card_data: dict, bg_output_dir: Path, force_refresh: bool = True) -> List[Path]:
    """
    각 세트별 폴더(output/{CURRENT_WEEK}/{batch_id}/backgrounds/)에
    기사 스크랩 사진을 배치합니다.

    [규칙]
    1. 사용자가 직접 해당 폴더에 넣은 커스텀 파일(custom_bg_slide_0X.*)이 있으면 최우선 유지
    2. 기사 원문 링크에서 실제 기사 대표 사진(og:image)을 스크랩하여 다운로드
    3. 사진이 없는 기사나 아웃트로/인사이트 슬라이드는 '직전 슬라이드의 사진(이전 사진)'을 그대로 이어받아 적용
    4. (최초 슬라이드부터 사진이 없는 경우에만 로컬 기본 프리셋 사진을 시드 이미지로 사용)
    """
    bg_output_dir.mkdir(parents=True, exist_ok=True)
    slides = card_data.get("slides", [])
    news_items = card_data.get("news_items", [])
    total_slides = max(len(slides), 6)
    assigned_bg_files: List[Path] = []

    def get_smart_fallback(text: str, slide_num: int) -> Path:
        """슬라이드 내용과 순서에 맞는 전문 의료 배경을 선별합니다."""
        t = text.lower()
        if slide_num == 5:
            cand = FALLBACK_BG_DIR / "bg_insight.jpg"
            if cand.exists(): return cand
        elif slide_num == 6:
            cand = FALLBACK_BG_DIR / "bg_outro.jpg"
            if cand.exists(): return cand

        if any(k in t for k in ["로봇", "신기술", "ai", "웨어러블", "외골격", "robot"]):
            cand = FALLBACK_BG_DIR / "bg_robotics.jpg"
            if cand.exists(): return cand
        elif any(k in t for k in ["보험", "수가", "심평원", "정책", "법안", "삭감", "실손"]):
            cand = FALLBACK_BG_DIR / "bg_insurance.jpg"
            if cand.exists(): return cand
        elif any(k in t for k in ["척추", "도수", "경추", "요추", "디스크", "spine"]):
            cand = FALLBACK_BG_DIR / "bg_spine.jpg"
            if cand.exists(): return cand
        elif any(k in t for k in ["관절", "무릎", "어깨", "임상", "운동", "joint"]):
            cand = FALLBACK_BG_DIR / "bg_joint.jpg"
            if cand.exists(): return cand
        
        return DEFAULT_FALLBACK_IMAGE if DEFAULT_FALLBACK_IMAGE.exists() else list(FALLBACK_BG_DIR.glob("*.jpg"))[0]

    # 이전 유효 배경 추적
    last_valid_bg: Path = get_smart_fallback(card_data.get("title", ""), 1)

    for idx, slide in enumerate(slides, start=1):
        target_file = bg_output_dir / f"bg_slide_{idx:02d}.jpg"
        slide_text = f"{slide.get('title', '')} {slide.get('subtitle', '')} {slide.get('content', '')}"

        # 1. 수동 파일 오버라이드 확인 (custom_bg_slide_0X.*)
        existing_custom = None
        for ext in [".jpg", ".jpeg", ".png", ".webp"]:
            custom_candidate = bg_output_dir / f"custom_bg_slide_{idx:02d}{ext}"
            if custom_candidate.exists() and custom_candidate.stat().st_size > 5000:
                existing_custom = custom_candidate
                break

        if existing_custom:
            last_valid_bg = existing_custom
            assigned_bg_files.append(existing_custom)
            print(f"    [수동 커스텀 배경] Slide {idx}: {existing_custom.name}")
            continue

        # 2. 해당 슬라이드에 해당하는 기사 링크 결정
        target_link = ""
        if idx == 1 and news_items:
            target_link = news_items[0].get("link", "")
        elif 2 <= idx <= 4 and len(news_items) >= (idx - 1):
            target_link = news_items[idx - 2].get("link", "")

        # 3. 기사 원문 사진 스크랩 시도
        img_downloaded = False
        if target_link:
            og_img_url = fetch_article_og_image(target_link)
            if og_img_url:
                img_downloaded = download_image_to_file(og_img_url, target_file)

        if img_downloaded:
            last_valid_bg = target_file
            assigned_bg_files.append(target_file)
            print(f"    [기사 사진 스크랩] Slide {idx}: 원문 사진 다운로드 성공 ({target_file.stat().st_size} bytes)")
        else:
            # 4. 사진이 없는 경우: 1차로 직전 기사 사진 상속, 슬라이드 1이거나 특화 슬라이드는 스마트 배경 적용
            if idx in [5, 6] or last_valid_bg is None or not last_valid_bg.exists():
                fallback_chosen = get_smart_fallback(slide_text, idx)
            else:
                fallback_chosen = last_valid_bg

            if fallback_chosen and fallback_chosen.exists():
                shutil.copy2(fallback_chosen, target_file)
                last_valid_bg = target_file
                assigned_bg_files.append(target_file)
                print(f"    [배경 자동 매칭/상속] Slide {idx}: {fallback_chosen.name} 적용")
            else:
                assigned_bg_files.append(target_file)

    return assigned_bg_files
