"""THEPT YouTube · Instagram 통합 SNS 성과 수집 및 중복 진단 모듈.

- YouTubeShortsUploader 및 InstagramGraphUploader 인증 설정을 재사용합니다.
- 공유 계정(@teamthept)에서 'THEPT 주간 브리핑'과 '4THEPT 제품 홍보' 슬롯을 구분 집계합니다.
- 당일 동일 포맷·동일 제목 중복 업로드 경고를 탐지합니다.
"""

from __future__ import annotations

import re
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import requests

from config import BASE_DIR, OUTPUT_DIR, PROMO_OUTPUT_DIR
from modules.instagram_uploader import GRAPH_API_VERSION, InstagramGraphUploader
from modules.youtube_uploader import YouTubeShortsUploader

PUBLISH_LOG_PATH = BASE_DIR / "promo_4thept" / "campaigns" / "publish_log.md"

KST = timezone(timedelta(hours=9))
ISO_DURATION_RE = re.compile(r"^PT(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?$")


def _parse_iso_duration_sec(raw: str) -> int:
    m = ISO_DURATION_RE.match((raw or "").strip())
    if not m:
        return 0
    return int(m.group(1) or 0) * 3600 + int(m.group(2) or 0) * 60 + int(m.group(3) or 0)


def _to_kst_strings(raw_ts: str) -> tuple[str, str]:
    if not raw_ts:
        return ("-", "-")
    norm = raw_ts.strip()
    if norm.endswith("Z"):
        norm = norm[:-1] + "+00:00"
    elif re.search(r"[+-]\d{4}$", norm):
        norm = norm[:-2] + ":" + norm[-2:]
    dt = datetime.fromisoformat(norm).astimezone(KST)
    return (dt.strftime("%Y-%m-%d %H:%M"), dt.strftime("%Y-%m-%d"))


def _classify_post(text: str) -> str:
    lower = (text or "").lower()
    if "주간 브리핑" in lower or "thept 주간" in lower or "1분 브리핑" in lower:
        return "THEPT 주간 브리핑"
    if any(kw in lower for kw in ("4thept", "포더피티", "차팅", "바디차트", "세션기록지", "치료기록지")):
        return "4THEPT 제품 홍보"
    return "기타"


def collect_youtube_analytics(limit: int = 20) -> dict[str, Any]:
    """인증된 YouTube 채널의 최근 쇼츠/영상 성과를 조회합니다."""
    try:
        uploader = YouTubeShortsUploader()
        svc = uploader.get_service()
        align = uploader.check_channel_alignment()
    except Exception as e:
        return {"ok": False, "error": str(e)}

    ch_res = svc.channels().list(part="snippet,statistics,contentDetails", mine=True).execute()
    items = ch_res.get("items", [])
    if not items:
        return {"ok": False, "error": "인증된 YouTube 채널을 찾을 수 없습니다."}

    ch = items[0]
    ch_stats = ch.get("statistics", {})
    uploads_id = ch["contentDetails"]["relatedPlaylists"]["uploads"]

    video_ids: list[str] = []
    page_token = None
    while len(video_ids) < limit:
        pl_res = svc.playlistItems().list(
            part="contentDetails",
            playlistId=uploads_id,
            maxResults=min(50, limit - len(video_ids)),
            pageToken=page_token,
        ).execute()
        for item in pl_res.get("items", []):
            video_ids.append(item["contentDetails"]["videoId"])
        page_token = pl_res.get("nextPageToken")
        if not page_token:
            break

    videos = []
    for idx in range(0, len(video_ids), 50):
        chunk = video_ids[idx:idx + 50]
        if not chunk:
            continue
        v_res = svc.videos().list(part="snippet,statistics,contentDetails", id=",".join(chunk)).execute()
        for v in v_res.get("items", []):
            snip = v.get("snippet", {})
            st = v.get("statistics", {})
            cd = v.get("contentDetails", {})
            pub_kst, date_kst = _to_kst_strings(snip.get("publishedAt", ""))
            dur_sec = _parse_iso_duration_sec(cd.get("duration", ""))
            title = snip.get("title", "")
            desc = snip.get("description", "")
            videos.append({
                "id": v["id"],
                "published_kst": pub_kst,
                "date_kst": date_kst,
                "duration_sec": dur_sec,
                "views": int(st.get("viewCount", 0) or 0),
                "likes": int(st.get("likeCount", 0) or 0),
                "comments": int(st.get("commentCount", 0) or 0),
                "category": _classify_post(f"{title}\n{desc}"),
                "title": title,
            })

    return {
        "ok": True,
        "alignment": align,
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
            vals = row.get("values") or []
            if vals:
                metrics[row.get("name")] = int(vals[0].get("value", 0) or 0)
    except Exception:
        pass

    if product_type == "REELS":
        try:
            r2 = requests.get(
                f"{api_base}/{media_id}/insights",
                params={"metric": "ig_reels_avg_watch_time", "access_token": token},
                timeout=10,
            ).json()
            for row in r2.get("data", []):
                vals = row.get("values") or []
                if vals:
                    avg_watch_sec = round(float(vals[0].get("value", 0) or 0) / 1000.0, 1)
        except Exception:
            pass

    return metrics, avg_watch_sec


def collect_instagram_analytics(limit: int = 20) -> dict[str, Any]:
    """Instagram 비즈니스 계정 최근 게시물·릴스 성과 및 중복 발행 여부를 수집합니다."""
    uploader = InstagramGraphUploader()
    if not uploader.is_configured():
        return {"ok": False, "error": "INSTAGRAM_ACCOUNT_ID 또는 INSTAGRAM_ACCESS_TOKEN 미설정"}

    api_base = f"https://graph.facebook.com/{GRAPH_API_VERSION}" if not uploader.access_token.startswith("IG") else uploader.api_base
    prof = requests.get(
        f"{api_base}/{uploader.account_id}",
        params={"fields": "id,username,name,followers_count,media_count", "access_token": uploader.access_token},
        timeout=10,
    ).json()
    if "error" in prof:
        return {"ok": False, "error": prof["error"].get("message", "프로필 조회 실패")}

    media_res = requests.get(
        f"{api_base}/{uploader.account_id}/media",
        params={
            "fields": "id,caption,media_type,media_product_type,timestamp,permalink,like_count,comments_count",
            "limit": limit,
            "access_token": uploader.access_token,
        },
        timeout=12,
    ).json()
    if "error" in media_res:
        return {"ok": False, "error": media_res["error"].get("message", "미디어 조회 실패")}

    posts = []
    for m in media_res.get("data", []):
        caption = m.get("caption") or ""
        first_line = next((ln.strip()[:60] for ln in caption.splitlines() if ln.strip()), "(캡션 없음)")
        pub_kst, date_kst = _to_kst_strings(m.get("timestamp", ""))
        product_type = (m.get("media_product_type") or m.get("media_type") or "FEED").upper()
        ins, avg_watch = _fetch_ig_insights(api_base, m["id"], product_type, uploader.access_token)
        posts.append({
            "id": m["id"],
            "published_kst": pub_kst,
            "date_kst": date_kst,
            "product_type": product_type,
            "category": _classify_post(caption),
            "first_line": first_line,
            "views": ins.get("views", 0),
            "reach": ins.get("reach", 0),
            "saved": ins.get("saved", 0),
            "shares": ins.get("shares", 0),
            "likes": ins.get("likes", int(m.get("like_count", 0) or 0)),
            "comments": ins.get("comments", int(m.get("comments_count", 0) or 0)),
            "avg_watch_sec": avg_watch,
        })

    grouped: dict[tuple[str, str, str], list[str]] = defaultdict(list)
    for p in posts:
        grouped[(p["date_kst"], p["product_type"], p["first_line"])].append(p["id"])
    duplicates = [
        {"date_kst": k[0], "product_type": k[1], "first_line": k[2], "count": len(ids), "ids": ids}
        for k, ids in grouped.items()
        if len(ids) > 1
    ]

    return {"ok": True, "profile": prof, "posts": posts, "duplicates": duplicates}


def format_analytics_markdown(yt: dict, ig: dict) -> str:
    """수집된 YouTube·Instagram 성과를 마크다운 리포트로 포맷팅합니다."""
    now_kst = datetime.now(KST).strftime("%Y-%m-%d %H:%M KST")
    lines = [
        f"# 📊 THEPT 주간 SNS 성과 리포트 ({now_kst})",
        "",
    ]

    if yt.get("ok"):
        ch = yt["channel"]
        align = yt.get("alignment", {})
        lines.extend([
            "## 1. YouTube 성과",
            f"- **연동 채널**: {ch['title']} ({ch['handle']} / `{ch['id']}`)",
            f"- **목표 채널(THEPT) 일치**: {'예 ✅' if align.get('matched') else '아니오 ⚠️ (auth-yt 재인증 필요)'}",
            f"- **구독자 / 누적 조회 / 총 영상**: {ch['subscribers']}명 / {ch['total_views']}회 / {ch['video_count']}편",
            "",
            "| 게시일(KST) | 분류 | 길이 | 조회수 | 좋아요 | 댓글 | 제목 |",
            "|---|---|---:|---:|---:|---:|---|",
        ])
        for v in yt.get("videos", [])[:10]:
            lines.append(
                f"| {v['published_kst']} | {v['category']} | {v['duration_sec']}s | "
                f"{v['views']} | {v['likes']} | {v['comments']} | {v['title'][:50]} |"
            )
        lines.append("")
    else:
        lines.extend([f"## 1. YouTube 성과 수집 실패: {yt.get('error')}", ""])

    if ig.get("ok"):
        prof = ig["profile"]
        lines.extend([
            "## 2. Instagram 성과 (`@teamthept` 공유 슬롯 분류)",
            f"- **계정**: @{prof.get('username')} (팔로워 {prof.get('followers_count', 0)}명 / 게시물 {prof.get('media_count', 0)}건)",
            "",
            "| 일시(KST) | 슬롯 분류 | 포맷 | 조회 | 도달 | 저장 | 공유 | 평균시청 | 첫 줄 요약 |",
            "|---|---|---|---:|---:|---:|---:|---:|---|",
        ])
        for p in ig.get("posts", [])[:15]:
            watch_str = f"{p['avg_watch_sec']:.1f}s" if p["avg_watch_sec"] > 0 else "-"
            lines.append(
                f"| {p['published_kst']} | {p['category']} | {p['product_type']} | "
                f"{p['views']} | {p['reach']} | {p['saved']} | {p['shares']} | {watch_str} | {p['first_line']} |"
            )
        dups = ig.get("duplicates", [])
        if dups:
            lines.extend(["", "### ⚠️ 당일 중복 업로드 감지"])
            for d in dups:
                lines.append(f"- `{d['date_kst']}` · `{d['product_type']}` · {d['count']}회 중복 — `{d['first_line']}`")
        lines.append("")
    else:
        lines.extend([f"## 2. Instagram 성과 수집 실패: {ig.get('error')}", ""])

    return "\n".join(lines)


def sync_publish_log(yt: dict[str, Any], ig: dict[str, Any], log_path: Path = PUBLISH_LOG_PATH) -> int:
    """promo_4thept/campaigns/publish_log.md 내 매칭되는 YouTube/Instagram ID 행의 성과 수치를 동기화합니다."""
    if not log_path.exists():
        return 0

    yt_map = {v["id"]: v for v in (yt.get("videos") or [])}
    ig_map = {p["id"]: p for p in (ig.get("posts") or [])}
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
                metric_str = f"조회 {v['views']:,} · 좋아요 {v['likes']:,} · 댓글 {v['comments']:,}"
                break
        if metric_str is None:
            for mid, p in ig_map.items():
                if mid in id_cell:
                    extra = f" · 평균 {p['avg_watch_sec']}s" if p["product_type"] == "REELS" and p["avg_watch_sec"] > 0 else ""
                    metric_str = (
                        f"조회 {p['views']:,} · 도달 {p['reach']:,} · 저장 {p['saved']:,} · "
                        f"좋아요 {p['likes']:,} · 댓글 {p['comments']:,}{extra}"
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


def run_analytics_report(limit: int = 20, save_report: bool = False, sync_log: bool = False) -> Path | None:
    """콘솔에 성과 요약을 출력하고 옵션에 따라 결과물/THEPT뉴스/analytics_report.md 및 4THEPT 스냅샷을 저장합니다."""
    yt = collect_youtube_analytics(limit=limit)
    ig = collect_instagram_analytics(limit=limit)
    md = format_analytics_markdown(yt, ig)
    print("\n" + md)

    if sync_log:
        synced = sync_publish_log(yt, ig, PUBLISH_LOG_PATH)
        print(f"📝 [발행 로그 동기화] {PUBLISH_LOG_PATH.name} ({synced}건 매칭 갱신)")

    if save_report:
        OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        out_path = OUTPUT_DIR / "analytics_report.md"
        out_path.write_text(md, encoding="utf-8")
        print(f"📁 [리포트 저장 완료] {out_path.resolve()}")

        PROMO_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        snap_path = PROMO_OUTPUT_DIR / "analytics_snapshot.md"
        snap_path.write_text(md, encoding="utf-8")
        print(f"📁 [4THEPT 스냅샷 갱신] {snap_path.resolve()}")
        return out_path
    return None
