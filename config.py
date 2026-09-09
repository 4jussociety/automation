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

# 표준 템플릿 경로 (4:5 인스타그램 피드 & 9:16 유튜브 쇼츠)
TEMPLATE_4X5 = TEMPLATES_DIR / "card_4x5.html"
TEMPLATE_9X16 = TEMPLATES_DIR / "card_9x16_broadcast.html"
TEMPLATE_9X16_BROADCAST = TEMPLATE_9X16
LOGO_PATH = TEMPLATES_DIR / "logo_thept_transparent.png"
if not LOGO_PATH.exists():
    LOGO_PATH = TEMPLATES_DIR / "logo_thept.png"

BACKGROUNDS_DIR = ASSETS_DIR / "backgrounds"
DEFAULT_BG_PATH = BACKGROUNDS_DIR / "pt_clinic_bg.jpg"
AI_TECH_BG_PATH = BACKGROUNDS_DIR / "ai_rehab_bg.jpg"
OUTRO_IMG_PATH = ASSETS_DIR / "outro_thept_team.jpg"

# 이미지 및 비디오 규격
CARD_WIDTH = 1080
CARD_HEIGHT = 1350   # 4:5 인스타그램 피드 최적 해상도

VIDEO_WIDTH = 1080
VIDEO_HEIGHT = 1920  # 9:16 쇼츠/릴스 세로형 해상도

# TTS 음성 설정 (빠른 템포: 약 55초 이내 남녀 듀오 나레이션)
TTS_VOICE_FEMALE = "ko-KR-SunHiNeural"  # 여성 아나운서 톤 (오프닝, 뉴스2, 광고)
TTS_VOICE_MALE = "ko-KR-InJoonNeural"    # 남성 앵커 톤 (뉴스1, 뉴스3, 아웃트로)
TTS_VOICE = TTS_VOICE_FEMALE
TTS_RATE = "+20%"                       # 1분 미만(55초) 쇼츠에 최적화된 빠른 호흡 (+20%)
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
    "title": "병원 밖 독립을 위한 <span class=\"hl-yellow\">핵심 솔루션 2가지</span>",
    "sub_badge": "물리치료사 필수 솔루션",
    "categories": [
        {
            "num": "01",
            "name": "방문재활 AI 음성차팅",
            "tag": "4thept.com",
            "bullets": [
                "🎙️ 말로 하는 스마트 차팅: SOAP 및 라포 기록 자동화",
                "⏱️ 수기 행정 부담 경감, 환자 1인당 차팅 시간 60% 단축"
            ]
        },
        {
            "num": "02",
            "name": "소규모 가성비 센터창업 가이드",
            "subname": "- 병원밖 물리치료사",
            "tag": "크몽 전자책",
            "bullets": [
                "📖 병원 밖에서 자립하는 1인 센터 창업 실전 노하우 A to Z",
                "💡 입지 분석, 인테리어, 가성비 장비 세팅 및 마케팅 올인원"
            ]
        }
    ],
    "cta_text": "👉 두 서비스 모두 하단 고정 댓글 링크에서 지금 확인하세요!",
    "inquiry_text": "📢 4thept.com & 크몽(kmong.com/gig/813101) | 문의: teamthept@gmail.com",
    "narration": "방문재활 AI 음성차팅 4THEPT와 크몽 센터창업 가이드북, 지금 바로 하단 고정댓글에서 확인해보세요!",
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

