# 이 파일은 주간 6대 카테고리 2단계 마크다운 큐레이션 및 파이프라인 구동 CLI 도구입니다.
# 1단계 수집(fetch) -> 2단계 검토(review) -> 최종 제작 및 히스토리 아카이빙(build)을 지원합니다.

import sys
import os
import argparse
import asyncio
import json
import re
from pathlib import Path
from datetime import datetime

# 윈도우 UTF-8 출력 보장
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

sys.path.append(str(Path(__file__).resolve().parent))

from config import BASE_DIR, OUTPUT_DIR
from modules.news_collector import collect_6categories_candidates, SIX_CATEGORIES
from modules.curation_manager import (
    save_candidates_cache,
    load_candidates_cache,
    generate_candidates_titles_markdown,
    parse_candidates_titles_markdown,
    generate_candidates_detail_markdown,
    parse_candidates_detail_markdown,
    append_to_curation_history,
    rebalance_selected_articles,
    CACHE_FILE,
    HISTORY_FILE
)
from modules.article_image_fetcher import fetch_article_images


def get_weekly_dir(date_str: str = None, create: bool = True) -> Path:
    """
    주간 큐레이션 통합 작업 디렉토리(output/{YYYY-MM-DD}_curated_weekly) 경로를 반환합니다.
    """
    if not date_str:
        date_str = datetime.now().strftime("%Y-%m-%d")
    weekly_dir = OUTPUT_DIR / f"{date_str}_curated_weekly"
    if create:
        weekly_dir.mkdir(parents=True, exist_ok=True)
    return weekly_dir


def find_active_weekly_dir(date_str: str = None) -> Path:
    """
    작업할 주간 디렉토리를 결정합니다.
    - 날짜가 지정되면 해당 날짜 디렉토리 반환
    - 오늘 디렉토리가 있으면 오늘 디렉토리 반환
    - 없으면 가장 최근 생성된 *_curated_weekly 디렉토리 반환
    """
    if date_str:
        return get_weekly_dir(date_str, create=True)

    today_dir = get_weekly_dir(create=False)
    if today_dir.exists():
        return today_dir

    if OUTPUT_DIR.exists():
        weekly_dirs = sorted(
            [d for d in OUTPUT_DIR.iterdir() if d.is_dir() and d.name.endswith("_curated_weekly")],
            key=lambda x: x.name,
            reverse=True
        )
        if weekly_dirs:
            return weekly_dirs[0]

    return get_weekly_dir(create=True)


def cmd_fetch(args):
    """1단계: 6대 카테고리 최대 100건 후보 수집 및 candidates_titles.md 생성"""
    target_count = args.count if args.count else 17
    weekly_dir = get_weekly_dir(getattr(args, "date", None), create=True)
    titles_md = weekly_dir / "candidates_titles.md"

    print("\n🚀 [1단계] 주 6일 6대 카테고리 후보 기사 대량 수집을 시작합니다...")
    candidates = collect_6categories_candidates(target_per_category=target_count)

    # 캐시 저장
    save_candidates_cache(candidates, CACHE_FILE)

    # 마크다운 생성 (output 주차별 폴더 내)
    generate_candidates_titles_markdown(candidates, titles_md)

    print("\n" + "=" * 70)
    print("✅ [완료] 1단계 제목 스크리닝 파일이 생성되었습니다!")
    print(f"👉 파일 경로: {titles_md.resolve()}")
    print("=" * 70)
    print("📋 [다음 작업 안내]:")
    print(f" 1. 에디터에서 아래 파일을 엽니다:\n    👉 {titles_md.resolve()}")
    print(" 2. 관심 있는 기사의 [ ] 를 [x] 로 체크하세요. (요일당 3~5개 권장)")
    print(" 3. 추가하고 싶은 기사가 있다면 맨 아래 [✍️ 직접 기사 추가]에 URL을 적어주세요.")
    print(" 4. 저장이 끝나면 아래 명령어를 실행하세요:")
    print("    👉 python curate.py review")
    print("=" * 70)


async def cmd_review_async(args):
    """2단계: 1차 선택된 기사의 상세 본문/사진을 파싱하여 candidates_detail.md 생성"""
    weekly_dir = find_active_weekly_dir(getattr(args, "date", None))
    titles_md = weekly_dir / "candidates_titles.md"
    detail_md = weekly_dir / "candidates_detail.md"

    if not titles_md.exists():
        print(f"❌ [오류] 1단계 파일이 존재하지 않습니다: {titles_md.resolve()}")
        print(f"   먼저 1단계 수집을 실행하세요: python curate.py fetch")
        sys.exit(1)

    print(f"\n🔍 [2단계] 1단계 체크박스 파싱 중: {titles_md.name} ({weekly_dir.name})")
    selected_by_cat = parse_candidates_titles_markdown(titles_md, CACHE_FILE)
    total_selected = sum(len(v) for v in selected_by_cat.values())

    if total_selected == 0:
        print("⚠️ [주의] 1단계에서 [x]로 체크된 기사가 하나도 없습니다!")
        print(f"   파일({titles_md.resolve()})에서 관심 기사에 [x]를 표시한 뒤 다시 실행해주세요.")
        sys.exit(1)

    print(f"  -> 총 {total_selected}건의 기사가 1차 선택되었습니다.")
    for k, meta in SIX_CATEGORIES.items():
        print(f"     - [{meta['day']}] {meta['title']}: {len(selected_by_cat.get(k, []))}건")

    # 보도 사진 및 원문 본문 크롤링 (통합된 backgrounds 폴더)
    bg_dir = weekly_dir / "backgrounds"
    bg_dir.mkdir(parents=True, exist_ok=True)

    print("\n🌐 각 기사의 원문 웹페이지에서 본문 및 보도 사진을 크롤링합니다...")
    for k, arts in selected_by_cat.items():
        if arts:
            prefix = k[:3]
            try:
                await fetch_article_images(arts, bg_dir, prefix=prefix)
            except Exception as e:
                print(f"  - [{prefix}] 크롤링 경고: {e}")

    # 캐시 업데이트
    cached = load_candidates_cache(CACHE_FILE)
    for k, arts in selected_by_cat.items():
        if k in cached:
            # 기존 캐시에 기사 본문 및 이미지 정보 병합
            for art in arts:
                for idx, c_art in enumerate(cached[k]):
                    if c_art.get("id") == art.get("id"):
                        cached[k][idx] = art
    save_candidates_cache(cached, CACHE_FILE)

    # 2단계 상세 마크다운 생성 (output 주차별 폴더 내)
    generate_candidates_detail_markdown(selected_by_cat, detail_md)

    print("\n" + "=" * 70)
    print("✅ [완료] 2단계 상세 검토 파일이 생성되었습니다!")
    print(f"👉 파일 경로: {detail_md.resolve()}")
    print("=" * 70)
    print("📋 [다음 작업 안내]:")
    print(f" 1. 에디터에서 아래 파일을 엽니다:\n    👉 {detail_md.resolve()}")
    print(" 2. 요일별로 최종 발행할 기사를 [x] 로 체크하세요. (선택 이유 작성 불필요)")
    print(" 3. 저장이 끝나면 아래 명령어를 실행하여 주간 6일 콘텐츠를 일괄 제작하세요:")
    print("    👉 python curate.py build")
    print("=" * 70)


def cmd_build(args):
    """3단계: 최종 선택 기사 확정, 큐레이션 히스토리 저장 및 주 6일 콘텐츠 일괄 제작"""
    weekly_dir = find_active_weekly_dir(getattr(args, "date", None))
    detail_md = weekly_dir / "candidates_detail.md"

    if not detail_md.exists():
        print(f"❌ [오류] 2단계 검토 파일이 존재하지 않습니다: {detail_md.resolve()}")
        print(f"   먼저 2단계 검토 파일을 생성하세요: python curate.py review")
        sys.exit(1)

    print(f"\n⚙️ [3단계] 최종 큐레이션 검토 결과 파싱 중: {detail_md.name} ({weekly_dir.name})")
    final_by_cat, history_records = parse_candidates_detail_markdown(detail_md, CACHE_FILE)

    total_final = sum(len(v) for v in final_by_cat.values())
    if total_final == 0:
        print("⚠️ [주의] 2단계에서 [x]로 최종 채택된 기사가 없습니다!")
        print(f"   파일({detail_md.resolve()})에서 각 요일별 기사에 [x]를 체크해주세요.")
        sys.exit(1)

    print(f"  -> 총 {total_final}건의 기사가 최종 채택되었습니다.")
    for k, meta in SIX_CATEGORIES.items():
        arts = final_by_cat.get(k, [])
        print(f"     - [{meta['day']}] {meta['title']}: {len(arts)}건 채택")
        for a in arts:
            print(f"       * {a['title'][:40]}")

    # 큐레이션 히스토리 영구 누적 저장 (향후 에이전트 학습용)
    append_to_curation_history(history_records, HISTORY_FILE)
    print(f"\n📁 [데이터셋 저장] {len(history_records)}건의 큐레이션 기록이 '{HISTORY_FILE}'에 안전하게 누적되었습니다.")

    # 사용자 선택 기사 기반 요일별 균등 재배치 및 자동 보충 (요일별 3건, 총 18건 보장)
    rebalanced_by_cat, rebalance_logs = rebalance_selected_articles(final_by_cat, min_per_day=3, max_per_day=3)
    if rebalance_logs:
        print("\n" + "=" * 70)
        print("🔄 [기사 3건 균등 재배치 및 자동 보충 실행]")
        print("   주 6일 매일 정확히 3건(총 18건)을 맞추기 위해 기사를 재배치/보충했습니다:")
        for log in rebalance_logs:
            print(f"   {log}")
        print("=" * 70)

    # 렌더링 파이프라인 구동
    do_render = getattr(args, "render", False)
    if do_render:
        print("\n🎬 주 6일 통합 콘텐츠(쇼츠 비디오 + 4:5 카드뉴스 + 4THEPT 광고 + SNS 캡션) 일괄 렌더링을 시작합니다...")
    else:
        print("\n📝 주 6일 통합 콘텐츠 패키지(OpenAI LLM 요약 + 쇼츠 대본 + 4THEPT 광고 + SNS 캡션) 생성을 시작합니다...")
        print("   (※ 카드뉴스 이미지/비디오 렌더링은 --render 옵션 사용 시 수행됩니다.)")

    from pipeline import run_curated_6days_pipeline
    results = asyncio.run(run_curated_6days_pipeline(rebalanced_by_cat, render_media=do_render, target_dir=weekly_dir))

    print("\n" + "=" * 70)
    print("🎉 [제작 성공] 주간 6일 연계 콘텐츠 생성이 모두 완료되었습니다!")
    print(f"👉 마스터 저장 폴더: {results.get('weekly_dir', weekly_dir)}")
    print("=" * 70)

    # 자동 SNS 예약 업로드 연동
    if getattr(args, "upload", False):
        print("\n" + "=" * 70)
        print("🚀 [자동 업로드 옵션 감지] 주간 콘텐츠 SNS 예약 업로드를 연계 실행합니다...")
        cmd_upload(args)


def cmd_upload(args):
    """
    주간 콘텐츠(유튜브 쇼츠, 인스타그램 카드뉴스 캐러셀, 릴스)를 자동 예약 업로드합니다.
    --dry-run 옵션 지정 시 실제 API 호출 없이 스케줄 및 메타데이터, GitHub Raw URL을 시뮬레이션합니다.
    """
    weekly_dir = find_active_weekly_dir(getattr(args, "date", None))
    dry_run = getattr(args, "dry_run", False)
    platform = getattr(args, "platform", "all").lower()
    content_type = getattr(args, "type", "all").lower()

    print("\n" + "=" * 70)
    mode_str = "🧪 [시뮬레이션 모드 (DRY-RUN)]" if dry_run else "🚀 [실제 API 업로드 모드]"
    print(f"{mode_str} 주간 SNS 자동 예약 발행 파이프라인을 시작합니다.")
    print(f"👉 대상 디렉토리: {weekly_dir.resolve()}")
    print(f"👉 대상 플랫폼: {platform.upper()} | 대상 콘텐츠: {content_type.upper()}")
    print("=" * 70)

    # 요일 폴더 탐색 (01_Mon_Policy, 02_Tue_Creator, ...)
    day_folders = sorted(
        [d for d in weekly_dir.iterdir() if d.is_dir() and re.match(r"^\d{2}_", d.name)],
        key=lambda x: x.name
    )

    if not day_folders:
        print(f"❌ [오류] 요일별 콘텐츠 폴더를 찾을 수 없습니다: {weekly_dir}")
        print("   먼저 콘텐츠를 제작하세요: python curate.py build --render")
        return

    from modules.sns_scheduler import get_schedule_for_day, get_github_raw_url
    from modules.youtube_uploader import upload_youtube_short
    from modules.instagram_uploader import upload_instagram_carousel, upload_instagram_reel

    total_tasks = 0
    success_tasks = 0

    for folder in day_folders:
        folder_name = folder.name
        pkg_file = folder / "package_data.json"
        caption_file = folder / "instagram_caption.txt"
        card_dir = folder / "card_images_4x5"
        shorts_files = list(folder.glob("shorts_*.mp4")) or list(folder.glob("*.mp4"))

        # 메타데이터 로드
        pkg_data = {}
        if pkg_file.exists():
            try:
                with open(pkg_file, "r", encoding="utf-8") as f:
                    pkg_data = json.load(f)
            except Exception as e:
                print(f"⚠️ [{folder_name}] package_data.json 로드 실패: {e}")

        # 캡션 로드
        caption = ""
        if caption_file.exists():
            caption = caption_file.read_text(encoding="utf-8").strip()
        elif "caption" in pkg_data:
            caption = pkg_data["caption"].strip()

        # 스케줄 계산 (월~토)
        sched = get_schedule_for_day(folder_name)
        day_label = pkg_data.get("day_name", folder_name)
        cat_title = pkg_data.get("category_title", folder_name)

        print(f"\n📅 [{day_label}] {cat_title} ({folder_name})")
        print(f"   ⏰ 예약 발행 시각: {sched['formatted_kst']}")

        # 1. YouTube Shorts 업로드
        if platform in ("all", "youtube") and content_type in ("all", "shorts", "video"):
            if not shorts_files:
                print("   ⚠️ [YouTube Shorts] 비디오 파일(.mp4)이 없어 건너뜁니다.")
            else:
                total_tasks += 1
                video_path = shorts_files[0]
                raw_title = pkg_data.get("title", f"{day_label} 물리치료 브리핑")
                clean_title = re.sub(r"<[^>]+>", "", raw_title).strip()
                yt_title = f"[{day_label}] {clean_title} #Shorts"[:95]

                # 생성된 전용 유튜브 설명란 파일이 있으면 우선 사용
                yt_caption_file = folder / "youtube_shorts_caption.txt"
                if yt_caption_file.exists():
                    yt_desc = yt_caption_file.read_text(encoding="utf-8").strip()
                else:
                    yt_desc = (
                        f"📢 [{day_label}] {clean_title} #Shorts\n\n"
                        f"{caption}\n\n"
                        f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
                        f"📌 물리치료사를 위한 전문 플랫폼 THEPT\n"
                        f"• 방문재활 AI 음성 차팅: https://4thept.com\n"
                        f"• THEPT 공식 커뮤니티: https://thept.co.kr\n"
                        f"• 광고 및 비즈니스 제휴: teamthept@gmail.com\n"
                        f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
                        f"#물리치료 #물리치료사 #쇼츠 #Shorts #THEPT #더피티 #재활"
                    )

                first_comment = (
                    "📌 방문재활 물리치료사를 위한 가장 스마트한 AI 음성 차팅 솔루션!\n"
                    "👉 지금 바로 무료로 체험해보세요: https://4thept.com\n\n"
                    "💬 이번 주 다룬 최신 물리치료 임상·정책 자료와 동료 치료사들의 의견은 'THEPT커뮤니티'에서 확인해보세요!\n"
                    "👉 THEPT커뮤니티 바로가기: https://thept.co.kr\n\n"
                    "📢 광고 및 비즈니스 제휴 문의: teamthept@gmail.com"
                )

                print(f"   ▶️ [YouTube Shorts] 예약 업로드 요청 중...")
                res_yt = upload_youtube_short(
                    video_path=video_path,
                    title=yt_title,
                    description=yt_desc,
                    tags=["물리치료", "물리치료사", "Shorts", "쇼츠", "재활", "THEPT", "4THEPT"],
                    publish_at_rfc3339=sched["rfc3339"],
                    first_comment=first_comment,
                    dry_run=dry_run
                )
                if res_yt.get("success"):
                    success_tasks += 1
                    print(f"     ✅ YouTube 성공: {res_yt.get('video_id', 'DRY-RUN')} (상태: {res_yt.get('status')})")
                else:
                    print(f"     ❌ YouTube 실패: {res_yt.get('error')}")

        # 2. Instagram Carousel 업로드
        if platform in ("all", "instagram") and content_type in ("all", "carousel"):
            card_images = sorted(list(card_dir.glob("*.png"))) if card_dir.exists() else []
            if not card_images:
                print("   ⚠️ [Instagram 캐러셀] 카드뉴스 이미지(*.png)가 없어 건너뜁니다.")
            else:
                total_tasks += 1
                image_urls = [get_github_raw_url(p) for p in card_images]
                print(f"   📸 [Instagram 캐러셀] 예약 업로드 요청 중... (총 {len(card_images)}장)")
                first_comment = (
                    "📌 방문재활 물리치료사를 위한 가장 스마트한 AI 음성 차팅 솔루션!\n"
                    "👉 지금 바로 무료로 체험해보세요: https://4thept.com\n\n"
                    "💬 이번 주 다룬 최신 물리치료 임상·정책 자료와 동료 치료사들의 의견은 'THEPT커뮤니티'에서 확인해보세요!\n"
                    "👉 THEPT커뮤니티 바로가기: https://thept.co.kr\n\n"
                    "📢 광고 및 비즈니스 제휴 문의: teamthept@gmail.com"
                )
                res_ig = upload_instagram_carousel(
                    image_urls=image_urls,
                    caption=caption,
                    scheduled_timestamp=sched["unix_timestamp"],
                    first_comment=first_comment,
                    dry_run=dry_run
                )
                if res_ig.get("success"):
                    success_tasks += 1
                    print(f"     ✅ Instagram 캐러셀 성공: ID {res_ig.get('container_id', 'DRY-RUN')}")
                else:
                    print(f"     ❌ Instagram 캐러셀 실패: {res_ig.get('error')}")

        # 3. Instagram Reels 업로드
        if platform in ("all", "instagram") and content_type in ("all", "shorts", "video", "reel", "reels"):
            if not shorts_files:
                print("   ⚠️ [Instagram 릴스] 비디오 파일(.mp4)이 없어 건너뜁니다.")
            else:
                total_tasks += 1
                video_url = get_github_raw_url(shorts_files[0])
                print(f"   🎥 [Instagram 릴스] 예약 업로드 요청 중...")
                first_comment = (
                    "📌 방문재활 물리치료사를 위한 가장 스마트한 AI 음성 차팅 솔루션!\n"
                    "👉 지금 바로 무료로 체험해보세요: https://4thept.com\n\n"
                    "💬 이번 주 다룬 최신 물리치료 임상·정책 자료와 동료 치료사들의 의견은 'THEPT커뮤니티'에서 확인해보세요!\n"
                    "👉 THEPT커뮤니티 바로가기: https://thept.co.kr\n\n"
                    "📢 광고 및 비즈니스 제휴 문의: teamthept@gmail.com"
                )
                res_reel = upload_instagram_reel(
                    video_url=video_url,
                    caption=caption,
                    scheduled_timestamp=sched["unix_timestamp"],
                    first_comment=first_comment,
                    dry_run=dry_run
                )
                if res_reel.get("success"):
                    success_tasks += 1
                    print(f"     ✅ Instagram 릴스 성공: ID {res_reel.get('container_id', 'DRY-RUN')}")
                else:
                    print(f"     ❌ Instagram 릴스 실패: {res_reel.get('error')}")

    print("\n" + "=" * 70)
    print(f"🏁 [발행 파이프라인 결과] 총 {total_tasks}개 대상 작업 중 {success_tasks}건 완료!")
    if dry_run:
        print("💡 [DRY-RUN 모드 안내] 실제 업로드는 수행되지 않았으며 스케줄과 메타데이터가 정상 검증되었습니다.")
        print("   실제 업로드를 진행하려면 --dry-run 플래그를 제외하고 실행해주세요.")
    print("=" * 70)


def cmd_auth_yt(args):
    """YouTube Data API OAuth 인증 도우미"""
    from modules.youtube_uploader import authenticate_youtube
    print("\n🔑 [YouTube Data API] OAuth 2.0 사용자 인증을 시작합니다...")
    service = authenticate_youtube()
    if service:
        print("\n🎉 [인증 완료] YouTube API 인증이 성공적으로 완료되었습니다!")
        print("   이제 'python curate.py upload --platform youtube'로 예약 업로드할 수 있습니다.")
    else:
        print("\n❌ [인증 실패] YouTube 인증에 실패했습니다. docs/api_setup_guide.md 를 참고해주세요.")


def cmd_test_insta(args):
    """Instagram Graph API 연결 진단 도우미"""
    from modules.instagram_uploader import test_instagram_connection
    print("\n🔍 [Instagram Graph API] 비즈니스 계정 및 토큰 연동 상태를 진단합니다...")
    ok = test_instagram_connection()
    if ok:
        print("\n🎉 [진단 통과] Instagram Graph API가 정상적으로 연동되어 있습니다!")
        print("   이제 'python curate.py upload --platform instagram'로 예약 업로드할 수 있습니다.")
    else:
        print("\n❌ [진단 실패] Instagram API 연결에 문제가 있습니다. docs/api_setup_guide.md 를 확인해주세요.")


def cmd_stats(args):
    """누적된 큐레이션 히스토리 데이터셋 통계 확인"""
    if not HISTORY_FILE.exists():
        print("📊 아직 누적된 큐레이션 히스토리가 없습니다.")
        return

    total = 0
    selected = 0
    reasons_count = 0
    with open(HISTORY_FILE, "r", encoding="utf-8") as f:
        for line in f:
            if not line.strip():
                continue
            total += 1
            data = json.loads(line)
            if data.get("final_selected"):
                selected += 1
                if data.get("selection_reason"):
                    reasons_count += 1

    print("\n" + "=" * 50)
    print("📊 [THEPT] 큐레이션 데이터셋 누적 현황")
    print("=" * 50)
    print(f"• 총 검토 기사 수: {total}건")
    print(f"• 최종 채택 기사 수: {selected}건")
    print(f"• 선택 이유 작성 건수: {reasons_count}건")
    print(f"• 히스토리 파일: {HISTORY_FILE}")
    print("=" * 50)


def main():
    parser = argparse.ArgumentParser(
        description="THEPT 주 6일 6대 카테고리 2단계 마크다운 큐레이션 및 자동 발행 도구"
    )
    subparsers = parser.add_subparsers(dest="command", help="실행할 작업 선택")

    # 1. fetch
    p_fetch = subparsers.add_parser("fetch", help="1단계: 6대 카테고리 최대 100건 후보 수집 및 제목 마크다운 생성")
    p_fetch.add_argument("--count", type=int, default=17, help="카테고리당 수집 건수 (기본 17건, 총 약 100건)")
    p_fetch.add_argument("--date", type=str, default=None, help="대상 주간 날짜 (기본값: 오늘 YYYY-MM-DD)")

    # 2. review
    p_review = subparsers.add_parser("review", help="2단계: 1차 선택 기사 상세 본문/사진 크롤링 및 검토 마크다운 생성")
    p_review.add_argument("--date", type=str, default=None, help="대상 주간 날짜 (기본값: 최신 주차)")

    # 3. build
    p_build = subparsers.add_parser("build", help="3단계: 최종 선택 기사 확정, 이유 저장 및 주 6일 콘텐츠 일괄 제작")
    p_build.add_argument("--render", action="store_true", default=False, help="카드뉴스 PNG 및 쇼츠 MP4 미디어 렌더링까지 즉시 수행")
    p_build.add_argument("--date", type=str, default=None, help="대상 주간 날짜 (기본값: 최신 주차)")
    p_build.add_argument("--upload", action="store_true", default=False, help="콘텐츠 제작 완료 후 유튜브/인스타 자동 예약 업로드 연계 실행")
    p_build.add_argument("--dry-run", action="store_true", default=False, help="업로드 연계 시 실제 API 호출 없이 시뮬레이션만 수행")

    # 4. upload
    p_upload = subparsers.add_parser("upload", help="주간 콘텐츠(카드뉴스/쇼츠)를 유튜브 및 인스타그램에 자동 예약 업로드")
    p_upload.add_argument("--date", type=str, default=None, help="대상 주간 날짜 (기본값: 최신 주차)")
    p_upload.add_argument("--platform", type=str, default="all", choices=["all", "youtube", "instagram"], help="대상 플랫폼 선택 (all, youtube, instagram)")
    p_upload.add_argument("--type", type=str, default="all", choices=["all", "carousel", "shorts", "video"], help="대상 콘텐츠 유형 (all, carousel, shorts)")
    p_upload.add_argument("--dry-run", action="store_true", default=False, help="실제 API 호출 없이 예약 스케줄 및 업로드 매핑 시뮬레이션")

    # 5. auth-yt
    p_auth_yt = subparsers.add_parser("auth-yt", help="YouTube Data API OAuth 최초 1회 브라우저 인증 도우미")

    # 6. test-insta
    p_test_insta = subparsers.add_parser("test-insta", help="Instagram Graph API 토큰 및 비즈니스 계정 연결 진단 도우미")

    # 7. stats
    p_stats = subparsers.add_parser("stats", help="누적된 큐레이션 데이터셋 통계 확인")

    args = parser.parse_args()

    if args.command == "fetch":
        cmd_fetch(args)
    elif args.command == "review":
        asyncio.run(cmd_review_async(args))
    elif args.command == "build":
        cmd_build(args)
    elif args.command == "upload":
        cmd_upload(args)
    elif args.command == "auth-yt":
        cmd_auth_yt(args)
    elif args.command == "test-insta":
        cmd_test_insta(args)
    elif args.command == "stats":
        cmd_stats(args)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
