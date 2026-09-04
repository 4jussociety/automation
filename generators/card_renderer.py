import sys
import base64

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

import asyncio
from pathlib import Path
from playwright.async_api import async_playwright
from config import TEMPLATES_DIR, BASE_DIR, CURRENT_WEEK

TEMPLATE_4X5_PATH = TEMPLATES_DIR / "card_4x5.html"
TEMPLATE_9X16_PATH = TEMPLATES_DIR / "card_9x16.html"
ASSETS_DIR = BASE_DIR / "assets"
LOGO_PATH = ASSETS_DIR / "logo_thept_transparent.png"

def get_image_base64_uri(image_path: Path) -> str:
    """로컬 이미지를 Data URI로 변환하여 CSS/HTML에 인라인 주입"""
    if image_path.exists():
        with open(image_path, "rb") as img_file:
            b64_str = base64.b64encode(img_file.read()).decode("utf-8")
            ext = image_path.suffix.lower().replace(".", "")
            if ext == "jpg":
                ext = "jpeg"
            return f"data:image/{ext};base64,{b64_str}"
    return ""

def apply_title_highlight(title: str) -> str:
    """핵심 키워드에 옐로우 골드 하이라이트 적용"""
    keywords = ["도수치료", "실손보험", "거북목", "물리치료", "오십견", "심평원", "가이드라인", "햄스트링", "재활 로봇", "만성 요통"]
    highlighted = title
    for kw in keywords:
        if kw in highlighted:
            highlighted = highlighted.replace(kw, f'<span class="hl-yellow">{kw}</span>', 1)
            break
    return highlighted

def render_slide_body_html(slide, is_4x5=False):
    slide_type = slide.get("type")
    
    if slide_type == "cover":
        bullet_items = slide.get("bullet_points", [])
        teasers_html = "".join([
            f'<div class="cover-item-row"><div class="cover-num-bullet">{i}</div><div>{pt}</div></div>'
            for i, pt in enumerate(bullet_items[:3], start=1)
        ])
        title_with_hl = apply_title_highlight(slide.get('title', ''))
        return f"""
        <div>
          <div class="cover-tag-box">📢 {slide.get('tag', 'THEPT 주간 브리핑')}</div>
          <div class="cover-huge-title">{title_with_hl}</div>
          <div class="cover-desc-card">
            <div class="cover-desc-text">{slide.get('subtitle', '')}</div>
          </div>
          <div class="cover-item-list">
            {teasers_html}
          </div>
        </div>
        """
        
    elif slide_type == "news":
        body_lines_html = "".join([
            f'<div class="news-body-bullet">• {line}</div>'
            for line in slide.get("body_lines", [])
        ])
        headline_with_hl = apply_title_highlight(slide.get('headline', ''))
        return f"""
        <div>
          <div class="news-top-badge-row">
            <div class="news-index-badge">{slide.get('item_index', '01')}</div>
            <div class="news-category-badge">{slide.get('category_badge', '주요 이슈')}</div>
            <div class="news-source-badge">출처: {slide.get('source_badge', '보도자료')}</div>
          </div>
          <div class="news-main-headline">{headline_with_hl}</div>
          <div class="news-glass-box">
            {body_lines_html}
          </div>
          <div class="news-action-highlight">
            {slide.get('key_point', '')}
          </div>
        </div>
        """
        
    elif slide_type == "insight":
        checklist_html = "".join([
            f'<div class="insight-check-item"><span>⚡</span><div>{item}</div></div>'
            for item in slide.get("action_checklist", [])
        ])
        return f"""
        <div>
          <div class="insight-top-tag">💡 {slide.get('tag', 'EXPERT INSIGHT')}</div>
          <div class="insight-huge-title">{slide.get('title', '')}</div>
          <div class="insight-summary-card">
            {slide.get('summary', '')}
          </div>
          <div class="insight-checklist">
            {checklist_html}
          </div>
        </div>
        """
        
    elif slide_type == "outro":
        title_formatted = slide.get('title', '').replace('\\n', '<br>')
        cta_formatted = slide.get('cta_text', '').replace('\\n', '<br>')
        return f"""
        <div class="outro-card-box">
          <div class="outro-header-text">{title_formatted}</div>
          <div class="outro-sub-text">{cta_formatted}</div>
          
          <div class="outro-insta-buttons">
            <div class="insta-button">
              <span class="btn-icon">❤️</span>
              <span>좋아요</span>
            </div>
            <div class="insta-button">
              <span class="btn-icon">💬</span>
              <span>댓글</span>
            </div>
            <div class="insta-button">
              <span class="btn-icon">✈️</span>
              <span>공유</span>
            </div>
            <div class="insta-button highlight-save">
              <span class="btn-icon">🔖</span>
              <span>저장하기</span>
            </div>
          </div>

          <div class="outro-channel-tag">
            👉 @teamthept 팔로우하고 매주 최신 소식을 받아보세요!
          </div>
        </div>
        """
    return ""

def generate_dots_html(current_idx: int, total_slides: int) -> str:
    dots = []
    for i in range(1, total_slides + 1):
        if i == current_idx:
            dots.append('<div class="dot active"></div>')
        else:
            dots.append('<div class="dot"></div>')
    return "".join(dots)

from generators.bg_generator import prepare_set_backgrounds, file_to_base64_uri

async def render_cards_to_images(card_data, output_dir: Path, bg_files: list = None):
    slides = card_data.get("slides", [])
    total_slides = len(slides)
    batch_id = card_data.get("batch_id", "")

    # THEPT 브랜드 로고 Data URI 로드
    logo_uri = get_image_base64_uri(LOGO_PATH)

    # 배경 에셋 목록이 명시적으로 주어지지 않았을 경우 세트 폴더 backgrounds/ 에서 자동 확보
    if not bg_files:
        bg_output_dir = output_dir.parent / "backgrounds"
        bg_files = prepare_set_backgrounds(card_data, bg_output_dir)

    with open(TEMPLATE_4X5_PATH, "r", encoding="utf-8") as f:
        template_4x5 = f.read()

    with open(TEMPLATE_9X16_PATH, "r", encoding="utf-8") as f:
        template_9x16 = f.read()

    # 두 가지 규격 동시 저장 폴더 세팅
    dir_4x5 = output_dir / "feed_4x5"
    dir_9x16 = output_dir / "reels_shorts_9x16"
    dir_4x5.mkdir(parents=True, exist_ok=True)
    dir_9x16.mkdir(parents=True, exist_ok=True)

    fg_images_9x16 = []

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        
        # 1) 인스타 피드용 4:5 렌더링 컨텍스트 (1080 x 1350)
        ctx_4x5 = await browser.new_context(viewport={"width": 1080, "height": 1350}, device_scale_factor=1.2)
        page_4x5 = await ctx_4x5.new_page()

        # 2) 릴스/쇼츠용 9:16 렌더링 컨텍스트 (1080 x 1920)
        ctx_9x16 = await browser.new_context(viewport={"width": 1080, "height": 1920}, device_scale_factor=1.2)
        page_9x16 = await ctx_9x16.new_page()

        for idx, slide in enumerate(slides, start=1):
            header_tag = card_data.get("week_tag", CURRENT_WEEK)
            dots_html = generate_dots_html(idx, total_slides)
            
            # 이번 세트 아웃풋 폴더에 배치된 해당 슬라이드 배경 파일 가져오기
            bg_file = bg_files[idx - 1] if idx - 1 < len(bg_files) else bg_files[0]
            slide_bg_uri = file_to_base64_uri(bg_file)

            if idx == 1:
                swipe_label = "옆으로 넘겨서 확인 👉"
            elif idx == total_slides:
                swipe_label = "저장 & 팔로우 🔖"
            else:
                swipe_label = "다음 장으로 👉"

            # 4:5 버전 렌더링
            body_html_4x5 = render_slide_body_html(slide, is_4x5=True)
            html_4x5 = template_4x5 \
                .replace("{{BACKGROUND_IMAGE_DATA}}", slide_bg_uri) \
                .replace("{{LOGO_DATA}}", logo_uri) \
                .replace("{{HEADER_TAG}}", header_tag) \
                .replace("{{BODY_CONTENT}}", body_html_4x5) \
                .replace("{{CAROUSEL_DOTS}}", dots_html) \
                .replace("{{SWIPE_LABEL}}", swipe_label)

            await page_4x5.set_content(html_4x5, wait_until="networkidle")
            out_4x5 = dir_4x5 / f"card_{idx:02d}.png"
            await page_4x5.screenshot(path=str(out_4x5))

            # 9:16 버전 렌더링 (일반 카드뉴스 이미지)
            body_html_9x16 = render_slide_body_html(slide, is_4x5=False)
            html_9x16 = template_9x16 \
                .replace("{{BACKGROUND_IMAGE_DATA}}", slide_bg_uri) \
                .replace("{{LOGO_DATA}}", logo_uri) \
                .replace("{{HEADER_TAG}}", header_tag) \
                .replace("{{BODY_CONTENT}}", body_html_9x16) \
                .replace("{{CAROUSEL_DOTS}}", dots_html) \
                .replace("{{SWIPE_LABEL}}", swipe_label)

            await page_9x16.set_content(html_9x16, wait_until="networkidle")
            out_9x16 = dir_9x16 / f"card_{idx:02d}.png"
            await page_9x16.screenshot(path=str(out_9x16))

            # 9:16 쇼츠 동영상용 투명 전경 텍스트 카드 렌더링 (배경 제외하고 글씨/UI만 캡처)
            await page_9x16.evaluate("document.body.classList.add('transparent-bg')")
            out_fg_9x16 = dir_9x16 / f"fg_card_{idx:02d}.png"
            await page_9x16.screenshot(path=str(out_fg_9x16), omit_background=True)
            fg_images_9x16.append(out_fg_9x16)

            print(f"  [THEPT 맞춤 렌더링] card_{idx:02d}.png + fg_card_{idx:02d}.png 완료 (배경: {bg_file.name})")

        await browser.close()

    return {
        "dir_4x5": dir_4x5,
        "dir_9x16": dir_9x16,
        "bg_files": bg_files,
        "fg_images_9x16": fg_images_9x16
    }

def render_cards(card_data, output_dir: Path, bg_files: list = None):
    return asyncio.run(render_cards_to_images(card_data, output_dir, bg_files=bg_files))

