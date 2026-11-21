#!/usr/bin/env python3
"""4THEPT 2단계 바이럴 광고 · 고조회수 쇼츠 수집기 (YouTube Data API + Meta Ad Library).

1단계(대량 필터):
- YouTube Data API v3 (`자동화에이전트` 루트 단일 `token.pickle` 읽기 전용 참조, 메모리 내 토큰 갱신)로
  업종 무관 국내 고조회수 쇼츠(10~65초) 30~50건 수집 및 본인/PT·트레이너 운동 영상 제외
- Meta Ad Library(한국 active 광고) Playwright 수집으로 장기집행(`active_days`) 상위 광고 최대 25건 추출
  (로그인/CAPTCHA 차단 시 우회하지 않고 graceful하게 `blocked_or_gated` 상태로 기록 후 계속 진행)

2단계(상위권 심층 해부):
- YouTube 상위 N편 한국어 자막(`youtube-transcript-api`) 0~3초 훅/마무리 CTA/말하기 속도(초당 글자수) 추출,
  상위 댓글 5개 수집 및 고해상도 썸네일 저장 (`promo_4thept/campaigns/benchmark_captures/yt_*.jpg`)
- Meta 장기집행 상위 광고 카드 캡처 (`promo_4thept/campaigns/benchmark_captures/meta_ad_*.png`)
- 결과를 `promo_4thept/campaigns/ad_benchmark_data.json`으로 저장
"""

from __future__ import annotations

import argparse
import json
import math
import os
import pickle
import re
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any
from urllib.parse import quote

import requests
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

PROMO_DIR = Path(__file__).resolve().parents[1]
AUTO_ROOT = PROMO_DIR.parent
PROMO_OUT_DIR = AUTO_ROOT / "결과물" / "4THEPT마케팅"
CAMPAIGNS_DIR = PROMO_DIR / "campaigns"
CAPTURES_DIR = PROMO_OUT_DIR / "benchmark_captures"
DEFAULT_OUT_JSON = CAMPAIGNS_DIR / "ad_benchmark_data.json"
DEFAULT_CRED_DIR = Path(os.getenv("THEPT_SNS_CRED_DIR", str(AUTO_ROOT)))

KST = timezone(timedelta(hours=9))
ISO_DURATION_RE = re.compile(r"^PT(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?$")

# 본인 채널 및 물리치료사/트레이너/운동 영상 제외 규칙
EXCLUDED_CHANNEL_IDS = {
    "UCVL8-z6DfDMaWi71b8RA7rw",  # 4THEPT (@4thept)
    "UCbwC2jK9J-179R2Un3T0xPA",  # THEPT
}
EXCLUDED_KEYWORDS = (
    "물리치료",
    "도수치료",
    "스트레칭",
    "거북목",
    "헬스트레이너",
    "필라테스",
    "재활운동",
    "허리통증",
    "어깨통증",
    "골반교정",
    "4thept",
    "포더피티",
    "더피티",
    "thept",
)

# 업종 무관 국내 최상위 바이럴 광고 · 고조회수 쇼츠 기본 검색어
DEFAULT_YOUTUBE_QUERIES = (
    "이거 모르면 손해 #shorts",
    "꿀템 추천 광고 #shorts",
    "무료 AI 앱 추천 #shorts",
    "월 매출 마케팅 비결 #shorts",
    "올리브영 다이소 추천템 #shorts",
)

DEFAULT_META_QUERIES = (
    "무료 체험",
    "할인 특가",
    "자동화 앱",
    "온라인 클래스",
    "크림 앰플",
)


def parse_iso_duration_sec(raw: str) -> int:
    m = ISO_DURATION_RE.match((raw or "").strip())
    if not m:
        return 0
    return int(m.group(1) or 0) * 3600 + int(m.group(2) or 0) * 60 + int(m.group(3) or 0)


def parse_iso_dt(raw: str) -> datetime:
    norm = (raw or "").strip()
    if norm.endswith("Z"):
        norm = norm[:-1] + "+00:00"
    return datetime.fromisoformat(norm)


def is_excluded_text(*parts: str) -> bool:
    blob = " ".join(p or "" for p in parts).lower()
    return any(kw in blob for kw in EXCLUDED_KEYWORDS)


def clean_text(raw: str) -> str:
    return re.sub(r"\s+", " ", (raw or "").replace("\n", " ")).strip()


def load_youtube_service(cred_dir: Path):
    yt_token_path = cred_dir / "token.pickle"
    if not yt_token_path.exists():
        raise FileNotFoundError(f"YouTube 토큰 파일 없음: {yt_token_path}")

    with open(yt_token_path, "rb") as f:
        creds = pickle.load(f)

    # Refresh strictly in memory without writing to cred_dir
    if not creds.valid:
        if creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            raise RuntimeError("YouTube OAuth 토큰 만료 및 refresh_token 없음")

    return build("youtube", "v3", credentials=creds)


def collect_youtube_shorts(
    svc: Any,
    queries: tuple[str, ...],
    days: int,
    max_candidates: int = 40,
) -> tuple[str, list[dict[str, Any]]]:
    """Stage 1: Collect & score high-view KR non-PT/trainer YouTube Shorts."""
    published_after = (datetime.now(timezone.utc) - timedelta(days=days)).strftime("%Y-%m-%dT%H:%M:%SZ")
    seen_ids: set[str] = set()
    id_to_query: dict[str, str] = {}
    unique_ids: list[str] = []

    try:
        for q in queries:
            s_res = (
                svc.search()
                .list(
                    part="id",
                    q=q,
                    type="video",
                    videoDuration="short",
                    regionCode="KR",
                    relevanceLanguage="ko",
                    order="viewCount",
                    publishedAfter=published_after,
                    maxResults=15,
                )
                .execute()
            )
            for item in s_res.get("items", []):
                vid = item.get("id", {}).get("videoId")
                if vid and vid not in seen_ids:
                    seen_ids.add(vid)
                    id_to_query[vid] = q
                    unique_ids.append(vid)
    except HttpError as exc:
        return (f"error:{exc.resp.status if exc.resp else 'http'}", [])
    except Exception as exc:
        return (f"error:{type(exc).__name__}", [])

    now_utc = datetime.now(timezone.utc)
    pool: list[dict[str, Any]] = []
    for idx in range(0, len(unique_ids), 50):
        chunk = unique_ids[idx : idx + 50]
        try:
            v_res = svc.videos().list(part="snippet,contentDetails,statistics", id=",".join(chunk)).execute()
        except Exception:
            continue

        for v in v_res.get("items", []):
            vid = v.get("id", "")
            sn = v.get("snippet", {})
            st = v.get("statistics", {})
            cd = v.get("contentDetails", {})

            ch_id = sn.get("channelId", "")
            ch_title = sn.get("channelTitle", "")
            title = sn.get("title", "")
            desc = sn.get("description", "")
            tags = sn.get("tags", []) or []

            if ch_id in EXCLUDED_CHANNEL_IDS:
                continue
            if is_excluded_text(title, desc, ch_title, " ".join(tags)):
                continue

            dur_sec = parse_iso_duration_sec(cd.get("duration", ""))
            if dur_sec < 10 or dur_sec > 65:
                continue

            views = int(st.get("viewCount", 0) or 0)
            likes = int(st.get("likeCount", 0) or 0)
            comments = int(st.get("commentCount", 0) or 0)

            pub_dt = parse_iso_dt(sn.get("publishedAt", now_utc.isoformat()))
            age_days = max(1, (now_utc - pub_dt).days)
            views_per_day = round(views / age_days, 1)
            engagement_rate = round((likes + comments) / max(1, views) * 100.0, 3)
            composite = round(
                math.log10(max(10, views)) * 20.0
                + min(engagement_rate, 10.0) * 4.0
                + math.log10(max(10, views_per_day)) * 10.0,
                2,
            )

            thumbs = sn.get("thumbnails", {}) or {}
            thumb_url = (
                (thumbs.get("maxres") or {}).get("url")
                or (thumbs.get("standard") or {}).get("url")
                or (thumbs.get("high") or {}).get("url")
                or f"https://i.ytimg.com/vi/{vid}/hqdefault.jpg"
            )

            pool.append(
                {
                    "video_id": vid,
                    "url": f"https://www.youtube.com/shorts/{vid}",
                    "query": id_to_query.get(vid, ""),
                    "channel_id": ch_id,
                    "channel_title": ch_title,
                    "title": title,
                    "published_kst": pub_dt.astimezone(KST).strftime("%Y-%m-%d"),
                    "age_days": age_days,
                    "duration_sec": dur_sec,
                    "views": views,
                    "likes": likes,
                    "comments_count": comments,
                    "views_per_day": views_per_day,
                    "engagement_rate": engagement_rate,
                    "composite_score": composite,
                    "thumb_url": thumb_url,
                    "tags": tags[:10],
                }
            )

    # Apply view thresholds with graceful fallback
    tier30k = [x for x in pool if x["views"] >= 30_000]
    if len(tier30k) >= 8:
        selected = tier30k
    else:
        tier10k = [x for x in pool if x["views"] >= 10_000]
        selected = tier10k if len(tier10k) >= 5 else pool

    selected.sort(key=lambda x: (x["composite_score"], x["views"]), reverse=True)
    return ("ok", selected[:max_candidates])


def _fetch_transcript_items(vid: str) -> list[tuple[float, float, str]]:
    """Support both youtube-transcript-api v1.x (fetch) and v0.6.x (get_transcript)."""
    from youtube_transcript_api import YouTubeTranscriptApi  # type: ignore

    raw_items: Any = None
    if hasattr(YouTubeTranscriptApi, "get_transcript"):
        try:
            raw_items = YouTubeTranscriptApi.get_transcript(vid, languages=["ko", "ko-KR", "en"])
        except Exception:
            raw_items = None
    if raw_items is None:
        api = YouTubeTranscriptApi()
        if hasattr(api, "fetch"):
            raw_items = api.fetch(vid, languages=["ko", "ko-KR", "en"])

    parsed: list[tuple[float, float, str]] = []
    if not raw_items:
        return parsed
    for sn in raw_items:
        if isinstance(sn, dict):
            start = float(sn.get("start", 0.0) or 0.0)
            dur = float(sn.get("duration", 0.0) or 0.0)
            text = clean_text(str(sn.get("text", "") or ""))
        else:
            start = float(getattr(sn, "start", 0.0) or 0.0)
            dur = float(getattr(sn, "duration", 0.0) or 0.0)
            text = clean_text(str(getattr(sn, "text", "") or ""))
        if text:
            parsed.append((start, dur, text))
    return parsed


def _download_thumbnail(vid: str, fallback_url: str, dst: Path) -> str | None:
    candidates = [
        f"https://i.ytimg.com/vi/{vid}/maxresdefault.jpg",
        f"https://i.ytimg.com/vi/{vid}/hqdefault.jpg",
        fallback_url,
    ]
    for url in candidates:
        if not url:
            continue
        try:
            resp = requests.get(url, timeout=8)
            if resp.status_code == 200 and len(resp.content) > 2500:
                dst.write_bytes(resp.content)
                return str(dst.relative_to(PROMO_DIR)).replace("\\", "/")
        except Exception:
            continue
    return None


def enrich_youtube_deep(svc: Any, candidates: list[dict[str, Any]], deep_top: int) -> list[dict[str, Any]]:
    """Stage 2: Extract transcripts, top comments, and save thumbnails for top winners."""
    CAPTURES_DIR.mkdir(parents=True, exist_ok=True)
    for old_thumb in CAPTURES_DIR.glob("yt_*.jpg"):
        old_thumb.unlink(missing_ok=True)

    winners: list[dict[str, Any]] = []
    for rank, item in enumerate(candidates[:deep_top], 1):
        vid = item["video_id"]
        entry = dict(item)
        entry["rank"] = rank

        thumb_path = CAPTURES_DIR / f"yt_{rank:02d}_{vid}.jpg"
        entry["local_thumb"] = _download_thumbnail(vid, item.get("thumb_url", ""), thumb_path)

        # Transcript deep teardown
        try:
            snippets = _fetch_transcript_items(vid)
        except Exception as exc:
            snippets = []
            entry["transcript_status"] = f"unavailable:{type(exc).__name__}"
        else:
            entry["transcript_status"] = "ok" if snippets else "empty"

        if snippets:
            hook_parts = [t for (st, _d, t) in snippets if st <= 3.5]
            if not hook_parts:
                hook_parts = [snippets[0][2]]
            cta_cutoff = max(0.0, float(item.get("duration_sec", 0)) - 6.0)
            cta_parts = [t for (st, _d, t) in snippets if st >= cta_cutoff]
            if not cta_parts:
                cta_parts = [t for (_st, _d, t) in snippets[-2:]]

            full_text = clean_text(" ".join(t for (_st, _d, t) in snippets))
            spoken_start = snippets[0][0]
            spoken_end = max(spoken_start + 1.0, snippets[-1][0] + max(1.0, snippets[-1][1]))
            non_space_chars = len(re.sub(r"\s+", "", full_text))
            entry["hook_0_3s"] = clean_text(" ".join(hook_parts))[:180]
            entry["cta_last_5s"] = clean_text(" ".join(cta_parts))[:180]
            entry["chars_per_sec"] = round(non_space_chars / (spoken_end - spoken_start), 2)
            entry["transcript_preview"] = full_text[:450]
        else:
            entry["hook_0_3s"] = ""
            entry["cta_last_5s"] = ""
            entry["chars_per_sec"] = 0.0
            entry["transcript_preview"] = ""

        # Top viewer comments
        top_comments: list[str] = []
        try:
            c_res = (
                svc.commentThreads()
                .list(part="snippet", videoId=vid, order="relevance", maxResults=5, textFormat="plainText")
                .execute()
            )
            for c_item in c_res.get("items", []):
                c_sn = ((c_item.get("snippet") or {}).get("topLevelComment") or {}).get("snippet") or {}
                txt = clean_text(c_sn.get("textDisplay", ""))
                if txt:
                    top_comments.append(txt[:160])
        except Exception:
            pass
        entry["top_comments"] = top_comments
        winners.append(entry)

    return winners


def _parse_started_days(raw_text: str) -> tuple[str, int]:
    """Parse '2025. 10. 15.' or 'Oct 15, 2025' style Meta Ad Library start dates into active_days."""
    now_kst = datetime.now(KST).date()
    m_kr = re.search(r"(\d{4})\.\s*(\d{1,2})\.\s*(\d{1,2})\.", raw_text)
    if m_kr:
        try:
            dt = datetime(int(m_kr.group(1)), int(m_kr.group(2)), int(m_kr.group(3))).date()
            return dt.isoformat(), max(1, (now_kst - dt).days)
        except ValueError:
            pass
    m_en = re.search(r"([A-Za-z]{3,9}\s+\d{1,2},\s+\d{4})", raw_text)
    if m_en:
        for fmt in ("%b %d, %Y", "%B %d, %Y"):
            try:
                dt = datetime.strptime(m_en.group(1), fmt).date()
                return dt.isoformat(), max(1, (now_kst - dt).days)
            except ValueError:
                continue
    return ("", 0)


def collect_meta_ad_library(queries: tuple[str, ...], max_ads: int = 25, max_captures: int = 5) -> tuple[str, list[dict[str, Any]]]:
    """Collect active KR ads from Meta Ad Library using Playwright; aborts gracefully on login/CAPTCHA gates."""
    CAPTURES_DIR.mkdir(parents=True, exist_ok=True)
    for old_png in CAPTURES_DIR.glob("meta_ad_*.png"):
        old_png.unlink(missing_ok=True)

    try:
        from playwright.sync_api import sync_playwright
    except Exception as exc:
        return (f"playwright_unavailable:{type(exc).__name__}", [])

    seen_keys: set[tuple[str, str]] = set()
    collected: list[dict[str, Any]] = []
    gated_count = 0

    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            context = browser.new_context(
                viewport={"width": 1440, "height": 1200},
                locale="ko-KR",
                user_agent=(
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                    "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
                ),
            )
            page = context.new_page()

            for q in queries:
                url = (
                    "https://www.facebook.com/ads/library/?active_status=active&ad_type=all"
                    f"&country=KR&is_targeted_country=false&media_type=all&q={quote(q)}&search_type=keyword_unordered"
                )
                try:
                    page.goto(url, wait_until="domcontentloaded", timeout=20000)
                    page.wait_for_timeout(3200)
                except Exception:
                    continue

                cur_url = page.url.lower()
                body_sample = ""
                try:
                    body_sample = page.locator("body").inner_text(timeout=3000)[:1200]
                except Exception:
                    body_sample = ""

                # Respect access boundaries: detect CAPTCHA/login gates without attempting bypass
                lower_body = body_sample.lower()
                is_gated = (
                    "checkpoint" in cur_url
                    or "captcha" in lower_body
                    or "보안 확인" in body_sample
                    or "로봇이 아닙니다" in body_sample
                    or ("로그인" in body_sample and "라이브러리 ID" not in body_sample and "Started running" not in body_sample)
                )
                if is_gated:
                    gated_count += 1
                    continue

                try:
                    page.evaluate("window.scrollBy(0, 1100)")
                    page.wait_for_timeout(1500)
                except Exception:
                    pass

                cards_data = page.evaluate(
                    """() => {
                      const markerRe = /(게재 시작|Started running on|라이브러리 ID|Library ID)/;
                      const walkers = Array.from(document.querySelectorAll('div, span')).filter(el => {
                        if (el.children.length > 2) return false;
                        const txt = (el.innerText || '').trim();
                        return txt.length > 4 && txt.length < 90 && markerRe.test(txt);
                      });
                      const seenEls = new Set();
                      const results = [];
                      walkers.forEach((m, idx) => {
                        let box = m;
                        for (let step = 0; step < 7 && box.parentElement; step++) {
                          box = box.parentElement;
                          const rect = box.getBoundingClientRect();
                          if (rect.width >= 260 && rect.width <= 680 && rect.height >= 230 && rect.height <= 980) {
                            break;
                          }
                        }
                        if (!box || seenEls.has(box)) return;
                        const rect = box.getBoundingClientRect();
                        if (rect.width < 250 || rect.height < 200) return;
                        seenEls.add(box);
                        const markerId = 'meta-card-mark-' + results.length;
                        box.setAttribute('data-meta-card-id', markerId);
                        const lines = (box.innerText || '').split('\\n').map(s => s.trim()).filter(Boolean);
                        const hasVideo = box.querySelector('video') !== null;
                        results.push({
                          markerId,
                          lines: lines.slice(0, 18),
                          hasVideo,
                        });
                      });
                      return results.slice(0, 12);
                    }"""
                )

                for card in cards_data:
                    lines: list[str] = card.get("lines", [])
                    joined = "\n".join(lines)
                    if is_excluded_text(joined):
                        continue

                    lib_id = ""
                    started_raw = ""
                    advertiser = ""
                    cta_label = ""
                    body_lines: list[str] = []

                    META_UI_SKIP_PREFIXES = (
                        "활성",
                        "Active",
                        "플랫폼",
                        "광고 세부",
                        "See ad details",
                        "스폰서",
                        "Sponsored",
                        "드롭다운 열기",
                        "광고 상세 정보 보기",
                        "이 광고와 유사한 광고",
                        "여러 버전을 사용",
                    )
                    META_UI_EXACT = {"광고", "Ad", "·", "|", "Open dropdown", "See summary details"}

                    for raw_ln in lines:
                        ln = clean_text(raw_ln.replace("\u200b", ""))
                        if not ln or ln in META_UI_EXACT:
                            continue
                        if "라이브러리 ID" in ln or "Library ID" in ln:
                            m_id = re.search(r"(\d{8,20})", ln)
                            if m_id:
                                lib_id = m_id.group(1)
                        elif "게재 시작" in ln or "Started running on" in ln:
                            started_raw = ln
                        elif ln in ("더 알아보기", "지금 신청하기", "가입하기", "구매하기", "무료 체험", "Learn More", "Sign Up", "Shop Now", "문의하기", "자세히 알아보기"):
                            cta_label = ln
                        elif not ln.startswith(META_UI_SKIP_PREFIXES):
                            if not advertiser and 2 <= len(ln) <= 45:
                                advertiser = ln
                            else:
                                body_lines.append(ln)

                    started_iso, active_days = _parse_started_days(started_raw or joined)
                    ad_copy = clean_text(" ".join(body_lines))[:320]
                    dedup_key = (advertiser or lib_id, ad_copy[:45])
                    if dedup_key in seen_keys or (not advertiser and not ad_copy):
                        continue
                    seen_keys.add(dedup_key)

                    tmp_cap_path: str | None = None
                    if len(collected) < max_captures:
                        cap_idx = len(collected) + 1
                        out_png = CAPTURES_DIR / f"meta_ad_{cap_idx:02d}.png"
                        try:
                            loc = page.locator(f'[data-meta-card-id="{card["markerId"]}"]').first
                            loc.scroll_into_view_if_needed(timeout=2000)
                            page.wait_for_timeout(200)
                            loc.screenshot(path=str(out_png), timeout=4000)
                            tmp_cap_path = str(out_png.relative_to(PROMO_DIR)).replace("\\", "/")
                        except Exception:
                            tmp_cap_path = None

                    collected.append(
                        {
                            "query": q,
                            "library_id": lib_id,
                            "advertiser": advertiser or "(광고주 미상)",
                            "started_date": started_iso or started_raw,
                            "active_days": active_days,
                            "format": "video" if card.get("hasVideo") else "image_or_card",
                            "cta_label": cta_label,
                            "ad_copy": ad_copy,
                            "local_capture": tmp_cap_path,
                        }
                    )

            browser.close()
    except Exception as exc:
        if not collected:
            return (f"error:{type(exc).__name__}", [])

    collected.sort(key=lambda x: (x["active_days"], len(x.get("ad_copy", ""))), reverse=True)
    if not collected and gated_count > 0:
        return ("blocked_or_gated", [])
    status = "ok" if collected else "empty"
    return (status, collected[:max_ads])


def main() -> None:
    parser = argparse.ArgumentParser(description="Collect high-view YouTube Shorts & active Meta KR ads for 4THEPT benchmarking")
    parser.add_argument("--youtube", action="store_true", help="Collect YouTube Shorts only")
    parser.add_argument("--meta", action="store_true", help="Collect Meta Ad Library only")
    parser.add_argument("--deep-top", type=int, default=8, help="Number of top YouTube Shorts to enrich with transcript/comments/thumbnails")
    parser.add_argument("--days", type=int, default=365, help="YouTube publishedAfter lookback days (default: 365)")
    parser.add_argument("--queries", nargs="+", help="Custom search keywords overriding default presets")
    parser.add_argument("--cred-dir", default=str(DEFAULT_CRED_DIR), help="External read-only credentials directory")
    parser.add_argument("--out-json", default=str(DEFAULT_OUT_JSON), help="Output JSON path")
    args = parser.parse_args()

    run_yt = args.youtube or not args.meta
    run_meta = args.meta or not args.youtube

    yt_queries = tuple(f"{q} #shorts" if "#shorts" not in q.lower() else q for q in args.queries) if args.queries else DEFAULT_YOUTUBE_QUERIES
    meta_queries = tuple(args.queries) if args.queries else DEFAULT_META_QUERIES

    yt_status = "skipped"
    yt_candidates: list[dict[str, Any]] = []
    yt_deep: list[dict[str, Any]] = []

    if run_yt:
        try:
            svc = load_youtube_service(Path(args.cred_dir))
            yt_status, yt_candidates = collect_youtube_shorts(svc, yt_queries, days=args.days, max_candidates=40)
            if yt_candidates:
                yt_deep = enrich_youtube_deep(svc, yt_candidates, deep_top=max(1, args.deep_top))
        except Exception as exc:
            yt_status = f"error:{type(exc).__name__}:{exc}"

    meta_status = "skipped"
    meta_ads: list[dict[str, Any]] = []
    if run_meta:
        meta_status, meta_ads = collect_meta_ad_library(meta_queries, max_ads=25, max_captures=5)

    out_path = Path(args.out_json)
    existing_payload: dict[str, Any] = {}
    if out_path.exists():
        try:
            existing_payload = json.loads(out_path.read_text(encoding="utf-8"))
        except Exception:
            existing_payload = {}

    yt_block: dict[str, Any]
    if run_yt:
        yt_block = {
            "status": yt_status,
            "queries": list(yt_queries),
            "candidate_count": len(yt_candidates),
            "deep_count": len(yt_deep),
            "deep_winners": yt_deep,
            "candidates": yt_candidates,
        }
    elif "youtube" in existing_payload:
        yt_block = existing_payload["youtube"]
    else:
        yt_block = {
            "status": "skipped",
            "queries": list(yt_queries),
            "candidate_count": 0,
            "deep_count": 0,
            "deep_winners": [],
            "candidates": [],
        }

    meta_block: dict[str, Any]
    if run_meta:
        meta_block = {
            "status": meta_status,
            "queries": list(meta_queries),
            "ad_count": len(meta_ads),
            "ads": meta_ads,
        }
    elif "meta_ad_library" in existing_payload:
        meta_block = existing_payload["meta_ad_library"]
    else:
        meta_block = {
            "status": "skipped",
            "queries": list(meta_queries),
            "ad_count": 0,
            "ads": [],
        }

    payload = {
        "generated_at_kst": datetime.now(KST).strftime("%Y-%m-%d %H:%M KST"),
        "scope": "업종 무관 국내 고조회수 쇼츠 · 장기집행 Meta 광고 (본인 채널 및 물리치료/트레이너 운동 영상 제외)",
        "youtube": yt_block,
        "meta_ad_library": meta_block,
    }

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    print("=== 4THEPT 광고 · 고조회수 쇼츠 벤치마크 수집 완료 ===")
    print(f"YouTube: status={yt_block.get('status')} | candidates={yt_block.get('candidate_count')} | deep_winners={yt_block.get('deep_count')}")
    print(f"Meta Ad Library: status={meta_block.get('status')} | ads={meta_block.get('ad_count')}")
    print(f"JSON 저장: {out_path}")


if __name__ == "__main__":
    main()
