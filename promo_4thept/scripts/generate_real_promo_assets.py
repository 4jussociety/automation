"""
4THEPT 실제 최신 화면 기반 고해상도 스크린샷, OG 썸네일(1200x630),
블로그/단톡방용 6초 루프 GIF, 그리고 카드뉴스 13장 PNG 자동 생성 스크립트
"""
import os
import sys
import time
import urllib.request
import subprocess
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont
from playwright.sync_api import sync_playwright

PROMO_DIR = Path(__file__).resolve().parents[1]
FOURTHEPT_ROOT = Path(os.getenv("FOURTHEPT_WORKSPACE_DIR", r"c:\개발\4THEPT"))
BOOK_DIR = FOURTHEPT_ROOT / "book"
PUBLIC_DIR = BOOK_DIR / "public"
REAL_ASSETS_DIR = PROMO_DIR / "real_assets"
CARDS_DIR = PROMO_DIR / "cards"

REAL_ASSETS_DIR.mkdir(parents=True, exist_ok=True)
CARDS_DIR.mkdir(parents=True, exist_ok=True)

FONT_BLACK = "C:/Windows/Fonts/malgunbd.ttf"
FONT_BOLD = "C:/Windows/Fonts/malgunbd.ttf"
FONT_REG = "C:/Windows/Fonts/malgun.ttf"


def get_font(path: str, size: int) -> ImageFont.FreeTypeFont:
    try:
        return ImageFont.truetype(path, size)
    except Exception:
        return ImageFont.load_default()


def start_preview_server(port: int = 4173) -> subprocess.Popen:
    cmd = ["cmd", "/c", "npx", "vite", "preview", "--port", str(port), "--strictPort", "--host", "127.0.0.1"]
    proc = subprocess.Popen(
        cmd,
        cwd=str(BOOK_DIR),
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    url = f"http://127.0.0.1:{port}/intro"
    for _ in range(40):
        try:
            with urllib.request.urlopen(url, timeout=1.0) as resp:
                if resp.status == 200:
                    return proc
        except Exception:
            time.sleep(0.35)
    proc.terminate()
    raise RuntimeError("vite preview server did not become ready in time")


def launch_browser(p):
    for attempt in [
        lambda: p.chromium.launch(headless=True),
        lambda: p.chromium.launch(headless=True, channel="msedge"),
        lambda: p.chromium.launch(headless=True, channel="chrome"),
    ]:
        try:
            return attempt()
        except Exception:
            continue
    raise RuntimeError("No Playwright Chromium / Edge / Chrome browser could be launched.")


def save_zoom_crop(src_path: Path, dst_path: Path, crop_norm: tuple[float, float, float, float]) -> Path:
    """Save a focused single-panel zoomed crop from a high-res screenshot."""
    im = Image.open(src_path).convert("RGB")
    sw, sh = im.size
    cx1 = max(0, min(sw - 1, int(sw * crop_norm[0])))
    cy1 = max(0, min(sh - 1, int(sh * crop_norm[1])))
    cx2 = max(cx1 + 1, min(sw, int(sw * crop_norm[2])))
    cy2 = max(cy1 + 1, min(sh, int(sh * crop_norm[3])))
    im.crop((cx1, cy1, cx2, cy2)).save(str(dst_path), "PNG", optimize=True)
    return dst_path


def capture_real_screenshots(base_url: str) -> dict[str, Path]:
    paths: dict[str, Path] = {}
    with sync_playwright() as p:
        browser = launch_browser(p)
        context = browser.new_context(
            viewport={"width": 1280, "height": 900},
            device_scale_factor=2,
            locale="ko-KR",
            permissions=["clipboard-read", "clipboard-write"],
        )
        page = context.new_page()

        # 1. /intro 풀 히어로 + 워크벤치 상단 뷰
        page.goto(f"{base_url}/intro", wait_until="networkidle")
        page.wait_for_selector("#trial-section")
        page.wait_for_timeout(600)
        p_hero = REAL_ASSETS_DIR / "shot_1_intro_full_hero.png"
        page.screenshot(path=str(p_hero), full_page=False)
        paths["hero"] = p_hero

        # 2. 발목·족부 재활 워크벤치 클로즈업
        trial_loc = page.locator("#trial-section")
        trial_loc.scroll_into_view_if_needed()
        page.wait_for_timeout(300)
        p_foot = REAL_ASSETS_DIR / "shot_2_workbench_foot.png"
        trial_loc.screenshot(path=str(p_foot))
        paths["foot"] = p_foot

        # 3. 실시간 직접 타이핑 중간 상태 캡처 (GIF용)
        textarea = trial_loc.locator("textarea")
        textarea.click()
        textarea.fill("오른쪽 발 통증, 발꿈치들기 운동")
        page.wait_for_timeout(200)
        p_typing = REAL_ASSETS_DIR / "_tmp_typing.png"
        trial_loc.screenshot(path=str(p_typing))
        paths["typing"] = p_typing

        # 기본 예시로 복원
        reset_btn = trial_loc.get_by_text("기본 예시로 되돌리기")
        if reset_btn.count() > 0:
            reset_btn.click()
            page.wait_for_timeout(250)

        # 4. 회전근개·관절가동 탭 전환 클로즈업
        trial_loc.get_by_role("button", name="회전근개·관절가동").click()
        page.wait_for_timeout(450)
        p_shoulder = REAL_ASSETS_DIR / "shot_3_workbench_shoulder.png"
        trial_loc.screenshot(path=str(p_shoulder))
        paths["shoulder"] = p_shoulder

        # 5. 발목·족부 도수 복사 완료 상태 클로즈업
        trial_loc.get_by_role("button", name="발목·족부 도수").click()
        page.wait_for_timeout(450)
        trial_loc.get_by_role("button", name="EMR 양식 복사").click()
        page.wait_for_timeout(300)
        p_copied = REAL_ASSETS_DIR / "shot_4_workbench_copied.png"
        trial_loc.screenshot(path=str(p_copied))
        paths["copied"] = p_copied

        # 6. 무료 혜택 & AI 안전 원칙 섹션
        benefit_loc = page.locator("#benefit-section")
        benefit_loc.scroll_into_view_if_needed()
        page.wait_for_timeout(350)
        p_benefit = REAL_ASSETS_DIR / "shot_6_benefit_section.png"
        benefit_loc.screenshot(path=str(p_benefit))
        paths["benefit"] = p_benefit

        # 7. 홈페이지(/) 1안 토스 비즈니스 2분할 로그인 게이트웨이
        page.set_viewport_size({"width": 1280, "height": 820})
        page.goto(f"{base_url}/", wait_until="networkidle")
        page.wait_for_selector("text=Google 계정으로 시작하기 / 로그인")
        page.wait_for_timeout(500)
        p_portal = REAL_ASSETS_DIR / "shot_5_portal_login.png"
        page.screenshot(path=str(p_portal), full_page=False)
        paths["portal"] = p_portal

        browser.close()

    # 모바일 가독성 향상을 위한 2배 확대 단일 패널 크롭 이미지 생성
    paths["typing_zoom"] = save_zoom_crop(
        paths["typing"], REAL_ASSETS_DIR / "_tmp_typing_zoom.png", (0.018, 0.105, 0.495, 0.76)
    )
    paths["input_zoom"] = save_zoom_crop(
        paths["foot"], REAL_ASSETS_DIR / "shot_2_input_zoom.png", (0.018, 0.105, 0.495, 0.76)
    )
    paths["output_zoom"] = save_zoom_crop(
        paths["foot"], REAL_ASSETS_DIR / "shot_2_output_zoom.png", (0.502, 0.105, 0.982, 0.90)
    )
    paths["shoulder_zoom"] = save_zoom_crop(
        paths["shoulder"], REAL_ASSETS_DIR / "shot_3_output_zoom.png", (0.502, 0.105, 0.982, 0.90)
    )
    paths["copied_zoom"] = save_zoom_crop(
        paths["copied"], REAL_ASSETS_DIR / "shot_4_copied_zoom.png", (0.502, 0.105, 0.982, 0.88)
    )
    paths["login_zoom"] = save_zoom_crop(
        paths["portal"], REAL_ASSETS_DIR / "shot_5_login_zoom.png", (0.08, 0.06, 0.92, 0.88)
    )
    paths["benefit_zoom"] = save_zoom_crop(
        paths["benefit"], REAL_ASSETS_DIR / "shot_6_benefit_zoom.png", (0.01, 0.0, 0.535, 1.0)
    )
    return paths


def create_og_image(shot_foot_path: Path):
    """카카오톡/SNS 링크 공유용 1200x630 오픈그래프 썸네일 생성"""
    w, h = 1200, 630
    canvas = Image.new("RGB", (w, h), "#0F172A")
    draw = ImageDraw.Draw(canvas)

    # 좌측 타이포그래피 블록 (모바일 미리보기 가독성 확대)
    f_brand = get_font(FONT_BOLD, 38)
    f_badge = get_font(FONT_BOLD, 22)
    f_h1 = get_font(FONT_BOLD, 48)
    f_sub = get_font(FONT_REG, 26)
    f_url = get_font(FONT_BOLD, 24)

    draw.text((56, 48), "4THEPT", fill="#FFFFFF", font=f_brand)

    badge_text = "물리치료사·트레이너 AI 차팅 · 스케줄"
    bb = draw.textbbox((0, 0), badge_text, font=f_badge)
    bw = (bb[2] - bb[0]) + 34
    draw.rounded_rectangle([56, 112, 56 + bw, 156], radius=12, fill="#1E3A8A", outline="#3B82F6", width=2)
    draw.text((73, 120), badge_text, fill="#93C5FD", font=f_badge)

    draw.text((56, 190), "키워드 1줄 입력으로", fill="#FFFFFF", font=f_h1)
    draw.text((56, 254), "5초 만에 치료기록 [초안]", fill="#60A5FA", font=f_h1)

    draw.text((56, 344), "로그인 없이 바로 5초 체험 가능", fill="#CBD5E1", font=f_sub)
    draw.text((56, 386), "매월 120건 무료 · THEPT 회원 월 300건", fill="#CBD5E1", font=f_sub)

    url_text = "www.4thept.com/intro"
    ub = draw.textbbox((0, 0), url_text, font=f_url)
    uw = (ub[2] - ub[0]) + 52
    draw.rounded_rectangle([56, 492, 56 + uw, 558], radius=16, fill="#2563EB")
    draw.text((82, 510), url_text, fill="#FFFFFF", font=f_url)

    # 우측 실제 앱 단일 패널 2배 확대 스크린샷 카드 프레임
    shot = Image.open(shot_foot_path).convert("RGB")
    target_w = 500
    target_h = int(shot.height * (target_w / shot.width))
    if target_h > 540:
        target_h = 540
        target_w = int(shot.width * (target_h / shot.height))
    shot_resized = shot.resize((target_w, target_h), Image.Resampling.LANCZOS)

    mask = Image.new("L", (target_w, target_h), 0)
    ImageDraw.Draw(mask).rounded_rectangle([0, 0, target_w, target_h], radius=22, fill=255)

    x_pos = 1200 - target_w - 40
    y_pos = (h - target_h) // 2
    draw.rounded_rectangle([x_pos - 6, y_pos - 6, x_pos + target_w + 6, y_pos + target_h + 6], radius=26, fill="#1E293B")
    canvas.paste(shot_resized, (x_pos, y_pos), mask)

    out_real = REAL_ASSETS_DIR / "og-image.png"
    canvas.save(str(out_real), "PNG", optimize=True)
    if PUBLIC_DIR.exists():
        canvas.save(str(PUBLIC_DIR / "og-image.png"), "PNG", optimize=True)


def create_loop_gif(paths: dict[str, Path]):
    """네이버 블로그/카페/단톡방 최상단 삽입용 6초 실제 화면 작동 GIF (단일 패널 확대본)"""
    w, h = 960, 680
    header_h = 84
    footer_h = 52
    frame_specs = [
        (paths["typing_zoom"], "STEP 1 · 문장 대신 키워드 1줄 입력", "#2563EB", 1400),
        (paths["output_zoom"], "STEP 2 · 5초 만에 EMR 5단락 [초안] 완성", "#0F172A", 2100),
        (paths["shoulder_zoom"], "STEP 2 · 부위별(발목·경추·요추·어깨) 전환", "#2563EB", 1500),
        (paths["copied_zoom"], "STEP 3 · 직접 검수 후 [EMR 양식 복사] 완료", "#059669", 1800),
    ]

    f_title = get_font(FONT_BOLD, 30)
    f_badge = get_font(FONT_BOLD, 20)
    f_foot = get_font(FONT_REG, 19)

    frames = []
    durations = []

    for img_path, caption, accent, dur_ms in frame_specs:
        shot = Image.open(img_path).convert("RGB")
        avail_w = w - 44
        avail_h = h - header_h - footer_h - 20
        scale = min(avail_w / shot.width, avail_h / shot.height)
        nw = int(shot.width * scale)
        nh = int(shot.height * scale)
        resized = shot.resize((nw, nh), Image.Resampling.LANCZOS)

        page_img = Image.new("RGB", (w, h), "#F8F9FA")
        draw = ImageDraw.Draw(page_img)

        # 상단 캡션 바
        draw.rectangle([0, 0, w, header_h], fill="#FFFFFF")
        draw.line([0, header_h, w, header_h], fill="#E2E8F0", width=2)
        draw.rounded_rectangle([24, 21, 138, 61], radius=10, fill=accent)
        draw.text((39, 28), "4THEPT", fill="#FFFFFF", font=f_badge)
        draw.text((156, 24), caption, fill="#0F172A", font=f_title)

        # 스크린샷 배치
        sx = (w - nw) // 2
        sy = header_h + (avail_h - nh) // 2 + 10
        page_img.paste(resized, (sx, sy))

        # 하단 푸터
        draw.rectangle([0, h - footer_h, w, h], fill="#0F172A")
        draw.text(
            (24, h - 38),
            "www.4thept.com/intro  |  비로그인 5초 체험 · 월 120건 무료 · AI [초안] 검수 필수",
            fill="#E2E8F0",
            font=f_foot,
        )

        frames.append(page_img.convert("P", palette=Image.Palette.ADAPTIVE, colors=256))
        durations.append(dur_ms)

    # 임시 타이핑 이미지 정리
    for tmp_key in ("typing", "typing_zoom"):
        tmp = paths.get(tmp_key)
        if tmp and tmp.exists():
            tmp.unlink()

    gif_out = REAL_ASSETS_DIR / "demo_5s_charting_loop.gif"
    frames[0].save(
        str(gif_out),
        save_all=True,
        append_images=frames[1:],
        duration=durations,
        loop=0,
        optimize=True,
    )


def main():
    use_local = (BOOK_DIR / "dist").exists()
    print(f"[1/3] Source UI target: {'local vite preview' if use_local else 'https://www.4thept.com'}...")
    proc = start_preview_server(4173) if use_local else None
    try:
        base_url = "http://127.0.0.1:4173" if use_local else "https://www.4thept.com"
        print("[2/3] Capturing high-res screenshots via Playwright...")
        paths = capture_real_screenshots(base_url)
        print(f"Captured {len(paths)} assets into {REAL_ASSETS_DIR}")

        print("[3/3] Generating OG thumbnail (1200x630) and 6s real-UI loop GIF...")
        create_og_image(paths["output_zoom"])
        create_loop_gif(paths)
        print("[OK] Generated og-image.png and demo_5s_charting_loop.gif")
    finally:
        if proc is not None:
            proc.terminate()
            try:
                proc.wait(timeout=5)
            except Exception:
                proc.kill()


if __name__ == "__main__":
    main()
