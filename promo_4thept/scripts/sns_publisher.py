"""Publish 4THEPT card news & Shorts to the shared THEPT YouTube/Instagram accounts.

- Credentials (.env, client_secret.json, token.pickle) are unified at the
  automation root (c:\\개발\\자동화에이전트, overrideable via THEPT_SNS_CRED_DIR).
- Heavy promo assets stay local-only (.gitignore) in promo_4thept/; for Instagram
  Graph API publishing, finalized files are uploaded on demand to Supabase
  Storage public bucket `promo-media`.
"""

from __future__ import annotations

import argparse
import os
import pickle
import shutil
import sys
import time
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any
from urllib.parse import quote

import requests
from dotenv import dotenv_values
from google.auth.transport.requests import Request
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

PROMO_DIR = Path(__file__).resolve().parents[1]
AUTO_ROOT = PROMO_DIR.parent
if str(AUTO_ROOT) not in sys.path:
    sys.path.insert(0, str(AUTO_ROOT))
PROMO_OUT_DIR = AUTO_ROOT / "결과물" / "4THEPT마케팅"
SUPABASE_BUCKET = "promo-media"
DEFAULT_CRED_DIR = Path(os.getenv("THEPT_SNS_CRED_DIR", str(AUTO_ROOT)))
DEFAULT_GITHUB_REPO = "4jussociety/automation"
DEFAULT_GITHUB_BRANCH = "main"

KST = timezone(timedelta(hours=9))
GRAPH_API_VERSION = "v20.0"
YOUTUBE_SCOPES = [
    "https://www.googleapis.com/auth/youtube.upload",
    "https://www.googleapis.com/auth/youtube.force-ssl",
]
EXPECTED_YOUTUBE_CHANNEL_ID = "UCbwC2jK9J-179R2Un3T0xPA"
EXPECTED_YOUTUBE_CHANNEL_NAME = "THEPT"
DEFAULT_PLAYLIST_ID = "PLMJFgpIEDRBA"  # THEPT 채널 내 '4THEPT' 전용 재생목록 (뉴스 PLTEYR_IZibwI와 분리)


@dataclass(frozen=True)
class PromoPreset:
    key: str
    kind: str  # "carousel" | "video"
    label: str
    rel_files: tuple[str, ...]  # relative to PUBLIC_PROMO_DIR
    source_dir_map: tuple[tuple[str, str], ...]  # (src_rel_to_PROMO_DIR, dst_rel_to_PUBLIC_PROMO_DIR)
    youtube_title: str | None
    youtube_category_id: str
    tags: tuple[str, ...]
    caption: str
    first_comment: str


SHARED_FOOTER_COMPLIANCE = (
    "* AI 생성 결과는 기록 작성 보조 [초안]이며, 최종 진단·평가·처방은 담당 치료사가 [직접 검수] 후 사용합니다."
)

SHARED_CENTER_FOOTER_COMPLIANCE = (
    "* AI 생성 결과는 세션 기록 작성을 돕는 [초안]이며, 최종 상태 평가 및 운동 지도는 담당 전문가가 [직접 검수] 후 활용합니다."
)

SHARED_FIRST_COMMENT = (
    "[THEPT 물리치료사를 위한 공식 AI 차팅 안내]\n"
    "1) AI 차팅 무료 시작: https://www.4thept.com\n"
    "2) THEPT 회원 평생 월 300분 무료 혜택: 4thept.com 로그인 후 [구독 관리]에 THEPT ID를 입력하면 기본 월 120분에서 월 300분으로 즉시 업그레이드됩니다.\n"
    "3) THEPT 물리치료사 공식 커뮤니티: https://thept.co.kr\n"
    f"{SHARED_FOOTER_COMPLIANCE}"
)

SHARED_CENTER_FIRST_COMMENT = (
    "[4THEPT 무료 5초 체험 안내]\n"
    "로그인 없이 1줄 키워드 입력으로 5항목 세션기록지 초안 정리를 바로 테스트할 수 있습니다.\n"
    "- 무료 5초 체험: https://www.4thept.com/intro?utm_source=sns&utm_medium=comment&utm_campaign=center_intro\n\n"
    "- 별도 카드 등록 없이 기본 매월 120건(120분) 무료 (1건 = 1분 차감)\n"
    "- THEPT 회원은 구독 관리에서 THEPT ID 등록 시 평생 매월 300건(300분) 무료\n"
    "- 1인 PT샵부터 팀 센터까지 6자리 코드 하나로 스케줄·이용권·전자서명 공유\n"
    f"{SHARED_CENTER_FOOTER_COMPLIANCE}"
)


def _card_srcs(names: tuple[str, ...]) -> tuple[tuple[str, str], ...]:
    return tuple((f"cards/{n}", f"cards/{n}") for n in names)


PRESETS: dict[str, PromoPreset] = {
    "cheatsheet": PromoPreset(
        key="cheatsheet",
        kind="carousel",
        label="저장형 EMR 치트시트 카드뉴스 (5장)",
        rel_files=tuple(f"cards/card_cheatsheet_{i:02d}.png" for i in range(1, 6)),
        source_dir_map=_card_srcs(tuple(f"card_cheatsheet_{i:02d}.png" for i in range(1, 6))),
        youtube_title=None,
        youtube_category_id="27",
        tags=("물리치료사", "도수치료", "SOAP차트", "EMR차팅", "포더피티", "4THEPT"),
        caption=(
            "퇴근 전 차팅 시간 줄이는 부위별 물리치료 EMR 5단락 치트시트 (저장해 두고 바로 쓰세요)\n\n"
            "1. 진단평가 · 회차 / 시행시간\n"
            "2. 평가소견 (긴장도 · 제한 동작)\n"
            "3. 중재 및 세부 내용\n"
            "4. 중재 전·후 평가 (NRS 변화 + ROM 각도)\n"
            "5. 종합중재소견 및 자가운동 지도\n\n"
            "경추·어깨 도수, 회전근개·관절가동, 요추 통증, 발목·족부 재활 예시까지 한 번에 정리했습니다.\n"
            "매번 처음부터 문장 다듬기 번거롭다면, 프로필 링크(4thept.com/intro)에서 로그인 없이 1줄 키워드만 넣어 5초 만에 [초안]을 뽑아보세요.\n\n"
            "- 기본 매월 120건(120분) 무료 / THEPT 회원 월 300건 무료\n"
            f"{SHARED_FOOTER_COMPLIANCE}\n\n"
            "#물리치료사 #도수치료 #물리치료차팅 #EMR차팅 #치료기록지 #SOAP차트 #포더피티 #4THEPT #물리치료실 #임상팁"
        ),
        first_comment=SHARED_FIRST_COMMENT,
    ),
    "real_screen": PromoPreset(
        key="real_screen",
        kind="carousel",
        label="실사 구동 워크벤치 카드뉴스 (5장)",
        rel_files=tuple(f"cards/card_real_{i:02d}.png" for i in range(1, 6)),
        source_dir_map=_card_srcs(tuple(f"card_real_{i:02d}.png" for i in range(1, 6))),
        youtube_title=None,
        youtube_category_id="27",
        tags=("물리치료사", "도수치료", "EMR복붙", "포더피티", "4THEPT"),
        caption=(
            "오늘 도수 12명 뛰고, 차팅만 40분째 남아계신가요?\n\n"
            "가상 화면이 아닌 실제 4THEPT 구동 캡처로 확인하세요.\n"
            "1) 문장 대신 단어 몇 개만 1줄 키워드 창에 입력\n"
            "2) 경추·요추·어깨·발목 5단락 EMR [초안] 5초 생성\n"
            "3) 10초 직접 검수 후 [EMR 양식 복사] 버튼으로 바로 붙여넣기\n\n"
            "지금 https://www.4thept.com/intro 에서 로그인 없이 직접 키워드를 고쳐 써 볼 수 있습니다.\n"
            "- 별도 카드 등록 없이 매월 120건 무료 (THEPT 회원 평생 월 300건 무료)\n"
            f"{SHARED_FOOTER_COMPLIANCE}\n\n"
            "#물리치료사 #도수치료 #EMR차팅 #치료기록지 #물리치료실 #재활치료 #포더피티 #4THEPT #칼퇴"
        ),
        first_comment=SHARED_FIRST_COMMENT,
    ),
    "kakao": PromoPreset(
        key="kakao",
        kind="carousel",
        label="요약 포스터 카드뉴스 (3장)",
        rel_files=tuple(f"cards/card_kakao_{i:02d}.png" for i in range(1, 4)),
        source_dir_map=_card_srcs(tuple(f"card_kakao_{i:02d}.png" for i in range(1, 4))),
        youtube_title=None,
        youtube_category_id="27",
        tags=("물리치료사", "차팅꿀팁", "포더피티", "4THEPT"),
        caption=(
            "단어 5개만 적으면 5초 만에 병원 EMR 복붙용 치료기록지 [초안] 완성\n\n"
            "환자 12명 차팅, 40분 야근 vs 3분 검수·복붙!\n"
            "AI가 임의로 질환명을 지어내지 않고 치료사가 입력한 수치(NRS, ROM, 특수검사)만 5단락으로 정확히 정리합니다.\n\n"
            "지금 https://www.4thept.com/intro 에서 비로그인 5초 체험 가능\n"
            "- 매월 120건 무료 / THEPT 회원 월 300건 무료\n"
            f"{SHARED_FOOTER_COMPLIANCE}\n\n"
            "#물리치료사 #물리치료차팅 #도수치료 #치료기록지 #포더피티 #4THEPT"
        ),
        first_comment=SHARED_FIRST_COMMENT,
    ),
    "shorts_female": PromoPreset(
        key="shorts_female",
        kind="video",
        label="실사 UI 9:16 고속 쇼츠 · 릴스 (여성 내레이션 ~20초)",
        rel_files=("videos/shorts_charting_vertical_18s.mp4",),
        source_dir_map=(
            ("shorts_charting_vertical_18s.mp4", "videos/shorts_charting_vertical_18s.mp4"),
        ),
        youtube_title="도수 12명 보고 차팅 40분 남는 이유? 키워드 1줄 5초 정리 루틴 #Shorts",
        youtube_category_id="27",
        tags=("물리치료", "물리치료사", "도수치료", "EMR차팅", "치료기록지", "포더피티", "4THEPT", "THEPT", "Shorts"),
        caption=(
            "오늘 도수 12명 뛰고, 퇴근 전 차팅만 40분째 남아계신가요?\n\n"
            "바디차트 체크 + 단어 5개(ROM·NRS)만 남겨두면 5초 만에 표준 5단락 EMR [초안]으로 정리됩니다.\n"
            "- 로그인 없이 5초 무료 체험: https://www.4thept.com/intro?utm_source=yt&utm_medium=shorts&utm_campaign=series_b_hospital_charting\n"
            "- 기본 매월 120건(120분) 무료 · THEPT 회원 평생 월 300건(300분) 무료\n"
            f"{SHARED_FOOTER_COMPLIANCE}\n\n"
            "------------------------------------\n"
            "[THEPT 물리치료사를 위한 실무 플랫폼]\n"
            "- AI 치료·세션 차팅 및 스케줄 관리: https://www.4thept.com\n"
            "- 로그인 없는 5초 체험 안내: https://www.4thept.com/intro?utm_source=yt&utm_medium=shorts&utm_campaign=series_b_hospital_charting\n"
            "- THEPT 공식 커뮤니티: https://thept.co.kr\n"
            "- 문의: teamthept@gmail.com\n"
            "------------------------------------\n\n"
            "#물리치료사 #도수치료 #물리치료차팅 #EMR차팅 #치료기록지 #포더피티 #4THEPT #THEPT #Shorts"
        ),
        first_comment=SHARED_FIRST_COMMENT,
    ),
    "shorts_male": PromoPreset(
        key="shorts_male",
        kind="video",
        label="실사 UI 9:16 고속 쇼츠 · 릴스 (남성 내레이션 ~20초)",
        rel_files=("videos/shorts_charting_vertical_male.mp4",),
        source_dir_map=(
            ("shorts_charting_vertical_male.mp4", "videos/shorts_charting_vertical_male.mp4"),
        ),
        youtube_title="치료 끝나고 5초 메모로 병원 EMR 차팅 야근 끝내는 법 #Shorts",
        youtube_category_id="28",
        tags=("물리치료", "물리치료사", "도수치료", "AI차팅", "EMR", "포더피티", "4THEPT", "THEPT", "Shorts"),
        caption=(
            "발목·경추·요추·어깨 통증과 운동 키워드 1줄만 적어도 평가소견·중재·전후 NRS/ROM 비교까지 5가지 항목으로 정리됩니다.\n\n"
            "바디차트 4면 선택 후 직접 글자를 수정해 보고 병원 EMR에 바로 붙여넣어 보세요.\n"
            "- 로그인 없이 5초 무료 체험: https://www.4thept.com/intro?utm_source=yt&utm_medium=shorts&utm_campaign=series_b_hospital_male\n"
            "- 기본 매월 120건(120분) 무료 · THEPT 회원 평생 월 300건(300분) 무료\n"
            f"{SHARED_FOOTER_COMPLIANCE}\n\n"
            "------------------------------------\n"
            "[THEPT 물리치료사를 위한 실무 플랫폼]\n"
            "- AI 치료·세션 차팅 및 스케줄 관리: https://www.4thept.com\n"
            "- 로그인 없는 5초 체험 안내: https://www.4thept.com/intro?utm_source=yt&utm_medium=shorts&utm_campaign=series_b_hospital_male\n"
            "- THEPT 공식 커뮤니티: https://thept.co.kr\n"
            "- 문의: teamthept@gmail.com\n"
            "------------------------------------\n\n"
            "#물리치료사 #도수치료 #AI차팅 #EMR차팅 #치료기록지 #포더피티 #4THEPT #THEPT #Shorts"
        ),
        first_comment=SHARED_FIRST_COMMENT,
    ),
    "shorts_native": PromoPreset(
        key="shorts_native",
        kind="video",
        label="네이티브 고조회수 테스트본 9:16 쇼츠 · 릴스 (2초 컷 ~18초)",
        rel_files=("videos/shorts_native_viral_18s.mp4",),
        source_dir_map=(
            ("shorts_native_viral_18s.mp4", "videos/shorts_native_viral_18s.mp4"),
        ),
        youtube_title="도수 12명 끝나고 차팅 40분? 5초 만에 EMR [초안] 끝내는 법 #Shorts",
        youtube_category_id="28",
        tags=("물리치료", "물리치료사", "도수치료", "EMR차팅", "치료기록지", "포더피티", "4THEPT", "THEPT", "Shorts"),
        caption=(
            "도수 12명 끝나고 아직도 퇴근 전 차팅만 40분째 남아계신가요?\n\n"
            "바디차트 1번 터치 + 핵심 단어 5개만 1줄 남겨두면 5초 만에 표준 5단락 EMR [초안]이 정리됩니다.\n"
            "- 로그인 없이 5초 무료 체험: https://www.4thept.com/intro?utm_source=yt&utm_medium=shorts&utm_campaign=series_c_hospital_native\n"
            "- 기본 매월 120건(120분) 무료 · THEPT 회원 평생 월 300건(300분) 무료\n"
            f"{SHARED_FOOTER_COMPLIANCE}\n\n"
            "#물리치료사 #도수치료 #물리치료차팅 #EMR차팅 #치료기록지 #포더피티 #4THEPT #THEPT #Shorts"
        ),
        first_comment=SHARED_FIRST_COMMENT,
    ),
    "shorts_benchmark": PromoPreset(
        key="shorts_benchmark",
        kind="video",
        label="데이터 벤치마킹 실전본 9:16 쇼츠 · 릴스 (적색 콜아웃 · +34% 고속 ~18초)",
        rel_files=("videos/shorts_benchmark_hook_18s.mp4",),
        source_dir_map=(
            ("shorts_benchmark_hook_18s.mp4", "videos/shorts_benchmark_hook_18s.mp4"),
        ),
        youtube_title="도수치료 끝나고 차팅 순서 거꾸로 쓰고 계십니다 #Shorts",
        youtube_category_id="28",
        tags=("물리치료", "물리치료사", "도수치료", "EMR차팅", "치료기록지", "포더피티", "4THEPT", "THEPT", "Shorts"),
        caption=(
            "도수치료 끝나고 퇴근 전에 SOAP 차트 문장부터 다듬으시나요? 대부분 순서가 거꾸로입니다.\n\n"
            "치료 직후 4가지(부위 · ROM/특수검사 · 중재 · 전후 NRS) 단어 5개만 1줄 남겨두면 5초 만에 표준 5단락 EMR [초안]으로 정리됩니다.\n"
            "- 지금 저장해 두고 내일 바로 써보세요! 로그인 없이 5초 체험: https://www.4thept.com/intro?utm_source=yt&utm_medium=shorts&utm_campaign=series_b_hospital_soap_order\n"
            "- 기본 매월 120건(120분) 무료 · THEPT 회원 평생 월 300건(300분) 무료\n"
            f"{SHARED_FOOTER_COMPLIANCE}\n\n"
            "#물리치료사 #도수치료 #EMR차팅 #치료기록지 #물리치료차팅 #SOAP차트 #포더피티 #4THEPT #THEPT #Shorts"
        ),
        first_comment=SHARED_FIRST_COMMENT,
    ),
    "shorts_cinematic_v2": PromoPreset(
        key="shorts_cinematic_v2",
        kind="video",
        label="V2 시네마틱 실사 9:16 쇼츠 · 릴스 (THEPT 채널용 · 공식 로고 · 확대 UI)",
        rel_files=("videos/shorts_cinematic_v2_18s.mp4",),
        source_dir_map=(
            ("shorts_cinematic_v2_18s.mp4", "videos/shorts_cinematic_v2_18s.mp4"),
        ),
        youtube_title="도수치료 끝나고 밀린 차팅, 나만의 메모로 EMR 차트 쉽게 쓰는 법 #Shorts",
        youtube_category_id="28",
        tags=("물리치료", "물리치료사", "도수치료", "EMR차팅", "치료기록지", "포더피티", "4THEPT", "THEPT", "Shorts"),
        caption=(
            "치료 끝나고 밀린 차팅, 자세히 쓰자니 야근이고 대충 쓰자니 막막하셨죠?\n\n"
            "시행한 치료 테크닉과 환자 상태만 나만의 방식으로 간단히 적어도 병원 EMR에 바로 쓸 수 있는 자세한 차팅 [초안]으로 변환해 줍니다. 변환된 내용을 가볍게 검토한 뒤 복사 버튼만 누르세요.\n\n"
            "[THEPT 물리치료사를 위한 실무 플랫폼 혜택]\n"
            "1) AI 차팅 무료 시작: https://www.4thept.com/?utm_source=yt&utm_medium=shorts&utm_campaign=series_b_cinematic_v2\n"
            "2) THEPT 회원 평생 월 300분 무료: 4thept.com 로그인 후 [구독 관리]에 THEPT ID 등록 시 기본 월 120분에서 월 300분으로 업그레이드\n"
            "3) THEPT 공식 커뮤니티: https://thept.co.kr\n\n"
            f"{SHARED_FOOTER_COMPLIANCE}\n\n"
            "#물리치료사 #도수치료 #EMR차팅 #치료기록지 #물리치료차팅 #포더피티 #4THEPT #THEPT #Shorts"
        ),
        first_comment=SHARED_FIRST_COMMENT,
    ),
    "center_pack": PromoPreset(
        key="center_pack",
        kind="carousel",
        label="센터·트레이너 전용 4:5 저장형 카드뉴스 (5장)",
        rel_files=tuple(f"cards/card_center_{i:02d}.png" for i in range(1, 6)),
        source_dir_map=_card_srcs(tuple(f"card_center_{i:02d}.png" for i in range(1, 6))),
        youtube_title=None,
        youtube_category_id="27",
        tags=("헬스트레이너", "PT센터", "퍼스널트레이닝", "세션기록지", "포더피티", "4THEPT"),
        caption=(
            "운동·트레이닝·PT 센터 운영자 저장 필수: 이용권 기간 연기·양도 분쟁 막는 표준 기준 3가지\n\n"
            "1. 기간 연기: 당일 신청 허용 / 이용권 10회당 최대 2회 / 누적 최대 30일 이내\n"
            "2. 양도 기준: 자유 양도 + [명의변경 및 초기평가 수수료] (정상 1회권 상당) 명시\n"
            "3. 모바일·태블릿 전자서명 보관 + 수업 직후 키워드 1줄 5초 세션기록지 정리\n\n"
            "지금 https://www.4thept.com/intro?utm_source=ig&utm_medium=carousel&utm_campaign=series_a_center_holding_terms 에서 로그인 없이 5초 체험해 보세요.\n"
            "- 기본 매월 120건(120분) 무료 / THEPT 회원 월 300건 무료\n"
            f"{SHARED_CENTER_FOOTER_COMPLIANCE}\n\n"
            "#헬스트레이너 #PT센터운영 #퍼스널트레이닝 #운동센터 #세션기록지 #회원관리프로그램 #이용권관리 #전자서명동의서 #포더피티 #4THEPT"
        ),
        first_comment=SHARED_CENTER_FIRST_COMMENT,
    ),
    "shorts_center": PromoPreset(
        key="shorts_center",
        kind="video",
        label="센터·트레이너 전용 9:16 고속 쇼츠 · 릴스 (여성 내레이션 ~21초)",
        rel_files=("videos/shorts_center_mode_vertical.mp4",),
        source_dir_map=(
            ("shorts_center_mode_vertical.mp4", "videos/shorts_center_mode_vertical.mp4"),
        ),
        youtube_title="PT·트레이닝 센터 세션기록지 + 이용권 기간 연기 5초 정리 #Shorts",
        youtube_category_id="27",
        tags=("트레이너", "PT센터", "헬스트레이너", "세션기록지", "이용권관리", "포더피티", "4THEPT", "Shorts"),
        caption=(
            "수업 끝나고 카톡 일정, 엑셀 회차, 세션노트까지 아직 따로 정리하시나요?\n\n"
            "키워드 1줄 5초 세션기록지 초안부터 태블릿 전자서명 동의서, 이용권 기간 연기(10회당 2회·30일) 관리까지 한 화면에서 해결하세요.\n"
            "- 로그인 없는 5초 체험: https://www.4thept.com/intro?utm_source=sns&utm_medium=shorts&utm_campaign=series_b_center_ops\n"
            "- 기본 매월 120건(120분) 무료 · THEPT 회원 평생 월 300건(300분) 무료\n"
            f"{SHARED_CENTER_FOOTER_COMPLIANCE}\n\n"
            "#헬스트레이너 #PT센터운영 #퍼스널트레이닝 #세션기록지 #전자서명 #이용권관리 #포더피티 #4THEPT #Shorts"
        ),
        first_comment=SHARED_CENTER_FIRST_COMMENT,
    ),
}


@dataclass
class CredConfig:
    cred_dir: Path
    ig_account_id: str
    ig_access_token: str
    yt_client_secret: Path
    yt_token_file: Path
    yt_playlist_id: str
    supabase_url: str
    supabase_service_role_key: str
    github_repo: str = DEFAULT_GITHUB_REPO
    github_branch: str = DEFAULT_GITHUB_BRANCH


def load_credentials(cred_dir: Path) -> CredConfig:
    env_map: dict[str, str | None] = {}
    env_file = cred_dir / ".env"
    if env_file.exists():
        env_map = dotenv_values(env_file)

    def _get(key: str, default: str = "") -> str:
        return (os.getenv(key) or env_map.get(key) or default or "").strip()

    ig_id = _get("INSTAGRAM_ACCOUNT_ID")
    ig_token = _get("INSTAGRAM_ACCESS_TOKEN")
    playlist_id = _get("YOUTUBE_PROMO_PLAYLIST_ID", DEFAULT_PLAYLIST_ID)
    supabase_url = _get("SUPABASE_URL", "https://hcgrhgjobemtyvkexppi.supabase.co").rstrip("/")
    supabase_sr_key = _get("SUPABASE_SERVICE_ROLE_KEY")
    github_repo = _get("GITHUB_REPO", DEFAULT_GITHUB_REPO)
    github_branch = _get("GITHUB_BRANCH", DEFAULT_GITHUB_BRANCH)

    cs_raw = _get("YOUTUBE_CLIENT_SECRET_FILE", "client_secret.json")
    cs_path = Path(cs_raw)
    if not cs_path.is_absolute():
        cs_path = cred_dir / cs_path

    tk_path = cred_dir / "token.pickle"
    return CredConfig(
        cred_dir=cred_dir,
        ig_account_id=ig_id,
        ig_access_token=ig_token,
        yt_client_secret=cs_path,
        yt_token_file=tk_path,
        yt_playlist_id=playlist_id,
        supabase_url=supabase_url,
        supabase_service_role_key=supabase_sr_key,
        github_repo=github_repo,
        github_branch=github_branch,
    )


def resolve_local_asset(dst_rel: str, src_rel: str | None = None) -> Path:
    """결과물/4THEPT마케팅 하위 경로를 우선 탐색하고, 없으면 promo_4thept 내부 폴백 경로를 확인합니다."""
    out_candidate = PROMO_OUT_DIR / dst_rel
    if out_candidate.exists():
        return out_candidate
    if src_rel:
        fb = PROMO_DIR / src_rel
        if fb.exists():
            return fb
    return out_candidate


def resolve_public_base_url(creds: CredConfig, use_supabase: bool = False) -> str:
    override = os.getenv("THEPT_PROMO_PUBLIC_BASE_URL", "").strip().rstrip("/")
    if override:
        return override
    if use_supabase:
        return f"{creds.supabase_url}/storage/v1/object/public/{SUPABASE_BUCKET}"
    encoded_dir = quote("결과물/4THEPT마케팅", safe="/")
    return f"https://raw.githubusercontent.com/{creds.github_repo}/{creds.github_branch}/{encoded_dir}"


def sync_promo_media(
    creds: CredConfig,
    verbose: bool = True,
    presets_to_sync: list[PromoPreset] | None = None,
    use_supabase: bool = False,
    dry_run: bool = False,
) -> int:
    """Synchronize finalized promo cards/videos to GitHub (default) or Supabase Storage (--use-supabase)."""
    targets = presets_to_sync if presets_to_sync is not None else list(PRESETS.values())

    if not use_supabase:
        from modules.git_sync_manager import sync_promo_output_to_github

        target_files: list[Path] = []
        seen: set[Path] = set()
        for preset in targets:
            for src_rel, dst_rel in preset.source_dir_map:
                src = resolve_local_asset(dst_rel, src_rel)
                if not src.exists():
                    raise FileNotFoundError(f"Source promo asset missing: {src}")
                if src not in seen:
                    seen.add(src)
                    target_files.append(src)
        ok = sync_promo_output_to_github(target_paths=target_files if presets_to_sync else None, dry_run=dry_run)
        if not ok:
            raise RuntimeError("결과물/4THEPT마케팅 GitHub 동기화에 실패했습니다.")
        return len(target_files)

    if not creds.supabase_url or not creds.supabase_service_role_key:
        raise RuntimeError(
            "Supabase Storage 업로드를 위해 .env에 SUPABASE_URL 및 SUPABASE_SERVICE_ROLE_KEY가 필요합니다."
        )

    base_url = resolve_public_base_url(creds, use_supabase=True)
    uploaded = 0
    seen_dsts: set[str] = set()

    for preset in targets:
        for src_rel, dst_rel in preset.source_dir_map:
            if dst_rel in seen_dsts:
                continue
            seen_dsts.add(dst_rel)
            src = resolve_local_asset(dst_rel, src_rel)
            if not src.exists():
                raise FileNotFoundError(f"Source promo asset missing: {src}")

            local_size = src.stat().st_size
            public_url = f"{base_url}/{dst_rel}"
            try:
                head = requests.head(public_url, timeout=6, allow_redirects=True)
                if head.status_code == 200 and int(head.headers.get("Content-Length", -1)) == local_size:
                    continue
            except Exception:
                pass

            if dry_run:
                print(f"   [DRY-RUN] Supabase 업로드 예정: {dst_rel} ({local_size:,} bytes)")
                uploaded += 1
                continue

            ctype = "video/mp4" if dst_rel.lower().endswith(".mp4") else "image/png"
            upload_url = f"{creds.supabase_url}/storage/v1/object/{SUPABASE_BUCKET}/{dst_rel}"
            resp = requests.post(
                upload_url,
                headers={
                    "Authorization": f"Bearer {creds.supabase_service_role_key}",
                    "apikey": creds.supabase_service_role_key,
                    "x-upsert": "true",
                    "Content-Type": ctype,
                },
                data=src.read_bytes(),
                timeout=120,
            )
            if resp.status_code not in (200, 201):
                raise RuntimeError(f"Supabase Storage 업로드 실패 ({dst_rel}): HTTP {resp.status_code} {resp.text[:200]}")
            uploaded += 1
            if verbose:
                print(f"   Uploaded to {SUPABASE_BUCKET}: {dst_rel} ({local_size:,} bytes)")
    return uploaded


def parse_schedule_kst(raw: str | None) -> tuple[str | None, int | None, str]:
    """Parse 'YYYY-MM-DD HH:MM' (KST) into (rfc3339, unix_ts, display_label)."""
    if not raw:
        return None, None, "즉시 공개 (Immediate)"
    dt_naive = datetime.strptime(raw.strip(), "%Y-%m-%d %H:%M")
    dt_kst = dt_naive.replace(tzinfo=KST)
    now_kst = datetime.now(KST)
    delta_sec = (dt_kst - now_kst).total_seconds()
    if delta_sec < 1200:
        raise ValueError(
            f"예약 시각({dt_kst.isoformat()})이 너무 가깝거나 과거입니다. "
            "Instagram 예약 발행을 위해 현재 기준 최소 20분 이후로 지정해 주세요."
        )
    if delta_sec > 75 * 86400:
        raise ValueError("예약 시각은 최대 75일 이내만 지원됩니다.")
    return dt_kst.isoformat(), int(dt_kst.timestamp()), dt_kst.strftime("%Y-%m-%d %H:%M KST")


def verify_public_urls(urls: list[str]) -> tuple[bool, list[tuple[str, str]]]:
    results: list[tuple[str, str]] = []
    all_ok = True
    for url in urls:
        try:
            resp = requests.head(url, timeout=8, allow_redirects=True)
            ctype = resp.headers.get("Content-Type", "").lower()
            is_png = url.lower().endswith(".png")
            is_mp4 = url.lower().endswith(".mp4")
            if resp.status_code == 200:
                if is_png and not ctype.startswith("image/"):
                    all_ok = False
                    results.append((url, f"200이지만 Content-Type={ctype or 'unknown'} (미배포/SPA fallback)"))
                elif is_mp4 and ("text/html" in ctype or not (ctype.startswith("video/") or "octet-stream" in ctype)):
                    all_ok = False
                    results.append((url, f"200이지만 Content-Type={ctype or 'unknown'} (미배포/SPA fallback)"))
                else:
                    results.append((url, f"200 OK ({ctype.split(';')[0]})"))
            else:
                all_ok = False
                results.append((url, f"HTTP {resp.status_code}"))
        except Exception as exc:
            all_ok = False
            results.append((url, f"ERR ({type(exc).__name__})"))
    return all_ok, results


class InstagramPublisher:
    def __init__(self, account_id: str, access_token: str) -> None:
        self.account_id = account_id
        self.access_token = access_token
        if access_token.startswith("IG"):
            self.api_base = f"https://graph.instagram.com/{GRAPH_API_VERSION}"
        else:
            self.api_base = f"https://graph.facebook.com/{GRAPH_API_VERSION}"

    def is_configured(self) -> bool:
        return bool(self.account_id and self.access_token)

    def check_connection(self) -> dict[str, Any]:
        if not self.is_configured():
            return {"success": False, "error": "INSTAGRAM_ACCOUNT_ID 또는 INSTAGRAM_ACCESS_TOKEN 미설정"}
        try:
            res = requests.get(
                f"{self.api_base}/{self.account_id}",
                params={"fields": "id,username,name", "access_token": self.access_token},
                timeout=10,
            )
            data = res.json()
            if "error" in data:
                return {"success": False, "error": data["error"].get("message", "API 오류")}
            return {
                "success": True,
                "account_id": data.get("id"),
                "username": data.get("username"),
                "name": data.get("name"),
            }
        except Exception as exc:
            return {"success": False, "error": str(exc)}

    def _wait_container(self, container_id: str, max_checks: int, label: str) -> None:
        for _ in range(max_checks):
            time.sleep(5)
            s_res = requests.get(
                f"{self.api_base}/{container_id}",
                params={"fields": "status_code", "access_token": self.access_token},
                timeout=10,
            ).json()
            code = s_res.get("status_code")
            if code == "FINISHED":
                return
            if code == "ERROR":
                raise RuntimeError(f"Instagram {label} 처리 오류: {s_res}")
        raise TimeoutError(f"Instagram {label} 처리 시간 초과")

    def _add_comment(self, media_id: str, text: str) -> str | None:
        res = requests.post(
            f"{self.api_base}/{media_id}/comments",
            data={"message": text, "access_token": self.access_token},
            timeout=15,
        ).json()
        return res.get("id")

    def publish_carousel(
        self,
        image_urls: list[str],
        caption: str,
        schedule_ts: int | None,
        first_comment: str | None,
    ) -> dict[str, Any]:
        item_ids: list[str] = []
        for idx, url in enumerate(image_urls, 1):
            r = requests.post(
                f"{self.api_base}/{self.account_id}/media",
                data={"image_url": url, "is_carousel_item": "true", "access_token": self.access_token},
                timeout=20,
            ).json()
            if "id" not in r:
                raise RuntimeError(f"캐러셀 슬라이드 {idx} 실패: {r.get('error', r)}")
            item_ids.append(r["id"])
            print(f"   - 슬라이드 {idx}/{len(image_urls)} 컨테이너 완료 ({r['id']})")

        payload: dict[str, str] = {
            "media_type": "CAROUSEL",
            "children": ",".join(item_ids),
            "caption": caption,
            "access_token": self.access_token,
        }
        if schedule_ts:
            payload["published"] = "false"
            payload["scheduled_publish_time"] = str(schedule_ts)

        c_res = requests.post(f"{self.api_base}/{self.account_id}/media", data=payload, timeout=20).json()
        if "id" not in c_res:
            raise RuntimeError(f"캐러셀 부모 컨테이너 실패: {c_res.get('error', c_res)}")

        container_id = c_res["id"]
        self._wait_container(container_id, max_checks=12, label="캐러셀")

        pub = requests.post(
            f"{self.api_base}/{self.account_id}/media_publish",
            data={"creation_id": container_id, "access_token": self.access_token},
            timeout=20,
        ).json()
        if "id" not in pub:
            raise RuntimeError(f"캐러셀 최종 발행 실패: {pub.get('error', pub)}")

        post_id = pub["id"]
        comment_id = None
        if first_comment and not schedule_ts:
            comment_id = self._add_comment(post_id, first_comment)
        return {"post_id": post_id, "comment_id": comment_id, "scheduled": bool(schedule_ts)}

    def publish_reel(
        self,
        video_url: str,
        caption: str,
        schedule_ts: int | None,
        first_comment: str | None,
    ) -> dict[str, Any]:
        payload: dict[str, str] = {
            "media_type": "REELS",
            "video_url": video_url,
            "caption": caption,
            "share_to_feed": "true",
            "access_token": self.access_token,
        }
        if schedule_ts:
            payload["published"] = "false"
            payload["scheduled_publish_time"] = str(schedule_ts)

        r_res = requests.post(f"{self.api_base}/{self.account_id}/media", data=payload, timeout=25).json()
        if "id" not in r_res:
            raise RuntimeError(f"릴스 컨테이너 생성 실패: {r_res.get('error', r_res)}")

        container_id = r_res["id"]
        print("   - Meta 서버에서 릴스 인코딩 처리 대기 중...")
        self._wait_container(container_id, max_checks=36, label="릴스")

        pub = requests.post(
            f"{self.api_base}/{self.account_id}/media_publish",
            data={"creation_id": container_id, "access_token": self.access_token},
            timeout=20,
        ).json()
        if "id" not in pub:
            raise RuntimeError(f"릴스 최종 발행 실패: {pub.get('error', pub)}")

        reels_id = pub["id"]
        comment_id = None
        if first_comment and not schedule_ts:
            comment_id = self._add_comment(reels_id, first_comment)
        return {"reels_id": reels_id, "comment_id": comment_id, "scheduled": bool(schedule_ts)}


class YouTubePublisher:
    def __init__(self, client_secret: Path, token_file: Path) -> None:
        self.client_secret = client_secret
        self.token_file = token_file
        self._service = None

    def get_service(self, allow_interactive: bool = False, force_reauth: bool = False):
        if self._service and not force_reauth:
            return self._service

        creds = None
        if force_reauth:
            self._service = None
            if self.token_file.exists():
                backup_path = self.token_file.with_suffix(".pickle.prev")
                shutil.copy2(self.token_file, backup_path)
                print(f"[YouTube] 기존 토큰 백업 완료: {backup_path}")
        elif self.token_file.exists():
            with open(self.token_file, "rb") as f:
                creds = pickle.load(f)

        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token and not force_reauth:
                try:
                    creds.refresh(Request())
                    with open(self.token_file, "wb") as f:
                        pickle.dump(creds, f)
                except Exception:
                    if not allow_interactive:
                        raise
                    creds = None
            if (not creds or not creds.valid) and allow_interactive:
                if not self.client_secret.exists():
                    raise FileNotFoundError(f"OAuth client_secret 파일 없음: {self.client_secret}")
                flow = InstalledAppFlow.from_client_secrets_file(str(self.client_secret), scopes=YOUTUBE_SCOPES)
                creds = flow.run_local_server(port=0, prompt="consent")
                with open(self.token_file, "wb") as f:
                    pickle.dump(creds, f)
            elif not creds or not creds.valid:
                raise RuntimeError(
                    "YouTube OAuth 토큰이 유효하지 않습니다. "
                    "`py scripts/sns_publisher.py --auth-yt` 명령으로 브라우저 재인증을 진행하세요."
                )

        self._service = build("youtube", "v3", credentials=creds)
        return self._service

    def check_connection(self) -> dict[str, Any]:
        try:
            service = self.get_service(allow_interactive=False)
            res = service.channels().list(part="snippet", mine=True).execute()
            items = res.get("items", [])
            if not items:
                return {"success": False, "error": "인증된 채널 정보를 찾을 수 없습니다."}
            ch = items[0]
            ch_id = ch["id"]
            return {
                "success": True,
                "channel_id": ch_id,
                "title": ch["snippet"]["title"],
                "handle": ch["snippet"].get("customUrl", ""),
                "matched_expected": (not EXPECTED_YOUTUBE_CHANNEL_ID) or (ch_id == EXPECTED_YOUTUBE_CHANNEL_ID),
            }
        except Exception as exc:
            return {"success": False, "error": str(exc)}

    def publish_short(
        self,
        video_path: Path,
        title: str,
        description: str,
        tags: list[str],
        category_id: str,
        playlist_id: str | None,
        publish_at_rfc3339: str | None,
        first_comment: str | None,
    ) -> dict[str, Any]:
        service = self.get_service(allow_interactive=False)
        clean_title = title.strip()
        if "#Shorts" not in clean_title and "#shorts" not in clean_title:
            clean_title = f"{clean_title[:85]} #Shorts"

        status_body: dict[str, Any]
        if publish_at_rfc3339:
            status_body = {
                "privacyStatus": "private",
                "publishAt": publish_at_rfc3339,
                "selfDeclaredMadeForKids": False,
            }
        else:
            status_body = {
                "privacyStatus": "public",
                "selfDeclaredMadeForKids": False,
            }

        clean_description = description.replace("->", "에서").replace("<", "(").replace(">", ")")
        body = {
            "snippet": {
                "title": clean_title,
                "description": clean_description,
                "tags": tags,
                "categoryId": category_id,
            },
            "status": status_body,
        }

        media = MediaFileUpload(str(video_path), mimetype="video/mp4", resumable=True, chunksize=5 * 1024 * 1024)
        request = service.videos().insert(part="snippet,status", body=body, media_body=media)
        response = None
        while response is None:
            status, response = request.next_chunk()
            if status:
                print(f"   - YouTube 업로드 진행률: {int(status.progress() * 100)}%")

        video_id = response["id"]
        comment_id = None
        if first_comment:
            try:
                c_res = (
                    service.commentThreads()
                    .insert(
                        part="snippet",
                        body={
                            "snippet": {
                                "videoId": video_id,
                                "topLevelComment": {"snippet": {"textOriginal": first_comment}},
                            }
                        },
                    )
                    .execute()
                )
                comment_id = c_res.get("id")
            except Exception as exc:
                print(f"   [경고] YouTube 첫 댓글 등록 실패: {exc}")

        playlist_item_id = None
        if playlist_id and playlist_id.lower() != "none":
            try:
                p_res = (
                    service.playlistItems()
                    .insert(
                        part="snippet",
                        body={
                            "snippet": {
                                "playlistId": playlist_id,
                                "resourceId": {"kind": "youtube#video", "videoId": video_id},
                            }
                        },
                    )
                    .execute()
                )
                playlist_item_id = p_res.get("id")
            except Exception as exc:
                print(f"   [경고] YouTube 재생목록 추가 실패: {exc}")

        return {
            "video_id": video_id,
            "video_url": f"https://youtube.com/shorts/{video_id}",
            "comment_id": comment_id,
            "playlist_item_id": playlist_item_id,
        }


def run_check(creds: CredConfig) -> int:
    print("=" * 68)
    print("[4THEPT SNS 연동 상태 진단]")
    print(f"인증 참조 폴더: {creds.cred_dir}")
    print(f"유튜브 기본 재생목록: {creds.yt_playlist_id or '미지정'}")
    print(f"인스타 공개 URL 베이스: {resolve_public_base_url(creds)}")
    print("=" * 68)

    ig = InstagramPublisher(creds.ig_account_id, creds.ig_access_token)
    ig_res = ig.check_connection()
    if ig_res.get("success"):
        print(f"[Instagram] OK -> @{ig_res.get('username')} (ID: {ig_res.get('account_id')})")
    else:
        print(f"[Instagram] FAIL -> {ig_res.get('error')}")

    yt = YouTubePublisher(creds.yt_client_secret, creds.yt_token_file)
    yt_res = yt.check_connection()
    if yt_res.get("success"):
        print(f"[YouTube]   OK -> {yt_res.get('title')} ({yt_res.get('handle') or yt_res.get('channel_id')})")
        if not yt_res.get("matched_expected", True):
            print(
                f"   ⚠️ [채널 불일치] 목표 채널은 '{EXPECTED_YOUTUBE_CHANNEL_NAME}' ({EXPECTED_YOUTUBE_CHANNEL_ID})입니다. "
                "'py scripts/sns_publisher.py --auth-yt'로 THEPT 채널을 선택해 재인증하세요."
            )
    else:
        print(f"[YouTube]   FAIL -> {yt_res.get('error')}")

    return 0 if (ig_res.get("success") and yt_res.get("success")) else 1


def main() -> int:
    parser = argparse.ArgumentParser(description="4THEPT 카드뉴스/쇼츠 SNS 발행 CLI (기존 THEPT 계정 연동)")
    parser.add_argument("--preset", choices=sorted(PRESETS.keys()), help="발행할 4THEPT 에셋 프리셋")
    parser.add_argument("--platform", choices=["all", "youtube", "instagram"], default="all", help="대상 플랫폼")
    parser.add_argument("--schedule", type=str, default=None, help="예약 발행 시각 KST ('YYYY-MM-DD HH:MM', 미지정 시 즉시 공개)")
    parser.add_argument("--playlist-id", type=str, default=None, help="YouTube 재생목록 ID ('none' 입력 시 미지정)")
    parser.add_argument("--no-first-comment", action="store_true", help="첫 댓글 자동 등록 건너뛰기")
    parser.add_argument("--cred-dir", type=Path, default=DEFAULT_CRED_DIR, help="인증 파일 폴더 (기본: 자동화에이전트 루트)")
    parser.add_argument("--sync-promo-media", action="store_true", help="결과물/4THEPT마케팅 에셋을 GitHub(기본) 또는 Supabase Storage로 동기화")
    parser.add_argument("--use-supabase", action="store_true", default=False, help="GitHub Raw URL 대신 Supabase Storage(promo-media) 사용")
    parser.add_argument("--check", action="store_true", help="YouTube/Instagram 계정 연결 상태만 확인")
    parser.add_argument("--auth-yt", action="store_true", help="YouTube OAuth 브라우저 재인증 실행")
    parser.add_argument("--dry-run", action="store_true", help="실제 API 호출 없이 시뮬레이션만 실행 (기본값)")
    parser.add_argument("--publish", action="store_true", help="실제 YouTube/Instagram API로 발행 실행")
    args = parser.parse_args()

    creds = load_credentials(args.cred_dir)

    if args.sync_promo_media:
        mode_lbl = f"Supabase Storage ({SUPABASE_BUCKET})" if args.use_supabase else f"GitHub ({creds.github_repo})"
        print(f"[미디어 동기화] 결과물/4THEPT마케팅 -> {mode_lbl}")
        n = sync_promo_media(creds, verbose=True, use_supabase=args.use_supabase, dry_run=bool(args.dry_run))
        print(f"동기화 완료: {n}개 파일 대상")
        if not args.check and not args.preset and not args.auth_yt:
            return 0

    if args.auth_yt:
        yt = YouTubePublisher(creds.yt_client_secret, creds.yt_token_file)
        yt.get_service(allow_interactive=True, force_reauth=True)
        return run_check(creds)

    if args.check:
        return run_check(creds)

    if not args.preset:
        parser.print_help()
        print("\n사용 가능 프리셋:")
        for k, v in PRESETS.items():
            print(f"  - {k:14s}: {v.label} ({v.kind})")
        return 0

    preset = PRESETS[args.preset]
    publish_mode = bool(args.publish) and not bool(args.dry_run)

    rfc3339, unix_ts, sched_label = parse_schedule_kst(args.schedule)
    playlist_id = args.playlist_id if args.playlist_id is not None else creds.yt_playlist_id
    first_comment = None if args.no_first_comment else preset.first_comment

    local_paths = [resolve_local_asset(dst_rel, src_rel) for src_rel, dst_rel in preset.source_dir_map]
    for p in local_paths:
        if not p.exists():
            raise FileNotFoundError(f"대상 파일 없음: {p}")
    public_base_url = resolve_public_base_url(creds, use_supabase=args.use_supabase)
    public_urls = [f"{public_base_url}/{rel}" for rel in preset.rel_files]

    print("=" * 68)
    print(f"[모드] {'실제 발행 (--publish)' if publish_mode else '시뮬레이션 (DRY-RUN)'}")
    print(f"[프리셋] {preset.key} - {preset.label} ({preset.kind})")
    print(f"[플랫폼] {args.platform.upper()} | [발행 일정] {sched_label}")
    print("=" * 68)

    will_run_yt = args.platform in ("all", "youtube")
    will_run_ig = args.platform in ("all", "instagram")

    if will_run_yt:
        if preset.kind != "video":
            print("[YouTube] 캐러셀 이미지는 YouTube Shorts 대상이 아니므로 건너뜁니다.")
        else:
            print(f"\n[YouTube Shorts 준비]")
            print(f"  - 파일: {local_paths[0]}")
            print(f"  - 제목: {preset.youtube_title}")
            print(f"  - 카테고리 ID: {preset.youtube_category_id} | 재생목록: {playlist_id or '미지정'}")
            print(f"  - 첫 댓글 포함: {'예' if first_comment else '아니오'}")
            if publish_mode:
                yt = YouTubePublisher(creds.yt_client_secret, creds.yt_token_file)
                yt_out = yt.publish_short(
                    video_path=local_paths[0],
                    title=preset.youtube_title or preset.label,
                    description=preset.caption,
                    tags=list(preset.tags),
                    category_id=preset.youtube_category_id,
                    playlist_id=playlist_id,
                    publish_at_rfc3339=rfc3339,
                    first_comment=first_comment,
                )
                print(f"[YouTube 발행 완료] {yt_out['video_url']} (ID: {yt_out['video_id']}, Comment ID: {yt_out.get('comment_id')})")

    if will_run_ig:
        print(f"\n[Instagram 준비] ({'릴스' if preset.kind == 'video' else f'캐러셀 {len(public_urls)}장'})")
        sync_promo_media(
            creds,
            verbose=True,
            presets_to_sync=[preset],
            use_supabase=args.use_supabase,
            dry_run=not publish_mode,
        )
        urls_ok, url_statuses = verify_public_urls(public_urls)
        for u, st in url_statuses:
            print(f"  - {u} -> {st}")
        if not publish_mode:
            if not urls_ok:
                if args.use_supabase:
                    print("  [안내] Supabase Storage(promo-media) 공개 URL 검증에 실패했습니다. .env의 SUPABASE_SERVICE_ROLE_KEY를 확인하세요.")
                else:
                    print("  [안내] 아직 GitHub 원격 저장소에 푸시되지 않은 신규/이관 파일입니다. `--publish` 또는 `python curate.py sync` 시 자동 푸시되어 200 OK로 전환됩니다.")
        else:
            if not urls_ok:
                raise RuntimeError(
                    "Instagram API는 Meta 서버가 접근 가능한 200 OK 공개 URL이 필요합니다. "
                    "GitHub 동기화(`python curate.py sync`) 또는 Supabase Storage 상태를 확인해 주세요."
                )
            ig = InstagramPublisher(creds.ig_account_id, creds.ig_access_token)
            if preset.kind == "carousel":
                ig_out = ig.publish_carousel(
                    image_urls=public_urls,
                    caption=preset.caption,
                    schedule_ts=unix_ts,
                    first_comment=first_comment,
                )
                print(f"[Instagram 캐러셀 완료] Post ID: {ig_out['post_id']}")
            else:
                ig_out = ig.publish_reel(
                    video_url=public_urls[0],
                    caption=preset.caption,
                    schedule_ts=unix_ts,
                    first_comment=first_comment,
                )
                print(f"[Instagram 릴스 완료] Reels ID: {ig_out['reels_id']} (Comment ID: {ig_out.get('comment_id')})")

    if not publish_mode:
        print("\n[DRY-RUN 완료] 실제 업로드하려면 --publish 옵션을 추가해 실행하세요.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
