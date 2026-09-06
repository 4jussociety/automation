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
    "badge": "4THEPT CLINICAL",
    "title": "물리치료사 맞춤 임상 차팅 솔루션<br><span class=\"hl-yellow\">4THEPT</span>",
    "subtitle": "수작업 차팅 부담은 줄이고, 환자와 치료에 더 집중하세요.",
    "bullets": [
        "AI 기반 신속하고 정확한 물리치료 SOAP 차팅 지원",
        "표준화된 정밀 임상 평가 템플릿 및 환자 경과 관리",
        "지금 4thept.com 에서 무료로 체험해보세요"
    ],
    "cta_button": "4thept.com 바로가기 👆",
    "inquiry_text": "📢 광고 및 비즈니스 제휴 문의: thept.official@gmail.com",
    "narration": "물리치료사를 위한 가장 스마트한 임상 차팅 솔루션, 4THEPT! 복잡한 차팅은 줄이고 환자 치료에만 집중하세요. 지금 포더피티 닷컴에서 무료로 시작할 수 있습니다. 광고 및 제휴 문의도 언제든 환영합니다!",
    "link": "https://4thept.com"
}
