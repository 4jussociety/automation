# 이 모듈은 프로젝트 전역 경로 및 렌더링·콘텐츠 설정을 통합 관리합니다.
# 템플릿 위치, 출력 디렉토리, 폰트 및 TTS 기본 옵션을 제공합니다.

import os
from pathlib import Path
from dotenv import load_dotenv

# .env 파일이 존재하면 환경변수 로드
load_dotenv()

# 기본 디렉토리 경로
BASE_DIR = Path(__file__).resolve().parent
TEMPLATES_DIR = BASE_DIR / "templates"
OUTPUT_DIR = BASE_DIR / "output"
ASSETS_DIR = BASE_DIR / "assets"

# 템플릿, 로고 및 배경 파일 경로
TEMPLATE_4X5 = TEMPLATES_DIR / "card_4x5.html"
TEMPLATE_9X16 = TEMPLATES_DIR / "card_9x16.html"
LOGO_PATH = TEMPLATES_DIR / "logo_thept_transparent.png"
if not LOGO_PATH.exists():
    LOGO_PATH = TEMPLATES_DIR / "logo_thept.png"

BACKGROUNDS_DIR = ASSETS_DIR / "backgrounds"
DEFAULT_BG_PATH = BACKGROUNDS_DIR / "pt_clinic_bg.jpg"
AI_TECH_BG_PATH = BACKGROUNDS_DIR / "ai_rehab_bg.jpg"

# 이미지 및 비디오 규격
CARD_WIDTH = 1080
CARD_HEIGHT = 1350   # 4:5 인스타그램 피드 최적 해상도

VIDEO_WIDTH = 1080
VIDEO_HEIGHT = 1920  # 9:16 쇼츠/릴스 세로형 해상도

# TTS 음성 설정 (빠른 템포: 약 1분 이내 압축 나레이션)
TTS_VOICE = "ko-KR-SunHiNeural"  # 또는 "ko-KR-InJoonNeural"
TTS_RATE = "+22%"                # 1분 미만 쇼츠에 최적화된 빠른 호흡
TTS_VOLUME = "+0%"

# 네이버 API 설정 (환경변수 또는 None)
NAVER_CLIENT_ID = os.getenv("NAVER_CLIENT_ID", "")
NAVER_CLIENT_SECRET = os.getenv("NAVER_CLIENT_SECRET", "")

# OpenAI API 설정 (환경변수 또는 None)
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")

# 5번째 슬라이드: 광고/프로모션 페이지 기본 설정 (언제든 수정 가능)
DEFAULT_AD_CONFIG = {
    "badge": "THEPT SPONSOR",
    "title": "방문재활 물리치료사 맞춤<br><span class=\"hl-yellow\">AI음성 차팅</span>",
    "subtitle": "수작업 차팅 부담은 줄이고, 고객과의 소통에 더 집중하세요.",
    "bullets": [
        "AI음성분석 기반 SOAP차팅, 라포데이터 차팅 지원",
        "THEPT회원은 매월 무료5시간 사용가능!",
        "4thept.com 에서 무료로 체험해보세요!"
    ],
    "cta_button": "",
    "inquiry_text": "📢 광고 및 비즈니스 제휴 문의: teamthept@gmail.com",
    "narration": "방문재활 물리치료사를 위한 가장 스마트한 AI음성 차팅 솔루션, 수기차팅은 줄이고 환자 관리에만 집중하세요. 지금 4THEPT.com에서 무료로 시작할 수 있습니다. 광고 및 제휴 문의도 언제든 환영합니다!",
    "link": "https://4thept.com"
}

# SNS 자동 예약 업로드 설정
INSTAGRAM_ACCOUNT_ID = os.getenv("INSTAGRAM_ACCOUNT_ID", "")
INSTAGRAM_ACCESS_TOKEN = os.getenv("INSTAGRAM_ACCESS_TOKEN", "")

# YouTube Data API v3 OAuth 설정
YOUTUBE_CLIENT_SECRET_FILE = os.getenv("YOUTUBE_CLIENT_SECRET_FILE", str(BASE_DIR / "client_secret.json"))
YOUTUBE_TOKEN_FILE = BASE_DIR / "token.pickle"

# GitHub 원격 저장소 정보 (인스타그램 Graph API용 공개 Raw URL 생성에 활용)
GITHUB_REPO = os.getenv("GITHUB_REPO", "4jussociety/automation")
GITHUB_BRANCH = os.getenv("GITHUB_BRANCH", "main")

# SNS 발행 기본 시각 (오전 8시 KST)
PUBLISH_HOUR_KST = int(os.getenv("PUBLISH_HOUR_KST", "8"))

