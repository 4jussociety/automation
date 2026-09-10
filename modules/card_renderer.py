# 이 모듈은 Playwright를 사용하여 card_4x5.html 템플릿을 고화질 PNG 이미지로 렌더링합니다.
# 인스타그램 4:5 최적 규격(1080x1350)으로 슬라이드별 카드뉴스를 완벽하게 생성합니다.

import sys
from pathlib import Path
import re
import asyncio
from playwright.async_api import async_playwright

from datetime import datetime
import base64
from config import TEMPLATE_4X5, CARD_WIDTH, CARD_HEIGHT, LOGO_PATH, DEFAULT_BG_PATH
from modules.content_builder import build_slide_html


def get_image_data_uri(img_path) -> str:
    """이미지 파일을 읽어 base64 Data URI로 변환합니다."""
    if not img_path:
        return ""
    if str(img_path).startswith("data:"):
        return str(img_path)
    p = Path(img_path) if isinstance(img_path, (str, Path)) else None
    if not p or not p.exists():
        return ""
    suffix = p.suffix.lower().replace(".", "")
    mime = "jpeg" if suffix in ["jpg", "jpeg"] else "png"
    try:
        raw = p.read_bytes()
        encoded = base64.b64encode(raw).decode("utf-8")
        return f"data:image/{mime};base64,{encoded}"
    except Exception:
        return ""


def get_logo_data_uri() -> str:
    """THEPT 공식 로고 파일을 읽어 base64 Data URI로 변환합니다."""
    return get_image_data_uri(LOGO_PATH)


def generate_dots_html(total: int, active_index: int) -> str:
    """인디케이터 점들을 생성합니다."""
    dots = []
    for i in range(total):
        if i == active_index:
            dots.append('<div class="dot active"></div>')
        else:
            dots.append('<div class="dot"></div>')
    return "".join(dots)


async def render_cards_to_images(
    package: dict,
    output_dir: Path,
    template_path: Path = None,
    width: int = CARD_WIDTH,
    height: int = CARD_HEIGHT
) -> list[Path]:
    """
    Playwright를 사용해 슬라이드 패키지를 PNG 이미지들로 렌더링합니다.
    기본은 1080x1350(4:5)이며, 방송형 템플릿(1080x1920) 등 다양한 템플릿을 지원합니다.
    """
    if template_path is None:
        template_path = TEMPLATE_4X5
    if not template_path.exists():
        raise FileNotFoundError(f"템플릿 파일을 찾을 수 없습니다: {template_path}")

    output_dir.mkdir(parents=True, exist_ok=True)
    for old_f in output_dir.glob("*.png"):
        try:
            old_f.unlink()
        except Exception:
            pass
    template_content = template_path.read_text(encoding="utf-8")

    slides = package.get("slides", [])
    if not slides:
        raise ValueError("렌더링할 슬라이드 데이터가 없습니다.")

    total_slides = len(slides)
    rendered_paths = []

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        # 정확한 뷰포트 설정 (기본 1080x1350 또는 1080x1920)
        context = await browser.new_context(
            viewport={"width": width, "height": height},
            device_scale_factor=1
        )
        page = await context.new_page()

        now_dt = datetime.now()
        weekday_kr = ["월", "화", "수", "목", "금", "토", "일"][now_dt.weekday()]
        default_date_text = f"{now_dt.strftime('%y')}년 {now_dt.month}월 {now_dt.day}일 ({weekday_kr})"

        for idx, slide in enumerate(slides):
            slide_type = slide["type"]
            header_tag = slide.get("header_tag", "THEPT NEWS")
            swipe_label = slide.get("swipe_label", "밀어서 보기 👉")
            date_text = slide.get("date_text", package.get("date_text", default_date_text))
            broadcast_sub = slide.get("broadcast_subtitle", "오늘의 물리치료 뉴스")

            # slide data의 media_image를 Data URI로 변환하여 Chromium 렌더링 보장
            slide_data = dict(slide.get("data", {}))
            if "media_image" in slide_data and slide_data["media_image"]:
                slide_data["media_image"] = get_image_data_uri(slide_data["media_image"])
            body_html = build_slide_html(slide_type, slide_data)
            dots_html = generate_dots_html(total_slides, idx)

            # 슬라이드별 배경 이미지 로드
            bg_path_str = slide.get("background")
            bg_path = Path(bg_path_str) if bg_path_str else DEFAULT_BG_PATH
            bg_data_uri = get_image_data_uri(bg_path)

            # 푸터 THEPT 로고 노출 조건: 1, 5, 6페이지(표지, 광고, 아웃트로)에만 표시하고 뉴스페이지(2, 3, 4페이지)는 제외
            is_logo_page = slide_type != "news" and (idx == 0 or idx >= total_slides - 2 or slide_type in ["cover", "ad", "outro"])
            footer_style = "" if is_logo_page else "display: none;"

            # 템플릿 변수 치환
            rendered_html = template_content
            rendered_html = rendered_html.replace("{{FOOTER_STYLE}}", footer_style)
            rendered_html = rendered_html.replace("{{LOGO_DATA}}", get_logo_data_uri())
            rendered_html = rendered_html.replace("{{BACKGROUND_IMAGE_DATA}}", bg_data_uri)
            rendered_html = rendered_html.replace("{{HEADER_TAG}}", header_tag)
            rendered_html = rendered_html.replace("{{DATE_TEXT}}", date_text)
            rendered_html = rendered_html.replace("{{BROADCAST_SUBTITLE}}", broadcast_sub)
            rendered_html = rendered_html.replace("{{BODY_CONTENT}}", body_html)
            rendered_html = rendered_html.replace("{{CAROUSEL_DOTS}}", dots_html)
            rendered_html = rendered_html.replace("{{SWIPE_LABEL}}", swipe_label)

            # HTML 로드 및 렌더링 대기
            await page.set_content(rendered_html, wait_until="networkidle")

            # 폰트 로딩 대기
            await page.evaluate("document.fonts.ready")

            out_path = output_dir / f"slide_{idx+1:02d}_{slide_type}.png"
            await page.screenshot(
                path=str(out_path),
                clip={"x": 0, "y": 0, "width": width, "height": height}
            )

            if not out_path.exists() or out_path.stat().st_size == 0:
                raise RuntimeError(f"카드뉴스 이미지 렌더링 실패: {out_path}")

            rendered_paths.append(out_path)
            print(f"[렌더 완료] 슬라이드 {idx+1}/{total_slides}: {out_path.name}")

        await browser.close()

    return rendered_paths


if __name__ == "__main__":
    from modules.news_collector import collect_weekly_physical_therapy_news
    from modules.content_builder import build_content_package

    print("[테스트] 4:5 카드뉴스 렌더링 시작...")
    test_news = collect_weekly_physical_therapy_news(min_news_count=3)
    test_pkg = build_content_package(test_news)
    test_out = Path(__file__).resolve().parent.parent / "output" / "test_cards"
    paths = asyncio.run(render_cards_to_images(test_pkg, test_out))
    print(f"[성공] 총 {len(paths)}장의 카드뉴스가 생성되었습니다: {test_out}")
