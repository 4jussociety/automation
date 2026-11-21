"""Render 18 card-news PNGs (1080x1350 4:5 vertical) from docs/promo/pt_hospital_viral_kit.html."""

from __future__ import annotations

import functools
import http.server
import socketserver
import threading
import time
from pathlib import Path

from playwright.sync_api import sync_playwright

PROMO_DIR = Path(__file__).resolve().parents[1]
AUTO_ROOT = PROMO_DIR.parent
CARDS_DIR = AUTO_ROOT / "결과물" / "4THEPT마케팅" / "cards"

THEME_PREFIX = {
    "CHEAT_SHEET": "card_cheatsheet",
    "REAL_SCREEN": "card_real",
    "KAKAO_POSTER": "card_kakao",
    "CENTER_PACK": "card_center",
}


class QuietHandler(http.server.SimpleHTTPRequestHandler):
    def log_message(self, format: str, *args) -> None:  # noqa: A002
        return


class ReusableTCPServer(socketserver.ThreadingMixIn, http.server.HTTPServer):
    daemon_threads = True


def start_static_server(directory: Path) -> tuple[ReusableTCPServer, int]:
    handler = functools.partial(QuietHandler, directory=str(directory))
    server = ReusableTCPServer(("127.0.0.1", 0), handler)
    port = server.server_address[1]
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return server, port


def main() -> None:
    CARDS_DIR.mkdir(parents=True, exist_ok=True)
    server, port = start_static_server(PROMO_DIR)
    url = f"http://127.0.0.1:{port}/pt_hospital_viral_kit.html"

    exported: list[tuple[str, int]] = []
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            context = browser.new_context(
                viewport={"width": 1200, "height": 1500},
                device_scale_factor=1,
            )
            page = context.new_page()
            page.goto(url, wait_until="networkidle")
            page.evaluate("() => document.fonts.ready")

            theme_counts = page.evaluate(
                "() => Object.fromEntries(Object.entries(THEMES).map(([k, v]) => [k, v.cards.length]))"
            )
            print("Detected themes:", theme_counts)

            for theme_key, prefix in THEME_PREFIX.items():
                count = int(theme_counts[theme_key])
                for idx in range(count):
                    page.evaluate(
                        """({ themeKey, index, total }) => {
                            let stage = document.getElementById('playwright-export-stage');
                            if (!stage) {
                                stage = document.createElement('div');
                                stage.id = 'playwright-export-stage';
                                stage.style.position = 'fixed';
                                stage.style.top = '0';
                                stage.style.left = '0';
                                stage.style.width = '1080px';
                                stage.style.height = '1350px';
                                stage.style.zIndex = '2147483647';
                                stage.style.margin = '0';
                                stage.style.padding = '0';
                                stage.style.overflow = 'hidden';
                                stage.style.background = '#ffffff';
                                document.body.appendChild(stage);
                            }
                            const cardObj = THEMES[themeKey].cards[index];
                            stage.innerHTML = cardHtml(cardObj, index, total, themeKey);
                            const cardEl = stage.querySelector('.card');
                            if (cardEl) {
                                cardEl.style.transform = 'none';
                                cardEl.style.margin = '0';
                                cardEl.style.width = '1080px';
                                cardEl.style.height = '1350px';
                            }
                        }""",
                        {"themeKey": theme_key, "index": idx, "total": count},
                    )
                    # Wait for images inside the rendered card to load & decode cleanly.
                    broken_imgs = page.evaluate(
                        """async () => {
                            await document.fonts.ready;
                            const imgs = Array.from(document.querySelectorAll('#playwright-export-stage img'));
                            await Promise.all(imgs.map((img) => {
                                if (img.complete) return img.decode ? img.decode().catch(() => {}) : Promise.resolve();
                                return new Promise((resolve) => {
                                    img.addEventListener('load', () => resolve(), { once: true });
                                    img.addEventListener('error', () => resolve(), { once: true });
                                });
                            }));
                            return imgs.filter((img) => img.naturalWidth === 0).map((img) => img.getAttribute('src'));
                        }"""
                    )
                    if broken_imgs:
                        raise RuntimeError(f"Broken image(s) in {theme_key} card {idx + 1}: {broken_imgs}")

                    time.sleep(0.08)
                    out_file = CARDS_DIR / f"{prefix}_{idx + 1:02d}.png"
                    card_loc = page.locator("#playwright-export-stage .card").first
                    box = card_loc.bounding_box()
                    if not box or round(box["width"]) != 1080 or round(box["height"]) != 1350:
                        raise RuntimeError(f"Unexpected bounding box for {out_file.name}: {box}")
                    card_loc.screenshot(path=str(out_file), type="png")
                    exported.append((out_file.name, out_file.stat().st_size))

            browser.close()
    finally:
        server.shutdown()

    print(f"Exported {len(exported)} cards into {CARDS_DIR}:")
    for name, size in exported:
        print(f"  - {name}: {size:,} bytes")


if __name__ == "__main__":
    main()
