#!/usr/bin/env python3
"""4THEPT YouTube(THEPT 채널) · Instagram(@teamthept) 성과 데이터 수집 및 분석 리포트 CLI.

- 4THEPT 프로젝트 루트(.env, token.pickle)의 자체 OAuth/Graph API 인증 정보를 읽기 전용으로 불러옵니다.
- YouTube Shorts/영상 조회수·좋아요·댓글과 Instagram 게시물/릴스 조회·도달·저장·공유·평균시청시간을 수집합니다.
- 동일 날짜/유형/캡션 중복 업로드 경고를 자동 탐지합니다.
- --save-report 옵션 시 docs/promo/campaigns/analytics_snapshot.md를 최신화합니다.
- --sync-log 옵션 시 docs/promo/campaigns/publish_log.md 내 매칭되는 ID 행의 성과 수치를 동기화합니다.
"""

from __future__ import annotations

import argparse
import json
import os
import pickle
import re
import sys
from collections import defaultdict
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import requests
from dotenv import dotenv_values
from google.auth.transport.requests import Request
from googleapiclient.discovery import build

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
SNAPSHOT_PATH = PROMO_OUT_DIR / "analytics_snapshot.md"
PUBLISH_LOG_PATH = CAMPAIGNS_DIR / "publish_log.md"
DEFAULT_CRED_DIR = Path(os.getenv("THEPT_SNS_CRED_DIR", str(AUTO_ROOT)))

KST = timezone(timedelta(hours=9))
GRAPH_API_VERSION = "v20.0"

YT_PROMO_KEYWORDS = ("4thept", "포더피티", "4thept.com", "차팅", "바디차트", "치료기록지", "세션기록지")
IG_PROMO_KEYWORDS = ("4thept", "포더피티", "4thept.com", "차팅", "바디차트")
IG_NEWS_KEYWORDS = ("주간 브리핑", "thept 주간", "뉴스", "브리핑")

ISO_DURATION_RE = re.compile(r"^PT(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?$")


@dataclass
class YouTubeVideoStat:
    video_id: str
    published_kst: str
    date_kst: str
    title: str
    duration_sec: int
    views: int
    likes: int
    comments: int
    category: str
    url: str


@dataclass
class InstagramPostStat:
    media_id: str
    published_kst: str
    date_kst: str
    media_type: str
    product_type: str
    category: str
    caption_title: str
    permalink: str
    views: int
    reach: int
    saved: int
    shares: int
    likes: int
    comments: int
    total_interactions: int
    avg_watch_sec: float


def parse_iso_duration_sec(raw: str) -> int:
    m = ISO_DURATION_RE.match((raw or "").strip())
    if not m:
        return 0
    h = int(m.group(1) or 0)
    mins = int(m.group(2) or 0)
    secs = int(m.group(3) or 0)
    return h * 3600 + mins * 60 + secs


def to_kst_strings(raw_ts: str) -> tuple[str, str]:
    """Convert YouTube ISO 'Z' or Instagram '+0000' timestamp to ('YYYY-MM-DD HH:MM', 'YYYY-MM-DD')."""
    if not raw_ts:
        return ("-", "-")
    norm = raw_ts.strip()
    if norm.endswith("Z"):
        norm = norm[:-1] + "+00:00"
    elif re.search(r"[+-]\d{4}$", norm):
        norm = norm[:-2] + ":" + norm[-2:]
    dt = datetime.fromisoformat(norm).astimezone(KST)
    return (dt.strftime("%Y-%m-%d %H:%M"), dt.strftime("%Y-%m-%d"))


def classify_yt_category(title: str, description: str) -> str:
    blob = f"{title}\n{description}".lower()
    if "주간 브리핑" in blob or "1분 브리핑" in blob or "thept 주간" in blob:
        return "THEPT 뉴스 브리핑"
    if any(kw in blob for kw in YT_PROMO_KEYWORDS):
        return "4THEPT 홍보"
    return "현장 공감/기타"


def classify_ig_category(caption: str) -> str:
    lower = (caption or "").lower()
    # 주간 브리핑 스폰서 푸터에 4thept.com이 포함되므로 주간 브리핑을 먼저 분리합니다.
    if "주간 브리핑" in lower or "thept 주간" in lower:
        return "THEPT 뉴스 브리핑"
    if any(kw in lower for kw in IG_PROMO_KEYWORDS):
        return "4THEPT 홍보"
    if any(kw in lower for kw in IG_NEWS_KEYWORDS):
        return "THEPT 뉴스 브리핑"
    return "기타"


def first_caption_line(caption: str) -> str:
    for raw in (caption or "").splitlines():
        cleaned = re.sub(r"\s+", " ", raw).strip()
        if cleaned:
            return cleaned[:80]
    return "(캡션 없음)"


def load_creds(cred_dir: Path) -> tuple[str, str, Path]:
    env_file = cred_dir / ".env"
    env_map = dotenv_values(env_file) if env_file.exists() else {}
    ig_id = (os.getenv("INSTAGRAM_ACCOUNT_ID") or env_map.get("INSTAGRAM_ACCOUNT_ID") or "").strip()
    ig_token = (os.getenv("INSTAGRAM_ACCESS_TOKEN") or env_map.get("INSTAGRAM_ACCESS_TOKEN") or "").strip()
    yt_token_path = cred_dir / "token.pickle"
    return ig_id, ig_token, yt_token_path


def collect_youtube(yt_token_path: Path, limit: int) -> dict[str, Any]:
    """Fetch THEPT YouTube channel summary and recent video stats read-only."""
    if not yt_token_path.exists():
        return {"ok": False, "error": f"YouTube 토큰 파일 없음: {yt_token_path}"}

    with open(yt_token_path, "rb") as f:
        creds = pickle.load(f)

    # Refresh access token strictly in memory so external cred_dir remains untouched.
    if not creds.valid:
        if creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            return {"ok": False, "error": "YouTube OAuth 토큰 만료 및 refresh_token 없음"}

    svc = build("youtube", "v3", credentials=creds)
    ch_res = svc.channels().list(part="snippet,statistics,contentDetails", mine=True).execute()
    items = ch_res.get("items", [])
    if not items:
        return {"ok": False, "error": "인증된 YouTube 채널을 찾을 수 없습니다."}

    ch = items[0]
    ch_stats = ch.get("statistics", {})
    uploads_id = ch["contentDetails"]["relatedPlaylists"]["uploads"]

    video_ids: list[str] = []
    page_token: str | None = None
    while len(video_ids) < limit:
        pl_res = (
            svc.playlistItems()
            .list(
                part="contentDetails",
                playlistId=uploads_id,
                maxResults=min(50, limit - len(video_ids)),
                pageToken=page_token,
            )
            .execute()
        )
        for item in pl_res.get("items", []):
            vid = item["contentDetails"]["videoId"]
            video_ids.append(vid)
        page_token = pl_res.get("nextPageToken")
        if not page_token:
            break

    videos: list[YouTubeVideoStat] = []
    for idx in range(0, len(video_ids), 50):
        chunk = video_ids[idx : idx + 50]
        v_res = svc.videos().list(part="snippet,statistics,contentDetails", id=",".join(chunk)).execute()
        for v in v_res.get("items", []):
            snip = v.get("snippet", {})
            st = v.get("statistics", {})
            cd = v.get("contentDetails", {})
            pub_kst, date_kst = to_kst_strings(snip.get("publishedAt", ""))
            dur_sec = parse_iso_duration_sec(cd.get("duration", ""))
            title = snip.get("title", "")
            desc = snip.get("description", "")
            vid = v["id"]
            url = f"https://youtube.com/shorts/{vid}" if dur_sec <= 90 else f"https://www.youtube.com/watch?v={vid}"
            videos.append(
                YouTubeVideoStat(
                    video_id=vid,
                    published_kst=pub_kst,
                    date_kst=date_kst,
                    title=title,
                    duration_sec=dur_sec,
                    views=int(st.get("viewCount", 0) or 0),
                    likes=int(st.get("likeCount", 0) or 0),
                    comments=int(st.get("commentCount", 0) or 0),
                    category=classify_yt_category(title, desc),
                    url=url,
                )
            )

    return {
        "ok": True,
        "channel": {
            "id": ch["id"],
            "title": ch["snippet"]["title"],
            "handle": ch["snippet"].get("customUrl", ""),
            "subscribers": int(ch_stats.get("subscriberCount", 0) or 0),
            "total_views": int(ch_stats.get("viewCount", 0) or 0),
            "video_count": int(ch_stats.get("videoCount", 0) or 0),
        },
        "videos": videos,
    }


def _fetch_ig_insights(api_base: str, media_id: str, product_type: str, token: str) -> tuple[dict[str, int], float]:
    """Fetch supported Graph API v20.0 metrics without requesting deprecated 'plays'."""
    metrics: dict[str, int] = {}
    avg_watch_sec = 0.0

    try:
        r = requests.get(
            f"{api_base}/{media_id}/insights",
            params={
                "metric": "views,reach,saved,shares,likes,comments,total_interactions",
                "access_token": token,
            },
            timeout=10,
        ).json()
        for row in r.get("data", []):
            name = row.get("name")
            vals = row.get("values") or []
            if name and vals:
                metrics[name] = int(vals[0].get("value", 0) or 0)
    except Exception:
        pass

    if product_type == "REELS":
        try:
            r2 = requests.get(
                f"{api_base}/{media_id}/insights",
                params={
                    "metric": "ig_reels_avg_watch_time,ig_reels_video_view_total_time",
                    "access_token": token,
                },
                timeout=10,
            ).json()
            for row in r2.get("data", []):
                if row.get("name") == "ig_reels_avg_watch_time":
                    vals = row.get("values") or []
                    if vals:
                        ms = float(vals[0].get("value", 0) or 0)
                        avg_watch_sec = round(ms / 1000.0, 1)
        except Exception:
            pass

    return metrics, avg_watch_sec


def collect_instagram(ig_id: str, ig_token: str, limit: int) -> dict[str, Any]:
    """Fetch @teamthept profile, recent posts/reels insights, and duplicate warnings."""
    if not ig_id or not ig_token:
        return {"ok": False, "error": "INSTAGRAM_ACCOUNT_ID 또는 INSTAGRAM_ACCESS_TOKEN 미설정"}

    api_base = (
        f"https://graph.instagram.com/{GRAPH_API_VERSION}"
        if ig_token.startswith("IG")
        else f"https://graph.facebook.com/{GRAPH_API_VERSION}"
    )

    prof = requests.get(
        f"{api_base}/{ig_id}",
        params={"fields": "id,username,name,followers_count,media_count", "access_token": ig_token},
        timeout=10,
    ).json()
    if "error" in prof:
        return {"ok": False, "error": prof["error"].get("message", "Instagram 프로필 조회 실패")}

    raw_posts: list[dict[str, Any]] = []
    next_url: str | None = f"{api_base}/{ig_id}/media"
    params: dict[str, Any] | None = {
        "fields": "id,media_type,media_product_type,permalink,timestamp,like_count,comments_count,caption",
        "limit": min(25, limit),
        "access_token": ig_token,
    }

    while next_url and len(raw_posts) < limit:
        res = requests.get(next_url, params=params, timeout=12).json()
        if "error" in res:
            return {"ok": False, "error": res["error"].get("message", "Instagram 미디어 목록 조회 실패")}
        raw_posts.extend(res.get("data", []))
        next_url = (res.get("paging") or {}).get("next")
        params = None  # 'next' URL already contains query params and access_token

    raw_posts = raw_posts[:limit]
    posts: list[InstagramPostStat] = []
    for item in raw_posts:
        media_id = str(item["id"])
        product_type = str(item.get("media_product_type") or item.get("media_type") or "FEED")
        pub_kst, date_kst = to_kst_strings(item.get("timestamp", ""))
        caption = item.get("caption") or ""
        ins, avg_watch_sec = _fetch_ig_insights(api_base, media_id, product_type, ig_token)
        likes = ins.get("likes", int(item.get("like_count", 0) or 0))
        comments = ins.get("comments", int(item.get("comments_count", 0) or 0))
        posts.append(
            InstagramPostStat(
                media_id=media_id,
                published_kst=pub_kst,
                date_kst=date_kst,
                media_type=str(item.get("media_type") or ""),
                product_type=product_type,
                category=classify_ig_category(caption),
                caption_title=first_caption_line(caption),
                permalink=str(item.get("permalink") or ""),
                views=ins.get("views", 0),
                reach=ins.get("reach", 0),
                saved=ins.get("saved", 0),
                shares=ins.get("shares", 0),
                likes=likes,
                comments=comments,
                total_interactions=ins.get("total_interactions", likes + comments),
                avg_watch_sec=avg_watch_sec,
            )
        )

    dup_groups: dict[tuple[str, str, str], list[InstagramPostStat]] = defaultdict(list)
    for p in posts:
        key = (p.date_kst, p.product_type, p.caption_title[:45])
        dup_groups[key].append(p)

    duplicates: list[dict[str, Any]] = []
    for (d_kst, ptype, cap_key), grp in dup_groups.items():
        if len(grp) >= 2:
            duplicates.append(
                {
                    "date_kst": d_kst,
                    "product_type": ptype,
                    "count": len(grp),
                    "title": cap_key,
                    "ids": [g.media_id for g in grp],
                }
            )
    duplicates.sort(key=lambda x: (x["date_kst"], x["product_type"]), reverse=True)

    return {
        "ok": True,
        "profile": {
            "id": prof.get("id", ig_id),
            "username": prof.get("username", ""),
            "name": prof.get("name", ""),
            "followers": int(prof.get("followers_count", 0) or 0),
            "media_count": int(prof.get("media_count", 0) or 0),
        },
        "posts": posts,
        "duplicates": duplicates,
    }


def _safe_md_cell(text: str, max_len: int = 44) -> str:
    cleaned = re.sub(r"\s+", " ", (text or "")).replace("|", "/").strip()
    return (cleaned[: max_len - 1] + "...") if len(cleaned) > max_len else cleaned


def build_recommendations(yt: dict[str, Any], ig: dict[str, Any]) -> list[str]:
    notes: list[str] = []
    if yt.get("ok"):
        videos: list[YouTubeVideoStat] = yt["videos"]
        promo_vids = [v for v in videos if v.category == "4THEPT 홍보"]
        empathy_vids = [v for v in videos if v.category != "4THEPT 홍보"]
        if promo_vids and empathy_vids:
            max_empathy = max(empathy_vids, key=lambda v: v.views)
            avg_promo = sum(v.views for v in promo_vids) / len(promo_vids)
            if max_empathy.views > avg_promo * 5:
                notes.append(
                    f"**80/20 훅 전환 유지**: YouTube에서 현장 공감형(`{max_empathy.views:,}`회) 대비 직접 홍보형 평균(`{avg_promo:.0f}`회)의 격차가 큽니다. 차주 기획은 0~12초 현장 고충으로 시작하는 **Series B** 비율을 우선 배정하세요."
                )
        elif not promo_vids:
            notes.append("**YouTube 4THEPT 신규 슬롯 필요**: 최근 영상 중 4THEPT 홍보 슬롯이 부족합니다. Series B/C 숏폼을 편성하세요.")

    if ig.get("ok"):
        dups = ig.get("duplicates", [])
        if dups:
            dup_dates = ", ".join(sorted({d["date_kst"] for d in dups}))
            notes.append(
                f"**중복 업로드 점검 필요**: Instagram에서 동일 날짜/유형/캡션 중복 게시가 감지되었습니다(`{dup_dates}`). `자동화에이전트` 스케줄과 `4THEPT` 발행 시간이 겹치지 않도록 1일 1게시 원칙을 유지하세요."
            )
        posts: list[InstagramPostStat] = ig["posts"]
        promo_ig = [p for p in posts if p.category == "4THEPT 홍보"]
        if not promo_ig:
            notes.append(
                f"**Instagram 내 4THEPT 홍보 비중 보강**: 최근 수집 {len(posts)}건 중 `4THEPT 홍보` 게시물이 0건입니다. 저장 유도형 **Series A** 캐러셀을 이번 주 피드에 우선 편성하세요."
            )
        else:
            top_saved = max(promo_ig, key=lambda p: (p.saved, p.reach))
            notes.append(
                f"**Instagram 저장 최다 4THEPT 포스트**: `{top_saved.caption_title}` (저장 `{top_saved.saved}`, 도달 `{top_saved.reach}`, 조회 `{top_saved.views}`)."
            )

    if not notes:
        notes.append("신규 발행 누적 후 48시간/7일 간격으로 `--save-report --sync-log`를 재실행해 상위 훅을 선별하세요.")
    return notes


def build_markdown_report(yt: dict[str, Any], ig: dict[str, Any]) -> str:
    now_str = datetime.now(KST).strftime("%Y-%m-%d %H:%M KST")
    lines: list[str] = [
        "# 4THEPT SNS 성과 스냅샷 (Analytics Snapshot)",
        "",
        f"- **생성 일시**: {now_str}",
        "- **인증 소스**: `자동화에이전트` 통합 인증 (`.env` · `token.pickle` 단일 소스)",
        "",
        "---",
        "",
        "## 1. 계정 현황 요약",
        "",
        "| 채널 | 핸들 / 이름 | 팔로워 · 구독자 | 누적 게시물 / 영상 | 비고 |",
        "| :--- | :--- | ---: | ---: | :--- |",
    ]

    if yt.get("ok"):
        ch = yt["channel"]
        lines.append(
            f"| YouTube | {ch['title']} ({ch['handle']}) | {ch['subscribers']:,}명 | {ch['video_count']:,}편 | 누적 조회 {ch['total_views']:,}회 |"
        )
    else:
        lines.append(f"| YouTube | 조회 실패 | - | - | {yt.get('error')} |")

    if ig.get("ok"):
        pf = ig["profile"]
        lines.append(
            f"| Instagram | @{pf['username']} ({pf['name']}) | {pf['followers']:,}명 | {pf['media_count']:,}건 | 최근 {len(ig['posts'])}건 분석 |"
        )
    else:
        lines.append(f"| Instagram | 조회 실패 | - | - | {ig.get('error')} |")

    lines.extend(["", "---", "", "## 2. YouTube 성과 (`THEPT` 채널)"])
    if yt.get("ok") and yt["videos"]:
        lines.extend(
            [
                "",
                "| 게시일(KST) | 분류 | 길이 | 조회수 | 좋아요 | 댓글 | 제목 | 링크 |",
                "| :--- | :--- | ---: | ---: | ---: | ---: | :--- | :--- |",
            ]
        )
        for v in yt["videos"]:
            lines.append(
                f"| {v.date_kst} | {v.category} | {v.duration_sec}s | {v.views:,} | {v.likes:,} | {v.comments:,} | {_safe_md_cell(v.title, 42)} | [영상]({v.url}) |"
            )
    else:
        lines.append("\n수집된 YouTube 영상이 없습니다.")

    lines.extend(["", "---", "", "## 3. Instagram 성과 (`@teamthept`)"])
    if ig.get("ok") and ig["posts"]:
        posts: list[InstagramPostStat] = ig["posts"]
        by_cat: dict[str, list[InstagramPostStat]] = defaultdict(list)
        for p in posts:
            by_cat[p.category].append(p)

        lines.extend(
            [
                "",
                "### 분류별 요약",
                "",
                "| 분류 | 수집 건수 | 총 조회(Views) | 총 도달 | 총 저장 | 총 좋아요 | 총 댓글 |",
                "| :--- | ---: | ---: | ---: | ---: | ---: | ---: |",
            ]
        )
        for cat in ("4THEPT 홍보", "THEPT 뉴스 브리핑", "기타"):
            grp = by_cat.get(cat, [])
            if not grp:
                continue
            lines.append(
                f"| {cat} | {len(grp)}건 | {sum(x.views for x in grp):,} | {sum(x.reach for x in grp):,} | "
                f"{sum(x.saved for x in grp):,} | {sum(x.likes for x in grp):,} | {sum(x.comments for x in grp):,} |"
            )

        lines.extend(
            [
                "",
                "### 최근 게시물 상세",
                "",
                "| 일시(KST) | 분류 | 포맷 | 조회 | 도달 | 좋아요 | 저장 | 공유 | 댓글 | 평균시청 | 첫 줄 요약 |",
                "| :--- | :--- | :--- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | :--- |",
            ]
        )
        for p in posts:
            avg_s = f"{p.avg_watch_sec}s" if p.product_type == "REELS" and p.avg_watch_sec > 0 else "-"
            lines.append(
                f"| {p.published_kst} | {p.category} | {p.product_type} | {p.views:,} | {p.reach:,} | {p.likes:,} | "
                f"{p.saved:,} | {p.shares:,} | {p.comments:,} | {avg_s} | {_safe_md_cell(p.caption_title, 36)} |"
            )
    else:
        lines.append("\n수집된 Instagram 게시물이 없습니다.")

    lines.extend(["", "---", "", "## 4. 계정 건강 상태 · 중복 발행 경고"])
    dups = ig.get("duplicates", []) if ig.get("ok") else []
    if dups:
        lines.append("")
        for d in dups:
            lines.append(
                f"- **[중복 경고]** `{d['date_kst']}` · `{d['product_type']}` · `{d['count']}회 중복` — `{_safe_md_cell(d['title'], 50)}` (IDs: {', '.join(d['ids'])})"
            )
    else:
        lines.append("\n최근 수집 구간 내 동일 일자/포맷 중복 발행이 감지되지 않았습니다.")

    lines.extend(["", "---", "", "## 5. 다음 주 기획 반영 포인트"])
    for rec in build_recommendations(yt, ig):
        lines.append(f"- {rec}")

    lines.append("")
    return "\n".join(lines)


def sync_publish_log(yt: dict[str, Any], ig: dict[str, Any], log_path: Path) -> int:
    """Update metrics column in publish_log.md for rows matching fetched YT/IG IDs."""
    if not log_path.exists():
        return 0

    yt_map: dict[str, YouTubeVideoStat] = {v.video_id: v for v in (yt.get("videos") or [])}
    ig_map: dict[str, InstagramPostStat] = {p.media_id: p for p in (ig.get("posts") or [])}
    if not yt_map and not ig_map:
        return 0

    raw_lines = log_path.read_text(encoding="utf-8").splitlines()
    updated_count = 0
    out_lines: list[str] = []

    for line in raw_lines:
        stripped = line.strip()
        if not (stripped.startswith("|") and stripped.endswith("|")):
            out_lines.append(line)
            continue
        cells = [c.strip() for c in stripped.split("|")[1:-1]]
        if len(cells) < 7 or cells[0].startswith(("발행일", ":---", "*(대기")):
            out_lines.append(line)
            continue

        id_cell = cells[5]
        metric_str: str | None = None
        for vid, v in yt_map.items():
            if vid in id_cell:
                metric_str = f"조회 {v.views:,} · 좋아요 {v.likes:,} · 댓글 {v.comments:,}"
                break
        if metric_str is None:
            for mid, p in ig_map.items():
                if mid in id_cell or (p.permalink and p.permalink in id_cell):
                    extra = f" · 평균 {p.avg_watch_sec}s" if p.product_type == "REELS" and p.avg_watch_sec > 0 else ""
                    metric_str = (
                        f"조회 {p.views:,} · 도달 {p.reach:,} · 저장 {p.saved:,} · "
                        f"좋아요 {p.likes:,} · 댓글 {p.comments:,}{extra}"
                    )
                    break

        if metric_str is not None:
            manual_note = ""
            if "| 메모:" in cells[6]:
                manual_note = " | 메모:" + cells[6].split("| 메모:", 1)[1].strip()
            cells[6] = metric_str + manual_note
            out_lines.append("| " + " | ".join(cells) + " |")
            updated_count += 1
        else:
            out_lines.append(line)

    if updated_count > 0:
        log_path.write_text("\n".join(out_lines) + "\n", encoding="utf-8")
    return updated_count


def print_console_summary(yt: dict[str, Any], ig: dict[str, Any], only_4thept: bool) -> None:
    print("=" * 72)
    print("[4THEPT SNS 성과 분석 리포트]")
    print("=" * 72)

    if yt.get("ok"):
        ch = yt["channel"]
        print(
            f"[YouTube] {ch['title']} ({ch['handle']}) | 구독 {ch['subscribers']:,} | "
            f"영상 {ch['video_count']:,} | 누적 조회 {ch['total_views']:,}"
        )
        for v in yt["videos"]:
            if only_4thept and v.category != "4THEPT 홍보":
                continue
            print(
                f"  - {v.date_kst} [{v.category}] {v.duration_sec:>3d}s | 조회 {v.views:>5,} | "
                f"좋아요 {v.likes:>2,} | 댓글 {v.comments:>2,} | {v.title[:48]}"
            )
    else:
        print(f"[YouTube] 오류: {yt.get('error')}")

    print("-" * 72)
    if ig.get("ok"):
        pf = ig["profile"]
        posts: list[InstagramPostStat] = ig["posts"]
        filtered = [p for p in posts if not only_4thept or p.category == "4THEPT 홍보"]
        print(
            f"[Instagram] @{pf['username']} | 팔로워 {pf['followers']:,} | "
            f"게시물 {pf['media_count']:,} | 표시 {len(filtered)}건 (수집 {len(posts)}건)"
        )
        for p in filtered[:10]:
            print(
                f"  - {p.published_kst} [{p.category}] {p.product_type:8s} | 조회 {p.views:>4,} | "
                f"도달 {p.reach:>4,} | 저장 {p.saved:>2,} | 좋아요 {p.likes:>2,} | 댓글 {p.comments:>2,} | {p.caption_title[:36]}"
            )
        for d in ig.get("duplicates", []):
            print(
                f"  [중복 경고] {d['date_kst']} {d['product_type']} {d['count']}회 중복: {d['title']}"
            )
    else:
        print(f"[Instagram] 오류: {ig.get('error')}")


def main() -> int:
    parser = argparse.ArgumentParser(description="4THEPT YouTube·Instagram 성과 데이터 수집기")
    parser.add_argument("--cred-dir", type=Path, default=DEFAULT_CRED_DIR, help="인증 파일 폴더 (기본: 4THEPT 프로젝트 루트)")
    parser.add_argument("--yt-limit", type=int, default=15, help="수집할 최근 YouTube 영상 수 (기본 15)")
    parser.add_argument("--ig-limit", type=int, default=20, help="수집할 최근 Instagram 게시물 수 (기본 20)")
    parser.add_argument("--only-4thept", action="store_true", help="터미널 출력 시 4THEPT 홍보 항목만 표시")
    parser.add_argument("--save-report", action="store_true", help="결과물/4THEPT마케팅/analytics_snapshot.md 저장")
    parser.add_argument("--sync-log", action="store_true", help="promo_4thept/campaigns/publish_log.md 매칭 행 성과 수치 갱신")
    parser.add_argument("--json", action="store_true", help="결과를 JSON으로 출력")
    args = parser.parse_args()

    ig_id, ig_token, yt_token_path = load_creds(args.cred_dir)
    yt = collect_youtube(yt_token_path, max(1, args.yt_limit))
    ig = collect_instagram(ig_id, ig_token, max(1, args.ig_limit))

    if args.save_report:
        SNAPSHOT_PATH.parent.mkdir(parents=True, exist_ok=True)
        SNAPSHOT_PATH.write_text(build_markdown_report(yt, ig), encoding="utf-8")

    synced_rows = sync_publish_log(yt, ig, PUBLISH_LOG_PATH) if args.sync_log else 0

    if args.json:
        payload = {
            "generated_at_kst": datetime.now(KST).isoformat(),
            "youtube": {
                **{k: v for k, v in yt.items() if k != "videos"},
                "videos": [asdict(v) for v in yt.get("videos", [])],
            },
            "instagram": {
                **{k: v for k, v in ig.items() if k != "posts"},
                "posts": [asdict(p) for p in ig.get("posts", [])],
            },
            "recommendations": build_recommendations(yt, ig),
            "synced_log_rows": synced_rows,
        }
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        print_console_summary(yt, ig, args.only_4thept)
        if args.save_report:
            print(f"\n[스냅샷 저장] {SNAPSHOT_PATH}")
        if args.sync_log:
            print(f"[발행 로그 동기화] {PUBLISH_LOG_PATH.name} ({synced_rows}건 매칭 갱신)")

    return 0 if (yt.get("ok") or ig.get("ok")) else 1


if __name__ == "__main__":
    raise SystemExit(main())
