"""Render 9:16 (1080x1920, 30fps) high-retention 80/20 Shorts & Reels promos via Edge TTS + PIL + FFmpeg.

Upgraded Stage 2 engine:
- ~20-23s fast-cut pacing (+24% TTS rate) tailored for YouTube Shorts & Instagram Reels completion rate
- 0-2s non-advertising empathy/pain hook before introducing 4THEPT solution (80/20 formula)
- Synchronized high-contrast bottom caption pills + animated typing cursor & click-pulse overlays
- Synthesized UI click & chime SFX mixed cleanly with soft ambient electric-piano BGM
- Dual-track variants: female/male hospital PT + dedicated non-medical center/Trainer variant
"""

from __future__ import annotations

import argparse
import asyncio
import math
import os
import struct
import subprocess
import tempfile
import wave
from dataclasses import dataclass
from pathlib import Path

import edge_tts
from PIL import Image, ImageDraw, ImageFilter, ImageFont

PROMO_DIR = Path(__file__).resolve().parents[1]
AUTO_ROOT = PROMO_DIR.parent
VIDEOS_DIR = AUTO_ROOT / "결과물" / "4THEPT마케팅" / "videos"
VIDEOS_DIR.mkdir(parents=True, exist_ok=True)
REAL_ASSETS = PROMO_DIR / "real_assets"

WIDTH = 1080
HEIGHT = 1920
FPS = 30

FONT_CANDIDATES_BOLD = (
    Path("C:/Windows/Fonts/Pretendard-ExtraBold.ttf"),
    Path(os.environ.get("LOCALAPPDATA", "")) / "Microsoft/Windows/Fonts/Pretendard-ExtraBold.ttf",
    Path("C:/Windows/Fonts/Pretendard-Bold.ttf"),
    Path(os.environ.get("LOCALAPPDATA", "")) / "Microsoft/Windows/Fonts/Pretendard-Bold.ttf",
    Path("C:/Windows/Fonts/malgunbd.ttf"),
)
FONT_CANDIDATES_REG = (
    Path("C:/Windows/Fonts/Pretendard-SemiBold.ttf"),
    Path("C:/Windows/Fonts/Pretendard-Medium.ttf"),
    Path(os.environ.get("LOCALAPPDATA", "")) / "Microsoft/Windows/Fonts/Pretendard-Medium.ttf",
    Path("C:/Windows/Fonts/malgun.ttf"),
)


@dataclass(frozen=True)
class SceneSpec:
    eyebrow: str
    headline_lines: tuple[str, ...]
    sub_text: str
    pills: tuple[str, ...]
    theme: str  # "dark" | "light" | "blue"
    shot_a: str
    shot_b: str | None
    crop_norm: tuple[float, float, float, float]
    zoom_end: float
    badge_text: str
    loupe_badge: str
    loupe_line1: str
    loupe_line2: str
    narration: str
    subtitle_chunks: tuple[tuple[str, str], ...]  # (line_text, highlight_token)
    overlay_mode: str  # "hook" | "typing" | "copy_pulse" | "cta"
    compliance_track: str  # "hospital" | "center"


HOSPITAL_SCENES: list[SceneSpec] = [
    SceneSpec(
        eyebrow="퇴근 전 현실 공감 · 물리치료실",
        headline_lines=("도수 12명 보고 나면", "차팅만 40분 남죠"),
        sub_text="기억 더듬으며 타이핑하느라 퇴근이 밀립니다",
        pills=("도수 12명 연속", "차팅 야근", "기억 혼합"),
        theme="dark",
        shot_a="shot_2_workbench_foot.png",
        shot_b=None,
        crop_norm=(0.018, 0.105, 0.495, 0.76),
        zoom_end=1.06,
        badge_text="치료 직후 5초 메모가 퇴근 시간을 바꿉니다",
        loupe_badge="2배 확대 · 1줄 키워드",
        loupe_line1="오른쪽 발 통증, 발꿈치들기 운동",
        loupe_line2="plantar flexion 30도 · NRS 5->2",
        narration="오늘 도수 열두 명 뛰고, 퇴근 전 차팅만 사십 분째 남아계신가요?",
        subtitle_chunks=(
            ("도수 12명 연속 보고 나면", "12명 연속"),
            ("차팅만 40분째 야근...", "40분째 야근"),
        ),
        overlay_mode="hook",
        compliance_track="hospital",
    ),
    SceneSpec(
        eyebrow="310구역 4면 바디차트 + 1줄 입력",
        headline_lines=("문장 쓰지 말고", "단어 5개만 남기세요"),
        sub_text="부위 터치 + 핵심 수치(ROM·NRS) 1줄이면 충분합니다",
        pills=("rt sh flex 120", "Neer (+)", "NRS 5->3"),
        theme="light",
        shot_a="shot_3_workbench_shoulder.png",
        shot_b=None,
        crop_norm=(0.018, 0.105, 0.495, 0.76),
        zoom_end=1.05,
        badge_text="바디차트 체크 + 키워드 1줄 직접 입력",
        loupe_badge="2배 확대 · 310 바디차트",
        loupe_line1="rt sh flex 120도 제한, Neer (+)",
        loupe_line2="단어 5개 남기면 준비 끝",
        narration="비결은 간단합니다. 바디차트 체크하고 단어 다섯 개만 남기세요.",
        subtitle_chunks=(
            ("문장 대신 바디차트 터치 +", "바디차트 터치"),
            ("핵심 단어 5개만 남기세요", "단어 5개"),
        ),
        overlay_mode="typing",
        compliance_track="hospital",
    ),
    SceneSpec(
        eyebrow="5초 구조화 · EMR 원클릭 복사",
        headline_lines=("5초 만에 5단락 초안", "검수 후 바로 복사"),
        sub_text="진단평가 · 평가소견 · 중재 · 전후비교 · 종합소견 정렬",
        pills=("5단락 구조화", "10초 직접 검수", "EMR 양식 복사"),
        theme="light",
        shot_a="shot_3_workbench_shoulder.png",
        shot_b="shot_4_workbench_copied.png",
        crop_norm=(0.502, 0.088, 0.982, 0.88),
        zoom_end=1.04,
        badge_text="10초 검수 -> [EMR 양식 복사] 완료",
        loupe_badge="2배 확대 · EMR 복사",
        loupe_line1="1. 진단평가 · 2. 평가소견 · 3. 중재",
        loupe_line2="10초 직접 검수 후 [EMR 양식 복사]",
        narration="한 줄만 치면 오 초 만에 표준 오단락 초안 완성. 그대로 복사하면 끝입니다.",
        subtitle_chunks=(
            ("5초 만에 EMR 5단락 초안 완성", "5초 만에"),
            ("검수 후 [EMR 양식 복사] 끝!", "EMR 양식 복사"),
        ),
        overlay_mode="copy_pulse",
        compliance_track="hospital",
    ),
    SceneSpec(
        eyebrow="로그인 없이 5초 테스트 · 4THEPT",
        headline_lines=("월 120건 기본 무료", "5초 만에 체험하세요"),
        sub_text="THEPT 회원 월 300건 무료 · 4thept.com/intro",
        pills=("기본 월 120건", "THEPT 월 300건", "비로그인 5초 체험"),
        theme="blue",
        shot_a="shot_6_benefit_section.png",
        shot_b="__benefit_stack__",
        crop_norm=(0.0, 0.0, 1.0, 1.0),
        zoom_end=1.03,
        badge_text="고정 댓글 링크에서 지금 5초 테스트",
        loupe_badge="2배 확대 · 무료 체험 혜택",
        loupe_line1="기본 월 120건 · THEPT 월 300건 무료",
        loupe_line2="고정 댓글 링크에서 로그인 없이 5초",
        narration="매월 백이십 건 무료. 고정 댓글 링크에서 로그인 없이 바로 체험해 보세요.",
        subtitle_chunks=(
            ("기본 월 120건 · THEPT 300건 무료", "월 120건 무료"),
            ("링크에서 로그인 없이 5초 체험!", "로그인 없이 5초"),
        ),
        overlay_mode="cta",
        compliance_track="hospital",
    ),
]


CENTER_SCENES: list[SceneSpec] = [
    SceneSpec(
        eyebrow="운동·트레이닝·PT 센터 운영 고민",
        headline_lines=("수업 후 카톡 · 엑셀", "세션노트 따로 쓰세요?"),
        sub_text="고객 회차 확인에 기간 연기 문의까지 매번 수기 대조",
        pills=("일정 파편화", "회차 확인 번거로움", "기간 연기 문의"),
        theme="dark",
        shot_a="shot_2_workbench_foot.png",
        shot_b=None,
        crop_norm=(0.018, 0.105, 0.495, 0.76),
        zoom_end=1.06,
        badge_text="센터 운영·세션기록지 올인원 정리",
        loupe_badge="2배 확대 · 1줄 키워드",
        loupe_line1="부위 터치 + 핵심 수치 1줄 입력",
        loupe_line2="예) 우측 발목 가동성 제한 · NRS 5->2",
        narration="수업 끝나고 카톡 일정, 엑셀 회차, 세션노트까지 따로 정리하시나요?",
        subtitle_chunks=(
            ("카톡 일정 · 엑셀 이용권 확인에", "엑셀 이용권"),
            ("세션기록지까지 따로 적고 계신가요?", "따로 적고"),
        ),
        overlay_mode="hook",
        compliance_track="center",
    ),
    SceneSpec(
        eyebrow="STEP 01 · 310구역 바디차트 + 키워드 1줄",
        headline_lines=("수업 직후 1줄 메모면", "5초 세션기록지 완성"),
        sub_text="코어 안정화 · 가동성 변화 · 맞춤 운동 지도까지 정리",
        pills=("세션기록지 5초", "바디차트 연동", "전문가 검수"),
        theme="light",
        shot_a="shot_2_workbench_foot.png",
        shot_b=None,
        crop_norm=(0.018, 0.105, 0.495, 0.76),
        zoom_end=1.05,
        badge_text="센터 내부 모드 · 바디차트 + 키워드 입력",
        loupe_badge="2배 확대 · 5초 세션기록",
        loupe_line1="수업 직후 짧은 메모 1줄이면 끝",
        loupe_line2="5단락 표준 세션기록지 [초안] 완성",
        narration="직후 키워드 한 줄이면 오 초 만에 고객 세션기록지 초안이 정리됩니다.",
        subtitle_chunks=(
            ("수업 직후 키워드 1줄만 남기면", "키워드 1줄"),
            ("5초 만에 세션기록지 초안 완성!", "세션기록지"),
        ),
        overlay_mode="typing",
        compliance_track="center",
    ),
    SceneSpec(
        eyebrow="STEP 02 · 전자서명 · 이용권 기간 연기",
        headline_lines=("태블릿 전자서명부터", "기간 연기까지 한 번에"),
        sub_text="10회당 2회·30일 기준 약관과 양도 수수료까지 내장",
        pills=("태블릿 전자서명", "기간 연기 관리", "6자리 팀 공유"),
        theme="light",
        shot_a="shot_6_benefit_section.png",
        shot_b=None,
        crop_norm=(0.01, 0.0, 0.535, 1.0),
        zoom_end=1.04,
        badge_text="센터·트레이너 내부 모드 자동 정렬",
        loupe_badge="2배 확대 · 약관 · 팀 공유",
        loupe_line1="태블릿 전자서명 · 이용권 기간 연기",
        loupe_line2="10회당 2회 · 6자리 팀 공유 지원",
        narration="태블릿 전자서명 동의서부터 이용권 기간 연기까지 한 화면에서 관리하세요.",
        subtitle_chunks=(
            ("종이 대신 태블릿 전자서명 보관", "전자서명"),
            ("이용권 기간 연기·양도 한 화면 관리", "이용권 기간 연기"),
        ),
        overlay_mode="copy_pulse",
        compliance_track="center",
    ),
    SceneSpec(
        eyebrow="트레이너 · PT 센터 · 월 120건 무료",
        headline_lines=("로그인 없이 5초 체험", "지금 바로 열어보세요"),
        sub_text="기본 월 120건 · THEPT 회원 월 300건 (4thept.com/intro)",
        pills=("센터 내부 모드", "월 120건 무료", "카드 등록 없음"),
        theme="blue",
        shot_a="shot_6_benefit_section.png",
        shot_b=None,
        crop_norm=(0.01, 0.0, 0.535, 1.0),
        zoom_end=1.04,
        badge_text="프로필·고정댓글 링크에서 5초 무료 체험",
        loupe_badge="2배 확대 · 지금 무료 체험",
        loupe_line1="카드 등록 없이 매월 120건 기본 무료",
        loupe_line2="프로필·고정댓글 링크에서 5초 체험",
        narration="매월 백이십 건 무료. 포더피티 인트로에서 로그인 없이 바로 체험해 보세요.",
        subtitle_chunks=(
            ("카드 등록 없이 월 120건 무료", "월 120건 무료"),
            ("내부 설정으로 센터 용어 전환!", "센터 용어"),
        ),
        overlay_mode="cta",
        compliance_track="center",
    ),
]


@dataclass(frozen=True)
class NativeCutSpec:
    mode: str  # "dark_hook" | "full_ui" | "dark_cta"
    shot: str
    crop_norm: tuple[float, float, float, float]
    hero_lines: tuple[str, ...]
    hero_hl: str
    cta_url: str
    flash_in: bool
    sfx_mode: str  # "pop" | "typing" | "copy_pulse" | "cta"
    narration: str
    subtitle_chunks: tuple[tuple[str, str], ...]


NATIVE_VIRAL_SCENES: list[NativeCutSpec] = [
    NativeCutSpec(
        mode="dark_hook",
        shot="shot_3_output_zoom.png",
        crop_norm=(0.0, 0.0, 1.0, 1.0),
        hero_lines=("도수 12명 끝나고", "차팅만 40분?"),
        hero_hl="40분?",
        cta_url="",
        flash_in=False,
        sfx_mode="pop",
        narration="도수 열두 명 끝나고, 차팅만 사십 분 남죠?",
        subtitle_chunks=(
            ("도수 12명 끝나고", "12명"),
            ("차팅만 40분 야근?", "40분 야근?"),
        ),
    ),
    NativeCutSpec(
        mode="full_ui",
        shot="shot_2_input_zoom.png",
        crop_norm=(0.0, 0.0, 1.0, 0.56),
        hero_lines=(),
        hero_hl="",
        cta_url="",
        flash_in=False,
        sfx_mode="pop",
        narration="문장 쓰지 말고, 바디차트 딱 한 번 터치.",
        subtitle_chunks=(
            ("문장 쓰지 마세요", "쓰지 마세요"),
            ("바디차트 1번 터치", "1번 터치"),
        ),
    ),
    NativeCutSpec(
        mode="full_ui",
        shot="shot_3_workbench_shoulder.png",
        crop_norm=(0.02, 0.36, 0.495, 0.72),
        hero_lines=(),
        hero_hl="",
        cta_url="",
        flash_in=False,
        sfx_mode="typing",
        narration="핵심 단어 다섯 개만 한 줄 적으면 끝.",
        subtitle_chunks=(
            ("단어 5개만", "단어 5개"),
            ("1줄 적으면 끝!", "1줄"),
        ),
    ),
    NativeCutSpec(
        mode="full_ui",
        shot="shot_3_output_zoom.png",
        crop_norm=(0.0, 0.0, 1.0, 0.62),
        hero_lines=(),
        hero_hl="",
        cta_url="",
        flash_in=True,
        sfx_mode="pop",
        narration="딱 오 초 만에 표준 오단락 초안 완성.",
        subtitle_chunks=(
            ("딱 5초 만에", "5초 만에"),
            ("5단락 초안 완성!", "5단락 초안"),
        ),
    ),
    NativeCutSpec(
        mode="full_ui",
        shot="shot_3_output_zoom.png",
        crop_norm=(0.0, 0.54, 1.0, 0.99),
        hero_lines=(),
        hero_hl="",
        cta_url="",
        flash_in=False,
        sfx_mode="pop",
        narration="전후 수치랑 중재까지 알아서 싹 정렬.",
        subtitle_chunks=(
            ("NRS 전후 비교", "NRS 전후"),
            ("자동으로 싹 정렬", "싹 정렬"),
        ),
    ),
    NativeCutSpec(
        mode="full_ui",
        shot="shot_4_copied_zoom.png",
        crop_norm=(0.0, 0.0, 1.0, 0.52),
        hero_lines=(),
        hero_hl="",
        cta_url="",
        flash_in=False,
        sfx_mode="copy_pulse",
        narration="십 초 검수하고 복사 버튼 누르면 칼퇴.",
        subtitle_chunks=(
            ("10초 직접 검수 후", "직접 검수"),
            ("[EMR 복사] 칼퇴!", "EMR 복사"),
        ),
    ),
    NativeCutSpec(
        mode="full_ui",
        shot="shot_6_benefit_section.png",
        crop_norm=(0.0, 0.0, 0.555, 1.0),
        hero_lines=(),
        hero_hl="",
        cta_url="",
        flash_in=False,
        sfx_mode="pop",
        narration="기본 월 백이십 건, 더피티는 삼백 건 무료.",
        subtitle_chunks=(
            ("기본 월 120건 무료", "120건 무료"),
            ("THEPT 월 300건!", "월 300건!"),
        ),
    ),
    NativeCutSpec(
        mode="dark_cta",
        shot="shot_4_copied_zoom.png",
        crop_norm=(0.0, 0.0, 1.0, 1.0),
        hero_lines=("고정댓글 링크", "로그인 없이 5초"),
        hero_hl="5초",
        cta_url="4thept.com/intro",
        flash_in=False,
        sfx_mode="cta",
        narration="고정 댓글 링크에서 로그인 없이 바로 써보세요.",
        subtitle_chunks=(
            ("로그인 없이 바로", "로그인 없이"),
            ("고정댓글 5초 체험!", "5초 체험!"),
        ),
    ),
]


VARIANTS = [
    {
        "id": "female",
        "renderer": "card",
        "voice": "ko-KR-SunHiNeural",
        "rate": "+24%",
        "scenes": HOSPITAL_SCENES,
        "out_mp4": VIDEOS_DIR / "shorts_charting_vertical_18s.mp4",
    },
    {
        "id": "male",
        "renderer": "card",
        "voice": "ko-KR-InJoonNeural",
        "rate": "+24%",
        "scenes": HOSPITAL_SCENES,
        "out_mp4": VIDEOS_DIR / "shorts_charting_vertical_male.mp4",
    },
    {
        "id": "center_female",
        "renderer": "card",
        "voice": "ko-KR-SunHiNeural",
        "rate": "+24%",
        "scenes": CENTER_SCENES,
        "out_mp4": VIDEOS_DIR / "shorts_center_mode_vertical.mp4",
    },
    {
        "id": "native_viral",
        "renderer": "native",
        "voice": "ko-KR-SunHiNeural",
        "rate": "+28%",
        "scenes": NATIVE_VIRAL_SCENES,
        "out_mp4": VIDEOS_DIR / "shorts_native_viral_18s.mp4",
    },
    {
        "id": "benchmark_hook",
        "renderer": "benchmark",
        "voice": "ko-KR-SunHiNeural",
        "rate": "+34%",
        "scenes": (),  # bound dynamically via BENCHMARK_HOOK_SCENES below
        "out_mp4": VIDEOS_DIR / "shorts_benchmark_hook_18s.mp4",
    },
]


@dataclass(frozen=True)
class BenchmarkCutSpec:
    cut_kind: str  # "compare_hook" | "checklist_4" | "ui_callout"
    shot: str
    crop_norm: tuple[float, float, float, float]
    callout_label: str
    callout_box: tuple[float, float, float, float] | None  # (cx_norm, cy_norm, rx_norm, ry_norm)
    callout_badge_pos: tuple[float, float]  # (cx_norm, cy_norm)
    flash_in: bool
    sfx_mode: str  # "pop" | "typing" | "copy_pulse" | "cta"
    narration: str
    subtitle_chunks: tuple[tuple[str, str], ...]


BENCHMARK_HOOK_SCENES: list[BenchmarkCutSpec] = [
    BenchmarkCutSpec(
        cut_kind="compare_hook",
        shot="shot_2_input_zoom.png",
        crop_norm=(0.0, 0.0, 1.0, 1.0),
        callout_label="",
        callout_box=None,
        callout_badge_pos=(0.5, 0.5),
        flash_in=False,
        sfx_mode="pop",
        narration="도수치료 끝나고 퇴근 전 문장부터 쓰시나요? 순서가 거꾸로입니다.",
        subtitle_chunks=(
            ("문장부터 쓰면", "문장부터"),
            ("순서 거꾸로!", "거꾸로!"),
        ),
    ),
    BenchmarkCutSpec(
        cut_kind="checklist_4",
        shot="shot_2_input_zoom.png",
        crop_norm=(0.0, 0.0, 1.0, 1.0),
        callout_label="",
        callout_box=None,
        callout_badge_pos=(0.5, 0.5),
        flash_in=False,
        sfx_mode="pop",
        narration="치료 직후 딱 네 가지만 남기세요. 부위, 각도, 중재, 통증 수치.",
        subtitle_chunks=(
            ("딱 4개만 남기면", "4개만"),
            ("기억 안 까먹음", "안 까먹음"),
        ),
    ),
    BenchmarkCutSpec(
        cut_kind="ui_callout",
        shot="shot_2_input_zoom.png",
        crop_norm=(0.0, 0.0, 1.0, 0.86),
        callout_label="바디차트 + 단어 5개",
        callout_box=(0.27, 0.145, 0.18, 0.055),
        callout_badge_pos=(0.71, 0.145),
        flash_in=False,
        sfx_mode="typing",
        narration="바디차트 한 번 찍고 단어 다섯 개만 한 줄 적으면 준비 끝.",
        subtitle_chunks=(
            ("바디차트 1터치", "1터치"),
            ("단어 5개만!", "5개만!"),
        ),
    ),
    BenchmarkCutSpec(
        cut_kind="ui_callout",
        shot="shot_3_output_zoom.png",
        crop_norm=(0.0, 0.0, 1.0, 0.72),
        callout_label="5초 5단락 정렬",
        callout_box=(0.28, 0.275, 0.21, 0.048),
        callout_badge_pos=(0.73, 0.275),
        flash_in=True,
        sfx_mode="pop",
        narration="딱 오 초 만에 병원 표준 오단락 초안으로 자동 정렬됩니다.",
        subtitle_chunks=(
            ("딱 5초 만에", "5초 만에"),
            ("5단락 자동 정렬!", "자동 정렬!"),
        ),
    ),
    BenchmarkCutSpec(
        cut_kind="ui_callout",
        shot="shot_4_copied_zoom.png",
        crop_norm=(0.0, 0.0, 1.0, 0.56),
        callout_label="검수 후 1클릭 복사",
        callout_box=(0.83, 0.11, 0.145, 0.065),
        callout_badge_pos=(0.74, 0.34),
        flash_in=False,
        sfx_mode="copy_pulse",
        narration="십 초 직접 검수하고 복사 버튼 누르면 그대로 칼퇴.",
        subtitle_chunks=(
            ("10초 직접 검수", "직접 검수"),
            ("[복사] 누르면 끝", "[복사]"),
        ),
    ),
    BenchmarkCutSpec(
        cut_kind="ui_callout",
        shot="shot_6_benefit_section.png",
        crop_norm=(0.0, 0.0, 0.555, 1.0),
        callout_label="지금 저장 · 고정댓글 5초 체험",
        callout_box=(0.38, 0.81, 0.125, 0.09),
        callout_badge_pos=(0.50, 0.96),
        flash_in=False,
        sfx_mode="cta",
        narration="지금 저장해 두세요. 월 백이십 건 무료, 고정 댓글에서 바로 체험해 보세요.",
        subtitle_chunks=(
            ("지금 저장 필수!", "저장 필수!"),
            ("고정댓글 5초 체험", "5초 체험"),
        ),
    ),
]


def _resolve_font_path(bold: bool) -> Path:
    candidates = FONT_CANDIDATES_BOLD if bold else FONT_CANDIDATES_REG
    for cand in candidates:
        if str(cand) and cand.exists():
            return cand
    return Path("C:/Windows/Fonts/malgun.ttf")


def load_font(size: int, bold: bool = True) -> ImageFont.FreeTypeFont:
    return ImageFont.truetype(str(_resolve_font_path(bold)), size=size)


def fit_single_line_font(
    draw: ImageDraw.ImageDraw, text: str, max_width: int, start_size: int, min_size: int = 18, bold: bool = True
) -> ImageFont.FreeTypeFont:
    size = start_size
    while size > min_size:
        font = load_font(size, bold=bold)
        if draw.textlength(text, font=font) <= max_width:
            return font
        size -= 2
    return load_font(min_size, bold=bold)


def probe_duration(media_path: Path) -> float:
    out = subprocess.check_output(
        [
            "ffprobe",
            "-v",
            "error",
            "-show_entries",
            "format=duration",
            "-of",
            "default=noprint_wrappers=1:nokey=1",
            str(media_path),
        ],
        text=True,
    ).strip()
    return float(out)


async def synth_tts_all(
    scenes: list, voice: str, rate: str, out_dir: Path, trim_silence: bool = False
) -> list[tuple[Path, float]]:
    results: list[tuple[Path, float]] = []
    for idx, scene in enumerate(scenes):
        raw_path = out_dir / f"tts_raw_{idx:02d}.mp3"
        mp3_path = out_dir / f"tts_{idx:02d}.mp3"
        target = raw_path if trim_silence else mp3_path
        comm = edge_tts.Communicate(scene.narration, voice=voice, rate=rate)
        await comm.save(str(target))
        if trim_silence:
            subprocess.run(
                [
                    "ffmpeg",
                    "-y",
                    "-i",
                    str(raw_path),
                    "-af",
                    (
                        "silenceremove=start_periods=1:start_silence=0.02:start_threshold=-45dB,"
                        "areverse,"
                        "silenceremove=start_periods=1:start_silence=0.03:start_threshold=-45dB,"
                        "areverse"
                    ),
                    str(mp3_path),
                ],
                check=True,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
        dur = probe_duration(mp3_path)
        results.append((mp3_path, dur))
    return results


def generate_ambient_bgm(wav_path: Path, total_duration: float, sample_rate: int = 44100) -> None:
    """Synthesize clean rhythmic electric-piano chord progression."""
    chords = [
        (261.63, 329.63, 392.00, 493.88, 587.33),  # Cmaj9
        (220.00, 261.63, 329.63, 392.00, 493.88),  # Am9
        (174.61, 220.00, 261.63, 329.63, 349.23),  # Fmaj7
        (196.00, 246.94, 293.66, 329.63, 392.00),  # G6
    ]
    chord_dur = 2.0
    n_samples = int((total_duration + 0.8) * sample_rate)
    buf = bytearray(n_samples * 2)

    for i in range(n_samples):
        t = i / sample_rate
        chord_idx = int(t / chord_dur) % len(chords)
        local_t = t % chord_dur

        if local_t < 0.10:
            env = local_t / 0.10
        elif local_t > chord_dur - 0.25:
            env = max(0.0, (chord_dur - local_t) / 0.25)
        else:
            env = 0.86 + 0.14 * math.exp(-(local_t - 0.10) * 1.6)

        freqs = chords[chord_idx]
        val = 0.0
        for fi, f in enumerate(freqs):
            w = 0.24 if fi == 0 else (0.19 if fi < 3 else 0.14)
            val += w * math.sin(2.0 * math.pi * f * t + fi * 0.4)
            val += (w * 0.15) * math.sin(4.0 * math.pi * f * t)

        pulse = 0.88 + 0.12 * math.sin(2.0 * math.pi * 2.2 * t)
        fade_in = min(1.0, t / 0.25)
        fade_out = 1.0 if t < total_duration - 0.8 else max(0.0, (total_duration - t) / 0.8)
        sample = int(max(-32767, min(32767, val * env * pulse * fade_in * fade_out * 5000)))
        struct.pack_into("<h", buf, i * 2, sample)

    with wave.open(str(wav_path), "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)
        wf.writeframes(buf)


def generate_ui_sfx_wav(
    wav_path: Path,
    scenes: list[SceneSpec],
    scene_start_sec: list[float],
    scene_frames: list[int],
    total_duration: float,
    sample_rate: int = 44100,
) -> None:
    """Synthesize crisp UI whoosh/click/chime SFX aligned to scene transitions & actions."""
    n_samples = int((total_duration + 0.8) * sample_rate)
    acc = [0.0] * n_samples

    def add_blip(t_start: float, freq0: float, freq1: float, dur: float, amp: float) -> None:
        i0 = max(0, int(t_start * sample_rate))
        n = int(dur * sample_rate)
        for k in range(n):
            idx = i0 + k
            if idx >= n_samples:
                break
            lt = k / sample_rate
            progress = k / max(1, n - 1)
            freq = freq0 + (freq1 - freq0) * progress
            env = math.sin(math.pi * progress) * math.exp(-lt * 16.0)
            acc[idx] += amp * env * math.sin(2.0 * math.pi * freq * lt)

    for idx, (scene, start_s, nf) in enumerate(zip(scenes, scene_start_sec, scene_frames)):
        scene_dur = nf / FPS
        if idx > 0:
            # Subtle crisp scene cut pop
            add_blip(start_s, 620.0, 960.0, 0.08, 0.35)
        mode = getattr(scene, "sfx_mode", getattr(scene, "overlay_mode", ""))
        if mode == "typing":
            t0 = start_s + min(scene_dur * 0.22, 0.45)
            step_dt = 0.16 if scene_dur < 2.6 else 0.22
            for step in range(4):
                add_blip(t0 + step * step_dt, 1100.0 + step * 80.0, 1450.0, 0.045, 0.22)
        elif mode == "copy_pulse":
            click_t = start_s + scene_dur * (0.35 if scene_dur < 2.6 else 0.45)
            add_blip(click_t, 880.0, 1320.0, 0.09, 0.38)
            add_blip(click_t + 0.09, 1318.5, 1760.0, 0.18, 0.32)
        elif mode == "cta":
            add_blip(start_s + min(0.24, scene_dur * 0.15), 1046.5, 1567.98, 0.22, 0.28)

    buf = bytearray(n_samples * 2)
    for i, s in enumerate(acc):
        val = int(max(-32767, min(32767, s * 22000)))
        struct.pack_into("<h", buf, i * 2, val)

    with wave.open(str(wav_path), "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)
        wf.writeframes(buf)


def theme_colors(theme: str) -> dict[str, tuple[int, ...]]:
    if theme == "dark":
        return {
            "bg": (15, 23, 42),
            "eyebrow_bg": (37, 99, 235),
            "eyebrow_fg": (255, 255, 255),
            "headline": (248, 250, 252),
            "sub": (148, 163, 184),
            "pill_bg": (30, 41, 59),
            "pill_border": (51, 65, 85),
            "pill_fg": (226, 232, 240),
            "card_bg": (255, 255, 255),
            "card_border": (59, 130, 246),
            "badge_bg": (37, 99, 235),
            "badge_fg": (255, 255, 255),
            "caption_bg": (30, 41, 59),
            "caption_fg": (248, 250, 252),
            "caption_hl": (96, 165, 250),
            "notice_bg": (30, 41, 59),
            "notice_fg": (203, 213, 225),
            "progress_track": (30, 41, 59),
            "progress_fill": (59, 130, 246),
        }
    if theme == "blue":
        return {
            "bg": (29, 78, 216),
            "eyebrow_bg": (255, 255, 255),
            "eyebrow_fg": (29, 78, 216),
            "headline": (255, 255, 255),
            "sub": (219, 234, 254),
            "pill_bg": (30, 64, 175),
            "pill_border": (96, 165, 250),
            "pill_fg": (255, 255, 255),
            "card_bg": (255, 255, 255),
            "card_border": (191, 219, 254),
            "badge_bg": (15, 23, 42),
            "badge_fg": (255, 255, 255),
            "caption_bg": (15, 23, 42),
            "caption_fg": (255, 255, 255),
            "caption_hl": (250, 204, 21),
            "notice_bg": (23, 37, 84),
            "notice_fg": (219, 234, 254),
            "progress_track": (30, 64, 175),
            "progress_fill": (255, 255, 255),
        }
    return {
        "bg": (248, 250, 252),
        "eyebrow_bg": (219, 234, 254),
        "eyebrow_fg": (29, 78, 216),
        "headline": (15, 23, 42),
        "sub": (71, 85, 105),
        "pill_bg": (255, 255, 255),
        "pill_border": (203, 213, 225),
        "pill_fg": (15, 23, 42),
        "card_bg": (255, 255, 255),
        "card_border": (203, 213, 225),
        "badge_bg": (15, 23, 42),
        "badge_fg": (255, 255, 255),
        "caption_bg": (15, 23, 42),
        "caption_fg": (248, 250, 252),
        "caption_hl": (96, 165, 250),
        "notice_bg": (241, 245, 249),
        "notice_fg": (71, 85, 105),
        "progress_track": (226, 232, 240),
        "progress_fill": (37, 99, 235),
    }


def ease_in_out(t: float) -> float:
    t = max(0.0, min(1.0, t))
    return t * t * (3.0 - 2.0 * t)


def build_static_chrome(
    scene: SceneSpec, scene_idx: int, total_scenes: int
) -> tuple[Image.Image, tuple[int, int, int, int]]:
    """Build static top header, showcase frame, and safe-zone compliance box."""
    c = theme_colors(scene.theme)
    canvas = Image.new("RGB", (WIDTH, HEIGHT), c["bg"])
    draw = ImageDraw.Draw(canvas)

    f_eyebrow = load_font(34, bold=True)
    f_pill = load_font(30, bold=True)
    f_badge = load_font(30, bold=True)
    f_brand = load_font(30, bold=True)

    draw.text((56, 56), "4THEPT  |  포더피티", font=f_brand, fill=c["sub"])
    step_label = f"{scene_idx + 1:02d} / {total_scenes:02d}"
    sw = draw.textlength(step_label, font=f_brand)
    draw.text((WIDTH - 56 - sw, 56), step_label, font=f_brand, fill=c["sub"])

    ey_text = scene.eyebrow
    ey_bbox = draw.textbbox((0, 0), ey_text, font=f_eyebrow)
    ey_w = (ey_bbox[2] - ey_bbox[0]) + 48
    ey_h = 60
    ey_x, ey_y = 56, 114
    draw.rounded_rectangle([ey_x, ey_y, ey_x + ey_w, ey_y + ey_h], radius=30, fill=c["eyebrow_bg"])
    draw.text((ey_x + 24, ey_y + 10), ey_text, font=f_eyebrow, fill=c["eyebrow_fg"])

    max_text_w = WIDTH - 112
    y_cursor = 192
    for line in scene.headline_lines:
        f_line = fit_single_line_font(draw, line, max_text_w, 78, min_size=52, bold=True)
        draw.text((56, y_cursor), line, font=f_line, fill=c["headline"])
        y_cursor += 92

    f_sub_fit = fit_single_line_font(draw, scene.sub_text, max_text_w, 36, min_size=26, bold=True)
    draw.text((56, 382), scene.sub_text, font=f_sub_fit, fill=c["sub"])

    px = 56
    py_row = 442
    for p_text in scene.pills:
        pw = int(draw.textlength(p_text, font=f_pill)) + 36
        if px + pw > WIDTH - 56:
            break
        draw.rounded_rectangle(
            [px, py_row, px + pw, py_row + 54],
            radius=16,
            fill=c["pill_bg"],
            outline=c["pill_border"],
            width=2,
        )
        draw.text((px + 18, py_row + 9), p_text, font=f_pill, fill=c["pill_fg"])
        px += pw + 12

    box_x1, box_y1 = 56, 516
    box_x2, box_y2 = WIDTH - 56, 1360
    shadow = Image.new("RGBA", (WIDTH, HEIGHT), (0, 0, 0, 0))
    s_draw = ImageDraw.Draw(shadow)
    s_draw.rounded_rectangle([box_x1, box_y1 + 12, box_x2, box_y2 + 12], radius=34, fill=(2, 6, 23, 75))
    shadow = shadow.filter(ImageFilter.GaussianBlur(18))
    canvas_rgba = canvas.convert("RGBA")
    canvas_rgba.alpha_composite(shadow)
    canvas = canvas_rgba.convert("RGB")
    draw = ImageDraw.Draw(canvas)

    draw.rounded_rectangle(
        [box_x1, box_y1, box_x2, box_y2],
        radius=32,
        fill=c["card_bg"],
        outline=c["card_border"],
        width=3,
    )

    badge_fit = fit_single_line_font(draw, scene.badge_text, (box_x2 - box_x1) - 88, 30, min_size=22, bold=True)
    badge_w = int(draw.textlength(scene.badge_text, font=badge_fit)) + 40
    draw.rounded_rectangle(
        [box_x1 + 26, box_y1 + 18, min(box_x2 - 26, box_x1 + 26 + badge_w), box_y1 + 70],
        radius=14,
        fill=c["badge_bg"],
    )
    draw.text((box_x1 + 46, box_y1 + 26), scene.badge_text, font=badge_fit, fill=c["badge_fg"])

    # 고지 박스를 릴스/쇼츠 하단 플랫폼 UI 안전 영역(y <= 1656) 안으로 상향 배치 + 27px 확대
    n_y1, n_y2 = 1540, 1656
    draw.rounded_rectangle([56, n_y1, WIDTH - 56, n_y2], radius=22, fill=c["notice_bg"])
    if scene.compliance_track == "center":
        line1 = "[기록 보조 안내] AI 생성 결과는 세션 기록 작성을 돕는 [초안]이며,"
        line2 = "최종 상태 평가 및 운동 지도는 담당 전문가가 [직접 검수] 후 활용합니다."
    else:
        line1 = "[기록 보조 안내] AI 생성 결과는 기록 작성 보조 [초안]이며,"
        line2 = "진단명 · 평가 · 처방은 담당 치료사가 [직접 검수] 후 최종 사용합니다."
    f_n1 = fit_single_line_font(draw, line1, WIDTH - 140, 27, min_size=21, bold=True)
    f_n2 = fit_single_line_font(draw, line2, WIDTH - 140, 27, min_size=21, bold=True)
    draw.text((76, n_y1 + 20), line1, font=f_n1, fill=c["notice_fg"])
    draw.text((76, n_y1 + 62), line2, font=f_n2, fill=c["notice_fg"])

    vp = (box_x1 + 20, box_y1 + 84, box_x2 - 20, box_y2 - 20)
    return canvas, vp


def draw_dynamic_overlays(
    frame_img: Image.Image,
    scene: SceneSpec,
    vp: tuple[int, int, int, int],
    progress: float,
    frame_idx: int,
) -> None:
    """Draw 2x magnified live loupe callout, micro-interactions, and 54px safe-zone subtitle."""
    draw = ImageDraw.Draw(frame_img)
    c = theme_colors(scene.theme)
    vx1, vy1, vx2, vy2 = vp

    # 1. 쇼케이스 하단 2배 확대 라이브 돋보기(Loupe) 콜아웃 카드 (y = 1048..1340)
    lx1, ly1, lx2, ly2 = 80, 1048, WIDTH - 80, 1340
    is_green = scene.overlay_mode in ("copy_pulse", "cta")
    loupe_border = (16, 185, 129) if is_green else (59, 130, 246)
    badge_bg = (5, 150, 105) if is_green else (37, 99, 235)
    line2_fg = (250, 204, 21) if scene.theme == "blue" else ((52, 211, 153) if is_green else (96, 165, 250))

    draw.rounded_rectangle(
        [lx1, ly1, lx2, ly2],
        radius=26,
        fill=(15, 23, 42),
        outline=loupe_border,
        width=3,
    )

    f_lbadge = load_font(26, bold=True)
    lb_w = int(draw.textlength(scene.loupe_badge, font=f_lbadge)) + 32
    draw.rounded_rectangle([lx1 + 26, ly1 + 22, lx1 + 26 + lb_w, ly1 + 68], radius=12, fill=badge_bg)
    draw.text((lx1 + 42, ly1 + 30), scene.loupe_badge, font=f_lbadge, fill=(255, 255, 255))

    # 우측 상단 실시간 액션 상태 배지
    if scene.overlay_mode == "typing":
        blink = "|" if (frame_idx // 8) % 2 == 0 else " "
        live_txt = f"1줄 키워드 입력 중 {blink}"
        f_live = load_font(24, bold=True)
        lw = int(draw.textlength(live_txt, font=f_live)) + 28
        draw.rounded_rectangle(
            [lx2 - lw - 26, ly1 + 22, lx2 - 26, ly1 + 68],
            radius=12,
            fill=(30, 41, 59),
            outline=(96, 165, 250),
            width=2,
        )
        draw.text((lx2 - lw - 12, ly1 + 30), live_txt, font=f_live, fill=(147, 197, 253))
    elif scene.overlay_mode == "copy_pulse" and progress > 0.35:
        pulse_t = ((progress - 0.35) / 0.65) % 0.5 / 0.5
        cx, cy = lx2 - 56, ly1 + 45
        r = int(12 + pulse_t * 20)
        draw.ellipse([cx - r, cy - r, cx + r, cy + r], outline=(52, 211, 153), width=3)
        draw.ellipse([cx - 8, cy - 8, cx + 8, cy + 8], fill=(16, 185, 129))
        live_txt = "복사 완료"
        f_live = load_font(24, bold=True)
        lw = int(draw.textlength(live_txt, font=f_live))
        draw.text((cx - 32 - lw, ly1 + 31), live_txt, font=f_live, fill=(52, 211, 153))

    max_lw = (lx2 - lx1) - 56
    f_l1 = fit_single_line_font(draw, scene.loupe_line1, max_lw, 40, min_size=30, bold=True)
    f_l2 = fit_single_line_font(draw, scene.loupe_line2, max_lw, 42, min_size=32, bold=True)
    draw.text((lx1 + 28, ly1 + 100), scene.loupe_line1, font=f_l1, fill=(248, 250, 252))
    draw.text((lx1 + 28, ly1 + 178), scene.loupe_line2, font=f_l2, fill=line2_fg)

    # 2. 릴스·쇼츠 하단 안전 영역(y = 1380..1522) 내 54px 동기화 자막 바
    chunks = scene.subtitle_chunks
    if not chunks:
        return
    chunk_idx = min(len(chunks) - 1, int(progress * len(chunks)))
    line_text, hl_token = chunks[chunk_idx]

    sub_y1, sub_y2 = 1380, 1522
    draw.rounded_rectangle(
        [56, sub_y1, WIDTH - 56, sub_y2],
        radius=26,
        fill=c["caption_bg"],
        outline=(51, 65, 85),
        width=2,
    )
    f_cap = fit_single_line_font(draw, line_text, WIDTH - 156, 54, min_size=38, bold=True)
    total_w = draw.textlength(line_text, font=f_cap)
    tb = draw.textbbox((0, 0), line_text, font=f_cap, stroke_width=2)
    text_h = tb[3] - tb[1]
    tx = int((WIDTH - total_w) / 2)
    ty = sub_y1 + ((sub_y2 - sub_y1) - text_h) // 2 - tb[1]

    if hl_token and hl_token in line_text:
        pre, post = line_text.split(hl_token, 1)
        draw.text((tx, ty), pre, font=f_cap, fill=c["caption_fg"], stroke_width=2, stroke_fill=(2, 6, 23))
        hl_x = tx + int(draw.textlength(pre, font=f_cap))
        draw.text((hl_x, ty), hl_token, font=f_cap, fill=c["caption_hl"], stroke_width=2, stroke_fill=(2, 6, 23))
        post_x = hl_x + int(draw.textlength(hl_token, font=f_cap))
        draw.text((post_x, ty), post, font=f_cap, fill=c["caption_fg"], stroke_width=2, stroke_fill=(2, 6, 23))
    else:
        draw.text((tx, ty), line_text, font=f_cap, fill=c["caption_fg"], stroke_width=2, stroke_fill=(2, 6, 23))


def fit_crop_in_viewport(
    src: Image.Image,
    vp_w: int,
    vp_h: int,
    crop_norm: tuple[float, float, float, float],
    zoom: float,
    pan_progress: float,
) -> Image.Image:
    sw, sh = src.size
    cx1 = int(sw * crop_norm[0])
    cy1 = int(sh * crop_norm[1])
    cx2 = int(sw * crop_norm[2])
    cy2 = int(sh * crop_norm[3])
    region = src.crop((cx1, cy1, cx2, cy2))

    rw, rh = region.size
    vp_aspect = vp_w / vp_h
    reg_aspect = rw / rh

    out = Image.new("RGB", (vp_w, vp_h), (248, 250, 252))
    if reg_aspect > vp_aspect * 1.15:
        base_scale = (vp_w * 0.97) / rw * zoom
        tw = max(1, int(rw * base_scale))
        th = max(1, int(rh * base_scale))
        resized = region.resize((tw, th), Image.Resampling.BICUBIC)
        px = (vp_w - tw) // 2
        py = int(max(0, (vp_h - th) * (0.15 + 0.08 * pan_progress)))
        out.paste(resized, (px, py))
    else:
        base_scale = max(vp_w / rw, vp_h / rh) * zoom if reg_aspect < vp_aspect * 0.95 else (vp_w / rw) * zoom
        tw = max(vp_w, int(rw * base_scale))
        th = max(vp_h, int(rh * base_scale))
        resized = region.resize((tw, th), Image.Resampling.BICUBIC)
        x0 = max(0, (tw - vp_w) // 2)
        max_y = max(0, th - vp_h)
        y0 = int(max_y * (0.0 + 0.04 * pan_progress))
        cropped = resized.crop((x0, y0, x0 + vp_w, y0 + vp_h))
        out.paste(cropped, (0, 0))
    return out


def make_rounded_mask(w: int, h: int, radius: int) -> Image.Image:
    mask = Image.new("L", (w, h), 0)
    d = ImageDraw.Draw(mask)
    d.rounded_rectangle([0, 0, w, h], radius=radius, fill=255)
    return mask


def prepare_audio_mix(
    scenes: list,
    voice: str,
    rate: str,
    variant_id: str,
    work_dir: Path,
    min_cut_dur: float,
    pad_sec: float,
    tail_pad_sec: float,
    min_cut_frames: int,
    tts_delay_sec: float,
    trim_silence: bool = False,
) -> tuple[list[int], int, float, Path]:
    """Synthesize TTS per scene/cut and mix BGM + UI SFX into a single AAC stream."""
    tts_dir = work_dir / f"tts_{variant_id}"
    tts_dir.mkdir(parents=True, exist_ok=True)
    tts_items = asyncio.run(synth_tts_all(scenes, voice, rate, tts_dir, trim_silence=trim_silence))

    scene_frames: list[int] = []
    scene_start_sec: list[float] = []
    cursor_sec = 0.0
    for idx, (_mp3, speech_dur) in enumerate(tts_items):
        dur = max(min_cut_dur, speech_dur + pad_sec)
        if idx == len(scenes) - 1:
            dur = max(dur, speech_dur + tail_pad_sec)
        n_frames = max(min_cut_frames, math.ceil(dur * FPS))
        scene_frames.append(n_frames)
        scene_start_sec.append(cursor_sec)
        cursor_sec += n_frames / FPS

    total_frames = sum(scene_frames)
    total_dur = total_frames / FPS

    bgm_wav = work_dir / f"bgm_{variant_id}.wav"
    sfx_wav = work_dir / f"sfx_{variant_id}.wav"
    generate_ambient_bgm(bgm_wav, total_dur)
    generate_ui_sfx_wav(sfx_wav, scenes, scene_start_sec, scene_frames, total_dur)

    audio_mixed = work_dir / f"audio_{variant_id}.m4a"
    ffmpeg_cmd: list[str] = ["ffmpeg", "-y", "-i", str(bgm_wav), "-i", str(sfx_wav)]
    filter_parts: list[str] = ["[0:a]volume=0.13[bgm]", "[1:a]volume=0.35[sfx]"]
    mix_labels = ["[bgm]", "[sfx]"]

    for idx, ((mp3_path, _dur), start_s) in enumerate(zip(tts_items, scene_start_sec)):
        ffmpeg_cmd.extend(["-i", str(mp3_path)])
        delay_ms = int(round((start_s + tts_delay_sec) * 1000))
        inp = idx + 2
        filter_parts.append(f"[{inp}:a]adelay={delay_ms}|{delay_ms},volume=1.22[v{idx}]")
        mix_labels.append(f"[v{idx}]")

    n_mix = len(mix_labels)
    filter_parts.append(
        "".join(mix_labels)
        + f"amix=inputs={n_mix}:duration=first:dropout_transition=0:normalize=0,"
        + f"atrim=0:{total_dur:.3f},"
        + f"afade=t=out:st={max(0.0, total_dur - 0.4):.3f}:d=0.4[aout]"
    )
    ffmpeg_cmd.extend(
        [
            "-filter_complex",
            ";".join(filter_parts),
            "-map",
            "[aout]",
            "-c:a",
            "aac",
            "-b:a",
            "192k",
            str(audio_mixed),
        ]
    )
    subprocess.run(ffmpeg_cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    return scene_frames, total_frames, total_dur, audio_mixed


def start_mp4_encoder(out_mp4: Path, audio_mixed: Path, err_log: Path):
    encode_cmd = [
        "ffmpeg",
        "-y",
        "-f",
        "rawvideo",
        "-pix_fmt",
        "rgb24",
        "-s",
        f"{WIDTH}x{HEIGHT}",
        "-r",
        str(FPS),
        "-i",
        "-",
        "-i",
        str(audio_mixed),
        "-map",
        "0:v:0",
        "-map",
        "1:a:0",
        "-c:v",
        "libx264",
        "-preset",
        "fast",
        "-crf",
        "19",
        "-pix_fmt",
        "yuv420p",
        "-c:a",
        "copy",
        "-shortest",
        "-movflags",
        "+faststart",
        str(out_mp4),
    ]
    err_file = open(err_log, "wb")
    proc = subprocess.Popen(
        encode_cmd,
        stdin=subprocess.PIPE,
        stdout=subprocess.DEVNULL,
        stderr=err_file,
    )
    return proc, err_file


def render_variant(variant: dict, shots: dict[str, Image.Image], work_dir: Path) -> Path:
    scenes: list[SceneSpec] = variant["scenes"]
    scene_frames, total_frames, total_dur, audio_mixed = prepare_audio_mix(
        scenes=scenes,
        voice=variant["voice"],
        rate=variant["rate"],
        variant_id=variant["id"],
        work_dir=work_dir,
        min_cut_dur=2.8,
        pad_sec=0.22,
        tail_pad_sec=0.45,
        min_cut_frames=int(FPS * 2.5),
        tts_delay_sec=0.10,
    )

    out_mp4: Path = variant["out_mp4"]
    err_log = work_dir / f"ffmpeg_{variant['id']}.log"
    print(f"Encoding [{variant['id']}] ({total_frames} frames, {total_dur:.2f}s)...", flush=True)
    proc, err_file = start_mp4_encoder(out_mp4, audio_mixed, err_log)
    try:
        assert proc.stdin is not None
        frame_counter = 0
        for idx, scene in enumerate(scenes):
            base_canvas, vp = build_static_chrome(scene, idx, len(scenes))
            vx1, vy1, vx2, vy2 = vp
            vw, vh = vx2 - vx1, vy2 - vy1
            mask = make_rounded_mask(vw, vh, radius=20)
            colors = theme_colors(scene.theme)

            img_a = shots[scene.shot_a]
            img_b = shots.get(scene.shot_b) if scene.shot_b else None
            n_f = scene_frames[idx]

            if scene.shot_b == "__benefit_stack__":
                stack_w, stack_h = 1280, 1600
                stacked = Image.new("RGB", (stack_w, stack_h), (248, 250, 252))
                s6_raw = shots["shot_6_benefit_section.png"]
                s6 = s6_raw.crop((int(s6_raw.width * 0.01), 0, int(s6_raw.width * 0.535), s6_raw.height))
                s5 = shots["shot_5_portal_login.png"]
                s6_h = int(s6.height * ((stack_w - 40) / s6.width))
                s6_r = s6.resize((stack_w - 40, s6_h), Image.Resampling.BICUBIC)
                s5_crop = s5.crop((int(s5.width * 0.08), int(s5.height * 0.06), int(s5.width * 0.92), int(s5.height * 0.88)))
                s5_h = int(s5_crop.height * ((stack_w - 40) / s5_crop.width))
                s5_r = s5_crop.resize((stack_w - 40, s5_h), Image.Resampling.BICUBIC)
                stacked.paste(s6_r, (20, 12))
                stacked.paste(s5_r, (20, 28 + s6_h))
                img_a = stacked
                img_b = None

            for f in range(n_f):
                p = f / max(1, n_f - 1)
                eased = ease_in_out(p)
                zoom = 1.0 + (scene.zoom_end - 1.0) * eased

                if img_b is not None and p > 0.48:
                    blend_t = ease_in_out((p - 0.48) / 0.06)
                    if blend_t < 1.0:
                        patch_a = fit_crop_in_viewport(img_a, vw, vh, scene.crop_norm, zoom, eased)
                        patch_b = fit_crop_in_viewport(img_b, vw, vh, scene.crop_norm, zoom, eased)
                        patch = Image.blend(patch_a, patch_b, blend_t)
                    else:
                        patch = fit_crop_in_viewport(img_b, vw, vh, scene.crop_norm, zoom, eased)
                else:
                    patch = fit_crop_in_viewport(img_a, vw, vh, scene.crop_norm, zoom, eased)

                frame_img = base_canvas.copy()
                frame_img.paste(patch, (vx1, vy1), mask)
                draw_dynamic_overlays(frame_img, scene, vp, p, frame_counter)

                g_prog = (frame_counter + 1) / total_frames
                f_draw = ImageDraw.Draw(frame_img)
                f_draw.rectangle([0, 0, WIDTH, 10], fill=colors["progress_track"])
                f_draw.rectangle([0, 0, int(WIDTH * g_prog), 10], fill=colors["progress_fill"])

                proc.stdin.write(frame_img.tobytes())
                frame_counter += 1

        proc.stdin.close()
        ret = proc.wait()
    finally:
        err_file.close()

    if ret != 0:
        err_text = err_log.read_text(encoding="utf-8", errors="replace") if err_log.exists() else ""
        raise RuntimeError(f"ffmpeg failed ({ret}): {err_text}")

    final_dur = probe_duration(out_mp4)
    print(
        f"Rendered [{variant['id']}] -> {out_mp4.name} "
        f"({final_dur:.2f}s, {out_mp4.stat().st_size:,} bytes, voice={variant['voice']})",
        flush=True,
    )
    return out_mp4


def _build_native_dark_backdrop(src: Image.Image) -> Image.Image:
    dark_base = Image.new("RGB", (WIDTH, HEIGHT), (11, 17, 32))
    sw, sh = src.size
    scale = max(WIDTH / sw, HEIGHT / sh)
    nw, nh = int(sw * scale), int(sh * scale)
    resized = src.resize((nw, nh), Image.Resampling.BICUBIC)
    x0 = max(0, (nw - WIDTH) // 2)
    y0 = max(0, (nh - HEIGHT) // 2)
    cropped = resized.crop((x0, y0, x0 + WIDTH, y0 + HEIGHT)).filter(ImageFilter.GaussianBlur(14))
    return Image.blend(dark_base, cropped, 0.22)


def _draw_native_compliance_pill(canvas: Image.Image) -> None:
    """Draw 1-line compliance notice strictly above bottom 480px safe zone (y=1356..1416)."""
    draw = ImageDraw.Draw(canvas)
    draw.rounded_rectangle(
        [110, 1356, 970, 1416],
        radius=16,
        fill=(15, 23, 42),
        outline=(30, 41, 59),
        width=1,
    )
    notice_txt = "AI 결과는 기록 보조 [초안] · 담당 치료사 [직접 검수] 후 사용"
    f_notice = fit_single_line_font(draw, notice_txt, 800, 24, min_size=19, bold=True)
    nw = draw.textlength(notice_txt, font=f_notice)
    tb = draw.textbbox((0, 0), notice_txt, font=f_notice)
    tx = int((WIDTH - nw) / 2)
    ty = 1356 + (60 - (tb[3] - tb[1])) // 2 - tb[1]
    draw.text((tx, ty), notice_txt, font=f_notice, fill=(203, 213, 225))


def render_native_variant(variant: dict, shots: dict[str, Image.Image], work_dir: Path) -> Path:
    """Render high-retention native 8-cut variant with 68px kinetic captions and strict 480px bottom safe zone."""
    cuts: list[NativeCutSpec] = variant["scenes"]
    scene_frames, total_frames, total_dur, audio_mixed = prepare_audio_mix(
        scenes=cuts,
        voice=variant["voice"],
        rate=variant["rate"],
        variant_id=variant["id"],
        work_dir=work_dir,
        min_cut_dur=1.75,
        pad_sec=0.08,
        tail_pad_sec=0.25,
        min_cut_frames=math.ceil(1.65 * FPS),
        tts_delay_sec=0.04,
    )

    out_mp4: Path = variant["out_mp4"]
    err_log = work_dir / f"ffmpeg_{variant['id']}.log"
    print(f"Encoding [{variant['id']}] ({total_frames} frames, {total_dur:.2f}s)...", flush=True)
    proc, err_file = start_mp4_encoder(out_mp4, audio_mixed, err_log)
    flash_surface = Image.new("RGB", (WIDTH, HEIGHT), (240, 248, 255))
    solid_dark = Image.new("RGB", (WIDTH, HEIGHT), (11, 17, 32))

    try:
        assert proc.stdin is not None
        frame_counter = 0
        for idx, cut in enumerate(cuts):
            n_f = scene_frames[idx]
            src_img = shots[cut.shot]

            if cut.mode in ("dark_hook", "dark_cta"):
                base_bg = _build_native_dark_backdrop(src_img)
                _draw_native_compliance_pill(base_bg)
                region = None
                fw = fh = fx1 = fy1 = fx2 = fy2 = 0
                base_fit = 1.0
                ui_mask = None
            else:
                base_bg = solid_dark.copy()
                _draw_native_compliance_pill(base_bg)
                sw, sh = src_img.size
                region = src_img.crop(
                    (
                        int(sw * cut.crop_norm[0]),
                        int(sh * cut.crop_norm[1]),
                        int(sw * cut.crop_norm[2]),
                        int(sh * cut.crop_norm[3]),
                    )
                )
                rw, rh = region.size
                base_fit = min(1032 / rw, 860 / rh)
                fw = int(rw * base_fit)
                fh = int(rh * base_fit)
                fx1 = (WIDTH - fw) // 2
                fy1 = 220 + (860 - fh) // 2
                fx2, fy2 = fx1 + fw, fy1 + fh
                ui_mask = make_rounded_mask(fw, fh, radius=28)

            is_emerald = cut.sfx_mode in ("copy_pulse", "cta")
            accent_outline = (52, 211, 153) if is_emerald else (59, 130, 246)
            hl_color = (52, 211, 153) if is_emerald else (250, 204, 21)

            for f in range(n_f):
                p = f / max(1, n_f - 1)
                frame_img = base_bg.copy()

                if cut.mode == "full_ui" and region is not None and ui_mask is not None:
                    eased = 1.0 - (1.0 - p) ** 2.4
                    zoom = 1.0 + 0.03 * eased
                    rw, rh = region.size
                    zw = max(fw, int(rw * base_fit * zoom))
                    zh = max(fh, int(rh * base_fit * zoom))
                    resized_ui = region.resize((zw, zh), Image.Resampling.BICUBIC)
                    cx0 = max(0, (zw - fw) // 2)
                    cy0 = max(0, (zh - fh) // 2)
                    patch = resized_ui.crop((cx0, cy0, cx0 + fw, cy0 + fh))
                    frame_img.paste(patch, (fx1, fy1), ui_mask)

                    f_draw = ImageDraw.Draw(frame_img)
                    f_draw.rounded_rectangle(
                        [fx1, fy1, fx2, fy2],
                        radius=28,
                        outline=accent_outline,
                        width=3,
                    )

                    if cut.sfx_mode == "copy_pulse" and p > 0.25:
                        pulse_t = ((p - 0.25) / 0.75) % 0.5 / 0.5
                        rx, ry = fx2 - 145, fy1 + 62
                        r = int(18 + pulse_t * 38)
                        f_draw.ellipse([rx - r, ry - r, rx + r, ry + r], outline=(52, 211, 153), width=5)
                        f_draw.ellipse([rx - 12, ry - 12, rx + 12, ry + 12], fill=(16, 185, 129))
                else:
                    # dark_hook / dark_cta giant centered 90px headline (x=140..940, y=520..880)
                    f_draw = ImageDraw.Draw(frame_img)
                    hero_pop = int((1.0 - min(1.0, f / 3.0)) * 20)
                    y_line = 540 + hero_pop
                    for line in cut.hero_lines:
                        f_hero = fit_single_line_font(f_draw, line, 800, 90, min_size=56, bold=True)
                        tw = f_draw.textlength(line, font=f_hero)
                        tx = int((WIDTH - tw) / 2)
                        if cut.hero_hl and cut.hero_hl in line:
                            pre, post = line.split(cut.hero_hl, 1)
                            f_draw.text((tx, y_line), pre, font=f_hero, fill=(248, 250, 252), stroke_width=4, stroke_fill=(2, 6, 23))
                            hx = tx + int(f_draw.textlength(pre, font=f_hero))
                            f_draw.text((hx, y_line), cut.hero_hl, font=f_hero, fill=(250, 204, 21), stroke_width=4, stroke_fill=(2, 6, 23))
                            px = hx + int(f_draw.textlength(cut.hero_hl, font=f_hero))
                            f_draw.text((px, y_line), post, font=f_hero, fill=(248, 250, 252), stroke_width=4, stroke_fill=(2, 6, 23))
                        else:
                            f_draw.text((tx, y_line), line, font=f_hero, fill=(248, 250, 252), stroke_width=4, stroke_fill=(2, 6, 23))
                        y_line += 126

                    if cut.cta_url:
                        f_cta = load_font(44, bold=True)
                        cw = int(f_draw.textlength(cut.cta_url, font=f_cta)) + 84
                        cx1 = (WIDTH - cw) // 2
                        cy1, cy2 = 890 + hero_pop, 984 + hero_pop
                        f_draw.rounded_rectangle(
                            [cx1, cy1, cx1 + cw, cy2],
                            radius=24,
                            fill=(37, 99, 235),
                            outline=(96, 165, 250),
                            width=3,
                        )
                        tb_c = f_draw.textbbox((0, 0), cut.cta_url, font=f_cta)
                        cty = cy1 + ((cy2 - cy1) - (tb_c[3] - tb_c[1])) // 2 - tb_c[1]
                        f_draw.text((cx1 + 42, cty), cut.cta_url, font=f_cta, fill=(255, 255, 255))

                if cut.flash_in and f < 3:
                    alpha = 0.35 * (1.0 - f / 3.0)
                    frame_img = Image.blend(frame_img, flash_surface, alpha)

                # Kinetic 68px Pop-Up Subtitles strictly within safe zone (x=140..940, y=1138..1310)
                draw = ImageDraw.Draw(frame_img)
                chunks = cut.subtitle_chunks
                if chunks:
                    n_chunks = len(chunks)
                    chunk_idx = min(n_chunks - 1, int(p * n_chunks))
                    chunk_start_f = int(chunk_idx * n_f / n_chunks)
                    cf = max(0, f - chunk_start_f)
                    offset_y = int((1.0 - min(1.0, cf / 3.0)) * 16)
                    line_text, hl_token = chunks[chunk_idx]

                    py1, py2 = 1138 + offset_y, 1310 + offset_y
                    draw.rounded_rectangle(
                        [110, py1, 970, py2],
                        radius=28,
                        fill=(10, 15, 28),
                        outline=accent_outline,
                        width=3,
                    )
                    f_cap = fit_single_line_font(draw, line_text, 800, 68, min_size=48, bold=True)
                    total_w = draw.textlength(line_text, font=f_cap)
                    tb = draw.textbbox((0, 0), line_text, font=f_cap, stroke_width=5)
                    tx = int((WIDTH - total_w) / 2)
                    ty = py1 + ((py2 - py1) - (tb[3] - tb[1])) // 2 - tb[1]

                    if hl_token and hl_token in line_text:
                        pre, post = line_text.split(hl_token, 1)
                        draw.text((tx, ty), pre, font=f_cap, fill=(248, 250, 252), stroke_width=5, stroke_fill=(2, 6, 23))
                        hl_x = tx + int(draw.textlength(pre, font=f_cap))
                        draw.text((hl_x, ty), hl_token, font=f_cap, fill=hl_color, stroke_width=5, stroke_fill=(2, 6, 23))
                        post_x = hl_x + int(draw.textlength(hl_token, font=f_cap))
                        draw.text((post_x, ty), post, font=f_cap, fill=(248, 250, 252), stroke_width=5, stroke_fill=(2, 6, 23))
                    else:
                        draw.text((tx, ty), line_text, font=f_cap, fill=(248, 250, 252), stroke_width=5, stroke_fill=(2, 6, 23))

                # Top 6px progress bar
                g_prog = (frame_counter + 1) / total_frames
                draw.rectangle([0, 0, WIDTH, 6], fill=(30, 41, 59))
                draw.rectangle([0, 0, int(WIDTH * g_prog), 6], fill=(59, 130, 246))

                proc.stdin.write(frame_img.tobytes())
                frame_counter += 1

        proc.stdin.close()
        ret = proc.wait()
    finally:
        err_file.close()

    if ret != 0:
        err_text = err_log.read_text(encoding="utf-8", errors="replace") if err_log.exists() else ""
        raise RuntimeError(f"ffmpeg failed ({ret}): {err_text}")

    final_dur = probe_duration(out_mp4)
    print(
        f"Rendered [{variant['id']}] -> {out_mp4.name} "
        f"({final_dur:.2f}s, {out_mp4.stat().st_size:,} bytes, voice={variant['voice']})",
        flush=True,
    )
    return out_mp4


def _draw_benchmark_chrome(canvas: Image.Image) -> None:
    """Draw pure black letterbox top 2-line hook title and 1-line safe-zone compliance footer."""
    draw = ImageDraw.Draw(canvas)
    line1 = "도수치료 끝나고"
    line2 = "차팅 순서 다 틀립니다"
    f_l1 = fit_single_line_font(draw, line1, 800, 56, min_size=40, bold=True)
    f_l2 = fit_single_line_font(draw, line2, 800, 66, min_size=46, bold=True)
    w1 = draw.textlength(line1, font=f_l1)
    w2 = draw.textlength(line2, font=f_l2)
    draw.text((int((WIDTH - w1) / 2), 202), line1, font=f_l1, fill=(248, 250, 252))
    draw.text((int((WIDTH - w2) / 2), 274), line2, font=f_l2, fill=(250, 204, 21))

    notice_txt = "AI 생성 결과는 기록 보조 [초안] · 담당 치료사 [직접 검수] 후 사용"
    f_n = fit_single_line_font(draw, notice_txt, 820, 23, min_size=18, bold=True)
    nw = draw.textlength(notice_txt, font=f_n)
    draw.text((int((WIDTH - nw) / 2), 1368), notice_txt, font=f_n, fill=(148, 163, 184))


def _draw_benchmark_compare_hook(canvas: Image.Image) -> None:
    """Cut 1 graphic: Red X wrong order vs Emerald right order."""
    draw = ImageDraw.Draw(canvas)
    # Wrong habit block
    draw.rounded_rectangle([76, 444, 1004, 722], radius=28, fill=(45, 18, 24), outline=(239, 68, 68), width=4)
    f_badge = load_font(26, bold=True)
    draw.rounded_rectangle([112, 474, 344, 522], radius=12, fill=(220, 38, 38))
    draw.text((130, 483), "순서 거꾸로 · X", font=f_badge, fill=(255, 255, 255))
    draw.text((112, 548), "퇴근 전 문장부터 타이핑", font=load_font(46, bold=True), fill=(248, 250, 252))
    draw.text((112, 616), "기억 더듬다 40분 야근", font=load_font(56, bold=True), fill=(248, 113, 113))

    # Right order block
    draw.rounded_rectangle([76, 756, 1004, 1034], radius=28, fill=(12, 38, 32), outline=(16, 185, 129), width=4)
    draw.rounded_rectangle([112, 786, 366, 834], radius=12, fill=(5, 150, 105))
    draw.text((130, 795), "치료 직후 순서 · O", font=f_badge, fill=(255, 255, 255))
    draw.text((112, 860), "치료 직후 순서 바꾸기", font=load_font(46, bold=True), fill=(248, 250, 252))
    draw.text((112, 928), "핵심 단어 4개 · 5초 메모", font=load_font(56, bold=True), fill=(52, 211, 153))


def _draw_benchmark_checklist_4(canvas: Image.Image) -> None:
    """Cut 2 graphic: 4-step clinical memo checklist with red numbered circles."""
    draw = ImageDraw.Draw(canvas)
    draw.rounded_rectangle([76, 424, 1004, 1068], radius=28, fill=(15, 23, 42), outline=(59, 130, 246), width=3)
    draw.rounded_rectangle([112, 452, 466, 504], radius=12, fill=(37, 99, 235))
    draw.text((132, 462), "치료 직후 5초 메모 4원칙", font=load_font(27, bold=True), fill=(255, 255, 255))

    rows = [
        ("1", "통증 부위", "바디차트 1번 터치"),
        ("2", "각도 · 검사", "ROM 120 · Neer (+)"),
        ("3", "시행 중재", "도수 · 운동 핵심만"),
        ("4", "전후 수치", "NRS 5 -> 2 변화"),
    ]
    f_num = load_font(34, bold=True)
    f_left = load_font(38, bold=True)
    f_right = load_font(34, bold=True)
    for idx, (num, label, cue) in enumerate(rows):
        ry1 = 532 + idx * 128
        ry2 = ry1 + 106
        draw.rounded_rectangle([112, ry1, 968, ry2], radius=20, fill=(30, 41, 59), outline=(51, 65, 85), width=2)
        draw.ellipse([136, ry1 + 21, 200, ry1 + 85], fill=(220, 38, 38))
        nw = draw.textlength(num, font=f_num)
        draw.text((168 - int(nw / 2), ry1 + 31), num, font=f_num, fill=(255, 255, 255))
        draw.text((224, ry1 + 30), label, font=f_left, fill=(248, 250, 252))
        rw = draw.textlength(cue, font=f_right)
        draw.text((942 - int(rw), ry1 + 33), cue, font=f_right, fill=(250, 204, 21))


def render_benchmark_variant(variant: dict, shots: dict[str, Image.Image], work_dir: Path) -> Path:
    """Render Formula 1 benchmark short: habit negation, red callout + yellow label, 70px borderless captions, silence-trimmed ~6.5-7.5 chars/sec."""
    cuts: list[BenchmarkCutSpec] = BENCHMARK_HOOK_SCENES
    scene_frames, total_frames, total_dur, audio_mixed = prepare_audio_mix(
        scenes=cuts,
        voice=variant["voice"],
        rate=variant["rate"],
        variant_id=variant["id"],
        work_dir=work_dir,
        min_cut_dur=1.7,
        pad_sec=0.06,
        tail_pad_sec=0.22,
        min_cut_frames=math.ceil(1.6 * FPS),
        tts_delay_sec=0.03,
        trim_silence=True,
    )

    out_mp4: Path = variant["out_mp4"]
    err_log = work_dir / f"ffmpeg_{variant['id']}.log"
    print(f"Encoding [{variant['id']}] ({total_frames} frames, {total_dur:.2f}s)...", flush=True)
    proc, err_file = start_mp4_encoder(out_mp4, audio_mixed, err_log)
    flash_surface = Image.new("RGB", (WIDTH, HEIGHT), (245, 250, 255))
    pure_black = Image.new("RGB", (WIDTH, HEIGHT), (0, 0, 0))

    try:
        assert proc.stdin is not None
        frame_counter = 0
        for idx, cut in enumerate(cuts):
            n_f = scene_frames[idx]
            base_bg = pure_black.copy()
            _draw_benchmark_chrome(base_bg)

            region = None
            fw = fh = fx1 = fy1 = fx2 = fy2 = 0
            base_fit = 1.0
            ui_mask = None

            if cut.cut_kind == "compare_hook":
                _draw_benchmark_compare_hook(base_bg)
            elif cut.cut_kind == "checklist_4":
                _draw_benchmark_checklist_4(base_bg)
            else:
                src_img = shots[cut.shot]
                sw, sh = src_img.size
                region = src_img.crop(
                    (
                        int(sw * cut.crop_norm[0]),
                        int(sh * cut.crop_norm[1]),
                        int(sw * cut.crop_norm[2]),
                        int(sh * cut.crop_norm[3]),
                    )
                )
                rw, rh = region.size
                base_fit = min(1000 / rw, 682 / rh)
                fw = int(rw * base_fit)
                fh = int(rh * base_fit)
                fx1 = (WIDTH - fw) // 2
                fy1 = 408 + (682 - fh) // 2
                fx2, fy2 = fx1 + fw, fy1 + fh
                ui_mask = make_rounded_mask(fw, fh, radius=24)

            is_emerald = cut.sfx_mode in ("copy_pulse", "cta")
            hl_color = (52, 211, 153) if is_emerald else (250, 204, 21)

            for f in range(n_f):
                p = f / max(1, n_f - 1)
                frame_img = base_bg.copy()

                if cut.cut_kind == "ui_callout" and region is not None and ui_mask is not None:
                    eased = 1.0 - (1.0 - p) ** 2.3
                    zoom = 1.0 + 0.03 * eased
                    rw, rh = region.size
                    zw = max(fw, int(rw * base_fit * zoom))
                    zh = max(fh, int(rh * base_fit * zoom))
                    resized_ui = region.resize((zw, zh), Image.Resampling.BICUBIC)
                    cx0 = max(0, (zw - fw) // 2)
                    cy0 = max(0, (zh - fh) // 2)
                    patch = resized_ui.crop((cx0, cy0, cx0 + fw, cy0 + fh))
                    frame_img.paste(patch, (fx1, fy1), ui_mask)

                    f_draw = ImageDraw.Draw(frame_img)
                    f_draw.rounded_rectangle([fx1, fy1, fx2, fy2], radius=24, outline=(51, 65, 85), width=2)

                    if cut.callout_box is not None:
                        cx_n, cy_n, rx_n, ry_n = cut.callout_box
                        ocx = fx1 + int(fw * cx_n)
                        ocy = fy1 + int(fh * cy_n)
                        orx = int(fw * rx_n)
                        ory = int(fh * ry_n)
                        f_draw.ellipse([ocx - orx, ocy - ory, ocx + orx, ocy + ory], outline=(239, 68, 68), width=7)

                    if cut.sfx_mode == "copy_pulse" and p > 0.22 and cut.callout_box is not None:
                        pulse_t = ((p - 0.22) / 0.78) % 0.5 / 0.5
                        rx = fx1 + int(fw * cut.callout_box[0])
                        ry = fy1 + int(fh * cut.callout_box[1])
                        r = int(16 + pulse_t * 34)
                        f_draw.ellipse([rx - r, ry - r, rx + r, ry + r], outline=(52, 211, 153), width=5)
                        f_draw.ellipse([rx - 10, ry - 10, rx + 10, ry + 10], fill=(16, 185, 129))

                    if cut.callout_label:
                        f_lbl = load_font(28, bold=True)
                        lw = int(f_draw.textlength(cut.callout_label, font=f_lbl)) + 34
                        lh = 52
                        bx = max(48, min(WIDTH - 48 - lw, fx1 + int(fw * cut.callout_badge_pos[0]) - lw // 2))
                        by = max(414, min(1090 - lh, fy1 + int(fh * cut.callout_badge_pos[1]) - lh // 2))
                        f_draw.rounded_rectangle(
                            [bx, by, bx + lw, by + lh],
                            radius=14,
                            fill=(250, 204, 21),
                            outline=(220, 38, 38),
                            width=3,
                        )
                        f_draw.text((bx + 17, by + 9), cut.callout_label, font=f_lbl, fill=(15, 23, 42))

                if cut.flash_in and f < 3:
                    alpha = 0.35 * (1.0 - f / 3.0)
                    frame_img = Image.blend(frame_img, flash_surface, alpha)

                # Floating Borderless 70px Stroked Subtitles strictly above 480px bottom safe zone (y=1140..1290)
                draw = ImageDraw.Draw(frame_img)
                chunks = cut.subtitle_chunks
                if chunks:
                    n_chunks = len(chunks)
                    chunk_idx = min(n_chunks - 1, int(p * n_chunks))
                    chunk_start_f = int(chunk_idx * n_f / n_chunks)
                    cf = max(0, f - chunk_start_f)
                    offset_y = int((1.0 - min(1.0, cf / 3.0)) * 16)
                    line_text, hl_token = chunks[chunk_idx]

                    f_cap = fit_single_line_font(draw, line_text, 800, 70, min_size=50, bold=True)
                    total_w = draw.textlength(line_text, font=f_cap)
                    tb = draw.textbbox((0, 0), line_text, font=f_cap, stroke_width=7)
                    tx = int((WIDTH - total_w) / 2)
                    ty = 1140 + offset_y + (150 - (tb[3] - tb[1])) // 2 - tb[1]

                    if hl_token and hl_token in line_text:
                        pre, post = line_text.split(hl_token, 1)
                        draw.text((tx, ty), pre, font=f_cap, fill=(255, 255, 255), stroke_width=7, stroke_fill=(0, 0, 0))
                        hl_x = tx + int(draw.textlength(pre, font=f_cap))
                        draw.text((hl_x, ty), hl_token, font=f_cap, fill=hl_color, stroke_width=7, stroke_fill=(0, 0, 0))
                        post_x = hl_x + int(draw.textlength(hl_token, font=f_cap))
                        draw.text((post_x, ty), post, font=f_cap, fill=(255, 255, 255), stroke_width=7, stroke_fill=(0, 0, 0))
                    else:
                        draw.text((tx, ty), line_text, font=f_cap, fill=(255, 255, 255), stroke_width=7, stroke_fill=(0, 0, 0))

                g_prog = (frame_counter + 1) / total_frames
                draw.rectangle([0, 0, WIDTH, 6], fill=(30, 41, 59))
                draw.rectangle([0, 0, int(WIDTH * g_prog), 6], fill=(250, 204, 21))

                proc.stdin.write(frame_img.tobytes())
                frame_counter += 1

        proc.stdin.close()
        ret = proc.wait()
    finally:
        err_file.close()

    if ret != 0:
        err_text = err_log.read_text(encoding="utf-8", errors="replace") if err_log.exists() else ""
        raise RuntimeError(f"ffmpeg failed ({ret}): {err_text}")

    final_dur = probe_duration(out_mp4)
    print(
        f"Rendered [{variant['id']}] -> {out_mp4.name} "
        f"({final_dur:.2f}s, {out_mp4.stat().st_size:,} bytes, voice={variant['voice']})",
        flush=True,
    )
    return out_mp4


def main() -> None:
    parser = argparse.ArgumentParser(description="Render 4THEPT 9:16 Reels/Shorts MP4 variants")
    parser.add_argument("--only", help="Render only matching variant id (e.g. native_viral)")
    args = parser.parse_args()

    required = {
        "shot_1_intro_full_hero.png",
        "shot_2_workbench_foot.png",
        "shot_3_workbench_shoulder.png",
        "shot_4_workbench_copied.png",
        "shot_5_portal_login.png",
        "shot_6_benefit_section.png",
        "shot_2_input_zoom.png",
        "shot_2_output_zoom.png",
        "shot_3_output_zoom.png",
        "shot_4_copied_zoom.png",
        "shot_6_benefit_zoom.png",
    }
    shots: dict[str, Image.Image] = {}
    for name in sorted(required):
        path = REAL_ASSETS / name
        if not path.exists():
            raise FileNotFoundError(f"Missing real screenshot asset: {path}")
        shots[name] = Image.open(path).convert("RGB")

    selected = [v for v in VARIANTS if not args.only or v["id"] == args.only]
    if not selected:
        raise ValueError(f"Unknown --only variant id: {args.only}")

    with tempfile.TemporaryDirectory(prefix="4thept_shorts_") as tmp:
        work_dir = Path(tmp)
        for variant in selected:
            r_kind = variant.get("renderer")
            if r_kind == "native":
                render_native_variant(variant, shots, work_dir)
            elif r_kind == "benchmark":
                render_benchmark_variant(variant, shots, work_dir)
            else:
                render_variant(variant, shots, work_dir)


if __name__ == "__main__":
    main()
