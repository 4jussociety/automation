# 기사 주제 및 슬라이드 특성에 맞춤형 배경 이미지를 매칭하고 자동 생성하는 모듈입니다.
# AI 배경 생성 기능과 테마별 고화질 프리셋 에셋 풀 폴백 메커니즘을 제공합니다.

import os
import re
import base64
from pathlib import Path
from config import BASE_DIR, GEMINI_API_KEY, ENABLE_AI_BG_GENERATION

BG_DIR = BASE_DIR / "assets" / "backgrounds"

THEME_PRESETS = {
    "cover": BG_DIR / "bg_clinic.jpg",
    "clinic": BG_DIR / "bg_clinic.jpg",
    "insurance": BG_DIR / "bg_insurance.jpg",
    "spine": BG_DIR / "bg_spine.jpg",
    "robotics": BG_DIR / "bg_robotics.jpg",
    "joint": BG_DIR / "bg_joint.jpg",
    "insight": BG_DIR / "bg_insight.jpg",
    "outro": BG_DIR / "bg_outro.jpg"
}

def determine_slide_theme(slide_data: dict, slide_index: int = 1, total_slides: int = 6) -> str:
    """슬라이드의 내용, 카테고리, 텍스트 키워드를 분석하여 배경 테마를 결정합니다."""
    slide_type = slide_data.get("type", "")

    if slide_type == "cover" or slide_index == 1:
        return "cover"
    if slide_type == "insight" or slide_index == total_slides - 1:
        return "insight"
    if slide_type == "outro" or slide_index == total_slides:
        return "outro"

    # 뉴스 본문 슬라이드 (텍스트 키워드 기반 분류)
    headline = slide_data.get("headline", "")
    category = slide_data.get("category_badge", "") + " " + slide_data.get("category", "")
    full_text = f"{headline} {category}".lower()

    # 1. 보험 / 정책 / 법안 / 수가
    if any(k in full_text for k in ["보험", "실손", "심평원", "수가", "법률", "법안", "의료기사", "정책", "가이드라인"]):
        return "insurance"
    
    # 2. 로봇 / 인공지능 / 신기술 / 웨어러블
    if any(k in full_text for k in ["로봇", "외골격", "웨어러블", "신기술", "ai", "첨단"]):
        return "robotics"

    # 3. 척추 / 경추 / 거북목 / 도수 / 디스크 / 요통
    if any(k in full_text for k in ["척추", "목", "경추", "거북목", "도수", "디스크", "요통", "체형", "골반", "spine"]):
        return "spine"

    # 4. 관절 / 무릎 / 어깨 / 햄스트링 / 스포츠 / 스트레칭 / 근육
    if any(k in full_text for k in ["관절", "무릎", "어깨", "햄스트링", "스포츠", "스트레칭", "근육", "오십견", "연골"]):
        return "joint"

    # 순환 기본값
    fallback_cycle = ["spine", "insurance", "joint", "robotics"]
    return fallback_cycle[(slide_index - 2) % len(fallback_cycle)]

def get_slide_background_file(slide_data: dict, slide_index: int = 1, total_slides: int = 6) -> Path:
    """슬라이드 맞춤형 순수 배경 이미지 파일 경로를 반환합니다."""
    theme = determine_slide_theme(slide_data, slide_index, total_slides)
    bg_file = THEME_PRESETS.get(theme, THEME_PRESETS["cover"])
    if not bg_file.exists():
        bg_file = THEME_PRESETS["cover"]
    return bg_file

def get_slide_background_uri(slide_data: dict, slide_index: int = 1, total_slides: int = 6) -> str:
    """슬라이드 맞춤형 배경 이미지를 찾아 Base64 Data URI로 반환합니다."""
    bg_file = get_slide_background_file(slide_data, slide_index, total_slides)

    if bg_file.exists():
        with open(bg_file, "rb") as f:
            b64 = base64.b64encode(f.read()).decode("utf-8")
            ext = bg_file.suffix.lower().replace(".", "")
            if ext == "jpg":
                ext = "jpeg"
            return f"data:image/{ext};base64,{b64}"
    return ""
