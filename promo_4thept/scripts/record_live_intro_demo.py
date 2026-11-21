"""Record real 30fps live 4THEPT /intro UI interactions with 2.2x zoomed clinical typography.

Outputs crisp 1000x840 MP4 clips into `docs/promo/media_library/ui_recordings/`:
- ui_01_bodychart_typing.mp4 : enlarged memo input card ONLY (body-chart box hidden) + live typing
- ui_02_soap_generate.mp4    : enlarged converted detailed EMR clinical charting result (Sections 1-5)
- ui_03_emr_copy_benefit.mp4 : quick clinician review sweep + enlarged [EMR 양식 복사] -> copied state
"""

from __future__ import annotations

import subprocess
import tempfile
import time
import urllib.request
from pathlib import Path

from playwright.sync_api import Locator, Page, sync_playwright

import os

PROMO_DIR = Path(__file__).resolve().parents[1]
FOURTHEPT_ROOT = Path(os.getenv("FOURTHEPT_WORKSPACE_DIR", r"c:\개발\4THEPT"))
BOOK_DIR = FOURTHEPT_ROOT / "book"
OUT_DIR = PROMO_DIR / "media_library" / "ui_recordings"
OUT_DIR.mkdir(parents=True, exist_ok=True)

VP_W = 1000
VP_H = 840
TARGET_W = 1000
TARGET_H = 840


CURSOR_AND_ZOOM_SCRIPT = """
(() => {
  if (!document.getElementById('v2-zoom-style')) {
    const style = document.createElement('style');
    style.id = 'v2-zoom-style';
    style.textContent = `
      ::-webkit-scrollbar { display: none !important; }
      html, body {
        scrollbar-width: none !important;
        -ms-overflow-style: none !important;
        background: #ffffff !important;
      }
      header.sticky { display: none !important; }
      main {
        padding: 0 !important;
        margin: 0 !important;
        max-width: none !important;
      }
      main > section:not(#trial-section) { display: none !important; }
      #trial-section { margin: 0 !important; padding: 0 !important; }
      #trial-section > div {
        border: none !important;
        border-radius: 0 !important;
        box-shadow: none !important;
      }
      #v2-cursor-root {
        position: fixed;
        inset: 0;
        pointer-events: none;
        z-index: 2147483647;
      }
      #v2-cursor {
        position: fixed;
        left: 500px;
        top: 420px;
        width: 42px;
        height: 50px;
        transform: translate(-4px, -3px);
        filter: drop-shadow(0 6px 14px rgba(15, 23, 42, 0.45));
        transition: transform 0.08s ease-out;
        will-change: left, top, transform;
      }
      #v2-cursor.clicking {
        transform: translate(-4px, -3px) scale(0.84);
      }
      #v2-ripple {
        position: fixed;
        width: 64px;
        height: 64px;
        margin-left: -32px;
        margin-top: -32px;
        border-radius: 9999px;
        border: 4px solid #2563EB;
        background: rgba(37, 99, 235, 0.24);
        opacity: 0;
        transform: scale(0.35);
        pointer-events: none;
      }
      #v2-ripple.active {
        animation: v2RippleAnim 0.48s cubic-bezier(0.22, 1, 0.36, 1) forwards;
      }
      @keyframes v2KeepAlive {
        0%   { opacity: 0.96; }
        50%  { opacity: 1.00; }
        100% { opacity: 0.96; }
      }
      #v2-keepalive {
        position: fixed;
        right: 0; bottom: 0;
        width: 2px; height: 2px;
        background: #f8fafc;
        animation: v2KeepAlive 0.25s linear infinite;
        pointer-events: none;
      }
      @keyframes v2RippleAnim {
        0%   { opacity: 0.95; transform: scale(0.35); }
        100% { opacity: 0; transform: scale(1.95); }
      }
    `;
    document.head.appendChild(style);
  }

  if (!document.getElementById('v2-cursor-root')) {
    const root = document.createElement('div');
    root.id = 'v2-cursor-root';
    root.innerHTML = `
      <div id="v2-keepalive"></div>
      <div id="v2-ripple"></div>
      <svg id="v2-cursor" viewBox="0 0 28 34" fill="none" xmlns="http://www.w3.org/2000/svg">
        <path d="M3 2L24 16.5L14.2 18.6L19.4 29.2L15.6 31L10.3 20.4L3 26.8V2Z"
              fill="#0F172A" stroke="#FFFFFF" stroke-width="2.4" stroke-linejoin="round"/>
      </svg>
    `;
    document.body.appendChild(root);
  }

  window.__v2CursorPos = { x: 500, y: 420 };
  window.__setV2Cursor = (x, y) => {
    window.__v2CursorPos = { x, y };
    const el = document.getElementById('v2-cursor');
    if (el) {
      el.style.left = x + 'px';
      el.style.top = y + 'px';
    }
  };
  window.__triggerV2Click = (x, y) => {
    window.__setV2Cursor(x, y);
    const el = document.getElementById('v2-cursor');
    const rip = document.getElementById('v2-ripple');
    if (el) {
      el.classList.add('clicking');
      setTimeout(() => el.classList.remove('clicking'), 120);
    }
    if (rip) {
      rip.style.left = x + 'px';
      rip.style.top = y + 'px';
      rip.classList.remove('active');
      void rip.offsetWidth;
      rip.classList.add('active');
    }
  };
})();
"""


SETUP_INPUT_ZOOM_JS = """
(() => {
  const frame = document.querySelector('#trial-section > div');
  if (frame && frame.children[0]) frame.children[0].style.display = 'none';
  const grid = document.querySelector('#trial-section .grid');
  if (!grid) return;
  const leftPanel = grid.children[0];
  const rightPanel = grid.children[1];
  if (rightPanel) rightPanel.style.display = 'none';
  if (!leftPanel) return;

  leftPanel.style.padding = '36px 40px';
  leftPanel.style.minHeight = '840px';
  leftPanel.style.justifyContent = 'flex-start';
  leftPanel.style.gap = '24px';

  // Hide body-chart container completely so AI charting memo stands alone cleanly
  leftPanel.querySelectorAll('div').forEach(el => {
    const cls = (el.className || '').toString();
    if (cls.includes('bg-slate-50/80') && cls.includes('rounded-2xl') && el.textContent && el.textContent.includes('310구역 4면 바디차트')) {
      el.style.display = 'none';
    }
  });

  const h2 = leftPanel.querySelector('h2');
  if (h2) {
    h2.textContent = '시행한 치료 테크닉 · 환자 상태 입력';
    h2.style.fontSize = '36px';
    h2.style.fontWeight = '900';
    h2.style.lineHeight = '1.25';
    if (h2.nextElementSibling) {
      h2.nextElementSibling.textContent = '간단한 약어 · 나만의 메모 가능';
      h2.nextElementSibling.style.fontSize = '22px';
    }
  }

  const ta = leftPanel.querySelector('textarea');
  if (ta && ta.parentElement) {
    const wrap = ta.parentElement;
    wrap.style.minHeight = '520px';
    wrap.style.padding = '32px 34px';
    wrap.style.borderWidth = '3px';
    wrap.style.borderRadius = '28px';
    wrap.style.marginTop = '12px';
    ta.style.fontSize = '36px';
    ta.style.lineHeight = '1.58';
    ta.style.fontWeight = '700';
    ta.rows = 6;
    const foot = wrap.lastElementChild;
    if (foot) {
      foot.style.fontSize = '23px';
      foot.style.paddingTop = '18px';
      foot.style.marginTop = '18px';
      if (foot.children[0]) foot.children[0].textContent = '김OO 환자 · 도수치료 4회차';
      if (foot.children[1]) foot.children[1].textContent = '나만의 메모 입력 ➔ 상세 차팅 변환';
    }
  }

  const bottomRow = leftPanel.children[1];
  if (bottomRow) {
    bottomRow.style.fontSize = '22px';
    bottomRow.style.paddingTop = '12px';
    const sp = bottomRow.querySelector('span');
    if (sp) sp.textContent = '나만의 방식으로 간단히 기록해도 EMR 양식으로 변환됩니다';
    const btn = bottomRow.querySelector('button');
    if (btn) btn.style.display = 'none';
  }
  window.scrollTo(0, 0);
})();
"""


SETUP_OUTPUT_ZOOM_JS = """
((largeCopyBtn) => {
  const frame = document.querySelector('#trial-section > div');
  if (frame && frame.children[0]) frame.children[0].style.display = 'none';
  const grid = document.querySelector('#trial-section .grid');
  if (!grid) return;
  const leftPanel = grid.children[0];
  const rightPanel = grid.children[1];
  if (leftPanel) leftPanel.style.display = 'none';
  if (!rightPanel) return;

  rightPanel.style.padding = '28px 36px 40px 36px';
  rightPanel.style.background = '#F8FAFC';

  // Hide ONLY leaf body-chart line inside section 1 grid (never parent containers!)
  rightPanel.querySelectorAll('div').forEach(el => {
    if (el.children.length === 2 && el.children[0].tagName === 'SPAN' && el.children[0].textContent.includes('연동 바디차트')) {
      el.style.display = 'none';
    }
  });

  // Hide compliance paragraph under output card
  const bottomNote = rightPanel.lastElementChild;
  if (bottomNote && bottomNote.tagName === 'P') {
    bottomNote.style.display = 'none';
  }

  const h2 = rightPanel.querySelector('h2');
  if (h2) {
    h2.textContent = 'EMR 상세 차팅 변환 결과';
    h2.style.fontSize = '34px';
    h2.style.fontWeight = '900';
  }

  const copyBtn = rightPanel.querySelector('button');
  if (copyBtn) {
    copyBtn.style.fontSize = largeCopyBtn ? '28px' : '24px';
    copyBtn.style.padding = largeCopyBtn ? '14px 26px' : '11px 20px';
    copyBtn.style.borderRadius = '16px';
    copyBtn.style.fontWeight = '900';
  }

  const card = rightPanel.querySelector('.bg-white.rounded-2xl');
  if (card) {
    card.style.padding = '26px 30px';
    card.style.borderRadius = '24px';
    card.style.borderWidth = '2px';
    card.classList.remove('space-y-3.5');
    card.style.display = 'flex';
    card.style.flexDirection = 'column';
    card.style.gap = '18px';

    card.querySelectorAll('span, p, div').forEach(el => {
      const cls = (el.className || '').toString();
      if (cls.includes('text-blue-600') && el.tagName === 'SPAN') {
        el.style.fontSize = '24px';
        el.style.fontWeight = '900';
        el.style.marginBottom = '4px';
      } else if (el.tagName === 'P' || cls.includes('grid')) {
        el.style.fontSize = '26px';
        el.style.lineHeight = '1.52';
      } else if (cls.includes('pb-2.5')) {
        el.querySelectorAll('span').forEach(s => {
          s.style.fontSize = '24px';
        });
      }
    });
  }
  window.scrollTo(0, 0);
})
"""


def start_preview_server(port: int = 4173) -> subprocess.Popen:
    cmd = ["cmd", "/c", "npx", "vite", "preview", "--port", str(port), "--strictPort", "--host", "127.0.0.1"]
    proc = subprocess.Popen(
        cmd,
        cwd=str(BOOK_DIR),
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    url = f"http://127.0.0.1:{port}/intro"
    for _ in range(45):
        try:
            with urllib.request.urlopen(url, timeout=1.0) as resp:
                if resp.status == 200:
                    return proc
        except Exception:
            time.sleep(0.35)
    proc.terminate()
    raise RuntimeError("vite preview server did not start in time")


def smooth_move(page: Page, target_x: float, target_y: float, duration_ms: int = 380, steps: int = 18) -> None:
    cur = page.evaluate("() => window.__v2CursorPos || {x: 500, y: 420}")
    sx, sy = float(cur["x"]), float(cur["y"])
    dt = max(12, int(duration_ms / max(1, steps)))
    for i in range(1, steps + 1):
        u = i / steps
        eased = u * u * (3.0 - 2.0 * u)
        nx = sx + (target_x - sx) * eased
        ny = sy + (target_y - sy) * eased
        page.evaluate("([x, y]) => window.__setV2Cursor && window.__setV2Cursor(x, y)", [nx, ny])
        page.wait_for_timeout(dt)


def move_and_click(page: Page, locator: Locator, move_ms: int = 380, post_ms: int = 240) -> dict:
    box = locator.bounding_box()
    if not box:
        raise RuntimeError("Target locator has no bounding box")
    tx = box["x"] + box["width"] * 0.5
    ty = box["y"] + box["height"] * 0.5
    smooth_move(page, tx, ty, duration_ms=move_ms)
    page.evaluate("([x, y]) => window.__triggerV2Click && window.__triggerV2Click(x, y)", [tx, ty])
    locator.click()
    page.wait_for_timeout(post_ms)
    return box


def smooth_scroll_y(page: Page, target_y: float, duration_ms: int = 950) -> None:
    page.evaluate(
        """([target, dur]) => {
            const start = window.scrollY;
            const diff = target - start;
            const t0 = performance.now();
            function tick(now) {
                const u = Math.min(1, (now - t0) / dur);
                const ease = u * u * (3 - 2 * u);
                window.scrollTo(0, start + diff * ease);
                if (u < 1) requestAnimationFrame(tick);
            }
            requestAnimationFrame(tick);
        }""",
        [target_y, duration_ms],
    )
    page.wait_for_timeout(duration_ms + 80)


def transcode_trim_crop(webm_path: Path, out_mp4: Path, ss_sec: float, duration_sec: float) -> None:
    cmd = [
        "ffmpeg",
        "-y",
        "-ss",
        f"{ss_sec:.3f}",
        "-i",
        str(webm_path),
        "-t",
        f"{duration_sec:.3f}",
        "-vf",
        f"fps=30,scale={TARGET_W}:{TARGET_H}:flags=lanczos,eq=contrast=1.02:saturation=1.03",
        "-an",
        "-c:v",
        "libx264",
        "-preset",
        "medium",
        "-crf",
        "17",
        "-pix_fmt",
        "yuv420p",
        str(out_mp4),
    ]
    subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    dur_out = subprocess.check_output(
        [
            "ffprobe",
            "-v",
            "error",
            "-show_entries",
            "format=duration",
            "-of",
            "default=noprint_wrappers=1:nokey=1",
            str(out_mp4),
        ],
        text=True,
    ).strip()
    print(f"UI_CLIP OK: {out_mp4.name} | dur={dur_out}s | bytes={out_mp4.stat().st_size}")


def record_clip(base_url: str, mode: str, tmp_dir: Path) -> tuple[Path, float, float]:
    """Record one zoomed UI sequence and return (webm_path, start_trim_s, clip_dur_s)."""
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            viewport={"width": VP_W, "height": VP_H},
            device_scale_factor=1,
            locale="ko-KR",
            permissions=["clipboard-read", "clipboard-write"],
            record_video_dir=str(tmp_dir),
            record_video_size={"width": VP_W, "height": VP_H},
        )
        page = context.new_page()
        t_open = time.monotonic()
        page.goto(f"{base_url}/intro", wait_until="networkidle")
        page.wait_for_selector("#trial-section")
        page.evaluate(CURSOR_AND_ZOOM_SCRIPT)
        page.wait_for_timeout(120)

        if mode == "bodychart_typing":
            textarea = page.locator("textarea[aria-label='1줄 키워드 입력 체험']")
            textarea.fill("")
            page.evaluate(SETUP_INPUT_ZOOM_JS)
            page.evaluate("() => window.__setV2Cursor(780, 620)")
            page.wait_for_timeout(240)
            t_seq0 = time.monotonic()

            move_and_click(page, textarea, move_ms=340, post_ms=140)
            textarea.type(
                "우측 어깨 도수치료 및 회전근개 이완, 견갑골 안정화 운동 시행, 굴곡 120->150도 개선, 통증 NRS 6->3",
                delay=25,
            )
            page.wait_for_timeout(1150)
            seq_wall = time.monotonic() - t_seq0

        elif mode == "soap_generate":
            page.locator("#trial-section").get_by_role("button", name="회전근개·관절가동").click()
            page.wait_for_timeout(260)
            page.evaluate(f"({SETUP_OUTPUT_ZOOM_JS})(false)")
            page.evaluate("() => window.__setV2Cursor(820, 680)")
            page.wait_for_timeout(240)
            t_seq0 = time.monotonic()

            # Brief subtle generation flash inside card
            page.evaluate(
                """() => {
                    const card = document.querySelector('#trial-section .bg-white.rounded-2xl');
                    if (card) {
                        card.style.transition = 'opacity 0.28s ease-out';
                        card.style.opacity = '0.35';
                        setTimeout(() => { card.style.opacity = '1'; }, 160);
                    }
                }"""
            )
            page.wait_for_timeout(1350)
            smooth_scroll_y(page, 280, duration_ms=1050)
            page.wait_for_timeout(1350)
            seq_wall = time.monotonic() - t_seq0

        elif mode == "emr_copy_benefit":
            page.locator("#trial-section").get_by_role("button", name="회전근개·관절가동").click()
            page.wait_for_timeout(260)
            page.evaluate(f"({SETUP_OUTPUT_ZOOM_JS})(true)")
            page.evaluate("() => window.__setV2Cursor(220, 420)")
            page.wait_for_timeout(240)
            t_seq0 = time.monotonic()

            # Quick clinician review sweep across evaluation & intervention before clicking Copy
            smooth_move(page, 640, 490, duration_ms=520, steps=20)
            page.wait_for_timeout(320)
            copy_btn = page.locator("#trial-section").get_by_role("button", name="EMR 양식 복사")
            box = move_and_click(page, copy_btn, move_ms=480, post_ms=1750)
            print(f"UI_03_COPY_BTN_BOX={box}")
            seq_wall = time.monotonic() - t_seq0

        else:
            raise ValueError(f"Unknown mode: {mode}")

        video_obj = page.video
        context.close()
        browser.close()
        webm_path = Path(video_obj.path())
        webm_dur = float(
            subprocess.check_output(
                [
                    "ffprobe",
                    "-v",
                    "error",
                    "-show_entries",
                    "format=duration",
                    "-of",
                    "default=noprint_wrappers=1:nokey=1",
                    str(webm_path),
                ],
                text=True,
            ).strip()
        )
        start_trim = max(0.0, webm_dur - seq_wall - 0.10)
        clip_dur = min(4.8, webm_dur - start_trim)
        return webm_path, start_trim, max(3.6, clip_dur)


def main() -> None:
    use_local = (BOOK_DIR / "dist").exists()
    proc = start_preview_server(4173) if use_local else None
    base_url = "http://127.0.0.1:4173" if use_local else "https://www.4thept.com"
    try:
        with tempfile.TemporaryDirectory() as td:
            tmp = Path(td)
            jobs = [
                ("bodychart_typing", OUT_DIR / "ui_01_bodychart_typing.mp4"),
                ("soap_generate", OUT_DIR / "ui_02_soap_generate.mp4"),
                ("emr_copy_benefit", OUT_DIR / "ui_03_emr_copy_benefit.mp4"),
            ]
            for mode, out_mp4 in jobs:
                sub = tmp / mode
                sub.mkdir(parents=True, exist_ok=True)
                webm_path, ss_sec, dur_sec = record_clip(base_url, mode, sub)
                transcode_trim_crop(webm_path, out_mp4, ss_sec, dur_sec)
    finally:
        if proc is not None:
            proc.terminate()
            try:
                proc.wait(timeout=5)
            except Exception:
                proc.kill()


if __name__ == "__main__":
    main()
