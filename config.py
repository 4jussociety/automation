import os
from pathlib import Path
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent
OUTPUT_DIR = BASE_DIR / "output"
TEMPLATES_DIR = BASE_DIR / "templates"
HISTORY_FILE = BASE_DIR / "history.json"

# Gemini API 설정
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
DEFAULT_MODEL = "gemini-2.5-flash"

# Edge-TTS 설정 (한국어 뉴스용 음성)
TTS_VOICE = "ko-KR-InJoonNeural"  # 차분하고 신뢰감 있는 남성 아나운서 톤 (또는 ko-KR-SunHiNeural 여성 톤)

# 현재 연도 및 주차 식별자 (예: 2026-W36)
CURRENT_WEEK = f"{datetime.now().year}-W{datetime.now().isocalendar().week:02d}"

# 3대 카테고리 정의
CATEGORIES = {
    "SET_1_KR_POLICY": {
        "id": "set1_국내정책_보험",
        "title": "국내 정책 / 보험 / 업계 이슈",
        "keywords": [
            "도수치료 실손보험",
            "물리치료사 법안",
            "심평원 물리치료 수가",
            "물리치료사 협회",
            "재활의료 정책"
        ],
        "rss_queries": [
            "도수치료 실손보험",
            "물리치료 정책",
            "물리치료사 단독개원"
        ]
    },
    "SET_2_KR_CLINICAL": {
        "id": "set2_국내임상_연구",
        "title": "국내 임상 / 연구 / 신기술",
        "keywords": [
            "물리치료 재활 연구",
            "도수치료 임상 효과",
            "재활 로봇 물리치료",
            "체형교정 연구",
            "거북목 디스크 재활"
        ],
        "rss_queries": [
            "물리치료 임상 연구",
            "재활치료 신기술",
            "도수치료 효과"
        ]
    },
    "SET_3_GLOBAL": {
        "id": "set3_해외동향_논문",
        "title": "해외 최신 동향 / 글로벌 논문",
        "keywords": [
            "Physical therapy clinical trial",
            "Physiotherapy rehabilitation study",
            "APTA physical therapy guidelines",
            "Musculoskeletal physical therapy journal",
            "Spine rehabilitation research"
        ],
        "rss_queries": [
            "physical therapy rehabilitation journal",
            "physiotherapy clinical study"
        ]
    }
}
