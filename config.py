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
    "badge": "THEPT RECOMMENDED",
    "title": "물리치료사 맞춤<br><span class=\"hl-yellow\">AI차팅 & 센터창업 전자책</span>",
    "subtitle": "차팅 부담은 줄이고, 독립 센터 창업 노하우를 한 번에!",
    "bullets": [
        "방문재활 AI 음성 차팅: SOAP·라포 차팅 자동화 (4thept.com)",
        "크몽 전자책: 『병원밖 물리치료사 - 가성비 소규모 센터창업 가이드』",
        "독립·방문재활 물리치료사를 위한 실전 솔루션 패키지!"
    ],
    "cta_button": "",
    "inquiry_text": "📢 4thept.com & 크몽(kmong.com/gig/813101) | 문의: teamthept@gmail.com",
    "narration": "물리치료사를 위한 스마트 솔루션! 수기 차팅을 줄여주는 방문재활 AI 음성 차팅 4THEPT와, 크몽 전자책 병원밖 물리치료사 가성비 소규모 센터창업 가이드를 지금 바로 확인해보세요. 상세 링크는 설명란과 첫 댓글에서 확인하실 수 있습니다.",
    "link": "https://4thept.com",
    "kmong_link": "https://kmong.com/gig/813101"
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

# 금요일: 운동/재활 추천 유튜브 채널 설정 파일 경로
YOUTUBE_CHANNELS_FILE = BASE_DIR / "data" / "youtube_channels.json"

# 기본 추천 유튜브 채널 목록 (언제든 data/youtube_channels.json 파일에서 채널 추가/삭제 가능)
DEFAULT_YOUTUBE_CHANNELS = [
    {"name": "피지컬갤러리", "query": "피지컬갤러리", "enabled": True},
    {"name": "라이프에이드", "query": "라이프에이드", "enabled": True},
    {"name": "자세요정", "query": "자세요정", "enabled": True},
    {"name": "핏블리", "query": "핏블리 재활", "enabled": True},
    {"name": "물리치료사 이과장", "query": "물리치료사 이과장", "enabled": True},
    {"name": "문교석 교수", "query": "문교석 물리치료", "enabled": True}
]

