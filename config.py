import os
import calendar
from pathlib import Path
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent
OUTPUT_DIR = BASE_DIR / "output"
TEMPLATES_DIR = BASE_DIR / "templates"
CONTENTS_DIR = BASE_DIR / "contents"
HISTORY_FILE = BASE_DIR / "history.json"

# Gemini API 설정
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
DEFAULT_MODEL = os.getenv("GEMINI_MODEL", "gemini-3.7-flash")
ENABLE_AI_BG_GENERATION = True  # 기사 맞춤형 배경 동적 매칭 및 생성 활성화

# Edge-TTS 설정 (한국어 뉴스용 음성)
TTS_VOICE = "ko-KR-InJoonNeural"  # 차분하고 신뢰감 있는 남성 아나운서 톤 (또는 ko-KR-SunHiNeural 여성 톤)

# SNS 자동 업로드 및 예약 설정
ASSETS_DIR = BASE_DIR / "assets"
INSTAGRAM_SESSION_FILE = ASSETS_DIR / "instagram_session.json"
INSTAGRAM_SCHEDULE_DEFAULT_HOUR = int(os.getenv("INSTAGRAM_SCHEDULE_DEFAULT_HOUR", "20"))  # 예약 시간 (기본 20시)
INSTAGRAM_HEADLESS = os.getenv("INSTAGRAM_HEADLESS", "false").lower() == "true"

YOUTUBE_CLIENT_SECRETS_FILE = ASSETS_DIR / "client_secrets.json"
YOUTUBE_TOKEN_FILE = ASSETS_DIR / "youtube_token.json"
YOUTUBE_DEFAULT_PRIVACY = os.getenv("YOUTUBE_DEFAULT_PRIVACY", "public")  # 'public', 'unlisted', or 'private'

def get_korean_week_str(dt: datetime = None) -> str:
    """현재 날짜를 기준으로 직관적인 'YYYY년 M월 N주차' 형식의 문자열을 반환합니다 (예: 2026년 9월 1주차)."""
    if dt is None:
        dt = datetime.now()
    cal = calendar.monthcalendar(dt.year, dt.month)
    week_num = 1
    for idx, week in enumerate(cal, 1):
        if dt.day in week:
            week_num = idx
            break
    return f"{dt.year}년 {dt.month}월 {week_num}주차"

# 현재 연도 및 몇월 몇주차 식별자 (예: 2026년 9월 1주차)
CURRENT_WEEK = get_korean_week_str()

# 3대 카테고리 정의 (타겟: 물리치료사 및 재활전문가)
CATEGORIES = {
    "SET_1_KR_POLICY": {
        "id": "set1_국내정책_보험",
        "title": "국내 정책 / 보험 / 업계 이슈",
        "keywords": [
            "도수치료 실손보험 인정기준",
            "물리치료사 업무범위 법안",
            "심평원 물리치료 수가 급여기준",
            "대한물리치료사협회 정책",
            "전문물리치료사 제도 도입"
        ],
        "rss_queries": [
            "도수치료 실손보험 심사",
            "물리치료사 법안 정책",
            "심평원 물리치료 급여"
        ]
    },
    "SET_2_KR_CLINICAL": {
        "id": "set2_국내임상_연구",
        "title": "국내 임상 / 연구 / 신기술",
        "keywords": [
            "물리치료 임상 프로토콜 연구",
            "도수치료 중재 임상시험",
            "재활로봇 물리치료 임상",
            "근골격계 물리치료 평가 지표",
            "신경계 재활 치료 가이드라인"
        ],
        "rss_queries": [
            "물리치료 임상 연구",
            "재활치료 신기술 임상",
            "도수치료 중재 효과"
        ]
    },
    "SET_3_GLOBAL": {
        "id": "set3_해외동향_논문",
        "title": "해외 최신 동향 / 글로벌 논문",
        "keywords": [
            "Physical therapy clinical trial",
            "APTA physical therapy clinical guidelines",
            "JOSPT musculoskeletal physiotherapy",
            "Physiotherapy rehabilitation RCT",
            "Spine manual therapy research"
        ],
        "rss_queries": [
            "physical therapy clinical trial",
            "physiotherapy guideline journal"
        ]
    },
    # 주간 이슈 렌더러 카테고리
    "spine": {"name": "척추/체형교정", "bg": "bg_spine.jpg", "color": "#3b82f6"},
    "joint": {"name": "관절/도수치료", "bg": "bg_joint.jpg", "color": "#10b981"},
    "clinic": {"name": "병원/치료정보", "bg": "bg_clinic.jpg", "color": "#6366f1"},
    "insurance": {"name": "실손/의료보험", "bg": "bg_insurance.jpg", "color": "#f59e0b"},
    "robotics": {"name": "로봇재활/첨단치료", "bg": "bg_robotics.jpg", "color": "#ec4899"},
    "insight": {"name": "피트니스/건강상식", "bg": "bg_insight.jpg", "color": "#8b5cf6"}
}

# 브랜드 및 카드뉴스/쇼츠 규격
BRAND_NAME = "Team The PT"
BRAND_HANDLE = "@teamthept"
BRAND_TAGLINE = "물리치료사 기반 도수·재활 전문 헬스케어"

CARD_WIDTH = 1080
CARD_HEIGHT = 1350
SHORTS_WIDTH = 1080
SHORTS_HEIGHT = 1920

DEFAULT_TTS_VOICE = "ko-KR-SunHiNeural"
MALE_TTS_VOICE = "ko-KR-InJoonNeural"

FONT_CANDIDATES = [
    # Linux (Ubuntu GitHub Actions)
    "/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc",
    "/usr/share/fonts/truetype/nanum/NanumGothicBold.ttf",
    "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    # Windows
    "C:/Windows/Fonts/malgunbd.ttf",
    "C:/Windows/Fonts/malgun.ttf",
    "C:/Windows/Fonts/gulim.ttc"
]

FONT_PATH = None
for f in FONT_CANDIDATES:
    if os.path.exists(f):
        FONT_PATH = f
        break
