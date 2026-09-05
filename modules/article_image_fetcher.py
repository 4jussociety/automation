# 이 모듈은 뉴스 기사 웹페이지에서 실제 고화질 보도 사진, 기사 본문 텍스트 및 원문 풀 제목을 크롤링합니다.
# 네이버 API의 제목 잘림을 원문 og:title로 정밀 복원하며, 카드뉴스 및 쇼츠의 완성도를 극대화합니다.

import sys
from pathlib import Path
import asyncio
import re
import requests
from playwright.async_api import async_playwright

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass


def clean_article_title(title: str) -> str:
    """웹페이지 og:title/h1에서 언론사명 접미사 및 웹페이지 노이즈를 제거하여 순수 기사 제목을 추출합니다."""
    if not title:
        return ""
    t = title.strip()
    # 1. HTML 엔티티 제거
    t = t.replace('&quot;', '"').replace('&apos;', "'").replace('&amp;', '&')
    t = t.replace('&lt;', '<').replace('&gt;', '>').replace('&middot;', '·')
    t = t.replace('&nbsp;', ' ')
    
    # 2. 흔한 언론사 웹페이지 구분자 뒤의 언론사명 제거
    # 예: " - 인더스트리뉴스", " | 한국경제", " : 동아일보"
    t = re.sub(r'\s*[\-–—|:]\s*[가-힣a-zA-Z0-9\s]{2,15}$', '', t)
    # 예: " < 기사본문 - 인더스트리뉴스"
    t = re.sub(r'\s*<.*$', '', t)
    # 예: "[포토]", "[속보]" 등 불필요한 단순 말머리 제거
    t = re.sub(r'\[포토\]|\[단독\]|\[속보\]', '', t)
    
    # 3. 말줄임표 제거
    t = t.replace('...', '').replace('…', '').replace('..', '').strip()
    return t


from modules.translator import translate_to_korean


async def fetch_article_images(articles: list[dict], bg_dir: Path, prefix: str = "news") -> dict[int, Path]:
    """
    Playwright를 사용하여 뉴스 링크의 실제 언론사 페이지로 리다이렉트 후,
    원문 보도 사진, 기사 본문 텍스트 및 온전한 원문 제목을 검수/추출합니다.
    - 외신 기사는 100% 한국어로 번역하여 반영합니다.
    - 보도 사진: {슬라이드번호(1-based): 파일경로} 딕셔너리로 반환
    - 기사 제목: art['title']에 잘리지 않은 원문 풀 제목 반영
    - 기사 본문: art['article_body']에 본문 텍스트 저장
    """
    results = {}
    bg_dir.mkdir(parents=True, exist_ok=True)

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36"
            )
        )
        page = await context.new_page()

        for idx, art in enumerate(articles[:3], start=1):
            target_path = bg_dir / f"{prefix}_{idx:02d}_article_photo.jpg"
            title_brief = art.get("title", "")[:30]
            print(f"  [{idx}/3] 기사 사진/본문 및 원문 제목 검수 중: {title_brief}...")

            try:
                # 1. 언론사 원문 링크로 리다이렉트 대기
                await page.goto(art["link"], wait_until="domcontentloaded", timeout=12000)
                await page.wait_for_timeout(2000)

                # 2. 웹페이지 원문 제목 검수 및 복원 (네이버 API의 40자 말줄임 제목 완벽 복원 및 외신 번역)
                raw_full_title = await page.evaluate('''() => {
                    // 1순위: og:title 또는 twitter:title (언론사가 등록한 표준 풀 제목)
                    const og = document.querySelector('meta[property="og:title"]') || 
                               document.querySelector('meta[name="og:title"]') ||
                               document.querySelector('meta[name="twitter:title"]');
                    if (og && og.content && og.content.trim().length >= 8) {
                        return og.content.trim();
                    }
                    // 2순위: 기사 헤드라인 태그 (h1)
                    const h1 = document.querySelector('.article-head-title, .news_title, #articleTitle, h1.headline, h1.tit, article h1, h1');
                    if (h1 && h1.innerText && h1.innerText.trim().length >= 8) {
                        return h1.innerText.trim();
                    }
                    // 3순위: document.title
                    if (document.title && document.title.trim().length >= 8) {
                        return document.title.trim();
                    }
                    return null;
                }''')

                if raw_full_title:
                    verified_title = clean_article_title(raw_full_title)
                    # 외신 기사이거나 영문일 경우 즉시 한국어로 번역 반영
                    from modules.translator import is_english_text
                    if art.get("is_global") or prefix == "b3" or is_english_text(verified_title):
                        ko_title = translate_to_korean(verified_title)
                        print(f"     🌐 외신 풀 제목 한국어 번역 완료: '{ko_title}'")
                        art["title"] = ko_title
                    elif len(verified_title) >= len(art.get("title", "")) or "..." in art.get("title", ""):
                        print(f"     📰 원문 풀 제목 검수 완료: '{verified_title}'")
                        art["title"] = verified_title

                # 3. 기사 본문 텍스트 추출
                body_text = await page.evaluate('''() => {
                    const selectors = [
                        '#dic_area', '#newsct_article', '#articleBody', '#article-view-content-div',
                        '.article-body', '.news_view', '[itemprop="articleBody"]', 'article', '.article_view'
                    ];
                    for (const sel of selectors) {
                        const el = document.querySelector(sel);
                        if (el) {
                            const clone = el.cloneNode(true);
                            clone.querySelectorAll('script, style, iframe, figcaption, .caption, .reporter_area, .byline, header, footer, nav, .ad, .advertisement').forEach(n => n.remove());
                            const text = clone.innerText.trim();
                            if (text && text.length > 50) {
                                return text;
                            }
                        }
                    }
                    const ps = Array.from(document.querySelectorAll('p'));
                    const valid = ps.map(p => p.innerText.trim()).filter(t => t.length > 25 && !t.includes('기자') && !t.includes('무단전재') && !t.includes('저작권') && !t.includes('배포금지'));
                    return valid.length > 0 ? valid.slice(0, 8).join('\\n') : '';
                }''')
                if body_text:
                    clean_b = body_text.strip()
                    from modules.translator import is_english_text
                    if art.get("is_global") or prefix == "b3" or is_english_text(clean_b):
                        clean_b = translate_to_korean(clean_b[:500])
                    art["article_body"] = clean_b
                    print(f"     📄 기사 본문 텍스트 획득 ({len(art['article_body'])}자)")

                # 3. og:image 및 본문 대표 보도사진 태그 추출
                img_url = await page.evaluate('''() => {
                    // og:image 또는 twitter:image 탐색
                    const og = document.querySelector('meta[property="og:image"]') || 
                               document.querySelector('meta[name="og:image"]') ||
                               document.querySelector('meta[name="twitter:image"]');
                    if (og && og.content && !og.content.includes("logo") && !og.content.includes("googleusercontent") && !og.content.includes("icon")) {
                        return og.content;
                    }
                    // 기사 본문 내 대표 보도사진 탐색
                    const candidates = Array.from(document.querySelectorAll(
                        'article img, .article img, #article img, #articleBody img, .news_view img, amp-img, img'
                    ));
                    for (const el of candidates) {
                        const src = el.src || el.getAttribute('src') || el.getAttribute('data-src');
                        if (src && (src.includes('/photo/') || src.includes('/upload/') || src.includes('article') || src.includes('news'))) {
                            if (!src.includes('logo') && !src.includes('icon') && !src.includes('banner')) {
                                return src;
                            }
                        }
                    }
                    return null;
                }''')

                # 4. 유효한 이미지일 경우 로컬에 다운로드
                if img_url and img_url.startswith("http"):
                    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
                    resp = requests.get(img_url, headers=headers, timeout=10)
                    if resp.status_code == 200 and len(resp.content) > 3000:
                        target_path.write_bytes(resp.content)
                        results[idx] = target_path
                        print(f"     ✅ 보도 사진 획득 완료: {target_path.name} ({len(resp.content)/1024:.1f} KB)")
                        continue

                print(f"     ℹ️ 기사 사진 없음 -> 보도사진 풀/기본 배경 적용 예정")

            except Exception as e:
                print(f"     ⚠️ 기사 페이지 크롤링 패스 ({e}) -> 기본 요약 및 풀 배경 적용")

        await browser.close()

    return results

